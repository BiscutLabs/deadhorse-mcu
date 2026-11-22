"""Frozen T21 block/integration tests and complete top emissions. Never invokes CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]

def snapshot():
    paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(set(paths))
            if p and (ROOT/p).is_file() and not p.endswith('.md')}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True);a=ap.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256=snapshot(),commands=[],ci='Neither tier run, per user instruction')
    def command(argv,label):
        before=time.monotonic()
        with (out/(label+'.log')).open('w') as f:
            p=subprocess.run(argv,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(command=argv,returncode=p.returncode,seconds=time.monotonic()-before,log=label+'.log'))
        if p.returncode:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        command([sys.executable,'dv/soc/prepare_io.py'],'prepare')
        command([sys.executable,'hw/top/reference/test_soc_map.py'],'map-tests')
        command([sys.executable,'tools/check_structure.py','--include-untracked'],'structure')
        suites=['deadhorse.gpio.GpioSpec','deadhorse.adc.AdcSpec','deadhorse.timers.TimersSpec',
                'deadhorse.top.SocIoSpec','deadhorse.top.SocI1Spec','deadhorse.top.SocI1ResetSpec',
                'deadhorse.top.SocI1CoreResetSpec','deadhorse.top.SocI1UsbSpec','deadhorse.top.SocNestedSpec']
        command([sys.executable,'tools/sbt.py','hw/testOnly '+' '.join(suites)],'simulation')
        commands=[sys.executable,'tools/sbt.py']
        for mhz in (8,9):
            for usb in ('stub','usb'):
                commands.append(f'hw/runMain deadhorse.top.EmitSocIo {out.relative_to(ROOT)}/soc-{mhz}-{usb} soc {usb} {mhz}')
        command(commands,'whole-soc')
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Frozen implementation changed during checks')
        receipt['status']='pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':sys.exit(main())
