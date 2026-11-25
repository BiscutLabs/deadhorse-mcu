"""PLAN05 Phase1 ELF/static-stack and existing-LiteHart timing measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'sw/lite/watcher'
sys.path.insert(0, str(ROOT))
from tools.spikes.s3_memory.firmware import linked_edges, relocation_edges, stack_frame

def parse_results(text):
    cases=[dict(kind=int(m[1]),response_edges=int(m[2]),cycles=int(m[3]),instructions=int(m[4]),
                milliseconds_estimated=int(m[3])*1000/32000)
           for line in text.splitlines() if (m:=re.fullmatch(r'CASE (\d+) (\d+) (\d+) (\d+)',line))]
    stacks=[(int(m[1]),int(m[2])) for line in text.splitlines() if (m:=re.fullmatch(r'STACK (\d+) (\d+)',line))]
    if [(c['kind'],c['response_edges']) for c in cases] != [(k,d) for d in (1,2,4) for k in (0,1,2,2)]:
        raise ValueError('case inventory incomplete')
    if [d for d,_ in stacks] != [1,2,4] or any(n<=0 for _,n in stacks):
        raise ValueError('stack inventory incomplete')
    if any(c['cycles']<=0 or c['instructions']<=0 for c in cases):
        raise ValueError('empty execution')
    return cases,max(n for _,n in stacks)

def source_hashes():
    paths=list(SOURCE.glob('*'))+list((ROOT/'hw/ip/lite_core/src/main').rglob('*.scala'))
    paths+=list((ROOT/'hw/lib/src/main').rglob('*.scala'))+list((ROOT/'project').glob('*'))
    paths+=[ROOT/p for p in ('build.sbt','tools/sbt.py','tools/env/lock.json','tools/env/run.py',
                           'tools/spikes/s3_memory/firmware.py','build/env/image.json',
                           'hw/top/reference/src/test/scala/deadhorse/top/WatcherTimingFixture.scala',
                           'hw/top/reference/src/main/scala/deadhorse/top/SocDebugRoute.scala',
                           'hw/ip/bus/src/main/scala/deadhorse/bus/BusFabric.scala')]
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/plan05/watcher')
    parser.add_argument('--routed',action='store_true',help='include existing production debug router and AON fabric')
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to(ROOT / 'build'):
        raise ValueError('output must be under build/')
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='running', classification='measured existing core with modeled AON peripherals, not integrated RTL',
                   commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), commands=[])
    receipt['sources'] = source_hashes()
    def run(cmd, label, expected_failure=None):
        start=time.monotonic()
        p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/(label+'.log')).write_text(p.stdout)
        receipt['commands'].append(dict(command=list(map(str,cmd)),seconds=time.monotonic()-start,returncode=p.returncode))
        if expected_failure is not None:
            if p.returncode==0 or expected_failure not in p.stdout:raise RuntimeError('fault was not detected: '+label)
        elif p.returncode:
            print(p.stdout);raise RuntimeError(label+' failed')
        return p.stdout
    prefix='riscv64-unknown-elf-'
    flags=['-march=rv32e_zicsr','-mabi=ilp32e','-Os','-ffreestanding','-fno-builtin',
           '-ffunction-sections','-fdata-sections','-fstack-usage','-fno-common',
           '-msmall-data-limit=0','-Wall','-Wextra','-Werror']
    try:
        run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror',SOURCE/'test_crc.c','-o',out/'test_crc'],'crc-build')
        print(run([out/'test_crc'],'crc-check'),end='')
        run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-DBAD_REMAINDER',SOURCE/'test_crc.c','-o',out/'bad_crc'],'crc-fault-build')
        run([out/'bad_crc'],'crc-fault-check','CRC_REMAINDER_MISMATCH')
        run([prefix+'gcc','--version'],'gcc-version')
        run(['verilator','--version'],'verilator-version')
        objects=[]
        for name in ('start.S','watcher.c'):
            obj=out/(Path(name).stem+'.o');objects.append(obj)
            run([prefix+'gcc',*flags,'-c',SOURCE/name,'-o',obj],name)
        elf=out/'watcher.elf';binary=out/'watcher.bin'
        run([prefix+'gcc',*flags,'-nostdlib','-Wl,--no-relax','-Wl,--gc-sections',
             '-Wl,-T,'+str(SOURCE/'watcher.ld'),*objects,'-o',elf],'link')
        run([prefix+'objcopy','-O','binary',elf,binary],'binary')
        sizes=run([prefix+'size','-A',elf],'size')
        sections={m[1]:int(m[2]) for line in sizes.splitlines() if (m:=re.match(r'(\.\S+)\s+(\d+)\s+\d+',line))}
        symbols=[]
        for line in run([prefix+'nm','-S','--defined-only',elf],'symbols').splitlines():
            if m:=re.match(r'([0-9a-f]+) ([0-9a-f]+) ([A-Za-z]) (\S+)$',line):
                symbols.append(dict(address=int(m[1],16),bytes=int(m[2],16),kind=m[3],name=m[4]))
        functions={s['name'] for s in symbols if s['kind'] in 'tT'}
        edges=linked_edges(run([prefix+'objdump','-d',elf],'disassembly'),symbols)
        for obj in objects:
            for name,targets in relocation_edges(run([prefix+'objdump','-dr',obj],obj.stem+'-relocations'),functions).items():
                edges[name].update(targets)
        frames={}
        for su in out.glob('*.su'):
            for row in su.read_text().splitlines():
                location,amount,kind=row.split('\t')
                if kind!='static':raise ValueError('nonstatic stack')
                frames[location.rsplit(':',1)[-1]]=int(amount)
        def chain(name,seen=frozenset()):
            if name in seen:raise ValueError('recursive call graph')
            return stack_frame(name,frames)+max((chain(c,seen|{name}) for c in edges[name]),default=0)
        static=chain('watcher') # start.S has no frame; global traps disabled.
        emitter='hw/Test/runMain deadhorse.top.EmitWatcherTimingFixture' if args.routed else 'hw/runMain deadhorse.lite_core.EmitLiteHart'
        top='WatcherTimingFixture' if args.routed else 'LiteHart'
        run([sys.executable,'tools/sbt.py',emitter+' '+str(out/'rtl')],'emit')
        rtl=sorted((out/'rtl').glob('*.sv'))
        receipt['rtl_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl}
        executable=out/('obj/V'+top)
        run(['verilator','--cc','--exe','--build','-j','4','--top-module',top,
             '--Mdir',out/'obj','-Wno-fatal',*(['-CFLAGS','-DWATCHER_ROUTED'] if args.routed else []),
             *rtl,SOURCE/'model.cpp'],'verilate')
        result=run([executable,binary],'simulation');print(result,end='')
        cases,observed=parse_results(result)
        publication=[dict(response_edges=int(m[1]),cycles=int(m[2]),milliseconds_estimated=int(m[2])*1000/32000)
            for line in result.splitlines() if (m:=re.fullmatch(r'PUBLISH (\d+) (\d+)',line))]
        if [p['response_edges'] for p in publication]!=[1,1,2,2,4,4] or any(p['cycles']<=0 for p in publication):
            raise ValueError('publication inventory incomplete')
        fault_obj=out/'fault.o';fault_elf=out/'fault.elf';fault_bin=out/'fault.bin'
        run([prefix+'gcc',*flags,'-DWATCHER_BAD_PAYLOAD','-c',SOURCE/'watcher.c','-o',fault_obj],'fault-compile')
        run([prefix+'gcc',*flags,'-nostdlib','-Wl,--no-relax','-Wl,--gc-sections',
             '-Wl,-T,'+str(SOURCE/'watcher.ld'),objects[0],fault_obj,'-o',fault_elf],'fault-link')
        run([prefix+'objcopy','-O','binary',fault_elf,fault_bin],'fault-binary')
        run([executable,fault_bin],'fault-simulation','FAIL mail payload mismatch')
        receipt['negative_control']='PASS: wrong-payload firmware rejected by independent mailbox oracle'
        reserved=max(static,observed)
        code=sections.get('.text',0)+sections.get('.rodata',0);data=sections.get('.data',0)+sections.get('.bss',0)
        working=code+data+reserved;required=(working*5+3)//4
        receipt.update(sections=sections,static_frames=frames,call_edges={k:sorted(v) for k,v in edges.items()},
            stack_observed=observed,stack_static=static,stack_reserved=reserved,working_bytes=working,
            required_with_margin_estimated=required,selected_bytes=2048 if required<=2048 else 3072 if required<=3072 else None,
            cases=cases,publication=publication,clock_hz_assumed=32000,
            scope=('Existing production debug router and AON fabric; no contention; optimistic target grant/response, not whole SoC.' if args.routed else
                   'Isolated core: memory response delay swept at 1/2/4 AON edges; no main clock or production peripheral modeled.'))
        if source_hashes()!=receipt['sources']:raise RuntimeError('sources changed during measurement')
        receipt['artifacts']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (elf,binary,fault_elf,fault_bin,executable)}
        receipt['status']='pass' if required<=3072 and all(c['cycles']<=3200 for c in cases if c['kind']==2) else 'stop-limit'
        print(json.dumps({k:receipt[k] for k in ('status','working_bytes','required_with_margin_estimated','selected_bytes','stack_reserved')},indent=2))
    except Exception as error:
        receipt.update(status='failed',error=str(error))
        raise
    finally:
        (out/'measurement.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['status']=='pass' else 2

if __name__=='__main__':sys.exit(main())
