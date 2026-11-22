"""Frozen focused T29 regressions and complete top emission; never invokes CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dv.soc.check_io import snapshot

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='running',source_sha256=snapshot(),commands=[],ci='Neither tier run',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    def run(argv,label):
        begin=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            code=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=argv,returncode=code,seconds=time.monotonic()-begin,log=label+'.log'))
        if code:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        run([sys.executable,'dv/soc/prepare_qspi.py'],'prepare')
        run([sys.executable,'hw/top/reference/test_soc_map.py'],'map-tests')
        run([sys.executable,'tools/check_structure.py','--include-untracked'],'structure')
        suites=['deadhorse.qspi.QspiSpec','deadhorse.qspi.QspiEngineSpec','deadhorse.qspi.QspiOwnerSpec',
                'deadhorse.top.SocQspiSpec','deadhorse.top.SocBootReleaseSpec','deadhorse.top.SocI1ResetSpec']
        run([sys.executable,'tools/sbt.py','hw/testOnly '+' '.join(suites)],'simulation')
        run([sys.executable,'hw/ip/qspi/formal/check.py','--output',str(out.relative_to(ROOT)/'formal')],'formal')
        run([sys.executable,'hw/ip/qspi/check_timing.py','--output',str(out.relative_to(ROOT)/'timing')],'timing')
        commands=[sys.executable,'tools/sbt.py']
        for mhz in (8,9):
            for usb in ('stub','usb'):
                commands.append(f'hw/runMain deadhorse.top.EmitSocQspi {out.relative_to(ROOT)}/soc-{mhz}-{usb} {usb} {mhz}')
        run(commands,'whole-soc')
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Frozen implementation changed')
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();sys.exit(main(a.output))
