"""Independent saved-request alignment and local ADD lemmas; no ISA acceptance."""
import argparse
import copy
import json
from pathlib import Path
import sys
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate, next_bit, property_cell, independent
from jalr_receipts import snapshot_baseline_audit, verify_hashes
from check_jalr_target import cone
from check_jalr_capture import BINDINGS as CAPTURE_BINDINGS, OUTPUTS as CAPTURE_OUTPUTS

EXEC='wrapper.core.u_ibex_core.ex_block_i.clocked_execute.'
BINDINGS={**CAPTURE_BINDINGS, **{port:EXEC+net for port,net in {
    'requestA':'request_q_a','requestB':'request_q_b','requestKind':'request_q_kind',
    'requestOp':'request_q_aluOp','requestFirst':'request_q_firstCycle','responseValid':'rsp_valid'}.items()}}
OUTPUTS=(*CAPTURE_OUTPUTS,'alignmentHolds','executeActive','executeAddHolds',
         'alignmentZero','alignmentNegative','executeCorner')

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
        key='__request_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in v] for p,v in c['connections'].items()}
        m['cells'][key]=c
    nets={}
    for name,n in monitor['netnames'].items():
        key='__request_'+name
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


def request_witness(text,role):
    fields=['capture','alignmentHolds','executeActive','executeAddHolds','requestA','requestB',
            'requestKind','requestOp','requestFirst','responseValid','sourceValue','idInstruction','executeTarget']
    scope=[];names={};values={};found=[];time=0
    def sample():
        required=(['capture','alignmentHolds','requestA','requestB','requestKind','requestOp',
                  'requestFirst','responseValid','sourceValue','idInstruction'] if role.startswith('alignment') else
                  ['executeActive','executeAddHolds','requestA','requestB','executeTarget'])
        if not all(n in names and names[n] in values for n in required): return
        data={n:values[names[n]] for n in required}
        if any(set(v)-set('01') for v in data.values()): return
        d={n:int(v,2) for n,v in data.items()}
        if role.startswith('alignment'):
            insn=d['idInstruction'];rs=(insn>>15)&31;imm=insn>>20
            imm=imm-4096 if imm&2048 else imm
            source=d['sourceValue'] if rs else 0
            expected=(d['responseValid']==1 and d['requestKind']==0 and d['requestOp']==0 and
                      d['requestFirst']==1 and d['requestA']==source and d['requestB']==(imm&0xffffffff))
            good=d['capture'] and d['alignmentHolds'] and expected
            match=(role=='alignment-zero' and good and rs==0 or
                   role=='alignment-negative' and good and rs!=0 and imm<0 or
                   role=='alignment-fault' and d['capture'] and not d['alignmentHolds'] and not expected and
                   d['requestA']==(source^1))
        else:
            expected=(d['requestA']+d['requestB'])&0xffffffff
            good=d['executeActive'] and d['executeAddHolds'] and d['executeTarget']==expected
            match=(role=='execute-cover' and good and d['requestA']>>31 and d['requestB']>>31 and expected&1 or
                   role=='execute-fault' and d['executeActive'] and not d['executeAddHolds'] and d['executeTarget']==(expected^2))
        if match: found.append(dict(time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts: continue
        if parts[0]=='$scope': scope.append(parts[2])
        elif parts[0]=='$upscope': scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for field in fields:
                if full=='rvfi_testbench.__request_'+field: names[field]=parts[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2: values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not found: raise ValueError('No active '+role+' witness')
    return found[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='request alignment/local ADD only; composition and ISA unresolved',results={})
    record=out/'result.json';protected={}
    try:
        audit_path=snapshot_baseline_audit(base,out);evidence=json.loads((base/'result.json').read_text())
        protected=dict(evidence['input_sha256'])
        for p in [base/'result.json',audit_path,Path(__file__),ROOT/'dv/core/check_jalr_capture.py',
                  ROOT/'dv/core/check_jalr_transport.py',ROOT/'dv/core/check_jalr_target.py',ROOT/'dv/core/jalr_receipts.py',
                  *[ROOT/'hw/ip/perf_core/formal'/('Jalr'+n+'Property.scala') for n in ('Request','Capture','Transport')]]:
            protected[str(p)]=digest(p)
        timeout=evidence['timeout_seconds'];depth=evidence['depth']
        if timeout>120: raise ValueError('Focused cap exceeded')
        receipt.update(timeout_seconds=timeout,depth=depth,assumptions=evidence['assumptions'],bindings=BINDINGS)
        run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
            f'hw/runMain deadhorse.perf_core.formal.EmitJalrRequestProperty {out}'],out,'emit')
        ys=out/'monitor.ys';mp=out/'monitor.json';sv=out/'JalrRequestProperty.sv'
        ys.write_text(f'read_slang --top JalrRequestProperty {sv}\nprep -top JalrRequestProperty -flatten\nwrite_json {mp}\n')
        run(['yosys','-Q','-T','-s',ys],out,'monitor')
        original=json.loads((base/'original.json').read_text())
        attached,signals,nets=attach(original,json.loads(mp.read_text())['modules']['JalrRequestProperty'])
        qualified=qualify_active(attached,signals,out)
        model,removed=independent(original,attached,signals)
        m=model['modules'][TOP];del m['cells']['__jalr_address_assert'];m['netnames'].update(nets)
        receipt['removed_only_in_independent_lemmas']=removed
        verify_hashes(protected)
        protected.update({str(p):digest(p) for p in [ys,mp,sv,*qualified]})
        for role in ('alignment-prove','alignment-zero','alignment-negative','alignment-fault',
                     'execute-prove','execute-cover','execute-fault'):
            job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
            align=role.startswith('alignment')
            obligation=signals['alignmentHolds' if align else 'executeAddHolds']
            m['cells']['__request_assert']=property_cell('assert',obligation)
            mode='prove';engine='abc pdr'
            if role in ('alignment-zero','alignment-negative','execute-cover'):
                name={'alignment-zero':'alignmentZero','alignment-negative':'alignmentNegative','execute-cover':'executeCorner'}[role]
                m['cells']['__request_assert']=property_cell('cover',gate(m,'$and',signals[name],obligation))
                mode='cover';engine='btor btormc'
            if role.endswith('fault'):
                net=BINDINGS['requestA' if align else 'executeTarget']
                bit=m['netnames'][net]['bits'][0 if align else 1]
                drivers=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                    if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                if len(drivers)!=1: raise ValueError('Fault needs unique production driver')
                n,p,i=drivers[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
                m['cells']['__request_fault']=dict(type='$xor',parameters={'A_WIDTH':'1','A_SIGNED':'0','B_WIDTH':'1','B_SIGNED':'0','Y_WIDTH':'1'},attributes={},
                    port_directions={'A':'input','B':'input','Y':'output'},
                    connections={'A':[fresh],'B':signals['capture' if align else 'executeActive'],'Y':[bit]})
                receipt[role+'_driver']=[n,p,i];mode='bmc';engine='btor btormc'
            path=job/'model.json';path.write_text(json.dumps(design))
            config=job/'check.sby';config.write_text(f'[options]\nmode {mode}\ndepth {depth}\nmulticlock on\ntimeout {timeout}\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
            status=(job/'work/status').read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            verify_hashes(protected)
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            if (status,result.returncode)!=(('FAIL',2) if role.endswith('fault') else ('PASS',0)):
                raise RuntimeError('JALR request '+role+': '+status)
            if not role.endswith('prove'):
                witnesses=[]
                for trace in (job/'work').glob('engine_*/trace*.vcd'):
                    try: witnesses.append(dict(path=str(trace),sha256=digest(trace),event=request_witness(trace.read_text(),role)))
                    except ValueError: continue
                if not witnesses: raise ValueError('No active '+role+' witness')
                receipt['results'][role]['witnesses']=witnesses
            print('JALR request '+role+': '+status,flush=True)
        receipt['status']='pass (request alignment/local ADD only; composition unresolved)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
