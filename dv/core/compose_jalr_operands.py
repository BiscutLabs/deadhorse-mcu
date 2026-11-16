"""Exact operand ownership induction; pending premises never become acceptance.

Preserves the original alignment predicate. The two-frame proof substitutes
actual emitted monitor D pins and checks reset separately. Previously proved
component guarantees are explicit implication antecedents, not production
assumptions. Source stability must be separately discharged before acceptance.
"""
import argparse
import copy
import json
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell
from jalr_receipts import combine_hashes, verify_hashes
from compose_jalr_ownership import frame, check_states, conjunction, implies, MODULE
from state_equiv import prepare
from qualify_owner_valid import inject
from check_jalr_request import BINDINGS, request_witness
from check_jalr_operands import witness as operand_witness
from check_jalr_capture import capture_witness


def payload_invariant(m,p):
    insn=p['idInstruction']; immediate=insn[20:32]+[insn[31]]*20
    value=conjunction(m,gate(m,'$eq',p['ownerOp'],['0']*7),
        gate(m,'$eq',p['ownerA'],p['sourceNow']),gate(m,'$eq',p['ownerB'],immediate))
    return implies(m,conjunction(m,p['ownerValid'],p['ownerJalr']),value)


def build(source,role,negative=False):
    states=check_states(source)
    for name in ('ownerA','ownerB','ownerOp','ownerSource','sourceBefore'):
        if not all(bit in states for bit in source['ports'][name]['bits']):
            raise ValueError('Operand state output not direct: '+name)
    m=dict(attributes={'top':'1'},ports={},cells={},netnames={})
    if role=='base':
        values={q:r for q,(_,r) in states.items()}
        if negative:
            values[source['ports']['ownerValid']['bits'][0]]='1'
            values[source['ports']['ownerJalr']['bits'][0]]='1'
        p,_=frame(m,source,'reset_',values); holds=payload_invariant(m,p)
    else:
        p,mapping=frame(m,source,'before_'); invariant=payload_invariant(m,p)
        if role=='step':
            values={q:mapping.get(d,d) for q,(d,_) in states.items()}
            if negative:
                q=source['ports']['ownerA']['bits'][0]
                values[q]=gate(m,'$not',[values[q]])[0]
            after,_=frame(m,source,'after_',values)
            premise=conjunction(m,invariant,gate(m,'$not',p['reset']),gate(m,'$not',after['reset']),
                p['retentionHolds'],p['operandIssueHolds'],after['stabilityHolds'],after['sourceStabilityHolds'])
            holds=implies(m,premise,payload_invariant(m,after))
        elif role=='final':
            response=implies(m,p['capture'],p['responseValid'])
            premise=conjunction(m,invariant,p['ownershipHolds'],p['retentionHolds'],p['retainedKindHolds'],
                p['operandRetentionHolds'],response)
            conclusion=implies(m,p['capture'],gate(m,'$not',gate(m,'$eq',p['requestA'],p['sourceNow']))) if negative else p['alignmentHolds']
            holds=implies(m,premise,conclusion)
        elif role=='arithmetic':
            premise=conjunction(m,p['alignmentHolds'],p['executeAddHolds'])
            conclusion=implies(m,p['capture'],gate(m,'$not',p['arithmeticHolds'])) if negative else p['arithmeticHolds']
            holds=implies(m,premise,conclusion)
        else: raise ValueError('Unknown composition role')
    m['ports']['holds']=dict(direction='output',bits=holds)
    m['netnames']={n:dict(bits=p['bits'],attributes={}) for n,p in m['ports'].items()}
    return dict(modules={MODULE:m})


