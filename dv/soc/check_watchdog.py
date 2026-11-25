"""Freeze focused watchdog and integration regressions; neither CI tier runs."""
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
        begin=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            code=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=argv,returncode=code,seconds=time.monotonic()-begin,log=label+'.log'))
        if code:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        run([sys.executable,'dv/soc/prepare_production.py'],'prepare')
        run([sys.executable,'hw/ip/watchdog/check_provenance.py'],'provenance')
        run([sys.executable,'hw/top/reference/test_soc_map.py'],'map-tests')
        run([sys.executable,'tools/check_structure.py','--include-untracked'],'structure')
        suites=['deadhorse.watchdog.WatchdogSpec','deadhorse.watchdog.WatchdogMmioSpec',
                'deadhorse.timers.GeneralTimersControlSpec','deadhorse.pinmux.PinmuxWatchdogSpec',
                'deadhorse.top.SocWatchdogSpec','deadhorse.top.SocWatchdogCoreSpec',
                'deadhorse.top.SocWatchdogEpochSpec',
                'deadhorse.top.SocLiteSpec','deadhorse.top.SocI1ResetSpec',
                'deadhorse.top.SocPwmCoreResetSpec','deadhorse.top.SocPinmuxCoreResetSpec']
        run([sys.executable,'tools/sbt.py','hw/testOnly '+' '.join(suites)],'simulation')
        commands=[sys.executable,'tools/sbt.py']
        for mhz in (8,9):
            for usb in ('stub','usb'):
                commands.append(f'hw/runMain deadhorse.top.EmitSocExternalClockTest {out.relative_to(ROOT)}/soc-{mhz}-{usb} {"production" if usb=="usb" else "usb-stub-test"} {mhz}')
        run(commands,'whole-soc')
        run([sys.executable,'hw/ip/watchdog/formal/check.py','--output',str(out.relative_to(ROOT)/'output-formal'),'--cases','break','pad'],'output-formal')
        run([sys.executable,'hw/ip/watchdog/check_timing.py','--output',str(out.relative_to(ROOT)/'timing')],'timing')
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Frozen sources changed')
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={x.relative_to(out).as_posix():hashlib.sha256(x.read_bytes()).hexdigest()
        for x in out.rglob('*') if x.is_file() and x!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())
