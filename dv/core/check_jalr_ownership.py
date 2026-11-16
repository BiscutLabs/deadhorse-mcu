"""Track actual accepted execute requests; no aggregate ISA acceptance."""
import argparse
import copy
import json
from pathlib import Path
import sys
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate, next_bit, property_cell, independent
from jalr_receipts import snapshot_baseline_audit, verify_hashes
from check_jalr_target import cone
from check_jalr_request import BINDINGS as REQUEST_BINDINGS, OUTPUTS as REQUEST_OUTPUTS

EXEC='wrapper.core.u_ibex_core.ex_block_i.clocked_execute.'
BINDINGS={**REQUEST_BINDINGS,**{port:EXEC+net for port,net in {
    'reqValid':'req_valid','reqReady':'req_ready','incomingKind':'req_bits_kind','rspReady':'rsp_ready'}.items()}}
OUTPUTS=(*REQUEST_OUTPUTS,'accepted','consumed','issueActive','issueHolds','retentionHolds','retainedKindHolds',
    'ownershipHolds','ownerValid','ownerKind','ownerFirst','ownerJalr','ownerInstruction','ownerPc',
    'responseCover','captureZero','captureReplacement')

def attach(original,monitor):
    design=copy.deepcopy(original);m=design['modules'][TOP];mapping={};fresh=next_bit(m)
    actual_inputs={n for n,p in monitor['ports'].items() if p['direction']=='input'}
    if actual_inputs!=set(BINDINGS): raise ValueError('Monitor binding inventory mismatch')
    for port,name in BINDINGS.items():
        old=monitor['ports'][port]['bits'];new=m['netnames'][name]['bits']
        if len(old)!=len(new): raise ValueError('Binding width mismatch: '+port)
        for a,b in zip(old,new):
            if a in mapping and mapping[a]!=b: raise ValueError('Aliased monitor inputs conflict')
            mapping[a]=b
    # The ghost state uses the same physical clock/reset as the RVFI stage.
    q=m['netnames']['checker_inst.rvfi_pc_wdata']['bits']
    stages=[c for c in m['cells'].values() if c['connections'].get('Q')==q]
    if len(stages)!=1 or stages[0]['type'] not in ('$adff','$aldff'): raise ValueError('Unexpected RVFI stage state')
    stage=stages[0]
    reset_port='ARST' if stage['type']=='$adff' else 'ALOAD'
    if stage['type']=='$aldff' and set(stage['connections']['AD'])!={'0'}:
        raise ValueError('RVFI stage async reset data must be zero')
    if stage['type']=='$adff' and int(stage['parameters']['ARST_VALUE'],2):
        raise ValueError('RVFI stage reset value must be zero')
    if (stage['connections']['CLK']!=m['netnames'][BINDINGS['clock']]['bits'] or
        stage['connections'][reset_port]!=m['netnames'][BINDINGS['reset']]['bits'] or
        int(stage['parameters']['CLK_POLARITY'],2)!=1 or int(stage['parameters'][reset_port+'_POLARITY'],2)!=1):
        raise ValueError('Ghost clock/reset differs from production RVFI')
    bits={b for c in monitor['cells'].values() for value in c['connections'].values() for b in value if isinstance(b,int)}
    bits|={b for n in monitor['netnames'].values() for b in n['bits'] if isinstance(b,int)}
    for bit in sorted(bits-set(mapping)): mapping[bit]=fresh;fresh+=1
    for name,c in monitor['cells'].items():
        key='__ownership_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in v] for p,v in c['connections'].items()}
        m['cells'][key]=c
    nets={}
    for name,n in monitor['netnames'].items():
        key='__ownership_'+name
        if key in m['netnames']: raise ValueError('Monitor net collision')
        n=copy.deepcopy(n);n['bits']=[mapping.get(b,b) for b in n['bits']];nets[key]=n
    restored=copy.deepcopy(design)
    for n in set(m['cells'])-set(original['modules'][TOP]['cells']): del restored['modules'][TOP]['cells'][n]
    if restored!=original: raise ValueError('Monitor changed original model')
    outputs={p:[mapping.get(b,b) for b in monitor['ports'][p]['bits']] for p in OUTPUTS}
    return design,outputs,nets


def qualify_active(attached,signals,out):
    m=copy.deepcopy(attached)['modules'][TOP]
    same=gate(m,'$eq',signals['active'],m['netnames'][PREFIX+'spec_valid']['bits'])
    model=cone(m,{'same':same});path=out/'guard.json';path.write_text(json.dumps(model))
    ys=out/'guard.ys';ys.write_text(f'read_json {path}\ncheck -assert\nsat -verify -prove same 1\n')
    result=run(['yosys','-Q','-T','-s',ys],out,'guard',timeout=120)
    if 'SAT proof finished - no model found: SUCCESS!' not in result.stdout: raise ValueError('RVFI activation qualification failed')
    return [path,ys]


