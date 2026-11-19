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
