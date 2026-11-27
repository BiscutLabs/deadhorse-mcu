"""Lift cone suggestions to legal full-chip vectors and replay physical faults."""
import argparse
from array import array
from collections import Counter
import json
from pathlib import Path
import random
import re
import time

from scan_faults import load, Replay, inventory
from scan_bench import Network
from scan_capture import MASK, ZERO, ONE, UNKNOWN, sha
from scan_serial import replay as serial_replay


def qualify_partition(cones,capture):
    result=json.loads((cones/'result.json').read_text())
    if result.get('status')!='exact_output_partition':raise ValueError('Unqualified cone partition')
    if result.get('capture_sha256')!=sha(capture/'result.json'):raise ValueError('Cone partition belongs to a different capture model')
    return result


def qualify(r):
    m=r.m;checked=[]
    # This real mux fault exposes an uncontrolled macro value. It must remain
    # unknown rather than being counted as a detected binary mismatch.
    probes=[('_t37_output_clamp_128','S',0),('i_chip_core.soc._140228_','I',0)]
    for name,pin,value in probes:
        changes,diff,unknown=r.fault((name,pin),value);oracle,_=m.capture((name,pin,value))
        if any(changes.get(node,r.values[node])!=oracle[n] for n,node in r.outputs.items()):raise ValueError('Targeted oracle mismatch')
        checked.append(dict(cell=name,pin=pin,stuck=value,unknown_observations=len(unknown)))
    if not checked[0]['unknown_observations']:raise ValueError('Unknown negative control ineffective')
    site=tuple(probes[1][:2]);nodes=r.sites[site]
    full=r.fault(site,0)[0];r.sites[site]=nodes[:1];wrong=r.fault(site,0)[0];r.sites[site]=nodes
    if not any(full.get(n,r.values[n])!=wrong.get(n,r.values[n]) for n in r.outputs.values()):raise ValueError('One-phase mutant not rejected')
    # Exhaustive two-input reconvergence example: a stem feeds both XOR arms.
    # Both arms must settle before observation (otherwise a false pulse counts).
    q=Replay.__new__(Replay);q.nodes=[];q.sites={};q.outputs={};q.out={};q.cache={}
    q.nodes=[(None,{},(0b1010,MASK)),('x',{'x':0},None),('x',{'x':1},None),('x',{'x':1},None),(('^','a','b'),{'a':2,'b':3},None)]
    q.sites={('stem','Z'):[1]};q.fanout=[[1],[2,3],[4],[4],[]];q.out={4:['capture']};q.outputs={'capture':4};q.values=q.baseline()
    for stuck in (0,1):
        changes,diff,unknown=q.fault(('stem','Z'),stuck)
        if diff or unknown or changes.get(4,q.values[4])!=ZERO:raise ValueError('Reconvergent fault produced false detection')
    return dict(targeted_oracles=checked,one_phase_only_mutant='rejected',reconvergent_cancellation='pass')


