"""Focused I0 control proof; does not run CI or re-prove core internals."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from formal import validate_job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=False)
    sources = [*sorted((ROOT / 'hw/top/reference/src/main/scala').rglob('*.scala')),
               Path(__file__), Path(__file__).with_name('SocMemoryFormal.scala'),
               ROOT / 'build/t20/map/soc.json', ROOT / 'build/t20/i0-firmware/boot.hex',
               ROOT / 'hw/lib/src/main/scala/deadhorse/lib/LocalBus.scala',
               ROOT / 'tools/formal.py', ROOT / 'tools/sbt.py', ROOT / 'build.sbt',
               ROOT / 'tools/env/lock.json', *sorted((ROOT/'project').glob('*'))]
    sources = [p for p in sources if p.is_file()]
    snapshot = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt = dict(status='running', commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
                   source_sha256=snapshot(), assumptions=['Both resets low initially; arbitrary thereafter'],
                   scope='Full-size production memory control only; no memory data integrity or subcycle reset proof',
                   configuration=dict(banks=4,read_latency=1,assertions=11,covers=3),
                   timeout_seconds=120, runs=[])
    def run(command, name, timeout=180):
        start = time.monotonic()
        with (output / (name+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        receipt['runs'].append(dict(command=command, seconds=time.monotonic()-start, returncode=result.returncode))
        return result.returncode
    try:
        code=run([sys.executable,'tools/sbt.py',
                  f'set hw / Compile / unmanagedSourceDirectories += file("{ROOT}/hw/top/reference/formal")',
                  f'hw/runMain deadhorse.top.EmitSocMemoryFormal build/t20/map/soc.json {ROOT}/build/t20/i0-firmware/boot.hex {output}/emit'], 'emit', 600)
        if code: raise RuntimeError('Emission failed')
        for variant, mode, engine in [('cover','cover','smtbmc z3'),('corrupt','bmc','smtbmc z3'),('correct','prove','abc pdr')]:
            files=sorted((output/'emit'/variant).glob('*.sv'))
            if not files: raise RuntimeError('No emitted source')
            config=output/(variant+'.sby')
            config.write_text('\n'.join(['[options]',f'mode {mode}','depth 32','timeout 120','',
                '[engines]',engine,'','[script]',
                'read_slang --top SocMemoryFormal '+' '.join(p.name for p in files),
                'prep -top SocMemoryFormal -flatten',
                "fminit -seq serviceReset_n 0,'z -seq clientReset_n 0,'z",'async2sync','chformal -lower',
                'select -assert-count 11 t:$assert',
                *(['select -assert-count 3 t:$cover'] if variant=='cover' else []),'',
                '[files]',*map(str,files),'']))
            code=run(['sby','-d',str(output/variant),str(config)],variant)
            status=(output/variant/'status').read_text().split()[0]
            failures=validate_job(output/variant,'negative' if variant=='corrupt' else mode,code,status,
                                  {'assert__chisel3_builtin_0','assert__chisel3_builtin_3'} if variant=='corrupt' else None)
            if variant=='corrupt' and 'assert__chisel3_builtin_0' not in failures:
                raise RuntimeError('Fault did not violate instruction response timing')
            if failures: receipt['runs'][-1]['failed_properties']=failures
            receipt['runs'][-1]['status']=status
            print(f'PASS I0 control {variant}: {status}',flush=True)
        if snapshot()!=receipt['source_sha256']: raise RuntimeError('Sources changed while proving')
        receipt['status']='pass'
    except Exception as error:
        unresolved = isinstance(error, subprocess.TimeoutExpired) or 'TIMEOUT' in str(error)
        receipt.update(status='unresolved' if unresolved else 'failed',error=str(error))
        raise
    finally:
        receipt['artifact_sha256'] = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(output.rglob('*')) if p.is_file() and p != output/'result.json'}
        (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
