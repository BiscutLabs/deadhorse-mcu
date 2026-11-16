"""Compose exact RF transitions with proved phase/address/write controls."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell
from jalr_receipts import combine_hashes, verify_hashes
from compose_jalr_ownership import frame, check_states, conjunction, implies
from induct_jalr_execute import cut_cone
from check_rf_source_control import BINDINGS, RF
from qualify_owner_valid import inject
from check_jalr_operands import witness as operand_witness


def rf_cones(production):
    states={}
    for index in range(1,32):
        bits=production['netnames'][RF+f'g_rf_flops_{index}_rf_reg_q']['bits']
        matches=[c for c in production['cells'].values() if c['connections'].get('Q')==bits]
        if len(matches)!=1:raise ValueError('Ambiguous RF word state')
        c=matches[0];p=c['parameters'];conn=c['connections']
        if (c['type']!='$aldff' or len(bits)!=32 or int(p['CLK_POLARITY'],2)!=1 or
            int(p['ALOAD_POLARITY'],2)!=1 or conn['CLK']!=production['netnames'][BINDINGS['clock']]['bits'] or
            conn['ALOAD']!=production['netnames'][BINDINGS['reset']]['bits'] or conn['AD']!=['0']*32):
            raise ValueError('RF clock/reset/width changed')
        states[index]=copy.deepcopy(c)
    names={'rfReadAddress':'raddr_a_i','rfWriteAddress':'waddr_a_i','rfWriteEnable':'we_a_i','rfWriteData':'wdata_a_i'}
    inputs={name:production['netnames'][RF+port]['bits'] for name,port in names.items()}
    read=production['netnames'][RF+'rdata_a_o']['bits']
    if read!=production['netnames'][BINDINGS['sourceValue']]['bits']:
        raise ValueError('RF output is not actual monitor source input')
    source=copy.deepcopy(production)
    for name,bits in inputs.items():source['ports']['rf_cut_'+name]=dict(direction='input',bits=bits)
    outputs={'read':read,**{f'd_{i}':c['connections']['D'] for i,c in states.items()}}
    complete=cut_cone(source,outputs);read_only=cut_cone(source,{'read':read})
    allowed=set(b for c in states.values() for b in c['connections']['Q'])|set(b for bs in inputs.values() for b in bs)
    for model in (complete,read_only):
        used={b for p in model['ports'].values() if p['direction']=='input' for b in p['bits']}
        if not used<=allowed:raise ValueError('RF cone crosses its actual interface')
    return complete,read_only,states,inputs


def graft(m,cone,prefix,bindings):
    allbits={b for c in cone['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    allbits|={b for p in cone['ports'].values() for b in p['bits'] if isinstance(b,int)}
    fresh=next_bit(m);mapping={b:fresh+i for i,b in enumerate(sorted(allbits))};mapping.update(bindings)
    cv=lambda bs:[mapping.get(b,b) for b in bs]
    for name,p in cone['ports'].items():
        if p['direction']=='input' and p['bits'][0] not in bindings:m['ports'][prefix+name]=dict(direction='input',bits=cv(p['bits']))
    for name,c in cone['cells'].items():
        c=copy.deepcopy(c);c['connections']={p:cv(bs) for p,bs in c['connections'].items()};m['cells'][prefix+name]=c
    return {n:cv(p['bits']) for n,p in cone['ports'].items()},mapping


def build(monitor,production,role,negative):
    m=dict(attributes={'top':'1'},ports={},cells={},netnames={});states=check_states(monitor)
    if role=='base':
        reset={q:r for q,(_,r) in states.items()}
        if negative:
            # Corrupt the actual prior-source-holding reset bit.
            choices=[c for c in monitor['cells'].values() if c['type']=='$aldff' and
                     c['connections']['D']==monitor['ports']['sourceHolding']['bits']]
            if len(choices)!=1:raise ValueError('Prior source-holding state not unique')
            reset[choices[0]['connections']['Q'][0]]='1'
        p,_=frame(m,monitor,'reset_',reset);holds=p['sourceStabilityHolds']
    else:
        p,mapping=frame(m,monitor,'before_')
        values={q:mapping.get(d,d) for q,(d,_) in states.items()}
        nxt,_=frame(m,monitor,'after_',values)
        complete,read_only,rfstates,inputs=rf_cones(production)
        bindings={b:v for n,bs in inputs.items() if n in p for b,v in zip(bs,p[n])}
        before,beforemap=graft(m,complete,'rf_before_',bindings)
        nextbindings={b:v for b,v in zip(inputs['rfReadAddress'],nxt['rfReadAddress'])}
        for i,c in rfstates.items():
            nextbindings.update(zip(c['connections']['Q'],before['d_'+str(i)]))
        after,_=graft(m,read_only,'rf_after_',nextbindings)
        if negative:
            after['read'][0]=gate(m,'$not',after['read'][0:1])[0]
        # Both monitor sourceValue inputs become the exact physical RF read;
        # no input assumption or symbolic value relation is introduced.
        replacement=dict(zip(p['sourceValue'],before['read']))
        replacement.update(zip(nxt['sourceValue'],after['read']))
        for c in m['cells'].values():c['connections']={n:[replacement.get(b,b) for b in bs] for n,bs in c['connections'].items()}
        del m['ports']['before_sourceValue'];del m['ports']['after_sourceValue']
        for port in m['ports'].values():port['bits']=[replacement.get(b,b) for b in port['bits']]
        premise=conjunction(m,gate(m,'$not',p['reset']),gate(m,'$not',nxt['reset']),
                            p['rfNoConflictHolds'],nxt['rfAddressHolds'],nxt['stabilityHolds'])
        holds=implies(m,premise,nxt['sourceStabilityHolds'])
    m['ports']['holds']=dict(direction='output',bits=holds)
    m['netnames']={n:dict(bits=p['bits'],attributes={}) for n,p in m['ports'].items()}
    return dict(modules={TOP:m})


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--controls',default='build/t13/rf-source-control')
    ap.add_argument('--audit',default='build/t13/rf-source-control-audit')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.controls);audit=local(args.audit);out=output_dir(args.output)
    receipt=dict(status='running',scope='normalized source stability only; operand composition/ISA unresolved',results={});protected={}
    try:
        raw=base/'result.json';aud=audit/'audit.json';control=json.loads(raw.read_text());checked=json.loads(aud.read_text())
        if control['status']!='pass (RF controls only; source stability composition unresolved)' or checked['status']!='pass (RF controls and inherited operand binding; source composition unresolved)':
            raise ValueError('RF premises are incomplete')
        protected=combine_hashes(control['input_sha256'],checked['input_sha256'])
        for p in (raw,aud,Path(__file__),Path(__file__).with_name('compose_jalr_ownership.py'),
                  Path(__file__).with_name('induct_jalr_execute.py')):protected[str(p)]=digest(p)
        verify_hashes(protected)
        monitor=json.loads((base/'monitor.json').read_text())['modules']['RfSourceControlProperty']
        sourcepath=base/'address-prove/model.json'
        if str(sourcepath) not in protected:raise ValueError('Unauthenticated physical model')
        production=json.loads(sourcepath.read_text())
        receipt.update(assumptions=control['assumptions'],timeout_seconds=120,depth=144,
            antecedents=['current RF no-conflict guarantee','next RF address-stability guarantee','next ID phase-stability guarantee'],
            transition='exact 31 physical RF word D cones/read muxes, exact monitor D pins, shared clock/reset verified; every old state and RF write data free')
        for role in ('base','step'):
            for negative in (False,True):
                name=role+('-negative' if negative else '');job=output_dir(out/name);path=job/'model.json'
                path.write_text(json.dumps(build(monitor,production['modules'][TOP],role,negative)))
                script=job/'check.ys';witness=job/'counterexample.json'
                script.write_text(f'read_json {path}\nhierarchy -top {TOP}\nopt_clean\ncheck -assert\nsat '+
                    ('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
                protected.update({str(p):digest(p) for p in (path,script)});verify_hashes(protected)
                result=run(['yosys','-Q','-T','-s',script],job,'check',timeout=120)
                expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
                if expected not in result.stdout or negative and not witness.exists():raise ValueError(name+' failed')
                receipt['results'][name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
                if negative:protected[str(witness)]=digest(witness)
                print('PASS '+name,flush=True)
        for role in ('source-cover','source-fault'):
            design=copy.deepcopy(production);m=design['modules'][TOP];net=lambda n:m['netnames']['__rfcontrol_'+n]['bits']
            m['cells']['__rfcontrol_assert']=property_cell('assert',net('sourceStabilityHolds'));mode='bmc'
            if role=='source-cover':
                nonzero=gate(m,'$ne',net('sourceNow'),['0']*32)
                m['cells']['__rfcontrol_assert']=property_cell('cover',conjunction(m,net('sourceStabilityActive'),net('sourceStabilityHolds'),nonzero));mode='cover'
            else:receipt['fault_driver']=inject(m,m['netnames'][BINDINGS['sourceValue']]['bits'][0],net('sourceStabilityActive'))
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statusfile=job/'work/status';status=statusfile.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('PASS',0) if mode=='cover' else ('FAIL',2)):raise RuntimeError(role+': '+status)
            protected[str(statusfile)]=digest(statusfile);witnesses=[]
            for trace in (job/'work').glob('engine_*/trace*.vcd'):
                try:event=operand_witness(trace.read_text().replace('__rfcontrol_','__operand_'),role)
                except ValueError:continue
                witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
            if not witnesses:raise ValueError('No exact source stability witness')
            receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        verify_hashes(protected);receipt['status']='pass (normalized source stability composition; operand composition and ISA unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
