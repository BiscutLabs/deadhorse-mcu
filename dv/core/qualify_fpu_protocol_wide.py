"""Exact concrete-to-abstract FPU protocol trace inclusion with split payloads.

This checks an explicit simulation relation, not arithmetic equivalence. Every
concrete selected-state D cone and every abstract transition/output equation is
retained. Other concrete state and inputs are universally free. Existential
abstract choices are witnessed by concrete current/next payload and valid.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
from common import ROOT, local, output_dir, run
from candidate import parameters
from jalr_invariant import digest, gate, next_bit
from jalr_receipts import verify_hashes
from compose_jalr_ownership import conjunction, implies
from induct_jalr_execute import cut_cone, constant

TOP='FpuProtocolInclusion'
CONCRETE=('state','ready','valid','busy','response_result','response_flags')
ABSTRACT=('pending','valid','response_result','response_flags','cleared')


def states(module,names):
    result={}
    for name in names:
        bits=module['netnames'][name]['bits']
        candidates=[c for c in module['cells'].values() if c['connections'].get('Q')==bits]
        if len(candidates)!=1:raise ValueError('Nonunique state: '+name)
        c=candidates[0];conn=c['connections'];p=c['parameters']
        if (c['type']!='$aldff' or conn['CLK']!=module['ports']['clock']['bits'] or
            conn['ALOAD']!=module['ports']['reset']['bits'] or
            int(p['CLK_POLARITY'],2)!=1 or int(p['ALOAD_POLARITY'],2)!=1 or
            len(conn['Q'])!=int(p['WIDTH'],2) or any(b not in ('0','1') for b in conn['AD'])):
            raise ValueError('Unsupported clock/reset state: '+name)
        result[name]=copy.deepcopy(c)
    return result


def eq(m,a,b):return gate(m,'$eq',a,b)


def invariant(m,s):
    idle=eq(m,s['state'],constant(0,4));hold=eq(m,s['state'],constant(13,4))
    legal=gate(m,'$le',s['state'],constant(13,4))
    return conjunction(m,legal,eq(m,s['ready'],idle),eq(m,s['busy'],gate(m,'$not',idle)),eq(m,s['valid'],hold))


def response(s):return s['response_flags']+s['response_result']


def instantiate(module,model,state_values,inputs):
    state=states(model,ABSTRACT)
    all_bits={b for c in model['cells'].values() for v in c['connections'].values() for b in v if isinstance(b,int)}
    all_bits|={b for p in model['ports'].values() for b in p['bits'] if isinstance(b,int)}
    fresh=next_bit(module)
    mapping={b:fresh+i for i,b in enumerate(sorted(all_bits))}
    if set(inputs)!={n for n,p in model['ports'].items() if p['direction']=='input'}:
        raise ValueError('Abstract input inventory changed')
    for name,values in inputs.items():
        bits=model['ports'][name]['bits']
        if len(bits)!=len(values):raise ValueError('Abstract input width changed')
        mapping.update(zip(bits,values))
    for name,values in state_values.items():
        bits=state[name]['connections']['Q']
        if len(bits)!=len(values):raise ValueError('Abstract state width changed')
        mapping.update(zip(bits,values))
    remap=lambda bits:[mapping.get(b,b) for b in bits]
    for name,c in model['cells'].items():
        if c['type']=='$aldff':continue
        if any(k in c['type'].lower() for k in ('dff','latch','mem')) or c['type'] in ('$assume','$assert','$check','$cover'):
            raise ValueError('Unexpected abstract state/property')
        c=copy.deepcopy(c);c['connections']={p:remap(bs) for p,bs in c['connections'].items()}
        module['cells']['__abstract_'+name]=c
    return {n:remap(p['bits']) for n,p in model['ports'].items()}, {n:remap(c['connections']['D']) for n,c in state.items()}


def build(concrete,abstract,role,negative=False):
    cs=states(concrete,CONCRETE);asts=states(abstract,ABSTRACT)
    current={n:c['connections']['Q'] for n,c in cs.items()}
    nxt={n:c['connections']['D'] for n,c in cs.items()}
    outputs={**{'current_'+n:v for n,v in current.items()},**{'next_'+n:v for n,v in nxt.items()},
        **{n:p['bits'] for n,p in concrete['ports'].items()}}
    m=cut_cone(concrete,outputs)
    creset={n:c['connections']['AD'] for n,c in cs.items()}
    areset={n:c['connections']['AD'] for n,c in asts.items()}
    if role=='base':
        if negative:areset['response_result']=constant(1,32)
        holds=conjunction(m,invariant(m,creset),eq(m,areset['pending'],creset['busy']),
            eq(m,areset['valid'],creset['valid']),eq(m,response(areset),response(creset)),
            eq(m,areset['cleared'],['1']),eq(m,response(creset),['0']*37))
    elif role=='control-step':
        if negative:
            nxt=copy.deepcopy(nxt);nxt['ready']=gate(m,'$not',nxt['ready'])
        holds=implies(m,invariant(m,current),invariant(m,nxt))
    else:
        cleared=[next_bit(m)]
        # next_bit uses cells; anchor the history input in a genuine buffer.
        anchor=cleared[0]+1
        m['ports']['history_cleared']=dict(direction='input',bits=cleared)
        m['cells']['__history_anchor']=dict(type='$not',attributes={},
            parameters=dict(A_WIDTH='1',A_SIGNED='0',Y_WIDTH='1'),
            port_directions=dict(A='input',Y='output'),connections=dict(A=cleared,Y=[anchor]))
        values=dict(pending=current['busy'],valid=current['valid'],response_result=current['response_result'],
                    response_flags=current['response_flags'],cleared=cleared)
        inputs={n:concrete['ports'][n]['bits'] for n,p in abstract['ports'].items()
                if p['direction']=='input' and n in concrete['ports']}
        inputs.update(io_finish=nxt['valid'],io_invalidPayload_result=current['response_result'],
            io_invalidPayload_flags=current['response_flags'],io_completionPayload_result=nxt['response_result'],
            io_completionPayload_flags=nxt['response_flags'])
        if negative and role=='outputs':
            # Recreate the old model's coupling: completion choice also drives
            # the invalid current payload. It must fail at publication.
            inputs['io_invalidPayload_result']=nxt['response_result']
            inputs['io_invalidPayload_flags']=nxt['response_flags']
        if negative and role=='step':
            bad=list(inputs['io_completionPayload_result']);bad[1]=gate(m,'$not',bad[1:2])[0]
            inputs['io_completionPayload_result']=bad
        ap,an=instantiate(m,abstract,values,inputs)
        history=implies(m,cleared,eq(m,response(current),['0']*37))
        premise=conjunction(m,invariant(m,current),history)
        if role=='outputs':
            comparisons=[eq(m,ap[n],concrete['ports'][n]['bits']) for n,p in concrete['ports'].items()
                         if p['direction']=='output' and n!='busy']
            holds=implies(m,premise,conjunction(m,*comparisons))
        elif role=='step':
            match=conjunction(m,eq(m,an['pending'],nxt['busy']),eq(m,an['valid'],nxt['valid']),
                eq(m,response(an),response(nxt)),eq(m,an['cleared'],inputs['io_cancel']),
                implies(m,an['cleared'],eq(m,response(nxt),['0']*37)))
            holds=implies(m,premise,match)
        elif role=='no-instant-completion':
            accepted=conjunction(m,inputs['io_req_valid'],current['ready'])
            goal=gate(m,'$not',nxt['valid'])
            if negative:goal=nxt['valid']
            holds=implies(m,conjunction(m,invariant(m,current),accepted),goal)
        else:raise ValueError(role)
    m['ports']['holds']=dict(direction='output',bits=holds)
    m['netnames']={n:dict(bits=p['bits'],attributes={}) for n,p in m['ports'].items()}
    return dict(modules={TOP:m})


def protect(inventory,paths):
    for path in paths:
        value=digest(path);name=str(path)
        if name in inventory and inventory[name]!=value:
            raise ValueError('Protected input changed: '+name)
        inventory[name]=value


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate',default='build/t13/exponent/candidate')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();candidate=local(args.candidate);out=output_dir(args.output)
    receipt=dict(status='running',scope='all-port FPU protocol trace inclusion only; no arithmetic/latency/ISA claim',results={});protected={}
    try:
        dependencies=(Path(__file__),ROOT/'hw/ip/perf_core/formal/FpuProtocolModelWide.scala',
            ROOT/'hw/ip/fpu/src/main/scala/deadhorse/fpu/Fpu.scala',ROOT/'tools/sbt.py',
            ROOT/'dv/core/induct_jalr_execute.py',ROOT/'dv/core/compose_jalr_ownership.py',
            ROOT/'dv/core/jalr_invariant.py',ROOT/'dv/core/jalr_receipts.py',ROOT/'dv/core/common.py',
            ROOT/'dv/core/candidate.py',ROOT/'dv/core/assertion_partitions.py')
        protect(protected,dependencies)
        manifest=candidate/'candidate.json';protect(protected,[manifest])
        parameters(candidate);data=json.loads(manifest.read_text())
        sources=sorted(candidate.glob('*.sv'))
        if {p.name for p in sources}!=set(data['extra_sources']):raise ValueError('Candidate extra source inventory differs')
        for p in sources:
            if digest(p)!=data['extra_sources'][p.name]:raise ValueError('Candidate FPU source hash mismatch')
            protect(protected,[p])
        verify_hashes(protected)
        emitted=output_dir(out/'model')
        run([sys.executable,'tools/sbt.py',f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/FpuProtocolModelWide.scala")',
             f'hw/runMain deadhorse.perf_core.EmitFpuProtocolModelWide {emitted}'],out,'emit-model',timeout=120)
        verify_hashes(protected)
        protect(protected,[emitted/'Fpu.sv'])
        paths=[]
        for role,files,extra in [('concrete',sources,'expose w:busy\n'),('abstract',[emitted/'Fpu.sv'],'')]:
            path=out/(role+'.json');ys=out/(role+'.ys')
            ys.write_text('read_slang --top Fpu '+' '.join(map(str,files))+'\n'+extra+
                f'prep -top Fpu -flatten\ncheck -assert\nwrite_json {path}\n')
            protect(protected,[*files,ys]);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',ys],out,role,timeout=120)
            verify_hashes(protected);protect(protected,[path]);paths.append(path)
        concrete,abstract=[json.loads(p.read_text())['modules']['Fpu'] for p in paths]
        receipt.update(timeout_seconds=120,assumptions=[],
            invariant='state legal; ready iff idle; busy iff nonidle; valid iff hold; cleared history implies concrete response zero',
            relation='abstract pending=concrete busy, valid=concrete valid, response=concrete response, cleared=previous cancel (true at reset)',
            choices='finish=concrete valid D; completionPayload=concrete response D; invalidPayload=concrete current response',
            reset='same positive-edge clock, active-high asynchronous reset; actual constant reset values checked',
            quantification='all other concrete state, external requests/ready/cancel and arithmetic values free; no deadline or fairness restriction')
        for role in ('base','control-step','outputs','step','no-instant-completion'):
            for negative in (False,True):
                name=role+('-negative' if negative else '');job=output_dir(out/name)
                path=job/'model.json';path.write_text(json.dumps(build(concrete,abstract,role,negative)))
                ys=job/'check.ys';witness=job/'witness.json'
                ys.write_text(f'read_json {path}\nhierarchy -top {TOP}\nopt_clean\ncheck -assert\nsat '+
                    ('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
                protect(protected,[path,ys]);verify_hashes(protected)
                result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
                expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
                if expected not in result.stdout or negative and not witness.is_file():raise ValueError(name+' unresolved')
                receipt['results'][name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
                verify_hashes(protected)
                if negative:protect(protected,[witness])
                print('PASS '+name,flush=True)
        verify_hashes(protected)
        receipt['status']='pass (all-port FPU protocol trace inclusion); integration safety and ISA reruns pending'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
