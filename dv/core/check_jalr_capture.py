"""Capture-time arithmetic and source transport; no aggregate ISA acceptance."""
import argparse
import copy
import json
from pathlib import Path
import sys

from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate, next_bit, property_cell, independent
from jalr_receipts import snapshot_baseline_audit, verify_hashes
from check_jalr_target import cone
from check_jalr_transport import BINDINGS as TRANSPORT_BINDINGS, OUTPUTS as TRANSPORT_OUTPUTS

CORE='wrapper.core.u_ibex_core.'
BINDINGS={**TRANSPORT_BINDINGS,
    'sourceValue':CORE+'id_stage_i.multdiv_operand_a_ex_o',
    'rvfiSource':'checker_inst.rvfi_rs1_rdata'}
OUTPUTS=(*TRANSPORT_OUTPUTS,'arithmeticHolds','sourceHolds','captureExpected','expectedSource',
         'sourceZero','sourceAlias','arithmeticNegative','arithmeticOdd','sourceFaultActive')


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
        key='__capture_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in v] for p,v in c['connections'].items()}
        m['cells'][key]=c
    nets={}
    for name,n in monitor['netnames'].items():
        key='__capture_'+name
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


def capture_witness(text,role):
    scope=[];names={};values={};time=0;found=[]
    source_role=role.startswith('source')
    fields=(['active','stageValid','sourceHolds','holds','rvfiInstruction','rvfiSource','expectedSource']
            if source_role else ['capture','arithmeticHolds','idInstruction','sourceValue','captureExpected','executeTarget'])
    wanted=['rvfi_testbench.__capture_'+p for p in fields]
    def sample():
        if not all(n in names and names[n] in values for n in wanted): return
        bits=[values[names[n]] for n in wanted]
        if any(set(b)-set('01') for b in bits): return
        if source_role:
            active,valid,sh,th,ri,rs,es=[int(b,2) for b in bits]
            rr=(ri>>15)&31;rd=(ri>>7)&31;normalized=rs if rr else 0
            good=active and valid and sh and th and normalized==es
            match=(role=='source-zero' and good and rr==0 or
                   role=='source-alias' and good and rr!=0 and rr==rd or
                   role=='source-fault' and active and valid and rr!=0 and not sh and normalized==(es^1))
            if match: found.append(dict(time=time,instruction=hex(ri),reported_source=hex(rs),expected_source=hex(es)))
        else:
            cap,ah,insn,source,expected,target=[int(b,2) for b in bits]
            ci=(insn>>15)&31;imm=insn>>20;imm=imm-4096 if imm&2048 else imm
            computed=((source if ci else 0)+imm)&0xffffffff
            good=cap and ah and (target&0xfffffffe)==(computed&0xfffffffe)==expected
            match=(role=='arithmetic-negative' and good and imm<0 or
                   role=='arithmetic-odd' and good and computed&1 or
                   role=='arithmetic-fault' and cap and not ah and (target&0xfffffffe)==(expected^2))
            if match: found.append(dict(time=time,instruction=hex(insn),source=hex(source),immediate=imm,
                target=hex(target),expected_target=hex(expected)))
    for line in text.splitlines():
        parts=line.split()
        if not parts: continue
        if parts[0]=='$scope': scope.append(parts[2])
        elif parts[0]=='$upscope': scope.pop()
        elif parts[0]=='$var': names['.'.join(scope+[parts[4]])]=parts[3]
        elif line.startswith('#'): sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2: values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ': values[line[1:]]=line[0]
    sample()
    if not found: raise ValueError('No active '+role+' witness')
    return found[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--resume-from',help='Reuse exact hash-verified successful models; recheck all witnesses')
    args=parser.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='capture/source correspondence only; aggregate ISA unresolved',results={})
    record=out/'result.json';record.write_text(json.dumps(receipt));protected={}
    try:
        previous=None;previous_dir=None
        if args.resume_from:
            previous_dir=local(args.resume_from);previous=json.loads((previous_dir/'result.json').read_text())
            source_archive=previous_dir/'check_jalr_capture.executed.py'
            verify_hashes(previous['input_sha256'],{str(Path(__file__)):str(source_archive)})
        audit_path=snapshot_baseline_audit(base,out);evidence=json.loads((base/'result.json').read_text())
        protected=dict(evidence['input_sha256'])
        for p in [base/'result.json',audit_path,Path(__file__),ROOT/'dv/core/jalr_receipts.py',
                  ROOT/'dv/core/check_jalr_target.py',ROOT/'dv/core/check_jalr_transport.py',
                  ROOT/'hw/ip/perf_core/formal/JalrTransportProperty.scala',ROOT/'hw/ip/perf_core/formal/JalrCaptureProperty.scala']:
            protected[str(p)]=digest(p)
        timeout=evidence['timeout_seconds'];depth=evidence['depth']
        if timeout>120: raise ValueError('Focused proof cap exceeded')
        original=json.loads((base/'original.json').read_text())
        if previous:
            ys=previous_dir/'monitor.ys';monitor_path=previous_dir/'monitor.json'
            monitor_sv=previous_dir/'JalrCaptureProperty.sv'
            receipt['reuse_from']=dict(receipt=str(previous_dir/'result.json'),sha256=digest(previous_dir/'result.json'))
            for path in (previous_dir/'result.json',previous_dir/'check_jalr_capture.executed.py'):
                protected[str(path)]=digest(path)
        else:
            run([sys.executable,'tools/sbt.py',
                'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
                f'hw/runMain deadhorse.perf_core.formal.EmitJalrCaptureProperty {out}'],out,'emit')
            ys=out/'monitor.ys';monitor_path=out/'monitor.json'
            ys.write_text(f'read_slang --top JalrCaptureProperty {out}/JalrCaptureProperty.sv\n'
                          f'prep -top JalrCaptureProperty -flatten\nwrite_json {monitor_path}\n')
            run(['yosys','-Q','-T','-s',ys],out,'monitor')
            monitor_sv=out/'JalrCaptureProperty.sv'
        attached,signals,nets=attach(original,json.loads(monitor_path.read_text())['modules']['JalrCaptureProperty'])
        qualified=qualify_active(attached,signals,out)
        model,removed=independent(original,attached,signals)
        m=model['modules'][TOP];m['cells']['__capture_assert']=m['cells'].pop('__jalr_address_assert')
        m['netnames'].update(nets)
        receipt.update(bindings=BINDINGS,removed_only_in_transport=removed,
                       timeout_seconds=timeout,depth=depth,assumptions=evidence['assumptions'])
        for p,h in protected.items():
            if digest(local(p))!=h: raise ValueError('Source changed during preparation: '+p)
        protected.update({str(p):digest(p) for p in [ys,monitor_path,monitor_sv,*qualified]})
        for role in ('source-prove','source-zero','source-alias','source-fault',
                     'arithmetic-prove','arithmetic-negative','arithmetic-odd','arithmetic-fault'):
            job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
            source_role=role.startswith('source-')
            obligation=gate(m,'$and',signals['holds'],signals['sourceHolds']) if source_role else signals['arithmeticHolds']
            m['cells']['__capture_assert']=property_cell('assert',obligation)
            mode='prove';engine='abc pdr'
            if not role.endswith(('prove','fault')):
                cover_signal={'source-zero':'sourceZero','source-alias':'sourceAlias',
                              'arithmetic-negative':'arithmeticNegative','arithmetic-odd':'arithmeticOdd'}[role]
                m['cells']['__capture_assert']=property_cell('cover',gate(m,'$and',signals[cover_signal],obligation))
                mode='cover';engine='btor btormc'
            if role.endswith('fault'):
                net='checker_inst.rvfi_rs1_rdata' if source_role else BINDINGS['executeTarget']
                bit=m['netnames'][net]['bits'][0 if source_role else 1]
                drivers=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                    if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                if len(drivers)!=1: raise ValueError('Fault needs one production driver')
                n,p,i=drivers[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
                m['cells']['__capture_output_fault']=dict(type='$xor',parameters={'A_WIDTH':'1','A_SIGNED':'0',
                    'B_WIDTH':'1','B_SIGNED':'0','Y_WIDTH':'1'},attributes={},
                    port_directions={'A':'input','B':'input','Y':'output'},
                    connections={'A':[fresh],'B':signals['sourceFaultActive' if source_role else 'capture'],'Y':[bit]})
                receipt[role+'_driver']=[n,p,i];mode='bmc';engine='btor btormc'
            path=job/'model.json';path.write_text(json.dumps(design))
            config=job/'check.sby';config.write_text(f'[options]\nmode {mode}\ndepth {depth}\n'
                f'multiclock on\ntimeout {timeout}\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            cached=previous['results'].get(role) if previous else None
            if cached:
                old_model=previous_dir/role/'model.json';old_config=previous_dir/role/'check.sby'
                if path.read_bytes()!=old_model.read_bytes(): raise ValueError('Cannot reuse changed proof model')
                if config.read_text()!=old_config.read_text().replace(str(old_model),str(path)):
                    raise ValueError('Cannot reuse changed proof configuration')
                status_path=previous_dir/role/'work/status'
                status=status_path.read_text().split()[0];returncode=cached['returncode']
                if status!=cached['status']: raise ValueError('Cached status differs from completed job')
                receipt['results'][role]={**cached,'reused_from':str(previous_dir/role)}
                protected[str(status_path)]=digest(status_path)
                trace_directory=previous_dir/role/'work'
            else:
                result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
                status=(job/'work/status').read_text().split()[0];returncode=result.returncode
                receipt['results'][role]=dict(status=status,returncode=returncode,seconds=result.elapsed_seconds)
                trace_directory=job/'work'
            for p,h in protected.items():
                if digest(local(p))!=h: raise ValueError('Proof input changed: '+p)
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            if (status,returncode)!=(('FAIL',2) if role.endswith('fault') else ('PASS',0)):
                raise RuntimeError('JALR capture '+role+': '+status)
            if not role.endswith('prove'):
                witnesses=[]
                for trace in trace_directory.glob('engine_*/trace*.vcd'):
                    try: witnesses.append(dict(path=str(trace),sha256=digest(trace),retirement=capture_witness(trace.read_text(),role)))
                    except ValueError: continue
                if not witnesses: raise ValueError('No active '+role+' witness')
                receipt['results'][role]['witnesses']=witnesses
            print('JALR capture '+role+': '+status,flush=True)
        receipt['status']='pass (capture arithmetic/source only; composition unresolved)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
