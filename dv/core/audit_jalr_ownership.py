"""Qualify issue/retention/retained-kind results without accepting unresolved identity."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, next_bit, property_cell
from jalr_receipts import verify_hashes
from check_jalr_ownership import ownership_witness, BINDINGS


def retained_witness(text):
    fields=['ownerValid','ownerJalr','ownerKind','retainedKindHolds','issueActive','incomingKind']
    scope=[];names={};values={};accepted=None;found=[];time=0
    def sample():
        nonlocal accepted
        if not all(n in names and names[n] in values for n in fields): return
        raw={n:values[names[n]] for n in fields}
        if any(set(v)-set('01') for v in raw.values()): return
        d={n:int(v,2) for n,v in raw.items()}
        if d['issueActive'] and d['incomingKind']==1: accepted=time
        if (accepted is not None and time>accepted and d['ownerValid'] and d['ownerJalr'] and
                d['ownerKind']==1 and not d['retainedKindHolds']):
            found.append(dict(accept_time=accepted,violation_time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts: continue
        if parts[0]=='$scope': scope.append(parts[2])
        elif parts[0]=='$upscope': scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for n in fields:
                if full=='rvfi_testbench.__ownership_'+n: names[n]=parts[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2: values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not found: raise ValueError('No accepted corrupted kind retained at a later time')
    return found[0]


def audit(directory,audit_output=None):
    out=local(directory);audit_out=output_dir(audit_output) if audit_output else out
    record=audit_out/'control-audit.json'
    receipt=dict(status='running',scope='issue/retention/retained-kind only; identity/arithmetic/ISA unresolved')
    record.write_text(json.dumps(receipt));protected={}
    try:
        raw=out/'result.json';evidence=json.loads(raw.read_text())
        protected={**evidence['input_sha256'],str(raw):digest(raw),str(Path(__file__)):digest(Path(__file__))}
        verify_hashes(protected)
        receipt['aggregate_status']=evidence['status'];receipt['identity_result']=evidence['results'].get('ownership-prove',{'status':'not run'})
        identity=evidence['results'].get('ownership-prove')
        if identity:
            status_path=out/'ownership-prove/work/status'
            if status_path.read_text().split()[0]!=identity['status']: raise ValueError('Identity status mismatch')
            protected[str(status_path)]=digest(status_path)
        roles=('issue-prove','issue-cover','issue-fault','retention-prove','retention-cover','retention-fault','retained-kind-prove')
        for role in roles:
            r=evidence['results'][role];work=local(r['reused_from']) if 'reused_from' in r else out/role
            status_path=work/'work/status';expected=('FAIL',2) if role.endswith('fault') else ('PASS',0)
            if (r['status'],r['returncode'])!=expected or status_path.read_text().split()[0]!=r['status']:
                raise ValueError('Control status mismatch: '+role)
            protected[str(status_path)]=digest(status_path)
            if not role.endswith('prove'):
                if not r.get('witnesses'): raise ValueError('Missing active witness')
                for w in r['witnesses']:
                    trace=local(w['path'])
                    if digest(trace)!=w['sha256'] or ownership_witness(trace.read_text(),role)!=w['event']:
                        raise ValueError('Changed control witness')
                    protected[str(trace)]=digest(trace)
        bad=copy.deepcopy(json.loads((out/'guard.json').read_text()))
        targets=[(n,c) for n,c in bad['modules'][TOP]['cells'].items() if n.startswith('__ownership_') and
                 c['type']=='$eq' and c['connections'].get('B')==list(reversed(format(0x67,'07b')))]
        if len(targets)!=1: raise ValueError('Guard opcode not unique')
        targets[0][1]['connections']['B'][0]='0'
        job=output_dir(audit_out/'guard-negative');path=job/'model.json';path.write_text(json.dumps(bad))
        ys=job/'check.ys';witness=job/'counterexample.json'
        ys.write_text(f'read_json {path}\ncheck -assert\nsat -prove same 1 -show-inputs -show-outputs -dump_json {witness}\n')
        protected.update({str(p):digest(p) for p in (path,ys)})
        result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
        if 'SAT proof finished - model found: FAIL!' not in result.stdout or not witness.is_file():
            raise ValueError('Wrong-opcode guard escaped')
        receipt['guard_negative']=dict(status='rejected',seconds=result.elapsed_seconds,witness_sha256=digest(witness))
        model=json.loads((out/'retained-kind-prove/model.json').read_text());m=model['modules'][TOP]
        def net(n): return m['netnames']['__ownership_'+n]['bits']
        assertion=m['cells']['__ownership_assert']
        gates=[c for c in m['cells'].values() if c['connections'].get('Y')==assertion['connections']['A']]
        if (assertion['type']!='$assert' or assertion['connections']['EN']!=['1'] or len(gates)!=1 or
                gates[0]['type']!='$and' or gates[0]['connections']['A']!=net('retainedKindHolds') or
                gates[0]['connections']['B']!=net('issueHolds')):
            raise ValueError('Positive retained-kind obligation changed')
        # Test the retained-state predicate itself; the earlier issue predicate
        # must not terminate the fault trace before the corrupt request is stored.
        m['cells']['__ownership_assert']=property_cell('assert',net('retainedKindHolds'))
        bit=m['netnames'][BINDINGS['incomingKind']]['bits'][0]
        drivers=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                 if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
        if len(drivers)!=1: raise ValueError('Incoming-kind driver not unique')
        n,p,i=drivers[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
        m['cells']['__retained_kind_fault']=dict(type='$xor',parameters={'A_WIDTH':'1','B_WIDTH':'1',
            'Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},attributes={},
            port_directions={'A':'input','B':'input','Y':'output'},
            connections={'A':[fresh],'B':net('issueActive'),'Y':[bit]})
        job=output_dir(audit_out/'retained-kind-fault');path=job/'model.json';path.write_text(json.dumps(model))
        config=job/'check.sby';config.write_text(f"[options]\nmode bmc\ndepth {evidence['depth']}\nmulticlock on\ntimeout {evidence['timeout_seconds']}\n"
            f'[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
        protected.update({str(p):digest(p) for p in (path,config)})
        result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=evidence['timeout_seconds']+30)
        status=(job/'work/status').read_text().split()[0]
        receipt['retained_kind_fault']=dict(status=status,seconds=result.elapsed_seconds,driver=[n,p,i])
        if (status,result.returncode)!=('FAIL',2): raise ValueError('Retained-kind fault escaped or unresolved')
        witnesses=[]
        for trace in (job/'work').glob('engine_*/trace*.vcd'):
            try: witnesses.append(dict(path=str(trace),sha256=digest(trace),event=retained_witness(trace.read_text())))
            except ValueError: continue
        if not witnesses: raise ValueError('Retained-kind fault lacks delayed witness')
        receipt['retained_kind_fault']['witnesses']=witnesses
        verify_hashes(protected)
        receipt['status']='pass (control components only)'
        print('PASS issue/retention/retained-kind audit; actual retained-kind fault rejected')
        print('Identity status: '+receipt['identity_result']['status']+'; aggregate: '+evidence['status'])
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--audit-output')
    args=parser.parse_args();audit(args.output,args.audit_output)
