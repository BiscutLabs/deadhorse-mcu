"""Export the qualified two-phase capture function for ATPG pattern suggestions.

Expanded gates are NOT physical fault sites. Tool coverage on this network must
not be reported as chip coverage; persistent physical-cell replay is required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from scan_capture import Capture, PREFIX, groups, sha


class Network:
    def __init__(self,model):
        self.model=model;self.nodes=[('GND',()),('VDD',())];self.unique={};self.inputs=[]
        self.leaves={};self.cache={};self.active=set()
        for net in sorted(model.initial):self.leaf('state',net)
        for net in sorted(set(model.stimuli)-set(model.pad_fixed)):self.leaf('pad',net)
    def leaf(self,kind,name):
        key=kind,name
        if key not in self.leaves:
            node=len(self.nodes);self.nodes.append(('INPUT' if kind!='unknown' else 'UNKNOWN',()))
            self.leaves[key]=node
            if kind!='unknown':self.inputs.append(dict(node=node,kind=kind,net=name))
        return self.leaves[key]
    def make(self,kind,*args):
        if kind=='NOT':
            a=args[0]
            if a<2:return 1-a
            if self.nodes[a][0]=='NOT':return self.nodes[a][1][0]
        else:
            a,b=sorted(args);args=(a,b)
            if kind=='AND':
                if a==0:return 0
                if a==1:return b
                if a==b:return a
            elif kind=='OR':
                if a==0:return b
                if a==1:return 1
                if a==b:return a
            elif kind=='XOR':
                if a==0:return b
                if a==1:return self.make('NOT',b)
                if a==b:return 0
            else:raise ValueError('Unknown operation')
        key=kind,args
        if key not in self.unique:
            self.unique[key]=len(self.nodes);self.nodes.append(key)
        return self.unique[key]
    def tree(self,ast,leaf):
        if isinstance(ast,str):return int(ast) if ast in ('0','1') else leaf(ast)
        if ast[0]=='!':return self.make('NOT',self.tree(ast[1],leaf))
        return self.make({'&':'AND','|':'OR','^':'XOR'}[ast[0]],self.tree(ast[1],leaf),self.tree(ast[2],leaf))
    def read(self,phase,net):
        key=phase,net
        if key in self.cache:return self.cache[key]
        if key in self.active:raise ValueError('Capture network cycle')
        self.active.add(key);m=self.model
        if net==m.controls['zero']:v=0
        elif net==m.controls['one'] or net in m.entry:v=1
        elif net in m.initial:
            source=m.drivers[net][0]
            v=self.read(0,m.graph[source]['pins']['D']) if phase==1 and source in m.rising else self.leaf('state',net)
        elif net==m.osc_pad:v=phase
        elif net in m.pad_fixed:v=m.pad_fixed[net]
        elif net in m.stimuli:v=self.leaf('pad',net)
        elif net in {m.graph[n]['pins']['Q'] for n in m.manifest['clock_gates']}:v=phase
        elif net not in m.drivers:v=self.leaf('unknown',f'{phase}:{net}')
        else:
            name,pin=m.drivers[net];c=m.graph[name];p=c['pins'];kind=c['type']
            read=lambda p:self.read(phase,c['pins'][p])
            if (kind,pin) in m.functions:v=self.tree(m.functions[kind,pin],read)
            elif kind in ('gf180mcu_fd_io__in_c','gf180mcu_fd_io__in_s') and pin=='Y':v=read('PAD')
            elif kind=='gf180mcu_fd_io__bi_24t' and pin=='Y':
                ie,oe=read('IE'),read('OE')
                if ie==0:v=0
                elif ie!=1 or oe not in (0,1):raise ValueError('Receiver not statically qualified')
                else:v=read('A') if oe else read('PAD')
            # An uncontrolled analog/memory value is not assumed stable
            # between capture phases. Sampled state retains its phase0 node.
            else:v=self.leaf('unknown',f'{phase}:{name}/{pin}')
        self.active.remove(key);self.cache[key]=v;return v
    def outputs(self):
        return [dict(cell=n,node=self.read(0 if n in self.model.rising else 1,self.model.graph[n]['pins']['D']))
            for n in sorted(self.model.scanned)]
    def used(self,outputs):
        seen=set();todo=[o['node'] for o in outputs]
        while todo:
            n=todo.pop()
            if n in seen:continue
            seen.add(n);todo.extend(self.nodes[n][1])
        if any(self.nodes[n][0]=='UNKNOWN' for n in seen):raise ValueError('Uncontrollable source in capture support')
        return seen
    def crosscheck(self,outputs):
        # Independent bit-vector gate evaluator in scan_capture vs this
        # simplified export graph on the exact same64 full-chip assignments.
        model=self.model;vals={0:0,1:(1<<64)-1}
        for row in self.inputs:
            vals[row['node']]=(model.initial if row['kind']=='state' else model.stimuli)[row['net']][0]
        used=self.used(outputs)
        for i,(kind,args) in enumerate(self.nodes):
            if i in vals or i not in used:continue
            a=vals[args[0]]
            if kind=='NOT':v=~a&((1<<64)-1)
            else:
                b=vals[args[1]];v=(a&b) if kind=='AND' else (a|b) if kind=='OR' else a^b
            vals[i]=v
        expected,_=model.capture()
        if any(vals[o['node']]!=expected[o['cell']][0] for o in outputs):raise ValueError('Export differs from actual capture replay')
        return used


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--insert',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--core',type=Path,required=True)
    p.add_argument('--liberty',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    capture=json.loads((a.capture/'result.json').read_text());insert=json.loads((a.insert/'result.json').read_text())
    if capture['status']!='pass_capture_model_only':raise ValueError('Unqualified capture model')
    for q,digest in capture['inputs'].items():
        if sha(q)!=digest:raise ValueError('Stale capture evidence: '+q)
    for name in ('before.json','after.json'):
        if sha(a.insert/name)!=insert['artifacts'][name]:raise ValueError('Stale physical graph')
    for q in (a.insert/'result.json',a.manifest,a.core,a.liberty):
        if sha(q) not in capture['inputs'].values():raise ValueError('Wrong capture input')
    m=Capture(json.loads((a.insert/'after.json').read_text()),json.loads((a.insert/'before.json').read_text()),
        json.loads(a.manifest.read_text()),insert['controls'],json.loads(a.core.read_text())['modules']['DeadhorseSoc'],
        dict(groups(a.liberty.read_text(),'cell')))
    m.verify_entry();network=Network(m);outputs=network.outputs();used=network.crosscheck(outputs)
    # Never tell a tester to drive an output-owned or unused pad. Unused scan
    # state remains assignable; unused pad variables are removed altogether.
    network.inputs=[r for r in network.inputs if r['kind']=='state' or r['node'] in used]
    lines=[f'INPUT(n{r["node"]})' for r in network.inputs]
    # Preserve each FF observation even if several have the same expression.
    for i,row in enumerate(outputs):lines.extend([f'OUTPUT(q{i})',f'q{i} = BUF(n{row["node"]})'])
    for n in sorted(used):
        kind,args=network.nodes[n]
        if kind=='INPUT':continue
        lines.append(f'n{n} = {kind}('+', '.join('n'+str(i) for i in args)+')')
    bench=a.output/'capture.bench';bench.write_text('\n'.join(lines)+'\n')
    (a.output/'ports.json').write_text(json.dumps(dict(inputs=network.inputs,outputs=outputs)))
    result=dict(status='pass_pattern_suggestion_export_only',seconds=time.monotonic()-start,
        capture_sha256=sha(a.capture/'result.json'),source_sha256=sha(__file__),
        artifacts={p.name:sha(p) for p in a.output.iterdir() if p.is_file()},
        inputs=len(network.inputs),observed_scan_state=len(outputs),expanded_nodes=len(used),
        warning='Expanded-gate ATPG coverage is not physical coverage. Persistent original-cell pin replay and complete fault-class inventory remain mandatory.')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS two-phase suggestion export:',result['inputs'],'inputs;',len(outputs),'observations;',len(used),'expanded nodes')


if __name__=='__main__':main()