def ownership_witness(text,role):
    issue=role.startswith('issue')
    retention=role.startswith('retention')
    fields=(['issueActive','issueHolds','incomingKind','idInstruction'] if issue else
            ['ownerValid','ownerKind','requestKind','ownerFirst','requestFirst','responseValid','ownerJalr','retentionHolds'] if retention else
            ['capture','ownershipHolds','ownerValid','ownerJalr','ownerFirst','ownerInstruction','idInstruction',
             'ownerPc','idPc','captureReplacement','sourceValue'])
    if role=='retention-fault': fields=['ownerValid','ownerKind','requestKind','retentionHolds']
    if role in ('ownership-zero','ownership-fault'):
        fields=[n for n in fields if n not in ('captureReplacement','sourceValue')]
    scope=[];names={};values={};found=[];time=0
    def sample():
        if not all(n in names and names[n] in values for n in fields): return
        raw={n:values[names[n]] for n in fields}
        if any(set(v)-set('01') for v in raw.values()): return
        d={n:int(v,2) for n,v in raw.items()}
        if issue:
            match=d['issueActive'] and ((role=='issue-cover' and d['issueHolds'] and d['incomingKind']==0) or
                (role=='issue-fault' and not d['issueHolds'] and d['incomingKind']==1))
        elif retention:
            match=d['ownerValid'] and ((role=='retention-cover' and d['responseValid'] and d['ownerJalr'] and
                d['retentionHolds'] and d['ownerKind']==d['requestKind'] and d['ownerFirst']==d['requestFirst']) or
                (role=='retention-fault' and not d['retentionHolds'] and d['requestKind']==(d['ownerKind']^1)))
        else:
            good=(d['capture'] and d['ownershipHolds'] and d['ownerValid'] and d['ownerJalr'] and d['ownerFirst'] and
                  d['ownerInstruction']==d['idInstruction'] and d['ownerPc']==d['idPc'])
            rs=(d['idInstruction']>>15)&31
            match=(role=='ownership-zero' and good and rs==0 or
                   role=='ownership-replacement' and good and d['captureReplacement'] and rs!=0 and d['sourceValue']!=0 or
                   role=='ownership-fault' and d['capture'] and d['ownerValid'] and not d['ownershipHolds'] and d['idPc']==(d['ownerPc']^4))
        if match: found.append(dict(time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts: continue
        if parts[0]=='$scope': scope.append(parts[2])
        elif parts[0]=='$upscope': scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for field in fields:
                if full=='rvfi_testbench.__ownership_'+field: names[field]=parts[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2: values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not found: raise ValueError('No active '+role+' witness')
    return found[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--resume-from',help='Reuse exact authenticated models/statuses after parser repair')
    args=parser.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='accepted request tracking only; composition and ISA unresolved',results={})
    record=out/'result.json';protected={}
    try:
        previous=None;previous_dir=None
        if args.resume_from:
            previous_dir=local(args.resume_from);previous=json.loads((previous_dir/'result.json').read_text())
            verify_hashes(previous['input_sha256'],{str(Path(__file__)):str(previous_dir/'check_jalr_ownership.executed.py')})
        audit_path=snapshot_baseline_audit(base,out);evidence=json.loads((base/'result.json').read_text())
        protected=dict(evidence['input_sha256'])
        for p in [base/'result.json',audit_path,Path(__file__),ROOT/'dv/core/check_jalr_request.py',ROOT/'dv/core/check_jalr_capture.py',
                  ROOT/'dv/core/check_jalr_transport.py',ROOT/'dv/core/check_jalr_target.py',ROOT/'dv/core/jalr_receipts.py',
                  *[ROOT/'hw/ip/perf_core/formal'/('Jalr'+n+'Property.scala') for n in ('Ownership','Request','Capture','Transport')]]:
            protected[str(p)]=digest(p)
        timeout=evidence['timeout_seconds'];depth=evidence['depth']
        if timeout>120: raise ValueError('Focused cap exceeded')
        receipt.update(timeout_seconds=timeout,depth=depth,assumptions=evidence['assumptions'],bindings=BINDINGS)
        if previous:
            ys=previous_dir/'monitor.ys';mp=previous_dir/'monitor.json';sv=previous_dir/'JalrOwnershipProperty.sv'
            receipt['reuse_from']=dict(receipt=str(previous_dir/'result.json'),sha256=digest(previous_dir/'result.json'))
            for p in (previous_dir/'result.json',previous_dir/'check_jalr_ownership.executed.py'):
                protected[str(p)]=digest(p)
        else:
            run([sys.executable,'tools/sbt.py',
                'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
                f'hw/runMain deadhorse.perf_core.formal.EmitJalrOwnershipProperty {out}'],out,'emit')
            ys=out/'monitor.ys';mp=out/'monitor.json';sv=out/'JalrOwnershipProperty.sv'
            ys.write_text(f'read_slang --top JalrOwnershipProperty {sv}\nprep -top JalrOwnershipProperty -flatten\nwrite_json {mp}\n')
            run(['yosys','-Q','-T','-s',ys],out,'monitor')
        original=json.loads((base/'original.json').read_text())
        attached,signals,nets=attach(original,json.loads(mp.read_text())['modules']['JalrOwnershipProperty'])
        qualified=qualify_active(attached,signals,out)
        model,removed=independent(original,attached,signals)
        m=model['modules'][TOP];del m['cells']['__jalr_address_assert'];m['netnames'].update(nets)
        receipt['removed_only_in_independent_lemmas']=removed
        verify_hashes(protected)
        protected.update({str(p):digest(p) for p in [ys,mp,sv,*qualified]})
        roles=('issue-prove','issue-cover','issue-fault','retention-prove','retention-cover','retention-fault',
               'retained-kind-prove','ownership-prove','ownership-zero','ownership-replacement','ownership-fault')
        for role in roles:
            job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
            family=role.split('-')[0]
            obligation=signals[{'issue':'issueHolds','retention':'retentionHolds','ownership':'ownershipHolds','retained':'retainedKindHolds'}[family]]
            if family=='retained': obligation=gate(m,'$and',obligation,signals['issueHolds'])
            m['cells']['__ownership_assert']=property_cell('assert',obligation)
            mode='prove';engine='abc pdr'
            if role in ('issue-cover','retention-cover','ownership-zero','ownership-replacement'):
                name={'issue-cover':'issueActive','retention-cover':'responseCover',
                      'ownership-zero':'captureZero','ownership-replacement':'captureReplacement'}[role]
                m['cells']['__ownership_assert']=property_cell('cover',gate(m,'$and',signals[name],obligation))
                mode='cover';engine='btor btormc'
            if role.endswith('fault'):
                port,index,active={'issue':('incomingKind',0,'issueActive'),
                    'retention':('requestKind',0,'ownerValid'),'ownership':('idPc',2,'capture')}[family]
                bit=m['netnames'][BINDINGS[port]]['bits'][index]
                drivers=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                    if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                if len(drivers)!=1: raise ValueError('Fault needs unique production driver')
                n,p,i=drivers[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
                m['cells']['__ownership_fault']=dict(type='$xor',parameters={'A_WIDTH':'1','A_SIGNED':'0','B_WIDTH':'1','B_SIGNED':'0','Y_WIDTH':'1'},attributes={},
                    port_directions={'A':'input','B':'input','Y':'output'},
                    connections={'A':[fresh],'B':signals[active],'Y':[bit]})
                receipt[role+'_driver']=[n,p,i];mode='bmc';engine='btor btormc'
            path=job/'model.json';path.write_text(json.dumps(design))
            config=job/'check.sby';config.write_text(f'[options]\nmode {mode}\ndepth {depth}\nmulticlock on\ntimeout {timeout}\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            cached=previous['results'].get(role) if previous else None
            if cached:
                old_model=previous_dir/role/'model.json';old_config=previous_dir/role/'check.sby'
                if path.read_bytes()!=old_model.read_bytes(): raise ValueError('Reuse model differs')
                if config.read_text()!=old_config.read_text().replace(str(old_model),str(path)):
                    raise ValueError('Reuse configuration differs')
                status_path=previous_dir/role/'work/status';status=status_path.read_text().split()[0]
                if status!=cached['status']: raise ValueError('Reuse status differs')
                returncode=cached['returncode']
                receipt['results'][role]={**cached,'reused_from':str(previous_dir/role)}
                protected[str(status_path)]=digest(status_path);trace_dir=previous_dir/role/'work'
            else:
                result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
                status=(job/'work/status').read_text().split()[0];returncode=result.returncode
                receipt['results'][role]=dict(status=status,returncode=returncode,seconds=result.elapsed_seconds)
                trace_dir=job/'work'
            verify_hashes(protected)
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            if (status,returncode)!=(('FAIL',2) if role.endswith('fault') else ('PASS',0)):
                raise RuntimeError('JALR ownership '+role+': '+status)
            if not role.endswith('prove'):
                witnesses=[]
                for trace in trace_dir.glob('engine_*/trace*.vcd'):
                    try: witnesses.append(dict(path=str(trace),sha256=digest(trace),event=ownership_witness(trace.read_text(),role)))
                    except ValueError: continue
                if not witnesses: raise ValueError('No active '+role+' witness')
                receipt['results'][role]['witnesses']=witnesses
            print('JALR ownership '+role+': '+status,flush=True)
        receipt['status']='pass (accepted request tracking only; composition unresolved)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
