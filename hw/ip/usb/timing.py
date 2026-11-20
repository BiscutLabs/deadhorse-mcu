"""Measure emitted USB production components without waivers or CDC STA claims."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
BLOCKS=dict(control='UsbControl',**{'in':'UsbInBuffer','out':'UsbOutBuffer'},
            resume='UsbResume',engine='UsbEngine',registers='UsbRegisters')


def run(emitted,output,blocks=None):
    emitted=Path(emitted).resolve();emitted.relative_to(ROOT/'build')
    output=Path(output).resolve();output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()):raise ValueError('Use fresh output')
    output.mkdir(parents=True)
    receipt=dict(status='running',blocks={},scope='Single-clock production components; not integrated wrapper-domain timing')
    for name in blocks or BLOCKS:
        sources=sorted((emitted/name).glob('*.sv'))
        if name=='engine':sources += [ROOT/'build/vendor/usb/rtl'/f for f in ('sie.v','phy_rx.v','phy_tx.v')]
        if not sources:raise ValueError('Missing production emission '+name)
        command=[sys.executable,'tools/timing/check.py','--top',BLOCKS[name],'--clock','clk','--output',str(output/name)]
        if name!='registers':command+=['--operating-point','usb-48mhz']
        for source in sources:command+=['--source',str(source)]
        result=subprocess.run(command,cwd=ROOT)
        path=output/name/'result.json'
        detail=json.loads(path.read_text()) if path.exists() else dict(status='missing')
        receipt['blocks'][name]=dict(returncode=result.returncode,result=detail)
    receipt['status']='pass' if all(v['returncode']==0 and v['result']['status']=='pass' for v in receipt['blocks'].values()) else 'failed'
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--block',action='append',choices=BLOCKS)
    args=parser.parse_args();sys.exit(0 if run(ROOT/args.emitted,ROOT/args.output,args.block)['status']=='pass' else 1)
