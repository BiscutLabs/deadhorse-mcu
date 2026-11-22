"""Fresh raw/legacy engine comparison under the existing9MHz T21 screen."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.timing.check import measure

def main(output,wrapper_only=False):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[*sorted((ROOT/'hw/ip/adc/src/main').rglob('*.scala')),
           *sorted((ROOT/'hw/ip/adc/timing').rglob('*.scala')),Path(__file__).resolve(),
           *sorted((ROOT/'tools/timing').glob('*.py')),*sorted((ROOT/'tools/timing').glob('*.tcl')),
           ROOT/'build.sbt',ROOT/'tools/sbt.py',ROOT/'tools/env/lock.json']
    if wrapper_only:paths += [*sorted((ROOT/'hw/lib/src/main').rglob('*.scala')),
        ROOT/'hw/ip/adc/adc.regmap.yaml',ROOT/'build/t21/adc/adc_regs.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),blocks={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope=('Production raw ADC wrapper' if wrapper_only else 'Standalone engine with production asynchronous reset')+
        '; main-9mhz conservative screen, ideal boundary, mapped pre-layout, no physical qualification')
    command=([sys.executable,'tools/sbt.py',
        f'hw/runMain deadhorse.adc.EmitAdc build/t21/adc/adc_regs.json {out}/wrapper/emit'] if wrapper_only else
        [sys.executable,'tools/sbt.py',
        'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/adc/timing")',
        *[f'hw/runMain deadhorse.adc.EmitAdcEngineTiming {n} {out}/{n}/emit' for n in ('legacy','raw')]])
    receipt['emission_command']=command
    try:
        with (out/'emit.log').open('w') as stream:subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        for n in (('wrapper',) if wrapper_only else ('legacy','raw')):
            receipt['blocks'][n]=measure('Adc' if wrapper_only else 'AdcEngineTiming',
                [str(p) for p in sorted((out/n/'emit').glob('*.sv'))],
                'clk' if wrapper_only else 'clock',out/n/'timing',operating_point='main-9mhz')
            print(n,receipt['blocks'][n]['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Sources changed during measurement')
        receipt['status']='pass' if all(r['status']=='pass' for r in receipt['blocks'].values()) else 'failed'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--wrapper-only',action='store_true')
    a=p.parse_args();sys.exit(main(a.output,a.wrapper_only))
