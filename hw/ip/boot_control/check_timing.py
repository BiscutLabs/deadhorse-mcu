"""Fresh mapped boot control timing at conservative main-9MHz; no CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.timing.check import measure

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for name in ('hw/lib','hw/ip/boot_control/src/main','tools/timing') for p in (ROOT/name).rglob('*')
           if p.is_file() and p.suffix in ('.scala','.py','.tcl')]
    paths += [Path(__file__),ROOT/'hw/ip/boot_control/boot_control.regmap.yaml',ROOT/'build/t28/boot_control/boot_control_regs.json',
              ROOT/'build.sbt',ROOT/'tools/env/lock.json',ROOT/'phys/gf180-ws-1x1/block-timing.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Mapped pre-layout; conservative9MHz for AON operation; physical wires/reset/hold qualification separate')
    try:
        cmd=[sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.boot_control.EmitBootControl build/t28/boot_control/boot_control_regs.json {out}/emit']
        receipt['command']=cmd
        with (out/'emit.log').open('w') as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        receipt['measurement']=measure('BootControl',[str(p) for p in sorted((out/'emit').glob('*.sv'))],
            'clk',out/'timing',operating_point='main-9mhz',reset_fanout=True)
        if hashes()!=receipt['source_sha256']:raise ValueError('Timing sources changed')
        receipt['status']=receipt['measurement']['status']
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();sys.exit(main(a.output))
