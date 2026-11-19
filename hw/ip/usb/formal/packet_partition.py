"""D52 one-attempt exhaustive partition of the unchanged packet assertions."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ALL = {'assert__chisel3_builtin', *(f'assert__chisel3_builtin_{n}' for n in range(5))}
DATA = {'assert__chisel3_builtin_1', 'assert__chisel3_builtin_3'}


def run(output, regmap):
    root = Path(__file__).resolve().parents[4]
    output = output.resolve(); output.relative_to(root/'build')
    regmap = regmap.resolve(); regmap.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    bound = [Path(__file__),Path('hw/ip/usb/formal/UsbBufferFormal.scala'),
        Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketSizing.scala'),
        Path('hw/ip/usb/formal/UsbFormal.scala'),Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketBuffer.scala'),
        Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbBitEnable.scala')]
    hashes = lambda: {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in bound}
    receipt = dict(status='unresolved',source_sha256=hashes(),jobs=[],
        scope='Exhaustive original assertion partition; no added assumptions; original real-model covers/faults and SIE composition remain required')
    assert DATA < ALL and (ALL-DATA)|DATA == ALL and not (ALL-DATA)&DATA
    for role, top in [('in','UsbInFormal'),('out','UsbOutFormal')]:
        directory = output/role
        directory.mkdir()
        with (directory/'emit.log').open('w') as log:
            subprocess.run([sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbFormal {regmap} {role} {directory}/emit'],
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        sources = sorted((directory/'emit/correct').glob('*.sv'))
        prepared = directory/'prepared.json'
        script = directory/'prepare.ys'
        script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,sources)),
            f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
            'select -assert-count 6 t:$assert',f'write_json {prepared}'])+'\n')
        with (directory/'prepare.log').open('w') as log:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        original = json.loads(prepared.read_text())
        cells = original['modules'][top]['cells']
        actual = {n for n,c in cells.items() if c['type']=='$assert'}
        if actual != ALL:
            raise ValueError('Original assertion identities changed; partition requires review')
        emitted_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        for kind, selected in [('control',ALL-DATA),('data',DATA)]:
            model = copy.deepcopy(original)
            for name in ALL-selected:
                del model['modules'][top]['cells'][name]
            source = directory/(kind+'.json')
            source.write_text(json.dumps(model))
            job = directory/(kind+'.sby')
            job.write_text('\n'.join(['[options]','mode prove','depth 48','timeout 120',
                '[engines]','abc pdr','[script]',f'read_json {source.name}',f'hierarchy -check -top {top}',
                f'select -assert-count {len(selected)} t:$assert','opt_clean -purge','stat -width',
                '[files]',str(source.resolve())])+'\n')
            then = time.monotonic()
            with (directory/(kind+'.log')).open('w') as log:
                process = subprocess.run(['sby','-d',str(directory/kind),str(job)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
            status = (directory/kind/'status').read_text().split()[0]
            row = dict(role=role,partition=kind,assertions=sorted(selected),solver_status=status,
                returncode=process.returncode,seconds=time.monotonic()-then,source_sha256=emitted_hashes,
                result='proved' if status=='PASS' and process.returncode==0 else 'unresolved' if status=='TIMEOUT' else 'failed')
            receipt['jobs'].append(row)
            receipt['seconds']=time.monotonic()-started
            (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(role,kind,status,flush=True)
    if hashes()!=receipt['source_sha256']:
        raise ValueError('Packet sources changed during partition attempt')
    receipt['status']='failed' if any(j['result']=='failed' for j in receipt['jobs']) else 'unresolved'
    receipt['seconds']=time.monotonic()-started
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--json',type=Path,required=True)
    args=parser.parse_args()
    receipt=run(args.output,args.json)
    print(receipt['status'].upper()+' packet assertion partitions',flush=True)
    sys.exit(0 if receipt['status']=='pass' else 1)
