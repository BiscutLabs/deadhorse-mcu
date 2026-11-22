"""Measure the real I0 memory path; enforce the unchanged T13 round-2 limit."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

from fixture import ROOT, RAM, ENTRY, CAPACITY, prepare, compile_sim, build_flight, write_images, digest, run
from lockstep import qemu_trace
from suites import flight_reentry

spec=importlib.util.spec_from_file_location('s1_metrics',ROOT/'tools/spikes/s1_core/performance.py')
metrics=importlib.util.module_from_spec(spec); spec.loader.exec_module(metrics)
BASELINES={'fixed':4350,'hard-float':8973}


def check_overhead(name,worst):
    if worst*10>BASELINES[name]*11:
        raise ValueError(f'{name}: {worst} cycles exceeds 110% of round-2 {BASELINES[name]}')


def stack_range(rows):
    """Check active SP values, validating the adjacent PC-relative startup pair."""
    writes=[(i,r) for i,r in enumerate(rows) if r['rd_addr']==2 and r['rd_wdata']]
    if not writes: raise ValueError('No observed stack initialization')
    first_index,first=writes[0]
    initialization=None
    if first['insn'] & 0xfff == 0x117:  # AUIPC sp: first half of la sp,_stack_top.
        if first_index+1>=len(rows): raise ValueError('Incomplete stack initialization pair')
        second=rows[first_index+1]
        immediate=(second['insn']>>20)&0xfff
        if immediate&0x800: immediate-=0x1000
        upper=first['insn']&0xfffff000
        expected=(first['pc_rdata']+upper)&0xffffffff
        if (second['insn']&0xfffff != 0x10113 or second['rd_addr']!=2 or
            second['rs1_addr']!=2 or second['rs1_rdata']!=expected or
            first['rd_wdata']!=expected or second['pc_rdata']!=first['pc_rdata']+4 or
            second['order']!=first['order']+1 or
            any(r['trap'] or r['intr'] for r in (first,second)) or
            second['rd_wdata']!=(expected+immediate)&0xffffffff or
            second['rd_wdata']!=RAM+CAPACITY):
            raise ValueError('Invalid stack initialization pair')
        initialization=dict(first_order=first['order'],intermediate_sp=first['rd_wdata'],
                            final_sp=second['rd_wdata'],kind='validated adjacent startup AUIPC/ADDI')
        writes=writes[1:]
    stack=[r['rd_wdata'] for _,r in writes]
    if not stack or min(stack)<RAM+CAPACITY-2048 or max(stack)>RAM+CAPACITY:
        raise ValueError('Observed stack escaped reserved 2KiB')
    return min(stack),max(stack),initialization


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--main-mhz',default='8,9'); ap.add_argument('--output',required=True)
    args=ap.parse_args(); frequencies=[int(v) for v in args.main_mhz.split(',')]
    if frequencies!=[8,9]: ap.error('T20 reports both unchanged trial frequencies: 8,9')
    out=(ROOT/args.output).resolve(); out.relative_to(ROOT/'build'); out.mkdir(parents=True,exist_ok=False)
    paths=[]
    for pattern in ('hw/top/reference/**/*.scala','hw/top/reference/*.py','hw/top/reference/*.yaml',
                    'hw/ip/perf_core/**/*.scala','hw/ip/fpu/**/*.scala','hw/ip/bus/**/*.scala',
                    'hw/ip/uart/**/*.scala','hw/lib/**/*.scala','dv/core/*.py','dv/core/*.json',
                    'dv/soc/*.py','dv/soc/*.cpp','tools/env/*.json','tools/sbt.py','build.sbt','project/*',
                    'hw/regmap/*.py','hw/ip/uart/*.yaml','hw/vendor/ibex_ref/*.py','hw/vendor/ibex_ref/*.json',
                    'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv',
                    'sw/flight/loop-measurement/src/*','sw/flight/loop-measurement/scenario/*.py',
                    'tools/spikes/s1_core/performance.py','docs/plan/tasks/reports/T13-round2.md'):
        paths.extend(p for p in ROOT.glob(pattern) if p.is_file())
    snapshot=lambda:{str(p.relative_to(ROOT)):digest(p) for p in paths}
    receipt=dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_sha256=snapshot(),workloads={},baseline_worst_cycles=BASELINES,
        scope='Integrated I0 core/local SRAM/fabric/UART, QEMU-map verification fixture; not production-map system acceptance',
        assumptions=['main frequency 8/9 MHz, not timing qualified','16KiB modeled SRAM preloaded, remaining bytes zero',
                     '2KiB reserved stack, checked against observed SP','no external interrupts or competing masters'],
        baseline_source='docs/plan/tasks/reports/T13-round2.md',ci='not run')
    def save(): (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    try:
        images=prepare(out/'images'); sim=compile_sim(out/'sim',images)
        for name,floating in [('fixed',False),('hard-float',True)]:
            directory=out/name; elf,workload,sections=build_flight(directory,floating)
            image=write_images(images,workload,RAM)
            shutil.copytree(images,directory/'loaded-images')
            binary=directory/'loaded-images/qemu.bin'
            iss=qemu_trace(elf,directory,RAM,binary,ENTRY,floating)
            iss,duplicates=flight_reentry(iss,binary.read_bytes(),RAM,allow_compressed=floating)
            (directory/'iss-reentry.json').write_text(json.dumps(duplicates,indent=2)+'\n')
            disassembly=run(['riscv64-unknown-elf-objdump','-d','--disassemble=main',elf],directory,'main-disassembly').stdout
            bounds=metrics.historical.loop_boundaries(disassembly)
            cycle_file=directory/'cycles.txt'
            result=run(['env',f'DEADHORSE_CYCLE_TRACE={cycle_file}',sim,'flight'],directory,'simulate')
            rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            cycles=metrics.historical.timed_rows(rows,cycle_file.read_text())
            correctness=metrics.compare_workload(rows,iss,binary.read_bytes(),RAM,floating)
            faults=metrics.faults(rows,iss,binary.read_bytes(),RAM,floating)
            loop=metrics.iteration_metrics(rows,cycles,bounds,9)
            stack_min,stack_max,stack_initialization=stack_range(rows)
            receipt['workloads'][name]=dict(status='measured; QEMU comparison and fault controls passed',
                sections=sections,stack_min=stack_min,stack_max=stack_max,
                stack_initialization=stack_initialization,correctness=correctness,
                negative_controls=faults,loop=loop,overhead_percent=(loop['worst_cycles']/BASELINES[name]-1)*100,
                estimated_loop_us={str(mhz):{k:loop[k]/mhz for k in ('mean_cycles','worst_cycles')} for mhz in frequencies},
                estimate_basis='measured cycles divided by assumed MHz; not routed/STA clock qualification')
            print(f"{name}: measured mean={loop['mean_cycles']:.3f}, worst={loop['worst_cycles']} cycles",flush=True)
            # Same acceptance function must reject an over-budget observation.
            try: check_overhead(name,BASELINES[name]*11//10+1)
            except ValueError: receipt['workloads'][name]['budget_negative_control']='rejected'
            else: raise RuntimeError('Overhead negative control escaped')
            save()
            try: check_overhead(name,loop['worst_cycles'])
            except ValueError as error:
                receipt.update(status='blocked_overhead',stop_reason=str(error)); break
        else: receipt['status']='pass_measured_fixture'
        if snapshot()!=receipt['source_sha256']: raise RuntimeError('Sources changed during measurement')
    except Exception as error:
        receipt.update(status='failed',error=str(error)); raise
    finally:
        receipt['artifact_sha256']={str(p.relative_to(out)):digest(p) for p in sorted(out.rglob('*'))
                                   if p.is_file() and p!=out/'result.json'}
        save()
    return 0 if receipt['status']=='pass_measured_fixture' else 1


if __name__=='__main__': sys.exit(main())
