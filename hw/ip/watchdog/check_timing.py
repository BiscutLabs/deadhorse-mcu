"""Fresh watchdog and changed pad binding GF180 block screen at the existing main-9MHz operating point."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.timing.check import measure

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--blocks',nargs='+',choices=('watchdog','pwm','pinmux'),default=['watchdog','pwm','pinmux'])
    a=p.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for name in ('hw/lib','hw/ip/watchdog/src/main','hw/ip/timers/src/main','hw/ip/pinmux/src/main','tools/timing') for p in (ROOT/name).rglob('*')
           if p.is_file() and p.suffix in ('.scala','.py','.tcl')]
    paths += [Path(__file__),ROOT/'hw/ip/timers/timers.regmap.yaml',ROOT/'build/t21/timers/timers_regs.json',
              ROOT/'hw/ip/watchdog/watchdog.regmap.yaml',ROOT/'build/t26/watchdog/watchdog_regs.json',
              ROOT/'hw/ip/pinmux/pinmux.regmap.yaml',ROOT/'build/t24/pinmux/pinmux_regs.json',
              ROOT/'build.sbt',ROOT/'tools/env/lock.json',ROOT/'phys/gf180-ws-1x1/block-timing.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Mapped pre-layout, no real wire delay; 9MHz conservative for the 8/9MHz profiles; physical qualification separate')
    try:
        receipt['blocks']={}
        for block,top in [('watchdog','Watchdog'),('pwm','GeneralTimers'),('pinmux','Pinmux')]:
            if block not in a.blocks:continue
            directory=out/block;directory.mkdir()
            command=[sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.watchdog.EmitWatchdogBindings {block} {directory}/emit']
            with (directory/'emit.log').open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            result=measure(top,[str(p) for p in sorted((directory/'emit').glob('*.sv'))],'clk',directory/'timing',
                operating_point='main-9mhz',reset_fanout=block in ('watchdog','pwm'))
            receipt['blocks'][block]=dict(command=command,measurement=result)
        if hashes()!=receipt['source_sha256']:raise ValueError('Timing sources changed')
        receipt['status']='pass' if all(b['measurement']['status']=='pass' for b in receipt['blocks'].values()) else 'failed'

    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':sys.exit(main())
