"""Authenticate a freshly elaborated USB hierarchy against certified source RTL."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from state_equiv import prepare


def bind_source(hierarchy,target,certificate,out,reference_top='Usb',fault_pin='pullupEnable'):
    out.mkdir(exist_ok=False)
    sources=[ROOT/n.removeprefix('/work/') for n in certificate['sources']]
    for p,value in zip(sources,certificate['sources'].values()):
        assert hashlib.sha256(p.read_bytes()).hexdigest()==value,('USB source changed',p)
    def run(lines,name,negative=False):
        script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n')
        p=subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,text=True,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
        (out/(name+'.log')).write_text(p.stdout)
        if negative:
            assert p.returncode!=0 and 'proof did fail' in p.stdout,'Binding fault not rejected by proof'
        else:assert p.returncode==0,(name,p.stdout[-1000:])
    run([f'read_slang --keep-hierarchy -DSYNTHESIS --top {reference_top} '+' '.join(map(str,sources)),
        f'hierarchy -check -top {reference_top}','proc','chformal -remove','memory_collect',f'write_json {out}/reference-hier.json'],'reference')
    gold=json.loads((out/'reference-hier.json').read_text());m=gold['modules'][reference_top]
    replacements={}
    if reference_top=='Usb':
        owner=m['ports'].pop('owner');assert owner['direction']=='input' and len(owner['bits'])==3
        replacements=dict(zip(owner['bits'],['1','0','0']))
    for c in m['cells'].values():c['connections']={p:[replacements.get(b,b) for b in bs] for p,bs in c['connections'].items()}
    for n in [*m['ports'].values(),*m['netnames'].values()]:n['bits']=[replacements.get(b,b) for b in n['bits']]
    (out/'reference-bound.json').write_text(json.dumps(gold))
    for role,path,top in [('gold',out/'reference-bound.json',reference_top),('candidate',hierarchy,target)]:
        run([f'read_json {path}',f'hierarchy -top {top}',f'rename {top} Usb' if top!='Usb' else 'check -assert',
            'flatten','memory_map','opt -full','clean -purge',f'write_json {out}/{role}.json'],role)
    def prove(candidate,directory,negative=False,names=None):
        directory.mkdir(exist_ok=False)
        a,b,evidence=prepare(out/'gold.json',candidate,'Usb',directory,names or {})
        # Every state D, clock/reset/control pin and output is compared; equal
        # named state is the inductive relation, not a new environment premise.
        run([f'read_json {a}','rename Usb gold',f'read_json {b}','rename Usb gate',
            'miter -equiv -flatten gold gate miter','hierarchy -top miter','opt_expr','opt_clean',
            'sat -verify -prove trigger 0 -show-inputs -show-outputs'],directory.name,negative)
        return evidence
    evidence=prove(out/'candidate.json',out/'proof')
    bad=json.loads((out/'candidate.json').read_text());module=bad['modules']['Usb']
    pin=fault_pin;old=module['ports'][pin]['bits'];assert len(old)==1
    bit=max(b for n in module['netnames'].values() for b in n['bits'] if isinstance(b,int))+1
    module['cells']['binding_fault']=dict(type='$not',parameters={'A_SIGNED':0,'A_WIDTH':1,'Y_WIDTH':1},attributes={},
        port_directions={'A':'input','Y':'output'},connections={'A':old[:],'Y':[bit]})
    module['ports'][pin]['bits']=[bit]
    module['netnames'][pin]['bits']=[bit]
    module['netnames']['binding_original_output']=dict(hide_name=0,bits=old[:],attributes={})
    badpath=out/'fault.json';badpath.write_text(json.dumps(bad))
    prove(badpath,out/'negative',True,{pin:'binding_original_output'})
    receipt=dict(status='proved',method='Unbounded named-state one-step induction',correspondence=evidence,
        specialization='owner=1 only; other inputs independent' if reference_top=='Usb' else 'All inputs independent',
        negative_control=f'Actual candidate {pin} output inverted; proof rejected',
        source_sha256=certificate['sources'],hierarchy_sha256=hashlib.sha256(hierarchy.read_bytes()).hexdigest())
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
