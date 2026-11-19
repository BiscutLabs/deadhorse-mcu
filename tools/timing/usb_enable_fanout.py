"""Phase-preserving physical replication of the USB cadence enable FF."""
import copy
import json
from pathlib import Path
import subprocess

PREFIX = 'usb_enable_replica_'
TAG = 'usb_enable_original'
TYPE = 'gf180mcu_fd_sc_mcu7t5v0__dffrnq_1'


def identities(module):
    """Prove the induction premises on actual mapped pins, through buffers."""
    parents = {c['connections']['Z'][0]:c['connections']['I'][0]
               for c in module['cells'].values()
               if c['type'].startswith('gf180mcu_fd_sc_mcu7t5v0__buf_')}
    def resolve(bit):
        seen=set()
        while bit in parents:
            if bit in seen: raise ValueError('Replica buffer cycle')
            seen.add(bit);bit=parents[bit]
        return bit
    result={}
    for name,c in module['cells'].items():
        if not name.startswith(PREFIX):continue
        original=c.get('attributes',{}).get(TAG)
        if original not in module['cells']:raise ValueError('Unbound USB enable replica')
        old=module['cells'][original]
        if c['type']!=old['type'] or c['type']!=TYPE or c.get('parameters')!=old.get('parameters'):
            raise ValueError('Replica reset value/type differs')
        if set(c['connections'])!={'D','Q','CLK','RN'}:raise ValueError('Unexpected replica pins')
        for p in ('D','CLK','RN'):
            if len(c['connections'][p])!=1 or resolve(c['connections'][p][0])!=resolve(old['connections'][p][0]):
                raise ValueError('Replica phase/clock/reset differs: '+name+'/'+p)
        if c['connections']['Q']==old['connections']['Q']:raise ValueError('Replica aliases original driver')
        result[c['connections']['Q'][0]]=old['connections']['Q'][0]
    return result


