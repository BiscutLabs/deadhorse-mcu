"""Transport proved capture arithmetic through exact ghost state to ISA JALR target."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell
from jalr_receipts import combine_hashes, verify_hashes
from compose_jalr_ownership import frame, check_states, conjunction, implies
from state_equiv import prepare
from check_jalr_target import attach, qualify, target_witness
from qualify_owner_valid import inject


def wide(m,kind,a,b,select=None):
    bits=list(range(next_bit(m),next_bit(m)+32))
    conn=dict(A=a,B=b,Y=bits);params=dict(A_WIDTH='100000',B_WIDTH='100000',Y_WIDTH='100000',A_SIGNED='0',B_SIGNED='0')
    if select is not None:conn['S']=select;params=dict(WIDTH='100000')
    m['cells']['__target_value_'+str(bits[0])]=dict(type=kind,attributes={},parameters=params,
        port_directions={n:'output' if n=='Y' else 'input' for n in conn},connections=conn)
    return bits


def expected(m,instruction,source):
    zero=gate(m,'$eq',instruction[15:20],['0']*5)
    base=wide(m,'$mux',source,['0']*32,zero)
    offset=instruction[20:32]+[instruction[31]]*20
    total=wide(m,'$add',base,offset)
    return ['0']+total[1:]


def fields(monitor,mapping):
    names={'capturedTarget':'capturedTarget','capturedInstruction':'capturedInstruction',
           'capturedSource':'capturedSource','stagedInstruction':'instruction'}
    states=check_states(monitor)
    result={}
    for field,name in names.items():
        bits=monitor['netnames'][name]['bits']
        if len(bits)!=32 or not all(b in states for b in bits):raise ValueError('Unbound capture/stage state: '+field)
        result[field]=[mapping.get(b,b) for b in bits]
    return result


def arithmetic_invariant(m,p):
    captured=gate(m,'$eq',p['capturedTarget'],expected(m,p['capturedInstruction'],p['capturedSource']))
    staged=gate(m,'$eq',p['expectedTarget'],expected(m,p['stagedInstruction'],p['expectedSource']))
    return conjunction(m,implies(m,p['captureValid'],captured),implies(m,p['stageValid'],staged))


def target_instance(m,target,bindings):
    if set(bindings)!={n for n,p in target['ports'].items() if p['direction']=='input'}:
        raise ValueError('Target monitor interface mismatch')
    allbits={b for c in target['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    fresh=next_bit(m);mapping={b:fresh+i for i,b in enumerate(sorted(allbits))}
    for n,bs in bindings.items():
        if len(bs)!=len(target['ports'][n]['bits']):raise ValueError('Target binding width mismatch')
        mapping.update(zip(target['ports'][n]['bits'],bs))
    for n,c in target['cells'].items():
        if any(s in c['type'].lower() for s in ('dff','latch','mem')) or c['type'] in ('$assert','$assume','$check','$cover'):
            raise ValueError('Target property is not pure combinational logic')
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in bs] for p,bs in c['connections'].items()}
        m['cells']['__target_spec_'+n]=c
    return {n:[mapping.get(b,b) for b in p['bits']] for n,p in target['ports'].items()}


def build(monitor,target,role,negative):
    states=check_states(monitor);m=dict(attributes={'top':'1'},ports={},cells={},netnames={})
    if role=='base':
        values={q:r for q,(_,r) in states.items()}
        if negative:
            values[monitor['ports']['captureValid']['bits'][0]]='1'
            values[monitor['netnames']['capturedTarget']['bits'][1]]='1'
        p,mapping=frame(m,monitor,'reset_',values);p.update(fields(monitor,mapping))
        holds=arithmetic_invariant(m,p)
    else:
        p,mapping=frame(m,monitor,'before_');p.update(fields(monitor,mapping))
        inv=arithmetic_invariant(m,p)
        if role=='step':
            values={q:mapping.get(d,d) for q,(d,_) in states.items()}
            if negative:
                bit=monitor['netnames']['capturedTarget']['bits'][1]
                values[bit]=gate(m,'$not',[values[bit]])[0]
            nxt,nmap=frame(m,monitor,'after_',values);nxt.update(fields(monitor,nmap))
            premise=conjunction(m,inv,p['arithmeticHolds'],p['holds'],gate(m,'$not',p['reset']),gate(m,'$not',nxt['reset']))
            holds=implies(m,premise,arithmetic_invariant(m,nxt))
        elif role=='final':
            reported=p['rvfiNextPc'][:]
            if negative:reported[1]=gate(m,'$not',reported[1:2])[0]
            spec=target_instance(m,target,dict(reset=p['checkerReset'],valid=p['rvfiValid'],
                instruction=p['rvfiInstruction'],sourceValue=p['rvfiSource'],reportedPc=reported))
            holds=implies(m,conjunction(m,inv,p['holds'],p['sourceHolds']),spec['holds'])
        else:raise ValueError('Unknown target composition role')
    m['ports']['holds']=dict(direction='output',bits=holds)
    m['netnames']={n:dict(bits=p['bits'],attributes={}) for n,p in m['ports'].items()}
    return dict(modules={TOP:m})


def bind_capture(old,new,out,protected):
    old=copy.deepcopy(old);new=copy.deepcopy(new)
    if not set(old['ports'])<=set(new['ports']):raise ValueError('Capture interface disappeared')
    for n,p in old['ports'].items():
        q=new['ports'][n]
        if (p['direction'],len(p['bits']))!=(q['direction'],len(q['bits'])):raise ValueError('Capture interface changed')
    extra=set(new['ports'])-set(old['ports'])
    for n in extra:del new['ports'][n]
    paths=[]
    for name,m in zip(('old','new'),(old,new)):
        raw=out/(name+'-raw.json');raw.write_text(json.dumps(dict(modules={'CaptureProjection':m})))
        canonical=out/(name+'.json');ys=out/(name+'.ys')
        ys.write_text(f'read_json {raw}\nprep -top CaptureProjection -flatten\nopt_clean\ncheck -assert\nwrite_json {canonical}\n')
        run(['yosys','-Q','-T','-s',ys],out,name,timeout=120)
        protected.update({str(p):digest(p) for p in (raw,canonical,ys)});paths.append(canonical)
    gold,candidate,state=prepare(*paths,'CaptureProjection',out,{})
    results={}
    for negative in (False,True):
        name='negative' if negative else 'positive';selected=candidate
        if negative:
            model=json.loads(candidate.read_text());m=model['modules']['CaptureProjection']
            bits=gate(m,'$not',m['ports']['sourceHolds']['bits']);m['ports']['sourceHolds']['bits']=bits;m['netnames']['sourceHolds']['bits']=bits
            selected=out/'negative.json';selected.write_text(json.dumps(model))
        ys=out/(name+'.ys');trace=out/(name+'-witness.json')
        ys.write_text(f'read_json {gold}\nrename CaptureProjection gold\nread_json {selected}\nrename CaptureProjection gate\n'
            'miter -equiv -flatten gold gate miter\nhierarchy -top miter\nopt_expr\nopt_merge\nopt_clean\n'+
            'sat '+('' if negative else '-verify ')+f'-prove trigger 0 -dump_json {trace}\n')
        protected.update({str(p):digest(p) for p in (gold,selected,ys)})
        result=run(['yosys','-Q','-T','-s',ys],out,name,timeout=120)
        expected_log='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
        if expected_log not in result.stdout or negative and not trace.exists():raise ValueError('Capture monitor binding failed')
        results[name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
        if negative:protected[str(trace)]=digest(trace)
    return dict(results=results,state_correspondence=state,removed_extra_ports=sorted(extra))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arithmetic',default='build/t13/operand-composition-complete')
    ap.add_argument('--capture',default='build/t13/jalr-capture-resumed')
    ap.add_argument('--target',default='build/t13/jalr-target')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();arithmetic=local(args.arithmetic);capture=local(args.capture);target=local(args.target);out=output_dir(args.output)
    receipt=dict(status='running',scope='JALR target and original line178 only; aggregate ISA unresolved',results={});protected={}
    try:
        paths=[arithmetic/'result.json',capture/'result.json',capture/'source-audit.json',target/'result.json']
        ar,cap,audit,tgt=[json.loads(p.read_text()) for p in paths]
        if ar['status']!='pass (saved operand alignment and capture arithmetic composition; ISA unresolved)':raise ValueError('Capture arithmetic premise incomplete')
        if audit['status']!='pass (source only)' or audit['receipt_sha256']!=digest(paths[1]):raise ValueError('Source/transport premise incomplete')
        if tgt['qualification']['positive']['status']!='PASS' or tgt['qualification']['negative']['status']!='rejected':raise ValueError('ISA target qualification incomplete')
        # The old target job used an earlier metadata-only runner revision.
        # Honor its already-recorded exact-byte relocations; never rewrite the
        # original receipt or substitute the current runner for historical input.
        relocation_path=target/'input-relocations.json'
        relocation=json.loads(relocation_path.read_text())
        if relocation['receipt_sha256']!=digest(paths[3]):raise ValueError('Historical target relocation mismatch')
        historical=dict(tgt['input_sha256'])
        for original,item in relocation['relocations'].items():
            archive=local(item['snapshot']);expected_hash=item['expected_sha256']
            if historical.get(original)!=expected_hash or digest(archive)!=expected_hash:
                raise ValueError('Historical target bytes missing')
            del historical[original];historical[str(archive)]=expected_hash
        protected=combine_hashes(ar['input_sha256'],cap['input_sha256'],audit['input_sha256'],historical)
        protected[str(relocation_path)]=digest(relocation_path)
        for p in (*paths,Path(__file__),Path(__file__).with_name('state_equiv.py'),Path(__file__).with_name('check_jalr_target.py')):
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        newpath=local('build/t13/jalr-operands/monitor.json');oldpath=local('build/t13/jalr-capture/monitor.json');targetpath=target/'monitor.json'
        if any(str(p) not in protected for p in (newpath,oldpath,targetpath)):raise ValueError('Monitor lineage incomplete')
        monitor=json.loads(newpath.read_text())['modules']['OperandOwnershipProperty']
        old=json.loads(oldpath.read_text())['modules']['JalrCaptureProperty']
        spec=json.loads(targetpath.read_text())['modules']['JalrTargetProperty']
        receipt.update(timeout_seconds=120,depth=144,assumptions=ar['assumptions'],
            invariant='captureValid implies captured target equals normalized captured source plus signed captured immediate with bit0 cleared; stageValid implies same relation for staged data',
            antecedents=['proved capture arithmeticHolds','proved joint transport holds and sourceHolds'],
            original_target_assertion=tgt['target_assertion'])
        receipt['capture_binding']=bind_capture(old,monitor,output_dir(out/'capture-binding'),protected)
        for role in ('base','step','final'):
            for negative in (False,True):
                name=role+('-negative' if negative else '');job=output_dir(out/name);path=job/'model.json';path.write_text(json.dumps(build(monitor,spec,role,negative)))
                script=job/'check.ys';witness=job/'counterexample.json'
                script.write_text(f'read_json {path}\nhierarchy -top {TOP}\nopt_clean\ncheck -assert\nsat '+
                    ('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
                protected.update({str(p):digest(p) for p in (path,script)});verify_hashes(protected)
                result=run(['yosys','-Q','-T','-s',script],job,'check',timeout=120)
                expected_log='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
                if expected_log not in result.stdout or negative and not witness.exists():raise ValueError(name+' failed')
                receipt['results'][name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
                if negative:protected[str(witness)]=digest(witness)
                print('PASS '+name,flush=True)
        originalpath=local('build/t13/jalr-address-strengthened/original.json')
        if str(originalpath) not in protected:raise ValueError('Original checker lineage missing')
        original=json.loads(originalpath.read_text());attached,signals=attach(original,spec)
        cell=attached['modules'][TOP]['cells'][tgt['target_assertion']]
        files,qualification=qualify(attached,signals,cell,out)
        protected.update({str(p):digest(p) for p in files});receipt['original_qualification']=qualification
        fullpath=target/'prove/model.json'
        if str(fullpath) not in protected:raise ValueError('Full target model lineage missing')
        full=json.loads(fullpath.read_text())
        for role in ('cover-zero','cover-odd','cover-negative','fault'):
            design=copy.deepcopy(full);m=design['modules'][TOP];mode='cover'
            if role.startswith('cover-'):
                field={'cover-zero':'coverZero','cover-odd':'coverOdd','cover-negative':'coverNegative'}[role]
                m['cells']['__jalr_target_assert']=property_cell('cover',signals[field])
            else:
                receipt['fault_driver']=inject(m,m['netnames']['checker_inst.rvfi_pc_wdata']['bits'][1],signals['faultActive']);mode='bmc'
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statuspath=job/'work/status';status=statuspath.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('FAIL',2) if role=='fault' else ('PASS',0)):raise RuntimeError(role+': '+status)
            protected[str(statuspath)]=digest(statuspath);witnesses=[]
            for trace in (job/'work').glob('engine_*/trace*.vcd'):
                try:event=target_witness(trace.read_text(),role)
                except ValueError:continue
                witnesses.append(dict(path=str(trace),sha256=digest(trace),retirement=event));protected[str(trace)]=digest(trace)
            if not witnesses:raise ValueError('No exact active target witness: '+role)
            receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        verify_hashes(protected);receipt['status']='pass (JALR target composition and original PC assertion; aggregate ISA unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
