"""T41 lite synchronous initialization versus the previous reset behavior."""
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
    paths=sorted((ROOT/'hw/ip/lite_core/src/main').rglob('*.scala'))+[ROOT/p for p in (
        'hw/ip/lite_core/formal/LiteInitializeFormal.scala','tools/formal.py','tools/sbt.py','tools/env/lock.json','build.sbt')]+[Path(__file__)]
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt = dict(status='running', scope="whole lite-core public behavior, including RVFI/debug, after registered local initialization", runs=[],
        assumptions=['reset asserted initially; subsequently arbitrary; local initialization request registered on the owning clock',
                     'ideal digital sampling; no analog metastability model'],
        clock_model='one real unconstrained clock; clk2fflogic retains async reference reset',
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
        code,_=run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSources += file("/work/hw/ip/lite_core/formal/LiteInitializeFormal.scala")',f'hw/runMain deadhorse.lite_core.EmitLiteInitializeFormal {out}/emit'],'emit',600)
        if code: raise RuntimeError('CDC formal emission failed')
        receipt['emitted_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (out/'emit').rglob('*.sv')}
        for variant in ('corrupt','cover','correct'):
            sources=sorted((out/'emit'/variant).glob('*.sv'))
            is_cover=variant.endswith('cover')
            is_fault=variant in ('corrupt',)
            top='LiteInitializeFormal'
            mode='cover' if is_cover else 'prove'
            engine='smtbmc z3' if is_cover else 'abc pdr'
            config=out/(variant+'.sby')
            config.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 48','timeout 120','',
                '[engines]',engine,'','[script]',
                f'read_slang --top {top} '+' '.join(p.name for p in sources),
                f'prep -top {top} -flatten',
                "fminit -seq reset 1,'z",
                'clk2fflogic','chformal -lower',
                f"select -assert-count {2 if is_cover else 11} t:${'cover' if is_cover else 'assert'}",
                'select -assert-count 1 t:$assume','',
                '[files]',*map(str,sources),'']))
            code,record=run(['sby','-d',str(out/variant),str(config)],variant)
            status_file=out/variant/'status'
            status=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
            record['status']=status
            expected='FAIL' if is_fault else 'PASS'
            if status != expected or code != (2 if is_fault else 0):
                raise RuntimeError(f'{variant}: {status}; see {out}/{variant}.log')
            # Stale x1 may affect an arbitrary instruction's address, control,
            # data or debug CSR operand. Only the seven comparison claims may
            # fail; the four embedded core invariants must remain satisfied.
            expected_faults={'corrupt':{'assert__chisel3_builtin'} |
                {f'assert__chisel3_builtin_{i}' for i in range(6)}}
            record['failed_properties']=validate_job(out/variant,'cover' if is_cover else 'negative' if is_fault else 'proof',
                code,status,expected_faults.get(variant))
            if is_cover:
                reached=set(re.findall(r'reached cover statement LiteInitializeFormal\.(cover__\w+)',(out/variant/'logfile.txt').read_text()))
                reached.update(re.findall(r'Reached cover statement in step \d+ at LiteInitializeFormal: (cover__\w+)',
                    (out/variant/'logfile.txt').read_text()))
                if reached!= {'cover__cover','cover__cover_1'}:
                    raise RuntimeError('Incomplete intended cover witnesses')
                record['reached_covers']=sorted(reached)
            print(f'PASS lite initialization {variant}: {status}',flush=True)
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
