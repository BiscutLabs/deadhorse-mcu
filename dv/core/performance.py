"""Measure existing flight/smoke workloads through port-only retirement timestamps.

Cycle counts include the existing ideal one-cycle memory responder. Arithmetic
figures are observed retirement spacing, not isolated execution-unit latency.
No RTL, firmware workload, or architectural comparison is changed.
"""
import argparse
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path

from common import ROOT, local, output_dir, run
from candidate import manifest, parameters
from lockstep import BASE, build_program, compile_sim, compare, qemu_trace
from suites import flight_program, flight_reentry
from float_suites import flight as float_flight
from float_compare import compare as compare_float


def stats(values):
    if not values:
        return dict(status='not observed', samples=0)
    return dict(status='measured', samples=len(values), mean=statistics.mean(values),
                worst=max(values), best=min(values), values=values)


def timed_rows(rows, text):
    times=[tuple(map(int,line.split())) for line in text.splitlines()]
    if len(times)!=len(rows): raise ValueError('Missing cycle observation')
    if any(order!=row['order'] for (order,_),row in zip(times,rows)):
        raise ValueError('Cycle observations differ from RVFI order')
    cycles=[cycle for _,cycle in times]
    if any(b<=a for a,b in zip(cycles,cycles[1:])):
        raise ValueError('Non-monotonic retirement cycles')
    return cycles


def loop_boundaries(disassembly):
    instructions=[]
    for line in disassembly.splitlines():
        m=re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]+)\s+(.+)',line)
        if m: instructions.append((int(m[1],16),m[3]))
    calls=[pc for pc,text in instructions if '<control_step>' in text]
    if len(calls)!=1: raise ValueError('Expected one static control_step call in main')
    enclosing=[]
    for pc,text in instructions:
        m=re.match(r'b\w+\s+.*?([0-9a-f]{8})\s+<',text)
        if m and int(m[1],16)<=calls[0]<pc:
            enclosing.append((int(m[1],16),pc))
    if not enclosing: raise ValueError('No enclosing iteration backedge')
    start,end=min(enclosing,key=lambda pair:pair[1]-pair[0])
    return dict(start=start,end=end,call=calls[0])


