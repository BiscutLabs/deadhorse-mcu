"""Partition the authenticated existing alignment conjunction, without assumptions."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, property_cell
from jalr_receipts import verify_hashes
from assertion_partitions import assertions, partition, validate_union

LABELS=('response-valid','alu-kind','add-operation','first-cycle','source-operand','immediate-operand')
PREFIX='__request_'


def split_alignment(original):
    if assertions(original)!=['__request_assert']: raise ValueError('Unexpected original assertion inventory')
    model=copy.deepcopy(original);m=model['modules'][TOP];cells=m['cells'];nets=m['netnames']
    prop=cells['__request_assert']
    if prop['type']!='$assert' or prop['connections']['EN']!=['1']:
        raise ValueError('Unexpected assertion enable/form')
    def net(n): return nets[PREFIX+n]['bits']
    def driver(bits):
        matches=[(n,c) for n,c in cells.items() if c['connections'].get('Y')==bits]
        if len(matches)!=1: raise ValueError('Nonunique expression driver')
        return matches[0]
    def boolean(bits,kind):
        n,c=driver(bits)
        if not n.startswith(PREFIX) or c['type']!=kind or len(c['connections']['A'])!=1 or len(bits)!=1:
            raise ValueError('Unexpected Boolean expression')
        if 'B' in c['connections'] and len(c['connections']['B'])!=1: raise ValueError('Wide Boolean operand')
        if 'B' in c['connections'] and int(c['parameters']['B_WIDTH'],2)!=1: raise ValueError('Wide Boolean parameter')
        if any(int(c['parameters'].get(p,'0'),2)!=1 for p in ('A_WIDTH','Y_WIDTH')):
            raise ValueError('Unexpected Boolean width')
        return c['connections']
    root=boolean(prop['connections']['A'],'$or')
    if boolean(root['A'],'$not')['A']!=net('capture'): raise ValueError('Capture guard changed')
    leaves=[]
    def visit(bits):
        if bits in (net('responseValid'),net('requestFirst')):
            leaves.append(bits);return
        n,c=driver(bits)
        if n.startswith(PREFIX) and c['type']=='$and':
            ports=boolean(bits,'$and');visit(ports['A']);visit(ports['B'])
        else: leaves.append(bits)
    visit(root['B'])
    if len(leaves)!=6 or len({tuple(b) for b in leaves})!=6: raise ValueError('Missing/duplicate alignment conjunct')
    expected=copy.deepcopy(leaves)
    expected[0]=net('responseValid');expected[3]=net('requestFirst')
    if leaves!=expected: raise ValueError('Response/phase conjunct changed')
    for index,name in ((1,'requestKind'),(2,'requestOp')):
        n,c=driver(leaves[index])
        if not n.startswith(PREFIX) or c['type']!='$logic_not' or c['connections']['A']!=net(name):
            raise ValueError('Kind/op conjunct changed')
        if int(c['parameters']['A_WIDTH'],2)!=len(net(name)) or int(c['parameters']['Y_WIDTH'],2)!=1:
            raise ValueError('Kind/op width changed')
    insn=net('idInstruction');offset=insn[20:32]+[insn[31]]*20
    for index,a,b in ((4,net('requestA'),net('normalizedSource')),(5,net('requestB'),offset)):
        n,c=driver(leaves[index])
        if not n.startswith(PREFIX) or c['type']!='$eq' or c['connections']['A']!=a or c['connections']['B']!=b:
            raise ValueError('Operand conjunct changed')
        if any(int(c['parameters'][p],2)!=v for p,v in
               [('A_WIDTH',32),('B_WIDTH',32),('Y_WIDTH',1),('A_SIGNED',0),('B_SIGNED',0)]):
            raise ValueError('Operand comparison parameters changed')
    del cells['__request_assert']
    groups=[];predicates=[]
    for label,leaf in zip(LABELS,leaves):
        pred=gate(m,'$or',root['A'],leaf);predicates.append(pred)
        name='__alignment_'+label;cells[name]=property_cell('assert',pred,prop['connections']['EN'])
        groups.append([name])
    validate_union(assertions(model),groups)
    # No preexisting expression, input, state, assumption or net may change.
    restored=copy.deepcopy(model);r=restored['modules'][TOP]
    for n in set(r['cells'])-set(original['modules'][TOP]['cells']): del r['cells'][n]
    r['cells']['__request_assert']=copy.deepcopy(prop)
    if restored!=original: raise ValueError('Partition preparation changed original model')
    return model,groups,dict(capture=net('capture'),leaves=leaves,original=prop['connections']['A'],predicates=predicates)


def qualification(model,info,omit_last=False):
    m=copy.deepcopy(model['modules'][TOP]);preds=info['predicates'][:-1] if omit_last else info['predicates']
    combined=preds[0]
    for pred in preds[1:]: combined=gate(m,'$and',combined,pred)
    same=gate(m,'$eq',info['original'],combined)
    cuts={b for bits in [info['capture'],*info['leaves']] for b in bits}
    selected={};seen=set();pending=list(same)
    while pending:
        bit=pending.pop()
        if not isinstance(bit,int) or bit in cuts or bit in seen: continue
        seen.add(bit)
        matches=[(n,c) for n,c in m['cells'].items() if c['connections'].get('Y')==[bit]]
        if len(matches)!=1: raise ValueError('Qualification driver ambiguity')
        n,c=matches[0]
        if c['type'] not in ('$and','$or','$not','$eq') or any(len(v)!=1 for v in c['connections'].values()):
            raise ValueError('Qualification crossed free Boolean boundary')
        selected[n]=copy.deepcopy(c)
        pending.extend(b for p,d in c['port_directions'].items() if d=='input' for b in c['connections'][p])
    ports={f'input_{b}':dict(direction='input',bits=[b]) for b in sorted(cuts)}
    ports['same']=dict(direction='output',bits=same)
    return dict(modules={TOP:dict(attributes={'top':'1'},ports=ports,cells=selected,
        netnames={n:dict(bits=p['bits'],attributes={}) for n,p in ports.items()})})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='alignment diagnostic only; covers/faults/ADD/ISA unresolved',results={})
    record=out/'result.json';protected={}
    try:
        raw=base/'result.json';prior=json.loads(raw.read_text());verify_hashes(prior['input_sha256'])
        protected={**prior['input_sha256'],str(raw):digest(raw),str(Path(__file__)):digest(Path(__file__))}
        for p in (Path(__file__).with_name('assertion_partitions.py'),Path(__file__).with_name('jalr_receipts.py')):
            protected[str(p)]=digest(p)
        original=json.loads((base/'alignment-prove/model.json').read_text())
        model,groups,info=split_alignment(original)
        complete=out/'complete.json';complete.write_text(json.dumps(model))
        protected[str(complete)]=digest(complete)
        timeout=prior['timeout_seconds'];depth=prior['depth']
        if timeout!=120 or depth!=144: raise ValueError('Unexpected baseline proof limits')
        receipt.update(timeout_seconds=timeout,depth=depth,assumptions=prior['assumptions'],groups=groups,
            conditions=dict(zip(LABELS,info['leaves'])),qualification={})
        for name,bad in (('qualification',False),('omitted-conjunct-negative',True)):
            job=output_dir(out/name);path=job/'model.json';path.write_text(json.dumps(qualification(model,info,bad)))
            ys=job/'check.ys';witness=job/'counterexample.json'
            ys.write_text(f'read_json {path}\ncheck -assert\nsat '+('' if bad else '-verify ')+
                f'-prove same 1 -show-inputs -show-outputs -dump_json {witness}\n')
            protected.update({str(p):digest(p) for p in (path,ys)})
            result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
            expected='SAT proof finished - model found: FAIL!' if bad else 'SAT proof finished - no model found: SUCCESS!'
            if expected not in result.stdout or bad and not witness.is_file(): raise ValueError('Partition qualification failed')
            receipt['qualification'][name]=dict(status='rejected' if bad else 'PASS',seconds=result.elapsed_seconds)
            if bad: receipt['qualification'][name]['witness_sha256']=digest(witness)
        for label,group in zip(LABELS,groups):
            job=output_dir(out/label);path=job/'model.json';path.write_text(json.dumps(partition(model,group)))
            config=job/'check.sby';config.write_text(f'[options]\nmode prove\ndepth {depth}\nmulticlock on\ntimeout {timeout}\n'
                f'[engines]\nabc pdr\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
            status=(job/'work/status').read_text().split()[0]
            receipt['results'][label]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds,assertions=group)
            verify_hashes(protected);record.write_text(json.dumps(receipt,indent=2)+'\n')
            if (status,result.returncode)!=('PASS',0): raise RuntimeError('Alignment conjunct '+label+': '+status)
            print('PASS alignment conjunct: '+label,flush=True)
        validate_union(assertions(model),[r['assertions'] for r in receipt['results'].values()])
        receipt['status']='positive partitions pass; covers/faults/ADD/ISA unresolved'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
