"""T19 acceptance inventory. Unresolved obligations fail closed; no timing waivers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def inputs():
    paths = [ROOT/'build.sbt', ROOT/'tools/env/lock.json']
    for name in ('hw/ip/usb','hw/vendor/usb','hw/top/stubs','hw/lib/src/main/scala','hw/regmap','tools/timing'):
        paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def run(output):
    output = Path(output).resolve(); output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()): raise ValueError('Use fresh output; preserve earlier failures')
    output.mkdir(parents=True)
    before = inputs(); started = time.monotonic()
    receipt = dict(status='running', task='T19', commands=[], timing={}, source_sha256=before,
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        unresolved=['Packet-buffer integrity/stall/service formal closure remains unresolved; monolithic proofs timed out',
                    'Complete wrapper clock-domain timing has not yet been qualified'],
        qualification_limits=['No physical pad/ESD/VBUS, clock tolerance or board electrical qualification',
                              'Standalone peripheral; whole-chip gateway and clock-controller integration remain separate'])
    def command(name, argv, child=None):
        then=time.monotonic()
        with (output/(name+'.log')).open('w') as log:
            process=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        row=dict(name=name,command=list(map(str,argv)),returncode=process.returncode,
                 seconds=time.monotonic()-then)
        receipt['commands'].append(row)
        if child:
            detail=json.loads(child.read_text()) if child.exists() else dict(status='missing')
            row['child_status']=detail.get('status');return detail
        return process.returncode
    try:
        py=sys.executable
        command('provenance',[py,'hw/vendor/usb/prepare.py'])
        command('timing-runner-tests',[py,'-m','unittest','tools.timing.test_fanout','tools.timing.test_timing'])
        command('regmap',[py,'hw/regmap/regmap.py','hw/ip/usb/usb.regmap.yaml','--out',output/'regmap'])
        # The independently runnable Scala suites use this deterministic generated fixture.
        command('test-regmap',[py,'hw/regmap/regmap.py','hw/ip/usb/usb.regmap.yaml','--out','build/t19/regmap'])
        command('simulation',[py,'tools/sbt.py','testOnly deadhorse.usb.*'])
        command('emit',[py,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsb {output}/emit {output}/regmap/usb_regs.json'])
        command('formal',[py,'hw/ip/usb/formal/check.py','--json',output/'regmap/usb_regs.json',
            '--output',output/'formal'],output/'formal/result.json')
        command('byte-cdc',[py,'hw/lib/formal/cdc_proof.py','--width','8','--depth','2','--output',output/'cdc'],output/'cdc/result.json')
        for name,top in [('control','UsbControl'),('in','UsbInBuffer'),('out','UsbOutBuffer'),
                         ('resume','UsbResume'),('engine','UsbEngine'),('registers','UsbRegisters')]:
            sources=sorted((output/'emit'/name).glob('*.sv'))
            if name=='engine': sources += [ROOT/'build/vendor/usb/rtl'/p for p in ('sie.v','phy_rx.v','phy_tx.v')]
            if not sources: raise ValueError('Missing emission '+name)
            argv=[py,'tools/timing/check.py','--top',top,'--clock','clk','--output',output/'timing'/name]
            if name!='registers': argv+=['--operating-point','usb-48mhz']
            for source in sources: argv+=['--source',source]
            receipt['timing'][name]=command('timing-'+name,argv,output/'timing'/name/'result.json')
        if inputs()!=before: raise RuntimeError('Source inputs changed during acceptance')
        passed=not receipt['unresolved'] and all(r['returncode']==0 and r.get('child_status','pass')=='pass' for r in receipt['commands'])
        receipt['status']='pass' if passed else 'failed'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['seconds']=time.monotonic()-started
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper()+' T19 USB; inspect result.json for every unresolved obligation',flush=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();sys.exit(0 if run(ROOT/args.output)['status']=='pass' else 1)
