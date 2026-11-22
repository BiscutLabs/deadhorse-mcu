"""Frozen focused T27 checks and receipt verification. Never invokes CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dv.soc.check_io import snapshot

def verify_receipt(path):
    receipt=json.loads(path.read_text())
    if receipt['status']!='pass':raise RuntimeError(f'Not passing: {path}')
    for name,digest in receipt['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Stale source {name} in {path}')
    for name,digest in receipt['artifact_sha256'].items():
        if hashlib.sha256((path.parent/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Changed artifact {name} in {path}')
    return dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def main(output,formal,timing):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    hashes=snapshot
    receipt=dict(status='running',source_sha256=hashes(),commands=[],evidence=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='D71 raw production ADC, firmware conversion and four full SoC emissions; neither CI tier run')
    try:
        for relative in (*formal,timing):receipt['evidence'].append(verify_receipt(ROOT/relative/'result.json'))
        top_command=[sys.executable,'tools/sbt.py',*[f'hw/runMain deadhorse.top.EmitSoc '+
            f'{out.relative_to(ROOT)}/soc-{mhz}-{usb} {usb} {mhz}' for mhz in (8,9)
            for usb in ('usb-stub-test','production')]]
        for name,argv in [
            ('prepare',[sys.executable,'dv/soc/prepare_production.py']),
            ('firmware',[sys.executable,'sw/hal/tests/test_adc_convert.py','--output',str(out/'firmware')]),
            ('simulation',[sys.executable,'tools/sbt.py','hw/testOnly deadhorse.adc.AdcSpec deadhorse.adc.AdcSampleStateSpec deadhorse.adc.AdcRawSpec deadhorse.top.SocIoSpec']),
            ('whole-soc',top_command),
            ('structure',[sys.executable,'tools/check_structure.py','--include-untracked'])]:
            start=time.monotonic()
            with (out/(name+'.log')).open('w') as stream:
                code=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
            receipt['commands'].append(dict(name=name,command=argv,returncode=code,seconds=time.monotonic()-start))
            print(name,'PASS' if code==0 else 'FAIL',flush=True)
            if code:raise RuntimeError(name+' failed')
        receipt['evidence'].append(verify_receipt(out/'firmware/result.json'))
        for relative in (*formal,timing):verify_receipt(ROOT/relative/'result.json')
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Sources changed during frozen checks')
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--formal',nargs='+',required=True)
    p.add_argument('--timing',required=True);a=p.parse_args();sys.exit(main(a.output,a.formal,a.timing))