def active_witness(text,fault=False):
    fields=('capture','responseValid');scope=[];names={};values={};found=[];time=0
    def sample():
        if not all(n in names and names[n] in values for n in fields):return
        raw={n:values[names[n]] for n in fields}
        if any(set(x)-set('01') for x in raw.values()):return
        d={n:int(v,2) for n,v in raw.items()}
        if d['capture'] and d['responseValid']==int(not fault):found.append(dict(time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='$scope':scope.append(parts[2])
        elif parts[0]=='$upscope':scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for n in fields:
                if full==TOP+'.__request_'+n:names[n]=parts[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2:values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No active response-valid witness')
    return found[0]


def bind_request(source,original,out,protected):
    old=copy.deepcopy(original);new=copy.deepcopy(source)
    if not set(old['ports'])<=set(new['ports']):raise ValueError('Request interface no longer inherited')
    for n,p in old['ports'].items():
        q=new['ports'][n]
        if p['direction']!=q['direction'] or len(p['bits'])!=len(q['bits']):raise ValueError('Inherited request interface changed')
    for n in set(new['ports'])-set(old['ports']):del new['ports'][n]
    models=[]
    for name,m in [('old',old),('new',new)]:
        path=out/(name+'-raw.json');path.write_text(json.dumps(dict(modules={'RequestProjection':m})))
        canonical=out/(name+'.json');ys=out/(name+'.ys')
        ys.write_text(f'read_json {path}\nprep -top RequestProjection -flatten\nopt_clean\ncheck -assert\nwrite_json {canonical}\n')
        run(['yosys','-Q','-T','-s',ys],out,name,timeout=120)
        protected.update({str(p):digest(p) for p in (path,canonical,ys)});models.append(canonical)
    a,b,state=prepare(*models,'RequestProjection',out,{})
    results={}
    for bad in (False,True):
        name='binding-negative' if bad else 'binding';candidate=b
        if bad:
            design=json.loads(b.read_text());m=design['modules']['RequestProjection']
            bits=gate(m,'$not',m['ports']['alignmentHolds']['bits'])
            m['ports']['alignmentHolds']['bits']=bits;m['netnames']['alignmentHolds']['bits']=bits
            candidate=out/'binding-negative.json';candidate.write_text(json.dumps(design))
        ys=out/(name+'.ys');witness=out/(name+'-witness.json')
        ys.write_text(f'read_json {a}\nrename RequestProjection gold\nread_json {candidate}\nrename RequestProjection gate\n'+
            'miter -equiv -flatten gold gate miter\nhierarchy -top miter\nopt_expr\nopt_merge\nopt_clean\n'+
            'sat '+('' if bad else '-verify ')+f'-prove trigger 0 -dump_json {witness}\n')
        protected.update({str(p):digest(p) for p in (a,candidate,ys)})
        result=run(['yosys','-Q','-T','-s',ys],out,name,timeout=120)
        expected='SAT proof finished - model found: FAIL!' if bad else 'SAT proof finished - no model found: SUCCESS!'
        if expected not in result.stdout or bad and not witness.is_file():raise ValueError('Inherited Request binding failed')
        if bad:protected[str(witness)]=digest(witness)
        results[name]=dict(status='rejected' if bad else 'proved',seconds=result.elapsed_seconds)
    return dict(results=results,correspondence=state)


def qualify_response(split,out,protected):
    positive=split/'response-valid/model.json';raw=split/'result.json';r=json.loads(raw.read_text())
    status=split/'response-valid/work/status'
    if r['results']['response-valid']['status']!='PASS' or status.read_text().split()[0]!='PASS':
        raise ValueError('Response-valid premise unresolved')
    protected[str(status)]=digest(status)
    if str(positive) not in protected:raise ValueError('Response-valid model unauthenticated')
    original=json.loads(positive.read_text());results={}
    for fault in (False,True):
        role='response-fault' if fault else 'response-cover';job=output_dir(out/role)
        design=copy.deepcopy(original);m=design['modules'][TOP]
        net=lambda n:m['netnames']['__request_'+n]['bits']
        if fault:
            # Force a premature jump during an actual first-phase JALR,
            # independently of responseValid and the capture predicate.
            active=conjunction(m,net('currentJalr'),net('idFirst'))
            driver=[]
            for name, value in [('pcSet',1),('pcMux',1)]:
                for index,bit in enumerate(m['netnames'][BINDINGS[name]]['bits']):
                    matches=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                        if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                    if len(matches)!=1:raise ValueError('Premature redirect requires unique driver')
                    n,p,i=matches[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
                    m['cells']['__early_redirect_'+name+str(index)]=dict(type='$mux',attributes={},
                        parameters={'WIDTH':'1'},port_directions={'A':'input','B':'input','S':'input','Y':'output'},
                        connections={'A':[fresh],'B':[str((value>>index)&1)],'S':active,'Y':[bit]})
                    driver.append([n,p,i])
        else:
            m['cells']['__alignment_response-valid']=property_cell('cover',conjunction(m,net('capture'),net('responseValid')))
        path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
        config.write_text(f'[options]\nmode {"bmc" if fault else "cover"}\ndepth 144\nmulticlock on\ntimeout 120\n'+
            f'[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
        protected.update({str(p):digest(p) for p in (path,config)})
        result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
        status=job/'work/status';actual=status.read_text().split()[0]
        if (actual,result.returncode)!=(('FAIL',2) if fault else ('PASS',0)):raise ValueError(role+': '+actual)
        witnesses=[]
        for trace in (job/'work').glob('engine_*/trace*.vcd'):
            try:event=active_witness(trace.read_text(),fault)
            except ValueError:continue
            witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
        if not witnesses:raise ValueError('Missing '+role+' active witness')
        protected[str(status)]=digest(status)
        results[role]=dict(status=actual,seconds=result.elapsed_seconds,witnesses=witnesses)
        if fault:results[role]['driver']=driver
        print(role+': '+actual,flush=True)
    return results


def qualify_alignment(out,protected):
    original_path=local('build/t13/jalr-request/alignment-prove/model.json')
    if str(original_path) not in protected:raise ValueError('Alignment model unauthenticated')
    original=json.loads(original_path.read_text());results={}
    for role in ('alignment-zero','alignment-negative','alignment-fault'):
        job=output_dir(out/role);design=copy.deepcopy(original);m=design['modules'][TOP]
        net=lambda n:m['netnames']['__request_'+n]['bits']
        fault=role=='alignment-fault'
        if fault:driver=inject(m,m['netnames'][BINDINGS['requestA']]['bits'][0],net('capture'))
        else:
            active=net('alignmentZero' if role=='alignment-zero' else 'alignmentNegative')
            m['cells']['__request_assert']=property_cell('cover',conjunction(m,active,net('alignmentHolds')))
        path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
        config.write_text(f'[options]\nmode {"bmc" if fault else "cover"}\ndepth 144\nmulticlock on\ntimeout 120\n'+
            f'[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
        protected.update({str(p):digest(p) for p in (path,config)})
        result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
        status=job/'work/status';actual=status.read_text().split()[0]
        if (actual,result.returncode)!=(('FAIL',2) if fault else ('PASS',0)):raise ValueError(role+': '+actual)
        witnesses=[]
        for trace in (job/'work').glob('engine_*/trace*.vcd'):
            try:event=request_witness(trace.read_text(),role)
            except ValueError:continue
            witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
        if not witnesses:raise ValueError('Missing exact alignment witness: '+role)
        protected[str(status)]=digest(status)
        results[role]=dict(status=actual,returncode=result.returncode,seconds=result.elapsed_seconds,witnesses=witnesses)
        if fault:results[role]['driver']=driver
        print(role+': '+actual,flush=True)
    return results


def source_premise(directory,protected):
    base=local(directory);raw=base/'result.json';r=json.loads(raw.read_text())
    audit=local('build/t13/rf-source-control-audit/audit.json');a=json.loads(audit.read_text())
    if r['status']!='pass (normalized source stability composition; operand composition and ISA unresolved)':
        raise ValueError('Source stability not composed')
    if a['status']!='pass (RF controls and inherited operand binding; source composition unresolved)':
        raise ValueError('RF inherited monitor binding unavailable')
    for role in ('base','step'):
        if r['results'][role]['status']!='proved' or r['results'][role+'-negative']['status']!='rejected':
            raise ValueError('Source implication incomplete')
    if a['results']['positive']['status']!='proved' or a['results']['negative']['status']!='rejected':
        raise ValueError('Source inherited binding incomplete')
    result=combine_hashes(protected,r['input_sha256'],a['input_sha256'])
    result.update({str(raw):digest(raw),str(audit):digest(audit)})
    for role,expected in [('source-cover','PASS'),('source-fault','FAIL')]:
        item=r['results'][role];status=base/role/'work/status'
        if item['status']!=expected or status.read_text().split()[0]!=expected:raise ValueError('Source role mismatch')
        result[str(status)]=digest(status)
        if not item.get('witnesses'):raise ValueError('Missing active source witness')
        for w in item['witnesses']:
            p=local(w['path'])
            if digest(p)!=w['sha256'] or operand_witness(p.read_text().replace('__rfcontrol_','__operand_'),role)!=w['event']:
                raise ValueError('Source witness changed')
            result[str(p)]=digest(p)
    verify_hashes(result)
    return result


def qualify_arithmetic(out,protected):
    original_path=local('build/t13/jalr-request/alignment-prove/model.json')
    if str(original_path) not in protected:raise ValueError('Arithmetic model unauthenticated')
    original=json.loads(original_path.read_text());results={}
    for role in ('arithmetic-negative','arithmetic-odd','arithmetic-fault'):
        job=output_dir(out/role);design=copy.deepcopy(original);m=design['modules'][TOP]
        net=lambda n:m['netnames']['__request_'+n]['bits']
        fault=role=='arithmetic-fault'
        m['cells']['__request_assert']=property_cell('assert',net('arithmeticHolds'))
        if fault:driver=inject(m,m['netnames'][BINDINGS['executeTarget']]['bits'][1],net('capture'))
        else:
            active=net('arithmeticNegative' if role=='arithmetic-negative' else 'arithmeticOdd')
            m['cells']['__request_assert']=property_cell('cover',conjunction(m,active,net('arithmeticHolds')))
        path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
        config.write_text(f'[options]\nmode {"bmc" if fault else "cover"}\ndepth 144\nmulticlock on\ntimeout 120\n'+
            f'[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
        protected.update({str(p):digest(p) for p in (path,config)})
        result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
        status=job/'work/status';actual=status.read_text().split()[0]
        if (actual,result.returncode)!=(('FAIL',2) if fault else ('PASS',0)):raise ValueError(role+': '+actual)
        witnesses=[]
        for trace in (job/'work').glob('engine_*/trace*.vcd'):
            try:event=capture_witness(trace.read_text().replace('__request_','__capture_'),role)
            except ValueError:continue
            witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
        if not witnesses:raise ValueError('Missing exact arithmetic witness: '+role)
        protected[str(status)]=digest(status)
        results[role]=dict(status=actual,returncode=result.returncode,seconds=result.elapsed_seconds,witnesses=witnesses)
        if fault:results[role]['driver']=driver
        print(role+': '+actual,flush=True)
    return results


def execute_premise(directory,protected):
    base=local(directory);raw=base/'result.json';r=json.loads(raw.read_text())
    if r['status']!='pass (local ADD induction; alignment and ISA unresolved)':raise ValueError('Local ADD proof incomplete')
    for role in ('base','step','final'):
        if r['results'][role]['status']!='proved' or r['results'][role+'-negative']['status']!='rejected':
            raise ValueError('Local ADD implication incomplete')
    result=combine_hashes(protected,r['input_sha256']);result[str(raw)]=digest(raw)
    for role,expected in [('execute-cover','PASS'),('execute-fault','FAIL')]:
        item=r['results'][role];status=base/role/'work/status'
        if item['status']!=expected or status.read_text().split()[0]!=expected:raise ValueError('Local ADD role mismatch')
        if not item.get('witnesses'):raise ValueError('Missing local ADD witness')
        result[str(status)]=digest(status)
        for w in item['witnesses']:
            p=local(w['path'])
            if digest(p)!=w['sha256'] or request_witness(p.read_text(),role)!=w['event']:raise ValueError('Local ADD witness changed')
            result[str(p)]=digest(p)
    verify_hashes(result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--operands',default='build/t13/jalr-operands')
    ap.add_argument('--audit',default='build/t13/jalr-operands-audit/audit.json')
    ap.add_argument('--kind',default='build/t13/request-kind-confirmed')
    ap.add_argument('--split',default='build/t13/jalr-alignment-split')
    ap.add_argument('--execute',default='build/t13/jalr-execute-induction-confirmed')
    ap.add_argument('--source',help='Reviewed exact RF source-stability composition directory; omit to keep premise pending')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.operands);audit=local(args.audit);kind=local(args.kind);split=local(args.split);out=output_dir(args.output)
    receipt=dict(status='running',scope='conditional operand composition only; source stability premise pending; no alignment/ISA acceptance',results={});protected={}
    try:
        paths=[base/'result.json',audit,kind/'result.json',kind/'audit.json',split/'result.json']
        evidence,checked,kindproof,kindaudit,partition=[json.loads(p.read_text()) for p in paths]
        if checked['status']!='pass (issue and retention only; source unresolved)':raise ValueError('Operand component audit unavailable')
        if kindaudit['status']!='pass':raise ValueError('Kind composition audit unavailable')
        protected=combine_hashes(*(d['input_sha256'] for d in (evidence,checked,kindproof,kindaudit,partition)))
        for p in paths:protected[str(p)]=digest(p)
        for p in (Path(__file__),ROOT/'dv/core/compose_jalr_ownership.py',ROOT/'dv/core/check_jalr_request.py',
            ROOT/'dv/core/qualify_owner_valid.py',ROOT/'dv/core/jalr_invariant.py',ROOT/'dv/core/jalr_receipts.py',ROOT/'dv/core/state_equiv.py'):
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        if args.source:protected=source_premise(args.source,protected)
        protected=execute_premise(args.execute,protected)
        for family in ('issue','retention'):
            for role,expected in [('prove','PASS'),('cover','PASS'),('fault','FAIL')]:
                job=family+'-'+role;status=base/job/'work/status'
                if evidence['results'][job]['status']!=expected or status.read_text().split()[0]!=expected:
                    raise ValueError('Operand component status mismatch: '+job)
        sourcepath=base/'monitor.json';requestpath=local('build/t13/jalr-request/monitor.json')
        if any(str(p) not in protected for p in (sourcepath,requestpath)):raise ValueError('Missing authenticated monitor')
        source=json.loads(sourcepath.read_text())['modules']['OperandOwnershipProperty']
        request=json.loads(requestpath.read_text())['modules']['JalrRequestProperty']
        receipt.update(timeout_seconds=120,depth=144,assumptions=evidence['assumptions'],
            pending_premises=[] if args.source else ['sourceStabilityHolds: direct proof TIMEOUT; reviewed exact RF composition not supplied'],
            invariant='ownerValid && ownerJalr implies ownerOp zero, ownerA equals current normalized source, ownerB equals current sign-extended immediate')
        receipt['request_binding']=bind_request(source,request,output_dir(out/'request-binding'),protected)
        receipt['results'].update(qualify_response(split,out,protected))
        for role in ('base','step','final','arithmetic'):
            for negative in (False,True):
                name=('arithmetic-implication' if role=='arithmetic' else role)+('-negative' if negative else '');job=output_dir(out/name)
                model=job/'model.json';model.write_text(json.dumps(build(source,role,negative)))
                ys=job/'check.ys';witness=job/'counterexample.json'
                ys.write_text(f'read_json {model}\nhierarchy -top {MODULE}\nopt_clean\ncheck -assert\n'+
                    'sat '+('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
                protected.update({str(p):digest(p) for p in (model,ys)});verify_hashes(protected)
                result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
                expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
                if expected not in result.stdout or negative and not witness.is_file():raise ValueError('Operand implication failed: '+name)
                receipt['results'][name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
                if negative:protected[str(witness)]=digest(witness)
                print('PASS '+name,flush=True)
        receipt['results'].update(qualify_alignment(out,protected))
        receipt['results'].update(qualify_arithmetic(out,protected))
        verify_hashes(protected)
        receipt['status']='pass (saved operand alignment and capture arithmetic composition; ISA unresolved)' if args.source else 'conditional implications proved; source stability premise pending; no alignment acceptance'
        if args.source:receipt['scope']='saved operand alignment and capture arithmetic only; ISA unresolved'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
