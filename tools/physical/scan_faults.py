"""Persistent physical-pin stuck-at replay of the qualified two-phase capture.

No Boolean expansion node is a fault site. Unknown observations and faults in
control/shift cones are never counted as detected. Timing faults are separate.
"""
import argparse
from collections import Counter, defaultdict
import heapq
import json
from pathlib import Path
import re
import time

from scan_capture import Capture, MASK, ONE, ZERO, UNKNOWN, evaluate, groups, sha, PREFIX


class Replay:
    def __init__(self, model):
        self.m=model; self.nodes=[]; self.cache={}; self.sites=defaultdict(list)
        self.active=set(); self.out={}; self.fanout=[]
        self.outputs={n:self.branch(0 if n in model.rising else 1,n,'D') for n in sorted(model.scanned)}
        for name,node in self.outputs.items():self.out.setdefault(node,[]).append(name)
        self.fanout=[[] for _ in self.nodes]
        for i,(ast,args,value) in enumerate(self.nodes):
            for predecessor in set(args.values()):self.fanout[predecessor].append(i)
        self.values=self.baseline()

    def add(self,ast=None,args=None,value=None,site=None):
        n=len(self.nodes);self.nodes.append((ast,args or {},value))
        if site:self.sites[site].append(n)
        return n

    def branch(self,phase,name,pin):
        key=('pin',phase,name,pin)
        if key not in self.cache:
            node=self.read(phase,self.m.graph[name]['pins'][pin])
            self.cache[key]=self.add('x',{'x':node},site=(name,pin))
        return self.cache[key]

    def read(self,phase,net):
        key=('net',phase,net)
        if key in self.cache:return self.cache[key]
        if key in self.active:raise ValueError('Combinational cycle')
        self.active.add(key);m=self.m;v=None;node=None
        if net==m.controls['zero']:v=ZERO
        elif net==m.controls['one'] or net in m.entry:v=ONE
        elif net in m.initial:
            source=m.drivers[net][0]
            if phase==1 and source in m.rising:node=self.branch(0,source,'D')
            else:v=m.initial[net]
        elif net==m.osc_pad:v=ONE if phase else ZERO
        elif net in m.pad_fixed:v=ONE if m.pad_fixed[net] else ZERO
        elif net in m.stimuli:v=m.stimuli[net]
        elif net in {m.graph[n]['pins']['Q'] for n in m.manifest['clock_gates']}:v=ONE if phase else ZERO
        elif net not in m.drivers:v=UNKNOWN
        else:
            name,pin=m.drivers[net];c=m.graph[name];kind=c['type']
            if (kind,pin) in m.functions:
                ast=m.functions[kind,pin]
                def leaves(a):
                    if isinstance(a,str):return {a} if a not in ('0','1') else set()
                    return set().union(*(leaves(x) for x in a[1:]))
                args={p:self.branch(phase,name,p) for p in sorted(leaves(ast))}
                node=self.add(ast,args,site=(name,pin))
            elif kind in ('gf180mcu_fd_io__in_c','gf180mcu_fd_io__in_s') and pin=='Y':node=self.read(phase,c['pins']['PAD'])
            elif kind=='gf180mcu_fd_io__bi_24t' and pin=='Y':
                # Keep unknowns and all pad mux branches. Faults that can alter
                # IE/OE/A or their cones are excluded by the inventory below.
                args={p:self.read(phase,c['pins'][p]) for p in ('IE','OE','A','PAD')}
                node=self.add(('&','IE',('|',('&','OE','A'),('&',('!','OE'),'PAD'))),args)
            else:v=UNKNOWN
        if node is None:node=self.add(value=v)
        self.active.remove(key);self.cache[key]=node;return node

    def baseline(self):
        vals=[]
        for ast,args,v in self.nodes:vals.append(v if ast is None else evaluate(ast,lambda p:vals[args[p]]))
        return vals

    def fault(self,site,stuck):
        forced=set(self.sites.get(site,()));change={};queue=list(forced);heapq.heapify(queue);pending=set(queue)
        while queue:
            n=heapq.heappop(queue);pending.remove(n)
            ast,args,v=self.nodes[n]
            value=(ONE if stuck else ZERO) if n in forced else evaluate(ast,lambda p:change.get(args[p],self.values[args[p]]))
            if value==self.values[n]:continue
            change[n]=value
            for nxt in self.fanout[n]:
                if nxt not in pending:heapq.heappush(queue,nxt);pending.add(nxt)
        # All changed nodes have settled before observing; a later unknown
        # cannot be hidden by early termination at the first detected output.
        differing=[];unknown=[]
        for node,value in change.items():
            if node not in self.out:continue
            if value[1]!=MASK:unknown.extend(self.out[node])
            elif value[0]!=self.values[node][0]:differing.extend(self.out[node])
        return change,differing,unknown


