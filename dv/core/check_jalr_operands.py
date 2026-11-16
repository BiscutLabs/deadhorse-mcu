"""Prove actual accepted operands, retention and source stability separately."""
import argparse
import copy
import json
from pathlib import Path
import sys
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell, independent
from jalr_receipts import snapshot_baseline_audit, verify_hashes
from check_phase_stability import BINDINGS as PHASE_BINDINGS, OUTPUTS as PHASE_OUTPUTS
from check_jalr_ownership import EXEC
from qualify_owner_valid import inject
BINDINGS = {**PHASE_BINDINGS, **{p: EXEC+n for p,n in {
    'incomingA':'req_bits_a', 'incomingB':'req_bits_b', 'incomingOp':'req_bits_aluOp'}.items()}}
OUTPUTS = (*PHASE_OUTPUTS, 'operandIssueHolds', 'operandRetentionHolds', 'sourceHolding',
    'sourceStabilityActive', 'sourceStabilityHolds', 'sourceNow', 'sourceBefore',
    'ownerA', 'ownerB', 'ownerOp', 'ownerSource')

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
        key='__operand_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in v] for p,v in c['connections'].items()}
        m['cells'][key]=c
    nets={}
    for name,n in monitor['netnames'].items():
        key='__operand_'+name
        if key in m['netnames']: raise ValueError('Monitor net collision')
        n=copy.deepcopy(n);n['bits']=[mapping.get(b,b) for b in n['bits']];nets[key]=n
    restored=copy.deepcopy(design)
    for n in set(m['cells'])-set(original['modules'][TOP]['cells']): del restored['modules'][TOP]['cells'][n]
    if restored!=original: raise ValueError('Monitor changed original model')
    outputs={p:[mapping.get(b,b) for b in monitor['ports'][p]['bits']] for p in OUTPUTS}
    return design,outputs,nets


def witness(text, role):
    family, kind = role.split('-')
    active, holds = {'issue':('issueActive','operandIssueHolds'),
        'retention':('ownerValid','operandRetentionHolds'),
        'source':('sourceStabilityActive','sourceStabilityHolds')}[family]
    fields = [active, holds] + {'issue':['incomingA','incomingB','incomingOp','sourceNow','idInstruction'],
        'retention':['requestA','requestB','requestOp','ownerA','ownerB','ownerOp'],
        'source':['sourceNow','sourceBefore']}[family]
    scope=[]; names={}; values={}; found=[]; time=0
    def sample():
        if not all(n in names and names[n] in values for n in fields): return
        raw={n:values[names[n]] for n in fields}
        if any(set(v)-set('01') for v in raw.values()): return
        d={n:int(v,2) for n,v in raw.items()}
        if not d[active] or d[holds] != int(kind=='cover'): return
        if family=='source' and d['sourceNow'] != (d['sourceBefore'] ^ int(kind=='fault')): return
        if family=='retention' and kind=='fault' and d['requestOp'] != (d['ownerOp'] ^ 1): return
        if family=='issue':
            immediate=d['idInstruction']>>20
            if immediate & 0x800: immediate |= 0xfffff000
            if d['incomingB'] != (immediate ^ int(kind=='fault')): return
            if kind=='cover' and (d['incomingA']!=d['sourceNow'] or d['incomingOp']!=0): return
        found.append(dict(time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts: continue
        if parts[0]=='$scope': scope.append(parts[2])
        elif parts[0]=='$upscope': scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for field in fields:
                if full==TOP+'.__operand_'+field: names[field]=parts[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2: values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not found: raise ValueError('No active operand witness: '+role)
    return found[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',default='build/t13/jalr-address-strengthened')
    parser.add_argument('--output',required=True)
    args=parser.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='operand components only; composition and ISA unresolved',results={});protected={}
    try:
        audit=snapshot_baseline_audit(base,out); evidence=json.loads((base/'result.json').read_text())
        protected=dict(evidence['input_sha256'])
        for p in (base/'result.json',audit,Path(__file__),ROOT/'hw/ip/perf_core/formal/OperandOwnershipProperty.scala',
                  ROOT/'hw/ip/perf_core/formal/PhaseStabilityProperty.scala',ROOT/'dv/core/check_phase_stability.py',
                  ROOT/'dv/core/check_jalr_ownership.py',ROOT/'dv/core/qualify_owner_valid.py'):
            protected[str(p)]=digest(p)
        receipt.update(timeout_seconds=120,depth=144,assumptions=evidence['assumptions'],bindings=BINDINGS)
        run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
             f'hw/runMain deadhorse.perf_core.formal.EmitOperandOwnershipProperty {out}'],out,'emit')
        sv=out/'OperandOwnershipProperty.sv';mp=out/'monitor.json';ys=out/'monitor.ys'
        ys.write_text(f'read_slang --top OperandOwnershipProperty {sv}\nprep -top OperandOwnershipProperty -flatten\nwrite_json {mp}\n')
        run(['yosys','-Q','-T','-s',ys],out,'monitor',timeout=120)
        original=json.loads((base/'original.json').read_text())
        attached,signals,nets=attach(original,json.loads(mp.read_text())['modules']['OperandOwnershipProperty'])
        model,removed=independent(original,attached,signals)
        m=model['modules'][TOP];del m['cells']['__jalr_address_assert'];m['netnames'].update(nets)
        receipt['removed_only_in_independent_lemmas']=removed
        protected.update({str(p):digest(p) for p in (sv,mp,ys)})
        for family in ('issue','retention','source'):
            for kind in ('prove','cover','fault'):
                role=family+'-'+kind;job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
                active,holds={'issue':('issueActive','operandIssueHolds'),'retention':('ownerValid','operandRetentionHolds'),
                    'source':('sourceStabilityActive','sourceStabilityHolds')}[family]
                m['cells']['__operand_assert']=property_cell('assert',signals[holds])
                mode='prove';engine='abc pdr'
                if kind=='cover':
                    m['cells']['__operand_assert']=property_cell('cover',gate(m,'$and',signals[active],signals[holds]))
                    mode='cover';engine='btor btormc'
                if kind=='fault':
                    port={'issue':'incomingB','retention':'requestOp','source':'sourceValue'}[family]
                    bit=m['netnames'][BINDINGS[port]]['bits'][0]
                    receipt[role+'_driver']=inject(m,bit,signals[active]);mode='bmc';engine='btor btormc'
                path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
                config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
                protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
                result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
                status_path=job/'work/status';status=status_path.read_text().split()[0]
                receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
                protected[str(status_path)]=digest(status_path)
                if (status,result.returncode)!=(('FAIL',2) if kind=='fault' else ('PASS',0)): raise RuntimeError(role+': '+status)
                if kind!='prove':
                    witnesses=[]
                    for trace in (job/'work').glob('engine_*/trace*.vcd'):
                        try: event=witness(trace.read_text(),role)
                        except ValueError: continue
                        witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
                    if not witnesses: raise ValueError('No active witness: '+role)
                    receipt['results'][role]['witnesses']=witnesses
                print(role+': '+status,flush=True)
                (out/'result.json').write_text(json.dumps({**receipt,'input_sha256':protected},indent=2)+'\n')
        verify_hashes(protected);receipt['status']='pass (operand components only; composition unresolved)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
