"""T14 actual dual-clock FIFO: unbounded safety, concrete covers and data fault."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    ap.add_argument('--width', type=int, default=32)
    ap.add_argument('--depth', type=int, default=2)
    ap.add_argument('--side-only', action='store_true', help='Run the existing Gray/reset-release properties only; no FIFO data-proof claim')
    args = ap.parse_args()
    out = (ROOT / args.output).resolve(); out.relative_to(ROOT / 'build')
    if (out / 'result.json').exists(): raise ValueError('Retain prior evidence; use fresh output')
    out.mkdir(parents=True, exist_ok=True)
    source_paths = [ROOT/'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala', Path(__file__),
                    ROOT/'hw/lib/formal/CdcFormal.scala', ROOT/'tools/sbt.py', ROOT/'build.sbt']
    snapshot = lambda: {str(p.relative_to(ROOT)): digest(p) for p in source_paths}
    tool_paths = {name: shutil.which(name) for name in ('sby', 'yosys', 'yosys-abc', 'z3')}
    if not all(tool_paths.values()): raise ValueError('Missing pinned CDC proof tool')
    receipt = dict(status='running', width=args.width, depth=args.depth, side_only=args.side_only, runs=[],
        assumptions=['both resets asserted initially; subsequently arbitrary',
                     'observer history initialized to zero (monitor-only)',
                     'ideal digital sampling; no analog metastability model'],
        clock_model='actual independent unconstrained clocks; SBY multiclock, no async2sync',
        engine='abc pdr', cover_depth=48, timeout_seconds=120,
        source_sha256=snapshot(), tool_sha256={name:digest(path) for name,path in tool_paths.items()})
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
        variants=('side_cover','side_bad_gray','side_early_release','side_correct') if args.side_only else (
            'cover','corrupt','correct','side_cover','side_bad_gray','side_early_release','side_correct')
        for variant in variants:
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
            proof_inputs = {str(p.relative_to(out)):digest(p) for p in [config,*sources]}
            code,record=run(['sby','-d',str(out/variant),str(config)],variant)
            record['input_sha256'] = proof_inputs
            if any(digest(out/p)!=h for p,h in proof_inputs.items()):
                raise RuntimeError('CDC model input changed during solver run')
            status_file=out/variant/'status'
            status=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
            record['status']=status
            expected='FAIL' if is_fault else 'PASS'
            if status != expected or code != (2 if is_fault else 0):
                raise RuntimeError(f'{variant}: {status}; see {out}/{variant}.log')
            if (is_cover or is_fault) and not list((out/variant).glob('engine_*/trace*.vcd')):
                raise RuntimeError('Missing concrete witness')
            print(f'PASS CDC {variant}: {status}',flush=True)
        if snapshot()!=receipt['source_sha256']:
            raise RuntimeError('CDC source changed during proof run')
        if any(digest(tool_paths[n])!=h for n,h in receipt['tool_sha256'].items()):
            raise RuntimeError('CDC tool changed during proof run')
        receipt['status']='pass'
    except Exception as exc:
        receipt.update(status='unresolved' if 'TIMEOUT' in str(exc) else 'failed',error=str(exc))
        print(str(exc),file=sys.stderr)
    finally:
        receipt['seconds']=time.monotonic()-started
        receipt['artifact_sha256']={str(p.relative_to(out)):digest(p)
            for p in sorted(out.rglob('*')) if p.is_file() and p != out/'result.json'}
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':sys.exit(main())
