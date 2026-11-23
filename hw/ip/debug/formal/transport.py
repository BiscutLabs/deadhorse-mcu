"""T32 actual dual-clock DMI transport: safety, concrete covers and corruption/reset faults."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import validate_job


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = (ROOT / args.output).resolve(); out.relative_to(ROOT / 'build')
    if (out / 'result.json').exists(): raise ValueError('Retain prior evidence; use fresh output')
    out.mkdir(parents=True, exist_ok=True)
    paths=[ROOT/p for p in ('hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',
        'hw/ip/debug/formal/DebugTransportFormal.scala','hw/ip/debug/src/main/scala/deadhorse/debug/DebugTransport.scala',
        'tools/formal.py','tools/sbt.py','tools/env/lock.json','build.sbt')]+[Path(__file__)]
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt = dict(status='running', request_width=41, response_width=34, depth=2, runs=[],
        assumptions=['POR asserted initially; subsequently arbitrary; clear is synchronous to TCK',
                     'DTM producer: one outstanding request; DM consumer: one arbitrary response per accepted request',
                     'ideal digital sampling; no analog metastability model'],
        clock_model='actual independent unconstrained clocks; SBY multiclock, no async2sync',
        engine='abc pdr', cover_depth=48, timeout_seconds=120,
        source_sha256=hashes(),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    (out/'runner.py').write_bytes(Path(__file__).read_bytes())
    started=time.monotonic()
    def run(cmd, label, timeout=180):
        begin=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            result=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        record=dict(command=cmd,returncode=result.returncode,seconds=time.monotonic()-begin,log=label+'.log')
        receipt['runs'].append(record)
        return result.returncode,record
    try:
        code,_=run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/debug/formal")',f'hw/runMain deadhorse.debug.EmitDebugTransportFormal {out}/emit'],'emit',600)
        if code: raise RuntimeError('CDC formal emission failed')
        receipt['emitted_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (out/'emit').rglob('*.sv')}
        for variant in ('corrupt','stale','cover','correct'):
            sources=sorted((out/'emit'/variant).glob('*.sv'))
            is_cover=variant.endswith('cover')
            is_fault=variant in ('corrupt','stale')
            top='DebugTransportFormal'
            mode='cover' if is_cover else 'prove'
            engine='smtbmc z3' if is_cover else 'abc pdr'
            config=out/(variant+'.sby')
            config.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 48','timeout 120','',
                '[engines]',engine,'','[script]',
                f'read_slang --top {top} '+' '.join(p.name for p in sources),
                f'prep -top {top} -flatten',
                "fminit -seq por_n 0,'z",
                'clk2fflogic','chformal -lower',
                f"select -assert-count {4 if is_cover else 8} t:${'cover' if is_cover else 'assert'}",
                'select -assert-count 1 t:$assume','',
                '[files]',*map(str,sources),'']))
            code,record=run(['sby','-d',str(out/variant),str(config)],variant)
            status_file=out/variant/'status'
            status=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
            record['status']=status
            expected='FAIL' if is_fault else 'PASS'
            if status != expected or code != (2 if is_fault else 0):
                raise RuntimeError(f'{variant}: {status}; see {out}/{variant}.log')
            expected_faults={'corrupt':{'assert__chisel3_builtin_3'},'stale':{'assert__chisel3_builtin'}}
            record['failed_properties']=validate_job(out/variant,'cover' if is_cover else 'negative' if is_fault else 'proof',
                code,status,expected_faults.get(variant))
            if is_cover:
                reached=set(re.findall(r'reached cover statement DebugTransportFormal\.(cover__\w+)',(out/variant/'logfile.txt').read_text()))
                if reached!={'cover__cover','cover__cover_1','cover__cover_2','cover__cover_3'}:
                    raise RuntimeError('Incomplete intended cover witnesses')
                record['reached_covers']=sorted(reached)
            print(f'PASS CDC {variant}: {status}',flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Sources changed during proof')
        receipt['status']='pass'
    except Exception as exc:
        receipt.update(status='unresolved' if 'TIMEOUT' in str(exc) else 'failed',error=str(exc))
        print(str(exc),file=sys.stderr)
    finally:
        receipt['seconds']=time.monotonic()-started
        receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':sys.exit(main())
