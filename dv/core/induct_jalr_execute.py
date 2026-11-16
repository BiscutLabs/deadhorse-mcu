"""Small exact production transition induction for registered execute ADD."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell
from jalr_receipts import verify_hashes
from compose_jalr_ownership import conjunction, implies
from check_jalr_request import BINDINGS, EXEC, request_witness
from qualify_owner_valid import inject

NAMES=('state_q','request_q_kind','request_q_aluOp','request_q_a','request_q_b','response_q_adder')


def constant(value,width):return list(reversed(format(value,'0'+str(width)+'b')))


def selected_state(m):
    result={}
    for name in NAMES:
        bits=m['netnames'][EXEC+name]['bits']
        cells=[c for c in m['cells'].values() if c['connections'].get('Q')==bits]
        if len(cells)!=1:raise ValueError('Nonunique production state: '+name)
        c=cells[0];p=c['parameters'];conn=c['connections']
        if (c['type']!='$aldff' or int(p['CLK_POLARITY'],2)!=1 or int(p['ALOAD_POLARITY'],2)!=1 or
            conn['CLK']!=m['netnames'][BINDINGS['clock']]['bits'] or
            conn['ALOAD']!=m['netnames'][BINDINGS['reset']]['bits'] or any(b!='0' for b in conn['AD'])):
            raise ValueError('Unsupported production clock/reset: '+name)
        result[name]=copy.deepcopy(c)
    return result


def cut_cone(source,outputs):
    drivers={};cuts={b for p in source['ports'].values() if p['direction']=='input' for b in p['bits']}
    for name,c in source['cells'].items():
        state=any(s in c['type'].lower() for s in ('dff','latch','mem')) or c['type'] in ('$anyseq','$anyconst','$initstate')
        for p,d in c['port_directions'].items():
            if d=='output':
                for b in c['connections'][p]:
                    if state:cuts.add(b)
                    else:drivers.setdefault(b,[]).append(name)
    selected={};seen=set();pending=[b for bs in outputs.values() for b in bs];used=set()
    while pending:
        b=pending.pop()
        if not isinstance(b,int) or b in seen:continue
        seen.add(b)
        if b in cuts:used.add(b);continue
        names=drivers.get(b,[])
        if len(names)!=1:raise ValueError('Ambiguous/nonstate boundary driver')
        n=names[0];c=source['cells'][n]
        if c['type'] in ('$assert','$assume','$check','$cover'):raise ValueError('Property in data cone')
        selected[n]=copy.deepcopy(c)
        pending.extend(b for p,d in c['port_directions'].items() if d=='input' for b in c['connections'][p])
    ports={f'free_{b}':dict(direction='input',bits=[b]) for b in sorted(used)}
    ports.update({n:dict(direction='output',bits=b) for n,b in outputs.items()})
    return dict(attributes={'top':'1'},ports=ports,cells=selected,netnames={})


def invariant(m,s):
    eq=lambda a,v:gate(m,'$eq',a,constant(v,len(a)))
    st=s['state_q'];kind=s['request_q_kind']
    mul=gate(m,'$or',eq(st,2),eq(st,3))
    div=gate(m,'$or',eq(st,4),gate(m,'$or',eq(st,5),eq(st,6)))
    active=conjunction(m,eq(st,7),eq(kind,0),eq(s['request_q_aluOp'],0))
    bits=list(range(next_bit(m),next_bit(m)+32))
    m['cells']['__sum_'+str(bits[0])]=dict(type='$add',attributes={},
        parameters=dict(A_WIDTH='100000',B_WIDTH='100000',Y_WIDTH='100000',A_SIGNED='0',B_SIGNED='0'),
        port_directions=dict(A='input',B='input',Y='output'),
        connections=dict(A=s['request_q_a'],B=s['request_q_b'],Y=bits))
    return conjunction(m,implies(m,eq(st,1),eq(kind,0)),implies(m,mul,eq(kind,1)),
                       implies(m,div,kind[1:2]),implies(m,active,gate(m,'$eq',s['response_q_adder'],bits)))


def build(source,role,negative):
    state=selected_state(source)
    current={n:c['connections']['Q'] for n,c in state.items()}
    nxt={n:c['connections']['D'] for n,c in state.items()}
    outs={**{'current_'+n:b for n,b in current.items()},**{'next_'+n:b for n,b in nxt.items()},
          'originalHolds':source['netnames']['__request_executeAddHolds']['bits']}
    m=cut_cone(source,outs)
    if role=='base':
        reset={n:c['connections']['AD'] for n,c in state.items()}
        if negative:reset['state_q']=constant(7,3);reset['response_q_adder']=constant(2,32)
        holds=invariant(m,reset)
    elif role=='step':
        if negative:
            nxt=copy.deepcopy(nxt);nxt['response_q_adder'][1]=gate(m,'$not',[nxt['response_q_adder'][1]])[0]
        holds=implies(m,invariant(m,current),invariant(m,nxt))
    elif role=='final':
        goal=gate(m,'$not',outs['originalHolds']) if negative else outs['originalHolds']
        holds=implies(m,invariant(m,current),goal)
    else:raise ValueError('Unknown induction role')
    m['ports']['holds']=dict(direction='output',bits=holds)
    m['netnames']={n:dict(bits=p['bits'],attributes={}) for n,p in m['ports'].items()}
    return dict(modules={TOP:m}),{n:c['parameters'] for n,c in state.items()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',default='build/t13/jalr-execute-only')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='local execute ADD only; JALR operand alignment and ISA unresolved',results={});protected={}
    try:
        raw=base/'result.json';prior=json.loads(raw.read_text());protected=dict(prior['input_sha256'])
        for p in (raw,Path(__file__),Path(__file__).with_name('compose_jalr_ownership.py')):protected[str(p)]=digest(p)
        verify_hashes(protected)
        sourcepath=base/'execute-prove/model.json'
        if str(sourcepath) not in protected:raise ValueError('Unauthenticated production model')
        model=json.loads(sourcepath.read_text());source=model['modules'][TOP]
        receipt.update(timeout_seconds=120,depth=144,assumptions=prior['assumptions'],
            invariant='ALU/MUL/DIV compute states have their corresponding saved kind; ADD response equals saved A+B modulo32',
            abstraction='Other production state and primary inputs are universally free in exact combinational D cones; no assumptions',
            preserved_global_result=prior['results']['execute-prove'])
        for role in ('base','step','final'):
            for negative in (False,True):
                name=role+('-negative' if negative else '');job=output_dir(out/name)
                design,states=build(source,role,negative);receipt['state_parameters']=states
                path=job/'model.json';path.write_text(json.dumps(design));script=job/'check.ys';witness=job/'counterexample.json'
                script.write_text(f'read_json {path}\nhierarchy -top {TOP}\nopt_clean\ncheck -assert\nsat '+
                    ('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
                protected.update({str(p):digest(p) for p in (path,script)})
                verify_hashes(protected)
                result=run(['yosys','-Q','-T','-s',script],job,'check',timeout=120)
                expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
                if expected not in result.stdout or negative and not witness.exists():raise ValueError(name+' failed')
                receipt['results'][name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
                if negative:protected[str(witness)]=digest(witness)
                print('PASS '+name,flush=True)
        for role in ('execute-cover','execute-fault'):
            design=copy.deepcopy(model);m=design['modules'][TOP]
            net=lambda n:m['netnames']['__request_'+n]['bits']
            if role=='execute-cover':
                m['cells']['__request_assert']=property_cell('cover',conjunction(m,net('executeCorner'),net('executeAddHolds')));mode='cover'
            else:
                receipt['fault_driver']=inject(m,m['netnames'][BINDINGS['executeTarget']]['bits'][1],net('executeActive'));mode='bmc'
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statusfile=job/'work/status';status=statusfile.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('PASS',0) if mode=='cover' else ('FAIL',2)):raise RuntimeError(role+': '+status)
            protected[str(statusfile)]=digest(statusfile)
            witnesses=[]
            for trace in (job/'work').glob('engine_*/trace*.vcd'):
                try:
                    event=request_witness(trace.read_text(),role)
                    witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
                except ValueError:continue
            if not witnesses:raise ValueError('No exact active '+role+' witness')
            receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        verify_hashes(protected);receipt['status']='pass (local ADD induction; alignment and ISA unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
