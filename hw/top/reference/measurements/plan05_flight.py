"""Paired production flight-loop measurement around a real oscillator-off sleep.

Prepare with plan03_production_benchmark04.py into a fresh directory. Workload
bytes are unchanged; only the ROM preamble uses the single performance boot master and a real GPIO deep wake.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'dv/core'),str(ROOT)]
spec=importlib.util.spec_from_file_location('metrics',ROOT/'tools/spikes/s1_core/performance.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();prepared=ROOT/args.prepared;out=ROOT/args.output;out.mkdir(parents=True,exist_ok=False)
    items=json.loads((prepared/'prepared.json').read_text())
    assert set(items)=={'fixed','hard-float'},'incomplete workload inventory'
    receipt={'status':'running','commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'scope':'Unchanged workloads after ROM copies all SRAM, baseline versus real GPIO deep-wake; passive RVFI. Not whole-program ISS lockstep.',
        'assumed_clocks_mhz':{'osc_in':48,'main':8,'aon':0.032},'commands':[],'workloads':{}}
    def save(): (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def run(argv,log,timeout=600):
        start=time.monotonic()
        with log.open('w') as f:
            try: code=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124
        receipt['commands'].append({'command':list(map(str,argv)),'returncode':code,'wall_seconds':time.monotonic()-start,'log':str(log.relative_to(out))})
        save();assert code==0,(log,code)
    try:
        historical=json.loads((ROOT/'build/plan04/flight-sleep03/result.json').read_text())
        assert historical['status']=='pass'
        for name,item in items.items():
            d=out/name;d.mkdir();payload=Path(item['out'])/'payload.bin'
            # Authenticate the historical target-ISS checksum reference to the
            # byte-identical freshly rebuilt workload, not its source filename.
            reference=ROOT/'build/plan03/production-performance04'/name
            assert digest(Path(item['out'])/'workload.bin')==digest(reference/'workload.bin')
            workload=(Path(item['out'])/'workload.bin').read_bytes()
            assert len(workload)<=16384 and payload.read_bytes()==workload+bytes(16384-len(workload)), 'loaded payload differs from authenticated workload'
            golden=json.loads((reference/'qemu-checks/result02.json').read_text())
            assert golden['status']=='pass_reference'
            sealed=historical['workloads'][name]
            assert digest(Path(item['out'])/'workload.bin')==sealed['workload_sha256']
            assert digest(reference/'qemu-checks/result02.json')==sealed['historical_target_reference']['sha256']
            item['expected']=golden['expected']
            asm=d/'boot.S';asm.write_text('''.section .text.start,"ax"
.global _start
.option norelax
_start:
la t0,payload
li t1,0x20000000
li t2,0x20004000
1: lw t3,0(t0)
sw t3,0(t1)
addi t0,t0,4
addi t1,t1,4
bne t1,t2,1b
# GPIO2 is diagnostic input selecting baseline or sleep; it drives no RTL bypass.
li s0,0x40012000
lw t0,8(s0)
andi t0,t0,4
beqz t0,enter
li t0,1
sw t0,12(s0)
sw t0,24(s0)
gpio_ready:
lw t0,40(s0)
andi t0,t0,8
beqz t0,gpio_ready
li t0,1
sw t0,28(s0)
sw t0,32(s0)
sw t0,36(s0)
gpio_armed:
lw t0,40(s0)
andi t0,t0,3
li t1,2
bne t0,t1,gpio_armed
li s1,0x40000400
li t0,2
sw t0,4(s1)
li t0,4
sw t0,8(s1)
li t0,6
sw t0,12(s1)
li t0,64
sw t0,40(s1)
li t0,1
sw t0,28(s1)
li t0,0x2000000
csrw mie,t0
csrci mstatus,8
li t0,1
sw t0,0(s1)
wfi
lw t0,24(s1)
li t1,2
bne t0,t1,failed
csrw mie,zero
li t0,1
sw t0,20(s0)
enter:
li t0,0x20000000
jr t0
failed:
li t0,0x40012000
li t1,0x3333
sw t1,0(t0)
j failed
.balign 4
payload:
.incbin "'''+str(payload)+'"\n')
            linker=d/'boot.ld';linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80; .text : { *(.text.start) } }\n')
            run(['riscv64-unknown-elf-gcc','-march=rv32i_zicsr','-mabi=ilp32','-nostdlib','-Wl,--no-relax','-T',linker,asm,'-o',d/'boot.elf'],d/'compile-boot.log')
            run(['riscv64-unknown-elf-objcopy','-O','binary',d/'boot.elf',d/'boot.bin'],d/'binary.log')
            rom=bytes(128)+(d/'boot.bin').read_bytes();assert len(rom)<=65536
            rom+=bytes(65536-len(rom));(d/'rom.hex').write_text(''.join(f'{int.from_bytes(rom[i:i+4],"little"):08x}\n' for i in range(0,len(rom),4)))
            item['golden_receipt']={'path':str(reference/'qemu-checks/result02.json'),'sha256':digest(reference/'qemu-checks/result02.json')}
        active=out/'active-rom.hex';shutil.copyfile(out/'fixed/rom.hex',active)
        emit=out/'emit'
        # Queue time behind another Scala suite is not emission runtime.
        with (ROOT/'build/sbt/compile.lock').open('a') as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        run([sys.executable,'tools/sbt.py',f'hw/Test/runMain deadhorse.top.EmitOscFlight {emit} {active}'],out/'emit.log')
        sources=sorted(emit.glob('*.sv'))+sorted(emit.glob('*.v'))
        package=emit/'dm_pkg.sv';sources.remove(package);sources.insert(0,package)
        gate=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
        driver=ROOT/'dv/soc/plan05/flight.cpp'
        # Reuse the reviewed exact vendor-file/two-hart selector exception.
        # All other diagnostics remain fatal; no global warning suppression.
        # This emitter strips the trailing source-location comment; the vendor
        # contents are otherwise byte-identical to SocDebugLint's pinned copy.
        assert digest(emit/'dm_csrs.sv')=='1614f20608419d944fee249dd706e4f275dabc6cdbc9102159806ef73d05d641'
        assert digest(ROOT/'hw/ip/debug/src/main/scala/deadhorse/debug/DebugVendor.scala')=='52583c538902eabc4efd154c43e3390edccfbd344a37b2eddbaceed6db02b9e4'
        assert json.loads((ROOT/'hw/vendor/riscv_dbg/riscv_dbg.lock.json').read_text())['parameters']['NrHarts']==2
        control=out/'debug-selector.vlt';control.write_text('`verilator_config\n'+
            f'lint_off -rule CMPCONST -file "{emit}/dm_csrs.sv" -match "Comparison is constant due to limited range*"\n')
        run(['verilator','--cc','--exe','--build','--assert','-DENABLE_INITIAL_MEM_','-DENABLE_INITIAL_REG_','-j','4',
             '--top-module','SocOscFlight','--Mdir',out/'obj',control,*sources,gate,driver],out/'compile.log')
        measured_inputs=[*sources,gate,driver,Path(__file__),control,prepared/'prepared.json',
            ROOT/'build/plan04/flight-sleep03/result.json',ROOT/'tools/spikes/s1_core/performance.py',ROOT/'dv/core/performance.py',
            ROOT/'hw/top/reference/src/test/scala/deadhorse/top/SocOscFlight.scala',
            *(out/name/'rom.hex' for name in items),
            *(Path(item['out'])/file for item in items.values() for file in ('workload.bin','payload.bin')),
            *(ROOT/'build/plan03/production-performance04'/name/file for name in items for file in ('workload.bin','qemu-checks/result02.json'))]
        receipt['source_sha256']={str(x):digest(x) for x in measured_inputs}
        for name,item in items.items():
            shutil.copyfile(out/name/'rom.hex',active);results={}
            for variant,sleep in [('baseline',False),('wake',True)]:
                d=out/name/variant;d.mkdir()
                run([out/'obj/VSocOscFlight',int(sleep),d/'rvfi.jsonl',d/'cycles.txt'],d/'simulate.log')
                rows=[json.loads(x) for x in (d/'rvfi.jsonl').read_text().splitlines()]
                cycles=metrics.historical.timed_rows(rows,(d/'cycles.txt').read_text())
                def checks(trace):
                    values=[r['mem_wdata'] for r in trace if r['mem_wmask'] and r['mem_addr']==0x40012004]
                    assert values==[v for pair in item['expected'] for v in pair],'checksum mismatch'
                    assert not any(r['trap'] or r['intr'] for r in trace)
                    assert trace[-1]['mem_addr']==0x40012000 and trace[-1]['mem_wdata']==0x5555
                    if item['floating']:assert any(r['frd_wen'] and r['ext_fs'] for r in trace)
                checks(rows)
                metric=[dict(r,mem_addr=0x10000000) if r['mem_wmask'] and r['mem_addr']==0x40012000 and r['mem_wdata'] in (0,1,2) else r for r in rows]
                loop=metrics.iteration_metrics(metric,cycles,item['bounds'],8)
                assert loop['iterations']==120,'Incomplete iteration inventory'
                bad=[dict(r) for r in rows];next(r for r in bad if r['mem_wmask'] and r['mem_addr']==0x40012004)['mem_wdata']^=1
                try: checks(bad)
                except AssertionError as e:assert 'checksum' in str(e)
                else:raise AssertionError('checksum fault escaped')
                first=next(i for i,r in enumerate(rows) if r['pc_rdata']==item['bounds']['start'])
                last=next(i for i in range(first,len(rows)) if rows[i]['pc_rdata']==item['bounds']['end'])
                try:
                    missing=metrics.iteration_metrics(metric[:first]+metric[last+1:],cycles[:first]+cycles[last+1:],item['bounds'],8)
                    assert missing['iterations']==120,'Incomplete iteration inventory'
                except (AssertionError,ValueError) as error:assert 'Incomplete' in str(error)
                else:raise AssertionError('Omitted iteration escaped')
                results[variant]={'omitted_iteration_fault':'rejected','loop':loop,'checksums':item['expected'],'checksum_fault':'rejected',
                    'trace_sha256':digest(d/'rvfi.jsonl'),'cycles_sha256':digest(d/'cycles.txt')}
            assert results['baseline']['loop']==results['wake']['loop'],'flight loop changed after wake'
            prior=historical['workloads'][name]['results']['baseline']['loop']
            assert results['baseline']['loop']['worst_cycles']<=prior['worst_cycles'],'Worst cycle regression'
            assert results['baseline']['loop']['mean_cycles']<=prior['mean_cycles'],'Mean cycle regression'
            receipt['workloads'][name]={'status':'pass','results':results,'workload_sha256':digest(Path(item['out'])/'workload.bin'),'historical_target_reference':item['golden_receipt']}
            print(name,'PASS unchanged before/after wake',results['wake']['loop']['mean_cycles'],results['wake']['loop']['worst_cycles'],flush=True);save()
        assert receipt['source_sha256']=={str(x):digest(x) for x in measured_inputs},'measurement inputs changed during run'
        receipt['status']='pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error));save();raise
    save()


if __name__=='__main__':main()