def inventory(m):
    """Count every connected signal pin, including explicitly excluded sites."""
    roots=[]
    for name,c in m.graph.items():
        outs=set(m.controls['output_pins'][c['type']])
        if name in m.scanned:
            roots.extend(c['pins'][p] for p in c['pins'] if p not in outs|{'D','VDD','VSS','VNW','VPW'})
        elif name in m.manifest['excluded'] or name in m.manifest['clock_gates'] or not c['type'].startswith(PREFIX):
            roots.extend(v for p,v in c['pins'].items() if p not in outs|{'VDD','VSS','VNW','VPW','vdd','vss','DVDD','DVSS'})
    protected=set();todo=list(roots)
    while todo:
        net=todo.pop()
        if net not in m.drivers:continue
        name,pin=m.drivers[net];c=m.graph[name]
        if name in protected:continue
        # Sequential state is a boundary; its physical pins are separately
        # excluded. No false requirement that functional D drive every control.
        if name in m.scanned or name in m.manifest['excluded']:continue
        protected.add(name)
        if (c['type'],pin) in m.functions:
            outs=set(m.controls['output_pins'][c['type']])
            todo.extend(v for p,v in c['pins'].items() if p not in outs|{'VDD','VSS','VNW','VPW'})
    rows=[];supplies=sum(len(c['power']) for c in m.graph.values())
    for name,c in sorted(m.graph.items()):
        for pin,net in sorted(c['pins'].items()):
            if pin in ('VDD','VSS','VNW','VPW','vdd','vss','DVDD','DVSS'):
                raise ValueError('Supply unexpectedly stored among signal pins')
            reason=None
            if not c['type'].startswith(PREFIX):reason='pad_macro_or_artwork'
            elif name in m.manifest['excluded']:reason='unscanned_access_state'
            elif name in m.manifest['clock_gates']:reason='clock_gate'
            elif name in m.scanned and pin!='D':reason='sequential_shift_or_control_pin'
            elif name in protected:reason='control_shift_or_macro_isolation_cone'
            elif net is None:reason='unconnected_pin'
            elif name not in m.scanned and not any(k==c['type'] for k,p in m.functions):raise ValueError('Unclassified cell '+name)
            rows.append(dict(cell=name,pin=pin,excluded=reason))
    return rows,dict(supply_pins_outside_digital_SA_model=supplies,protected_cells=len(protected))


def load(a):
    receipt=json.loads((a.capture/'result.json').read_text())
    if receipt['status']!='pass_capture_model_only':raise ValueError('Unqualified capture')
    for p,d in receipt['inputs'].items():
        if sha(p)!=d:raise ValueError('Stale capture premise '+p)
    ins=json.loads((a.insert/'result.json').read_text())
    for name in ('before.json','after.json','chains.json'):
        if sha(a.insert/name)!=ins['artifacts'][name]:raise ValueError('Changed inserted graph')
    for p in (a.insert/'result.json',a.core,a.manifest,a.liberty):
        if sha(p) not in receipt['inputs'].values():raise ValueError('Unbound capture input')
    return Capture(json.loads((a.insert/'after.json').read_text()),json.loads((a.insert/'before.json').read_text()),
        json.loads(a.manifest.read_text()),ins['controls'],json.loads(a.core.read_text())['modules']['DeadhorseSoc'],dict(groups(a.liberty.read_text(),'cell')))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','insert','manifest','core','liberty','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    m=load(a);m.verify_entry();r=Replay(m);expected,_=m.capture()
    if any(r.values[node]!=expected[n] or expected[n][1]!=MASK for n,node in r.outputs.items()):raise ValueError('Fault-free oracle mismatch')
    sites,counts=inventory(m)
    (a.output/'inventory.json').write_text(json.dumps(sites))
    eligible=[(x['cell'],x['pin']) for x in sites if x['excluded'] is None]
    # Both polarities, input branches, output stems, rising/falling endpoints
    # and deterministic distributed sites versus the independent full replay.
    probes=eligible[::max(1,len(eligible)//12)][:12]+[(n,'D') for n in sorted(m.falling)]
    tested=[]
    for site in probes:
        for stuck in (0,1):
            changes,_,_=r.fault(site,stuck);oracle,_=m.capture((*site,stuck))
            if any(changes.get(node,r.values[node])!=oracle[n] for n,node in r.outputs.items()):raise ValueError('Persistent fault oracle mismatch '+str(site))
            tested.append([*site,stuck])
    stats=Counter();witnesses=[]
    with (a.output/'faults.jsonl').open('w') as stream:
        for i,row in enumerate(sites):
            site=(row['cell'],row['pin'])
            for stuck in (0,1):
                witness=None
                if row['excluded']:status='excluded'
                else:
                    changes,observed,unknown=r.fault(site,stuck)
                    status='unresolved_unknown' if unknown else 'detected' if observed else 'unresolved_not_detected'
                    if status=='detected':
                        name=observed[0];node=r.outputs[name];bits=changes[node][0]^r.values[node][0]
                        witness=dict(cell=name,pattern=(bits&-bits).bit_length()-1)
                stats[status]+=1
                stream.write(json.dumps(dict(**row,stuck=stuck,status=status,witness=witness))+'\n')
            if i%10000==0:print('physical pins',i,'/',len(sites),dict(stats),flush=True)
    from scan_bench import Network
    net=Network(m);used=net.used(net.outputs())
    legal={row['net'] for row in net.inputs if row['kind']=='pad' and row['node'] in used}
    patterns=dict(state={n:v[0] for n,v in m.initial.items()},pads={n:m.stimuli[n][0] for n in sorted(legal)},
        fixed_fixture=m.pad_fixed,patterns=64,seed=37,
        protocol='Drive only listed free pads and fixed fixture; OSC toggles for capture, SE/test reset follow test-access protocol. Other pads are undriven.')
    (a.output/'patterns.json').write_text(json.dumps(patterns))
    result=dict(status='measured_physical_SA_replay',seconds=time.monotonic()-start,patterns=64,counts=dict(stats),inventory=counts,
        physical_faults=2*len(sites),untestable=0,transition_faults='unsupported/unqualified',oracle_probes=tested,
        inputs={str(q):sha(q) for q in (Path(__file__),a.capture/'result.json',a.insert/'result.json',a.insert/'after.json')},
        artifacts={q.name:sha(q) for q in a.output.iterdir() if q.is_file()},
        scope='Seeded patterns, physical-pin capture replay; not ATPG closure, timing qualification or a coverage-target waiver')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(dict(stats),result['seconds'])


if __name__=='__main__':main()
