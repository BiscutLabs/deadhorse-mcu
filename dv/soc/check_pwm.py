"""Freeze and verify T22 plus unchanged I/O integration regressions; no CI."""
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

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='running',source_sha256=snapshot(),commands=[],ci='Neither tier run',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip())
    def run(argv,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            code=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=argv,returncode=code,seconds=time.monotonic()-start,log=label+'.log'))
        if code:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        run([sys.executable,'dv/soc/prepare_production.py'],'prepare')
        run([sys.executable,'hw/top/reference/test_soc_map.py'],'map-tests')
        run([sys.executable,'tools/check_structure.py','--include-untracked'],'structure')
        suites=['deadhorse.pwm.PwmChannelSpec','deadhorse.pwm.PwmSpec','deadhorse.top.SocPwmSpec',
                'deadhorse.top.SocPwmCoreResetSpec','deadhorse.gpio.GpioSpec','deadhorse.adc.AdcSpec',
                'deadhorse.timers.TimersSpec','deadhorse.top.SocI1Spec','deadhorse.top.SocI1ResetSpec',
                'deadhorse.top.SocI1CoreResetSpec','deadhorse.top.SocI1UsbSpec','deadhorse.top.SocNestedSpec']
        run([sys.executable,'tools/sbt.py','hw/testOnly '+' '.join(suites)],'simulation')
        commands=[sys.executable,'tools/sbt.py']
        for mhz in (8,9):
            for usb in ('stub','usb'):
                commands.append(f'hw/runMain deadhorse.top.EmitSoc {out.relative_to(ROOT)}/soc-{mhz}-{usb} {"production" if usb=="usb" else "usb-stub-test"} {mhz}')
        run(commands,'whole-soc')
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Frozen sources changed')
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':sys.exit(main())