def prove_pair(liberty, output):
    """Unbounded induction for actual library FF type with shared D/CLK/RN."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    base={'attributes':{},'ports':{'clk':{'direction':'input','bits':[2]},'reset_n':{'direction':'input','bits':[3]},
          'data':{'direction':'input','bits':[4]},'equal':{'direction':'output','bits':[7]}},'netnames':{},'cells':{}}
    for name,q in [('original',5),('replica',6)]:
        base['cells'][name]={'type':TYPE,'parameters':{},'attributes':{},
            'port_directions':{'D':'input','CLK':'input','RN':'input','Q':'output'},
            'connections':{'D':[4],'CLK':[2],'RN':[3],'Q':[q]}}
    base['cells']['$equal_pair']={'type':'$eq','parameters':{'A_WIDTH':'1','B_WIDTH':'1','Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},
        'attributes':{},'port_directions':{'A':'input','B':'input','Y':'output'},'connections':{'A':[5],'B':[6],'Y':[7]}}
    results={}
    for variant in ('correct','wrong-reset','wrong-data'):
        m=copy.deepcopy(base)
        if variant=='wrong-reset':m['cells']['replica']['connections']['RN']=['1']
        if variant=='wrong-data':m['cells']['replica']['connections']['D']=['0']
        p=output/(variant+'.json');p.write_text(json.dumps({'modules':{'ReplicaPair':m}}))
        script=output/(variant+'.ys')
        script.write_text('\n'.join([f'read_liberty -ignore_miss_func {liberty}',f'read_json {p}',
            'hierarchy -check -top ReplicaPair','flatten','proc','async2sync','opt','check -assert','techmap','opt',
            'sat -seq 3 -tempinduct -set-def-inputs -set-at 1 reset_n 0 -prove equal 1 -verify'])+'\n')
        run=subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
        (output/(variant+'.log')).write_text(run.stdout+run.stderr)
        good=(run.returncode==0 and 'SUCCESS!' in run.stdout) if variant=='correct' else (run.returncode==1 and 'proof did fail' in run.stdout+run.stderr)
        if not good:raise ValueError('Enable replica proof/control failed: '+variant)
        results[variant]='proved' if variant=='correct' else 'fault_rejected'
    (output/'result.json').write_text(json.dumps({'status':'pass','jobs':results,
        'scope':'Shared actual D/CLK/RN and zero asynchronous reset; arbitrary shared input changes. Initial common reset required by production cadence contract. Digital sampled async2sync model; identical pins preserve asynchronous assertion semantics, but physical reset skew and inter-edge analog behavior are not proved.'},indent=2)+'\n')
    return results


def replicate(module, top, limit=1):
    if top not in ('UsbEngine','Usb','UsbSieTiming'):return copy.deepcopy(module),{}
    prefix='engine.' if top=='Usb' else ''
    aliases=[module['netnames'][prefix+n]['bits'] for n in ('cadence.enable','_cadence_enable') if prefix+n in module['netnames']]
    if not aliases or any(len(b)!=1 for b in aliases) or len({b[0] for b in aliases})!=1:
        raise ValueError('Missing or ambiguous original cadence enable')
    q=aliases[0][0]
    drivers=[(n,c) for n,c in module['cells'].items() if c['connections'].get('Q')==[q]]
    if len(drivers)!=1 or drivers[0][1]['type']!=TYPE:raise ValueError('Unexpected cadence enable flop')
    original,cell=drivers[0]
    def loads(bit):
        return [(n,p,i) for n,c in module['cells'].items() for p,d in c['port_directions'].items() if d=='input'
                for i,b in enumerate(c['connections'][p]) if b==bit]
    # ABC commonly puts a single buffer/inverter at the FF output. Copy that
    # prefix with the FF so the first real branching load group is replicated.
    branch=q;chain=[];seen=set()
    while len(loads(branch))==1:
        name,p,index=loads(branch)[0];c=module['cells'][name]
        if not c['type'].startswith(('gf180mcu_fd_sc_mcu7t5v0__buf_','gf180mcu_fd_sc_mcu7t5v0__inv_')):break
        outputs=[(pin,bs) for pin,bs in c['connections'].items() if c['port_directions'][pin]=='output']
        if p!='I' or index!=0 or len(outputs)!=1 or len(outputs[0][1])!=1:raise ValueError('Unsupported enable prefix')
        if name in seen:raise ValueError('Enable prefix cycle')
        seen.add(name);chain.append((name,outputs[0][0]));branch=outputs[0][1][0]
    sinks=loads(branch)
    if any(p in ('CLK','RN','SN') for _,p,_ in sinks):raise ValueError('Enable drives clock/reset')
    result=copy.deepcopy(module)
    all_bits=[b for c in module['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)]
    all_bits += [b for v in list(module['ports'].values())+list(module['netnames'].values()) for b in v['bits'] if isinstance(b,int)]
    next_bit=1+max(all_bits)
    added=[];added_logic=[];equal_bits={}
    # Each first-branch load cone is a group. The original drives one group;
    # each other group gets a true parallel FF, including small wrapper trees.
    for start in range(limit,len(sinks),limit):
        name=PREFIX+str(len(added))
        if name in result['cells']:raise ValueError('Replica name collision')
        c=copy.deepcopy(cell);c['connections']['Q']=[next_bit];c.setdefault('attributes',{})[TAG]=original
        result['cells'][name]=c
        result['netnames'][name+'_q']={'hide_name':0,'bits':[next_bit],'attributes':{}}
        leaf=next_bit;equal_bits[leaf]=q;next_bit+=1
        for old,pin in chain:
            copied='usb_enable_load_'+str(len(added_logic))
            if copied in result['cells']:raise ValueError('Enable prefix name collision')
            gate=copy.deepcopy(module['cells'][old]);gate['connections']['I']=[leaf]
            old_output=gate['connections'][pin][0]
            gate['connections'][pin]=[next_bit]
            result['cells'][copied]=gate
            equal_bits[next_bit]=old_output
            added_logic.append((copied,old));leaf=next_bit;next_bit+=1
        for n,p,i in sinks[start:start+limit]:result['cells'][n]['connections'][p][i]=leaf
        added.append(name)
    relations=identities(result)
    # Removing replicas and substituting their proved equal Q reproduces every
    # original connection, including original clock/reset pins and all ports.
    recovered=copy.deepcopy(result)
    for copied,old in added_logic:
        gate=copy.deepcopy(recovered['cells'][copied])
        gate['connections']={p:[equal_bits.get(b,b) for b in bs] for p,bs in gate['connections'].items()}
        if gate!=module['cells'][old]:raise ValueError('Enable prefix logic changed')
        del recovered['cells'][copied]
    for name in added:del recovered['cells'][name];del recovered['netnames'][name+'_q']
    for c in recovered['cells'].values():
        c['connections']={p:[equal_bits.get(b,b) for b in bs] for p,bs in c['connections'].items()}
    if recovered!=module:raise ValueError('Replica pass changed unrelated logic')
    return result,{'original':original,'replicas':added,'copied_prefixes':added_logic,'limit':limit,'loads':len(sinks),
                   'verification':'Exact substitution recovers original netlist; actual pin identity plus unbounded library-FF equality proof'}


def size_enable_buffers(module, liberty, output):
    """Size weak branches of the proved enable tree after fanout insertion.

    No nets, register phases, reset pins or non-enable cells change. Restrict
    the traversal to library buffers; do not cross functional logic.
    """
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    result=copy.deepcopy(module)
    relations=identities(module)
    roots=set(relations)|set(relations.values())
    buffer_prefix='gf180mcu_fd_sc_mcu7t5v0__buf_'
    reachable=set(roots);branches=[]
    pending={n:c for n,c in module['cells'].items() if c['type'].startswith(buffer_prefix)}
    while True:
        found=[n for n,c in pending.items() if c['connections']['I'][0] in reachable]
        if not found:break
        for n in found:
            c=pending.pop(n);reachable.add(c['connections']['Z'][0]);branches.append(n)
    loads={}
    for c in module['cells'].values():
        for p,direction in c['port_directions'].items():
            if direction=='input':
                for b in c['connections'][p]:loads[b]=loads.get(b,0)+1
    changed=[]
    for n in branches:
        c=result['cells'][n]
        if c['type']==buffer_prefix+'1' and loads.get(c['connections']['Z'][0],0)>1:
            c['type']=buffer_prefix+'4';changed.append(n)
    # Recover original cell types exactly: everything else must be unchanged.
    recovered=copy.deepcopy(result)
    for n in changed:recovered['cells'][n]['type']=module['cells'][n]['type']
    if recovered!=module:raise ValueError('Enable sizing altered connectivity')
    m={'ports':{'i':{'direction':'input','bits':[2]},'equal':{'direction':'output','bits':[5]}},'cells':{},'netnames':{},'attributes':{}}
    for n,size,q in [('before',1,3),('after',4,4)]:
        m['cells'][n]={'type':buffer_prefix+str(size),'parameters':{},'attributes':{},
            'port_directions':{'I':'input','Z':'output'},'connections':{'I':[2],'Z':[q]}}
    m['cells']['eq']={'type':'$eq','parameters':{'A_WIDTH':'1','B_WIDTH':'1','Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},
        'attributes':{},'port_directions':{'A':'input','B':'input','Y':'output'},'connections':{'A':[3],'B':[4],'Y':[5]}}
    (output/'pair.json').write_text(json.dumps({'modules':{'BufferPair':m}}))
    script=output/'pair.ys'
    script.write_text('\n'.join([f'read_liberty -ignore_miss_func {liberty}',f'read_json {output}/pair.json',
        'hierarchy -check -top BufferPair','flatten','proc','opt_clean','check -assert','techmap','opt',
        'sat -set-def-inputs -prove equal 1 -verify'])+'\n')
    r=subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
    (output/'pair.log').write_text(r.stdout+r.stderr)
    if r.returncode or 'SUCCESS!' not in r.stdout:raise ValueError('Enable buffer sizing equivalence failed')
    # A polarity-changing replacement must fail the same equality check.
    bad=copy.deepcopy(m);bad['cells']['after']['type']='gf180mcu_fd_sc_mcu7t5v0__inv_1'
    bad['cells']['after']['connections']={'I':[2],'ZN':[4]}
    bad['cells']['after']['port_directions']={'I':'input','ZN':'output'}
    (output/'wrong-polarity.json').write_text(json.dumps({'modules':{'BufferPair':bad}}))
    fault=output/'wrong-polarity.ys';fault.write_text(script.read_text().replace('pair.json','wrong-polarity.json'))
    r=subprocess.run(['yosys','-Q','-T','-s',str(fault)],capture_output=True,text=True,timeout=120)
    (output/'wrong-polarity.log').write_text(r.stdout+r.stderr)
    if r.returncode!=1 or 'proof did fail' not in r.stdout+r.stderr:raise ValueError('Enable sizing polarity fault escaped')
    receipt={'cells':changed,'from':buffer_prefix+'1','to':buffer_prefix+'4',
        'proof':'Exact type restoration recovers input netlist; actual Liberty combinational functions proved equal for every input',
        'scope':'Mapped pre-layout sizing only; no placement/parasitic claim'}
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return result,receipt
