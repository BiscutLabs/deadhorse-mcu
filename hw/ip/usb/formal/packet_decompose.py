"""One original packet assertion per job; no implicit environment assumptions."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from formal import validate_job

NAMES=['assert__chisel3_builtin',*(f'assert__chisel3_builtin_{i}' for i in range(5))]
PROPERTIES=['capacity','read_nonempty','integrity','held_valid','held_data','progress']
REVIEWED_HARNESS_SHA256='9b057f0f240e9c6f77f0dff5972fcd7ce4c47883d85b1d01a827e18f190ba853'
STATEMENTS={
    'in':['queued <= slots','take implies offset < queued','matchPosition implies data == watched',
          'enable && priorValid && priorIdle implies valid',
          'enable && priorValid && priorIdle implies data == priorData','service == 1 implies valid'],
    'out':['queued <= slots','appValid implies queued != 0','appValid && watching && position == 0 implies appData == watched',
           'held implies appValid','held implies appData == oldData','waitForData < 8']}

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def execute(command,log,timeout=120):
    with log.open('w') as stream:
        return subprocess.run(list(map(str,command)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def fault(model,top,role,prop):
    """Mutate a real DUT interface path, retaining the original assertion."""
    module=model['modules'][top];nets=module['netnames']
    valid='d.valid' if role=='in' else 'd.appValid'
    payload='d.data' if role=='in' else 'd.appData'
    if prop=='capacity':target,replacement=('d.appReady',['1']) if role=='in' else (valid,['1'])
    elif prop=='read_nonempty':target,replacement=valid,['1']
    elif prop in ('integrity','held_data'):target,replacement=payload,module['ports']['data']['bits']
    elif prop=='held_valid':target,replacement=valid,[module['ports']['data']['bits'][0]]
    elif prop=='progress':target,replacement=valid,['0']
    else:raise ValueError('Unknown original property')
    old=nets[target]['bits']
    if len(old)!=len(replacement) or not all(isinstance(b,int) for b in old):raise ValueError('Invalid fault pin binding')
    mapping=dict(zip(old,replacement));changed=0
    for cell in module['cells'].values():
        for pin,bits in cell['connections'].items():
            if cell['port_directions'][pin]=='input':
                new=[mapping.get(b,b) for b in bits];changed+=new!=bits;cell['connections'][pin]=new
    if not changed:raise ValueError('Fault has no consumers')
    return dict(target=target,replacement=replacement,changed_input_pins=changed)

def job(directory,model,top,assertion,engine,mode):
    directory.mkdir()
    module=model['modules'][top]
    actual={n for n,c in module['cells'].items() if c['type']=='$assert'}
    if actual!=set(NAMES):raise ValueError('Original assertion inventory changed')
    for name in actual-{assertion}:del module['cells'][name]
    source=directory/'model.json';save(source,model)
    config=directory/'job.sby'
    config.write_text('\n'.join(['[options]',f'mode {mode}','depth 48','timeout 120',
        '[engines]',engine,'[script]',f'read_json {source.name}',f'hierarchy -check -top {top}',
        'select -assert-count 1 t:$assert','opt_clean -purge','stat -width',
        '[files]',str(source.resolve())])+'\n')
    before=time.monotonic()
    process=execute(['sby','-d',directory/'job',config],directory/'run.log',180)
    statuspath=directory/'job/status'
    status=statuspath.read_text().split()[0] if statuspath.exists() else 'ERROR'
    row=dict(mode=mode,engine=engine,depth=48,cap_seconds=120,seconds=time.monotonic()-before,
        solver_status=status,returncode=process.returncode,model_sha256=digest(source),
        config_sha256=digest(config),directory=str(directory),
        result='unresolved' if status in ('TIMEOUT','UNKNOWN') else 'failed')
    if (mode=='prove' and status=='PASS') or (mode=='bmc' and status=='FAIL'):
        validate_job(directory/'job','proof' if mode=='prove' else 'negative',process.returncode,status)
        row['result']='proved' if mode=='prove' else 'fault_rejected'
    return row

def run(output,baseline,selected):
    output=output.resolve();output.relative_to(ROOT/'build')
    baseline=baseline.resolve();baseline.relative_to(ROOT/'build')
    output.mkdir(parents=True,exist_ok=False)
    prior=json.loads((baseline/'packet-controls/result.json').read_text())
    bound=prior['production_source_sha256']
    if not bound or any(digest(ROOT/p)!=h for p,h in bound.items()):raise ValueError('Stale production model')
    if digest(ROOT/'hw/ip/usb/formal/UsbBufferFormal.scala')!=REVIEWED_HARNESS_SHA256:
        raise ValueError('Original assertion semantic mapping requires renewed review')
    (output/'packet_decompose.py').write_bytes(Path(__file__).read_bytes())
    receipt=dict(status='running',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_sha256=bound,flow_sha256={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'tools/formal.py')},
        baseline_receipt=dict(path=str(baseline/'packet-controls/result.json'),sha256=digest(baseline/'packet-controls/result.json')),
        cover_evidence={r:[j for j in prior['cases'][r]['jobs'] if j['variant']=='cover'] for r in ('in','out')},
        scope='Step 2 independent split with original arbitrary-later-reset model; reset removal not applied',
        assumptions=prior['assumptions'],added_environment_assumptions=[],jobs=[],inventory=[])
    save(output/'result.json',receipt)
    for role,top in [('in','UsbInFormal'),('out','UsbOutFormal')]:
        directory=output/role;directory.mkdir()
        sources=sorted((baseline/'packet-controls'/role/'emit/correct').glob('*.sv'))
        expected=next(j for j in prior['cases'][role]['jobs'] if j['variant']=='correct')['source_sha256']
        if {p.name:digest(p) for p in sources}!=expected:raise ValueError('Stale emitted packet model')
        prepared=directory/'prepared.json';script=directory/'prepare.ys'
        script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,sources)),
            f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
            'select -assert-count 6 t:$assert',f'write_json {prepared}'])+'\n')
        execute(['yosys','-Q','-T','-s',script],directory/'prepare.log').check_returncode()
        original=json.loads(prepared.read_text());module=original['modules'][top]
        if {n for n,c in module['cells'].items() if c['type']=='$assert'}!=set(NAMES):raise ValueError('Missing/mixed original assertions')
        for name,prop,statement in zip(NAMES,PROPERTIES,STATEMENTS[role]):
            receipt['inventory'].append(dict(role=role,assertion=name,property=prop,statement=statement,model_sha256=digest(prepared)))
            if selected and role+'.'+prop not in selected:continue
            engine='smtbmc z3' if prop=='progress' else 'abc pdr'
            row=dict(role=role,property=prop,assertion=name,model_sha256=digest(prepared),assumptions='original; arbitrary later resets')
            row['positive']=job(directory/(prop+'-positive'),copy.deepcopy(original),top,name,engine,'prove')
            # A falsified original assertion is a stop, not a candidate for a stronger environment.
            if row['positive']['solver_status']=='FAIL':
                receipt['jobs'].append(row);receipt['status']='failed';save(output/'result.json',receipt)
                return receipt
            if row['positive']['result']=='proved':
                bad=copy.deepcopy(original);row['mutation']=fault(bad,top,role,prop)
                row['negative']=job(directory/(prop+'-negative'),bad,top,name,'btor btormc','bmc')
            receipt['jobs'].append(row);save(output/'result.json',receipt)
            print(role,prop,row['positive']['result'],row.get('negative',{}).get('result','not attempted'),flush=True)
    if any(digest(ROOT/p)!=h for p,h in bound.items()):raise ValueError('Source changed during split')
    receipt['status']='unresolved'
    if len(receipt['jobs'])==12 and all(r['positive']['result']=='proved' and r.get('negative',{}).get('result')=='fault_rejected' for r in receipt['jobs']):receipt['status']='pass'
    save(output/'result.json',receipt)
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--property',action='append',choices=[r+'.'+p for r in ('in','out') for p in PROPERTIES])
    args=parser.parse_args()
    try:result=run(args.output,args.baseline,args.property)
    except Exception as error:
        path=args.output/'result.json'
        if path.exists():
            result=json.loads(path.read_text());result.update(status='unresolved' if isinstance(error,subprocess.TimeoutExpired) else 'failed',error=str(error))
            save(path,result)
        else:raise
    print(result['status'].upper()+' packet assertion decomposition',flush=True)
    sys.exit(0 if result['status']=='pass' else 1)