def suggestions(cones,attempts):
    model=json.loads((cones/'result.json').read_text());rows={x['name']:x for x in model['cones']}
    packed=[];seen=set();count=0;completed=[]
    for attempt in attempts:
        receipt=json.loads((attempt/'result.json').read_text())
        if receipt['status']!='bounded_suggestions_only' or sha(cones/'result.json') not in receipt['inputs'].values():raise ValueError('Wrong suggestion receipt')
        for row in receipt['cones']:
            if row['status']!='suggestions_generated':continue
            name=row['name']
            if name in seen:raise ValueError('Repeated cone attempt')
            seen.add(name);completed.append(name)
            ports=cones/name/'ports.json'
            if sha(ports)!=rows[name]['files']['ports.json']:raise ValueError('Changed cone input mapping')
            inputs=json.loads(ports.read_text())['inputs']
            file=attempt/row.get('directory',name)/'patterns.test'
            if sha(file)!=row['patterns_sha256']:raise ValueError('Changed patterns')
            for line in file.read_text().splitlines():
                if not line.strip() or line.startswith('*'):continue
                match=re.fullmatch(r'\d+:\s*([01]*)',line.strip())
                if not match or len(match[1])!=len(inputs):raise ValueError('Unknown pattern format or input count')
                assignment={(p['kind'],p['net']):int(b) for p,b in zip(inputs,match[1])}
                # Merge only compatible partial assignments; each original
                # suggested vector survives intact in at least one full vector.
                target=next((v for v in packed if all(k not in v or v[k]==b for k,b in assignment.items())),None)
                if target is None:target={};packed.append(target)
                target.update(assignment);count+=1
    return packed,dict(cones_completed=len(completed),suggestions=count,compatible_full_vectors=len(packed),
        cones_unresolved=len(rows)-len(completed))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','insert','manifest','core','liberty','cones','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--suggestions',type=Path,nargs='+',required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    qualify_partition(a.cones,a.capture)
    m=load(a);m.verify_entry();r=Replay(m);proof=qualify(r)
    net=Network(m);used=net.used(net.outputs());legal={p['net'] for p in net.inputs if p['kind']=='pad' and p['node'] in used}
    packed,generation=suggestions(a.cones,a.suggestions)
    sites,counts=inventory(m);observations=sorted(m.scanned);obs_index={n:i for i,n in enumerate(observations)}
    # 0=not detected,1=detected,2=unknown,3=excluded. No untestable inference.
    statuses=bytearray(2*len(sites));patterns=array('i',[-1])*len(statuses);endpoints=array('i',[-1])*len(statuses)
    batches=[];rng=random.Random(371);commands=[]
    chains=json.loads((a.insert/'chains.json').read_text())
    def batch(index,number):
        nonlocal r
        r=Replay(m);correct,_=m.capture()
        if any(r.values[node]!=correct[n] or correct[n][1]!=MASK for n,node in r.outputs.items()):raise ValueError('Lifted vector differs from capture oracle')
        serial=serial_replay(m.graph,chains,37,
            desired_values={n:m.initial[m.graph[n]['pins']['Q']][0] for n in m.scanned},
            captured_values={n:v[0] for n,v in correct.items()})
        if index==0:
            try:serial_replay(m.graph,chains,37,mutate=True)
            except ValueError:proof['serial_chain_bypass']='rejected'
            else:raise ValueError('Broken chain not detected')
        file=a.output/f'vectors{index:04d}.json'
        file.write_text(json.dumps(dict(patterns=number,state={n:v[0] for n,v in m.initial.items()},
            pads={n:m.stimuli[n][0] for n in sorted(legal)},fixed_fixture=m.pad_fixed)))
        started=time.monotonic();added=0
        for i,row in enumerate(sites):
            site=row['cell'],row['pin']
            for stuck in (0,1):
                f=2*i+stuck
                if row['excluded']:statuses[f]=3;continue
                if statuses[f]==1:continue
                changes,diff,unknown=r.fault(site,stuck)
                if unknown:statuses[f]=2;continue
                if diff:
                    n=diff[0];node=r.outputs[n];bits=(changes[node][0]^r.values[node][0])&((1<<number)-1)
                    if bits:
                        statuses[f]=1;patterns[f]=index*64+(bits&-bits).bit_length()-1;endpoints[f]=obs_index[n];added+=1
        batches.append(dict(index=index,patterns=number,new_detections=added,seconds=time.monotonic()-started,file=file.name,sha256=sha(file),serial=serial))
        print('replayed batch',index,'patterns',number,'new physical detections',added,flush=True)
    batch(0,64)
    for offset in range(0,len(packed),64):
        selected=packed[offset:offset+64]
        m.initial={n:(rng.getrandbits(64),MASK) for n in m.initial}
        m.stimuli={n:(rng.getrandbits(64),MASK) for n in m.stimuli}
        for bit,assignment in enumerate(selected):
            for (kind,n),value in assignment.items():
                if kind=='pad' and n not in legal:raise ValueError('Suggestion drives a nonfixture pad')
                bank=m.initial if kind=='state' else m.stimuli
                old=bank[n][0];bank[n]=((old&~(1<<bit))|(value<<bit),MASK)
        batch(1+offset//64,len(selected))
    totals=Counter();labels=['unresolved_not_detected','detected','unresolved_unknown','excluded']
    with (a.output/'faults.jsonl').open('w') as stream:
        for i,row in enumerate(sites):
            for stuck in (0,1):
                f=2*i+stuck;label=labels[statuses[f]];totals[label]+=1
                witness=None if statuses[f]!=1 else dict(pattern=patterns[f],cell=observations[endpoints[f]])
                stream.write(json.dumps(dict(**row,stuck=stuck,status=label,witness=witness))+'\n')
    result=dict(status='measured_physical_SA_campaign',seconds=time.monotonic()-start,counts=dict(totals),physical_faults=len(statuses),
        inventory=counts,generation=generation,batches=batches,qualification=proof,untestable=0,transition='unsupported/unqualified',
        source_sha256={str(q):sha(q) for q in (Path(__file__),Path(__file__).with_name('scan_faults.py'),Path(__file__).with_name('scan_capture.py'),Path(__file__).with_name('scan_bench.py'),Path(__file__).with_name('scan_serial.py'))},
        inputs={str(q):sha(q) for q in (a.capture/'result.json',a.insert/'result.json',a.insert/'after.json',a.cones/'result.json',*(p/'result.json' for p in a.suggestions))},
        artifacts={'faults.jsonl':sha(a.output/'faults.jsonl')},
        scope='Unplaced inserted physical-pin SA faults; complete denominator including explicit exclusions/unresolved. No transition, electrical or numerical coverage-target acceptance.')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(dict(totals),result['seconds'])


if __name__=='__main__':main()