def loop_samples(rows, cycles, bounds, expected=120):
    samples=[]; active=None; calls=0; mode=None
    for i,row in enumerate(rows):
        if row['mem_wmask'] and row['mem_addr']==0x10000000:
            mode=row['mem_wdata']
        if row['pc_rdata']==bounds['start']:
            if active is not None or i==0: raise ValueError('Malformed iteration start')
            active=cycles[i-1];calls=0
        if active is not None and row['pc_rdata']==bounds['call']: calls+=1
        if row['pc_rdata']==bounds['end']:
            if active is None or calls!=1 or mode not in (0,1,2):
                raise ValueError('Malformed iteration end')
            samples.append(dict(mode=mode,cycles=cycles[i]-active));active=None
    if active is not None or len(samples)!=expected: raise ValueError('Incomplete flight iterations')
    if any(sum(s['mode']==m for s in samples)!=expected//3 for m in range(3)):
        raise ValueError('Incomplete flight modes')
    return samples


def arithmetic(rows,cycles):
    names=('mul','mulh','mulhsu','mulhu','div','divu','rem','remu')
    result={name:[] for name in (*names,'fmul.s','fdiv.s')}
    for i,row in enumerate(rows):
        insn=row['insn']
        if i and insn&0xfe00007f==0x02000033:
            result[names[(insn>>12)&7]].append(cycles[i]-cycles[i-1])
        elif i and insn&0x7f==0x53 and insn>>25 in (8,12):
            result['fmul.s' if insn>>25==8 else 'fdiv.s'].append(cycles[i]-cycles[i-1])
    return {name:stats(values) for name,values in result.items()}


def integer_rows(rows):
    return [{k:v for k,v in row.items() if not k.startswith(('frs','frd','ext_f','fregs'))}
            for row in rows]


def analyze_existing(directory):
    """Add FP spacing from immutable raw traces; never rerun or relabel simulation."""
    directory=local(directory);raw=directory/'result.json';data=json.loads(raw.read_text())
    if not data['status'].startswith('pass (measured'):raise ValueError('Measurement incomplete')
    protected={str(raw):hashlib.sha256(raw.read_bytes()).hexdigest()}
    for name,value in data['input_sha256'].items():
        path=Path(name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=value:
            if path==Path(__file__).resolve():path=directory/'executed-runner.py'
            elif path==ROOT/'dv/core/test_performance.py':path=directory/'executed-test_performance.py'
            else:raise ValueError('Measurement input differs: '+name)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=value:raise ValueError('Executed measurement source not preserved')
        protected[str(path)]=value
    result=dict(status='pass (analysis of existing measured retirement traces)',profiles={},input_sha256=protected,
        analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    for profile,workloads in data['profiles'].items():
        result['profiles'][profile]={}
        for name,prior in workloads.items():
            folder=directory/profile/name;trace=folder/'simulate.log';times=folder/'cycles.txt'
            rows=[json.loads(line) for line in trace.open() if line.startswith('{')]
            values=arithmetic(rows,timed_rows(rows,times.read_text()))
            if any(values[k]!=v for k,v in prior['arithmetic'].items()):raise ValueError('Prior arithmetic statistics differ')
            result['profiles'][profile][name]=values
            for p in (trace,times):protected[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    (directory/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS existing-trace arithmetic analysis; no simulation or RTL change',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--faithful',default='build/t11/ci/baseline')
    ap.add_argument('--registered',default='build/t13/current-baseline')
    ap.add_argument('--floating',default='build/t13/exponent/candidate')
    ap.add_argument('--faithful-floating',help='Optional faithful-pipeline F candidate')
    ap.add_argument('--profiles',default='faithful,registered,registered-f',
                    help='Comma-separated profiles to measure; faithful-f requires --faithful-floating')
    ap.add_argument('--output')
    ap.add_argument('--analyze-existing',help='Recompute integer/FP spacing from a completed raw measurement')
    args=ap.parse_args()
    if args.analyze_existing:return analyze_existing(args.analyze_existing)
    if not args.output:ap.error('--output required for simulation')
    out=output_dir(args.output)
    profiles={'faithful':local(args.faithful),'registered':local(args.registered),
              'registered-f':local(args.floating)}
    if args.faithful_floating: profiles['faithful-f']=local(args.faithful_floating)
    selected=args.profiles.split(',')
    if not selected or len(set(selected))!=len(selected) or any(p not in profiles for p in selected):
        ap.error('Unknown/duplicate profile or missing --faithful-floating')
    profiles={p:profiles[p] for p in selected}
    expected={'faithful':'faithful baseline; execution retiming remains separate',
              'registered':'registered-execution-v1','registered-f':'rv32imfc-v1',
              'faithful-f':'rv32imfc-faithful-v1'}
    protected={}
    for profile,directory in profiles.items():
        parameters(directory)
        if manifest(directory)['implementation']!=expected[profile]:raise ValueError('Wrong profile supplied: '+profile)
        for path in directory.rglob('*'):
            if path.is_file():protected[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    for pattern in ('dv/core/*.py','dv/core/*.cpp','dv/core/*.json','tools/env/*.json',
                    'sw/flight/loop-measurement/src/*','sw/flight/loop-measurement/scenario/*.py'):
        for path in ROOT.glob(pattern):
            if path.is_file():protected[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    receipt=dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        profiles={},input_sha256=protected,
        environment='port-only RTL simulation; ideal one-cycle instruction/data memory; no interrupts',
        iteration='previous retirement before first loop instruction through loop backedge retirement; includes input staging, control_step, checksum and loop housekeeping',
        arithmetic='retirement-to-retirement spacing from existing smoke/flight instructions; includes pipeline/fetch effects, not isolated unit latency',
        unsupported={'faithful/hard-float':'Integer-only faithful profile is RV32IMC; supply faithful-f separately for F.'})
    try:
        fixed=next(flight_program(out/'fixed'))
        floating=next(float_flight(out/'hard-float'))[:5]
        smoke_dir=output_dir(out/'smoke');smoke_elf=build_program(smoke_dir)
        smoke=(smoke_dir,smoke_elf,smoke_dir/'program.bin',BASE,[])
        workloads={'fixed':fixed,'hard-float':floating,'smoke':smoke}
        prepared={}
        for name,(directory,elf,binary,base,flags) in workloads.items():
            is_float=name=='hard-float'
            iss=qemu_trace(elf,directory,base,binary if flags else None,0x80010080 if flags else None,is_float)
            if flags: iss,_=flight_reentry(iss,binary.read_bytes(),base,allow_compressed=is_float)
            disassembly=run(['riscv64-unknown-elf-objdump','-d','--disassemble=main',elf],directory,'main-disassembly').stdout if flags else ''
            prepared[name]=(iss,loop_boundaries(disassembly) if flags else None)
            for p in (elf,binary):protected[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        reference={}
        for profile,candidate in profiles.items():
            sim=compile_sim(out/profile/'sim',candidate);receipt['profiles'][profile]={}
            for name in ('fixed','smoke',*(['hard-float'] if profile in ('registered-f','faithful-f') else [])):
                directory=output_dir(out/profile/name)
                _,elf,binary,base,flags=workloads[name];iss,bounds=prepared[name]
                cycle_file=directory/'cycles.txt'
                result=run(['env',f'DEADHORSE_CYCLE_TRACE={cycle_file}',sim,binary,*flags],directory,'simulate')
                rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                cycles=timed_rows(rows,cycle_file.read_text())
                if name=='hard-float':compare_float(rows,iss,binary.read_bytes(),base)
                else:
                    clean=integer_rows(rows)
                    if name not in reference: reference[name]=clean
                    compare(reference[name],clean,iss,binary.read_bytes(),base)
                measured=dict(status='measured; architectural lockstep passed',retirements=len(rows),
                              arithmetic=arithmetic(rows,cycles),model=manifest(candidate)['implementation'])
                if bounds:
                    samples=loop_samples(rows,cycles,bounds)
                    measured.update(boundaries=bounds,iterations=stats([s['cycles'] for s in samples]),
                        per_mode={str(m):stats([s['cycles'] for s in samples if s['mode']==m]) for m in range(3)})
                    measured['derived_loop_us']={str(mhz):{k:measured['iterations'][k]/mhz for k in ('mean','worst')}
                                                for mhz in (9,12,24)}
                receipt['profiles'][profile][name]=measured
                print(profile+'/'+name+': '+json.dumps({k:v for k,v in measured.items() if k not in ('arithmetic','per_mode')}),flush=True)
                (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        for path,value in protected.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=value:raise ValueError('Measurement input changed: '+path)
        receipt['status']='pass (measured selected supported profiles)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
