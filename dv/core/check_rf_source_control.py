"""Prove actual RF selection stability and no write conflict during source holding."""
import argparse
import copy
import json
from pathlib import Path
import sys
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, digest, gate, next_bit, property_cell, independent
from jalr_receipts import verify_hashes
from check_jalr_operands import BINDINGS as OPERAND_BINDINGS, OUTPUTS as OPERAND_OUTPUTS
from qualify_owner_valid import inject
RF='wrapper.core.gen_regfile_ff_register_file_i.'
BINDINGS={**OPERAND_BINDINGS,'rfReadAddress':RF+'raddr_a_i',
          'rfWriteAddress':RF+'waddr_a_i','rfWriteEnable':RF+'we_a_i'}
OUTPUTS=(*OPERAND_OUTPUTS,'rfAddressHolds','rfNoConflictHolds','rfPriorAddress')


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
        key='__rfcontrol_'+name
        if key in m['cells']: raise ValueError('Monitor cell collision')
        c=copy.deepcopy(c);c['connections']={p:[mapping.get(b,b) for b in v] for p,v in c['connections'].items()}
        m['cells'][key]=c
    nets={}
    for name,n in monitor['netnames'].items():
        key='__rfcontrol_'+name
        if key in m['netnames']: raise ValueError('Monitor net collision')
        n=copy.deepcopy(n);n['bits']=[mapping.get(b,b) for b in n['bits']];nets[key]=n
    restored=copy.deepcopy(design)
    for n in set(m['cells'])-set(original['modules'][TOP]['cells']): del restored['modules'][TOP]['cells'][n]
    if restored!=original: raise ValueError('Monitor changed original model')
    outputs={p:[mapping.get(b,b) for b in monitor['ports'][p]['bits']] for p in OUTPUTS}
    return design,outputs,nets


def witness(text,role):
    family,kind=role.split('-')
    active,holds={'address':('sourceStabilityActive','rfAddressHolds'),
                  'conflict':('sourceHolding','rfNoConflictHolds')}[family]
    fields=[active,holds,'rfReadAddress']+(['rfPriorAddress'] if family=='address' else ['rfWriteEnable','rfWriteAddress'])
    scope=[];names={};values={};found=[];time=0
    def sample():
        if any(n not in names or names[n] not in values for n in fields):return
        raw={n:values[names[n]] for n in fields}
        if any(set(v)-set('01') for v in raw.values()):return
        d={n:int(v,2) for n,v in raw.items()}
        if not d[active] or d[holds]!=int(kind=='cover') or not d['rfReadAddress']:return
        if family=='address' and d['rfReadAddress']!=(d['rfPriorAddress'] ^ int(kind=='fault')):return
        if family=='conflict':
            collision=d['rfWriteEnable'] and d['rfWriteAddress']==d['rfReadAddress']
            if bool(collision)!=(kind=='fault'):return
        found.append(dict(time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='$scope':scope.append(parts[2])
        elif parts[0]=='$upscope':scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for n in fields:
                if full==TOP+'.__rfcontrol_'+n:names[n]=parts[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2:values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No exact active RF control witness: '+role)
    return found[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--operand',default='build/t13/jalr-operands');ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.operand);out=output_dir(args.output)
    receipt=dict(status='running',scope='RF control only; source stability composition and ISA unresolved',results={});protected={}
    try:
        raw=base/'result.json';prior=json.loads(raw.read_text());protected=dict(prior['input_sha256'])
        for p in (raw,Path(__file__),ROOT/'hw/ip/perf_core/formal/RfSourceControlProperty.scala'):
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        receipt.update(timeout_seconds=120,depth=144,assumptions=prior['assumptions'],bindings=BINDINGS)
        run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/perf_core/formal")',
             f'hw/runMain deadhorse.perf_core.formal.EmitRfSourceControlProperty {out}'],out,'emit')
        sv=out/'RfSourceControlProperty.sv';mp=out/'monitor.json';ys=out/'monitor.ys'
        ys.write_text(f'read_slang --top RfSourceControlProperty {sv}\nprep -top RfSourceControlProperty -flatten\nwrite_json {mp}\n')
        run(['yosys','-Q','-T','-s',ys],out,'monitor',timeout=120)
        paths=[local(p) for p in protected if p.endswith('/jalr-address-strengthened/original.json')]
        if len(paths)!=1:raise ValueError('Missing exact baseline production model')
        original=json.loads(paths[0].read_text())
        attached,signals,nets=attach(original,json.loads(mp.read_text())['modules']['RfSourceControlProperty'])
        model,removed=independent(original,attached,signals)
        m=model['modules'][TOP];del m['cells']['__jalr_address_assert'];m['netnames'].update(nets)
        receipt['removed_only_in_independent_lemmas']=removed
        protected.update({str(p):digest(p) for p in (sv,mp,ys)})
        for family in ('address','conflict'):
            for kind in ('prove','cover','fault'):
                role=family+'-'+kind;job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
                active,holds={'address':('sourceStabilityActive','rfAddressHolds'),
                              'conflict':('sourceHolding','rfNoConflictHolds')}[family]
                m['cells']['__rfcontrol_assert']=property_cell('assert',signals[holds]);mode='prove';engine='abc pdr'
                if kind=='cover':
                    nonzero=gate(m,'$ne',m['netnames']['__rfcontrol_rfReadAddress']['bits'],['0']*5)
                    m['cells']['__rfcontrol_assert']=property_cell('cover',gate(m,'$and',nonzero,gate(m,'$and',signals[active],signals[holds])))
                    mode='cover';engine='btor btormc'
                if kind=='fault':
                    field='rfReadAddress' if family=='address' else 'rfWriteEnable'
                    receipt[role+'_driver']=inject(m,m['netnames'][BINDINGS[field]]['bits'][0],signals[active])
                    mode='bmc';engine='btor btormc'
                path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
                config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
                protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
                result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
                statuspath=job/'work/status';status=statuspath.read_text().split()[0]
                receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
                protected[str(statuspath)]=digest(statuspath)
                if (status,result.returncode)!=(('FAIL',2) if kind=='fault' else ('PASS',0)):raise RuntimeError(role+': '+status)
                if kind!='prove':
                    witnesses=[]
                    for trace in (job/'work').glob('engine_*/trace*.vcd'):
                        try:event=witness(trace.read_text(),role)
                        except ValueError:continue
                        witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
                    if not witnesses:raise ValueError('No active RF witness: '+role)
                    receipt['results'][role]['witnesses']=witnesses
                print(role+': '+status,flush=True)
                (out/'result.json').write_text(json.dumps({**receipt,'input_sha256':protected},indent=2)+'\n')
        verify_hashes(protected);receipt['status']='pass (RF controls only; source stability composition unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
