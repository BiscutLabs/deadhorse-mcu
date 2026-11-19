"""Bind existential sparse-memory witnesses to actual production RAM words.

No assumption is added. Proving this simulation relation is mandatory before
using a universally quantified sparse-model result for production acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'tools'))
from formal import validate_job

TOP='UsbPacketMemoryRefinement'

def bind(design):
    module=design['modules'][TOP]
    nets=module['netnames']; cells=module['cells']
    words=[]
    for bank in range(9):
        for index in range(8):
            name=f'real_0.banks_{bank}_ext.Memory[{index}]'
            bits=nets[name]['bits']
            assert len(bits)==8 and all(isinstance(b,int) for b in bits)
            drivers=[c for c in cells.values() if c['type'] in ('$dff','$dffe') and c['connections']['Q']==bits]
            assert len(drivers)==1, ('ambiguous RAM identity',name)
            words.append(bits)
    assert len({b for word in words for b in word})==576, 'Aliased production RAM words'
    next_bit=max(b for n in nets.values() for b in n['bits'] if isinstance(b,int))+1
    def allocate(width):
        nonlocal next_bit
        result=list(range(next_bit,next_bit+width));next_bit+=width;return result
    for witness,address in [('witnessRead','readQuery'),('witnessCache','cacheAddress'),('witnessTracked','trackAddress')]:
        result_bits=module['ports'].pop(witness)['bits']
        query=nets[address]['bits'];assert len(query)==7
        # Full 128-entry mux tree: out-of-range slots return zero, exactly as
        # the production bank selector. Every actual word remains unconstrained.
        layer=words+[['0']*8 for _ in range(56)]
        for level in range(7):
            new=[]
            for pair in range(len(layer)//2):
                output=result_bits if level==6 else allocate(8)
                cells[f'$witness${witness}${level}${pair}']={
                    'hide_name':1,'type':'$mux','parameters':{'WIDTH':format(8,'032b')},'attributes':{},
                    'port_directions':{'A':'input','B':'input','S':'input','Y':'output'},
                    'connections':{'A':layer[2*pair],'B':layer[2*pair+1],'S':[query[level]],'Y':output}}
                new.append(output)
            layer=new
    return design

def run(output,emit):
    output.mkdir(parents=True,exist_ok=False)
    receipt={'status':'running','binding':'actual RAM Q muxes; no added assumptions','jobs':[]}
    sources_to_bind=[Path(__file__),Path('hw/ip/usb/formal/UsbSparsePacketMemory.scala'),
        Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketBuffer.scala'),*sorted(emit.rglob('*.sv'))]
    def hashes():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources_to_bind}
    receipt['source_sha256']=hashes()
    for variant in ('cover','corrupt','correct'):
        directory=output/variant;directory.mkdir()
        sources=sorted((emit/variant).glob('*.sv'));assert sources
        prepared=directory/'prepared.json';bound=directory/'bound.json'
        script=directory/'prepare.ys'
        script.write_text('read_slang --top '+TOP+' '+' '.join(map(str,sources))+'\n'+
            f'prep -top {TOP} -flatten\nmemory_map\nopt\nwrite_json {prepared}\n')
        with (directory/'prepare.log').open('w') as log:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        bound.write_text(json.dumps(bind(json.loads(prepared.read_text()))))
        mode='cover' if variant=='cover' else 'bmc' if variant=='corrupt' else 'prove'
        job=directory/'job.sby'
        job.write_text('\n'.join(['[options]',f'mode {mode}','depth 48','timeout 120','','[engines]',
            'abc pdr' if mode=='prove' else 'btor btormc','','[script]',f'read_json {bound.name}',
            f'prep -top {TOP}',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
            'select -assert-count '+('2 t:$cover' if mode=='cover' else '3 t:$assert'),
            '','[files]',str(bound),'']))
        start=time.monotonic()
        with (directory/'job.log').open('w') as log:
            process=subprocess.run(['sby','-d',str(directory/'job'),str(job)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
        statusfile=directory/'job/status'
        status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
        receipt['jobs'].append(dict(variant=variant,status=status,seconds=time.monotonic()-start,
            returncode=process.returncode,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}))
        validate_job(directory/'job','cover' if mode=='cover' else 'negative' if variant=='corrupt' else 'proof',process.returncode,status)
        print(variant,status,flush=True)
    expected={'cover':'PASS','corrupt':'FAIL','correct':'PASS'}
    receipt['status']='pass' if all(j['status']==expected[j['variant']] for j in receipt['jobs']) else 'unresolved'
    if hashes()!=receipt['source_sha256']:
        receipt.update(status='failed',error='Sources changed during refinement')
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--emit',type=Path,required=True)
    args=parser.parse_args()
    for path in (args.output,args.emit):path.resolve().relative_to(Path('build').resolve())
    result=run(args.output,args.emit)
    raise SystemExit(0 if result['status']=='pass' else 1)
