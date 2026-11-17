"""T14 actual dual-clock FIFO: unbounded safety, concrete covers and data fault."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    ap.add_argument('--width', type=int, default=32)
    ap.add_argument('--depth', type=int, default=2)
    args = ap.parse_args()
    out = (ROOT / args.output).resolve(); out.relative_to(ROOT / 'build')
    if (out / 'result.json').exists(): raise ValueError('Retain prior evidence; use fresh output')
    out.mkdir(parents=True, exist_ok=True)
    receipt = dict(status='running', width=args.width, depth=args.depth, runs=[],
        assumptions=['both resets asserted initially; subsequently arbitrary',
                     'observer history initialized to zero (monitor-only)',
                     'ideal digital sampling; no analog metastability model'],
        clock_model='actual independent unconstrained clocks; SBY multiclock, no async2sync',
        engine='abc pdr', cover_depth=48, timeout_seconds=120,
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [ROOT/'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',Path(__file__),ROOT/'hw/lib/formal/CdcFormal.scala']})
    started=time.monotonic()
    def run(cmd, label, timeout=180):
        begin=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            result=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        record=dict(command=cmd,returncode=result.returncode,seconds=time.monotonic()-begin,log=label+'.log')
        receipt['runs'].append(record)
        return result.returncode,record
    try:
        code,_=run([sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.lib.EmitCdcFormal {args.width} {args.depth} {out}/emit'],'emit',600)
        if code: raise RuntimeError('CDC formal emission failed')
        for variant in ('cover','corrupt','correct','side_cover','side_bad_gray','side_early_release','side_correct'):
            sources=sorted((out/'emit'/variant).glob('*.sv'))
            is_cover=variant.endswith('cover')
            is_fault=variant in ('corrupt','side_bad_gray','side_early_release')
            top='CdcSideFormal' if variant.startswith('side_') else 'CdcFormal'
            mode='cover' if is_cover else 'prove'
            engine='smtbmc z3' if is_cover else 'abc pdr'
            config=out/(variant+'.sby')
            config.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 48','timeout 120','',
                '[engines]',engine,'','[script]',
                f'read_slang --top {top} '+' '.join(p.name for p in sources),
                f'prep -top {top} -flatten',
                "fminit -seq reset_n 0,'z" if top=='CdcSideFormal' else "fminit -seq wn 0,'z -seq rn 0,'z -seq checking 0,'z",
                'clk2fflogic','chformal -lower',
                f"select -assert-count {(2 if top=='CdcSideFormal' else 9) if is_cover else (3 if top=='CdcSideFormal' else 11)} t:${'cover' if is_cover else 'assert'}",'',
                '[files]',*map(str,sources),'']))
            code,record=run(['sby','-d',str(out/variant),str(config)],variant)
            status_file=out/variant/'status'
            status=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
            record['status']=status
            expected='FAIL' if is_fault else 'PASS'
            if status != expected or code != (2 if is_fault else 0):
                raise RuntimeError(f'{variant}: {status}; see {out}/{variant}.log')
            if (is_cover or is_fault) and not list((out/variant).glob('engine_*/trace*.vcd')):
                raise RuntimeError('Missing concrete witness')
            print(f'PASS CDC {variant}: {status}',flush=True)
        receipt['status']='pass'
    except Exception as exc:
        receipt.update(status='unresolved' if 'TIMEOUT' in str(exc) else 'failed',error=str(exc))
        print(str(exc),file=sys.stderr)
    finally:
        receipt['seconds']=time.monotonic()-started
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':sys.exit(main())
