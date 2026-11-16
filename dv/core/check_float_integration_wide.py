"""Rerun the unchanged F-integration properties with the qualified wide protocol.

Only the FPU module is replaced. Independent anyseq choice inputs are added at
that instance; all other hierarchy objects and property cells are byte-identical.
The original history/reset configuration, fault and cover inventory are kept.
Covers establish abstract-model reachability, not concrete arithmetic traces.
"""
import argparse
import copy
import json
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import digest
from jalr_receipts import combine_hashes, verify_hashes
from qualify_fpu_protocol_wide import protect

TOP='FloatIntegrationFormal'
CHOICES={'io_finish':1,'io_invalidPayload_result':32,'io_invalidPayload_flags':5,
         'io_completionPayload_result':32,'io_completionPayload_flags':5}


def fresh(module):
    bits=[b for c in module['cells'].values() for value in c['connections'].values() for b in value if isinstance(b,int)]
    bits += [b for p in module['ports'].values() for b in p['bits'] if isinstance(b,int)]
    bits += [b for p in module['netnames'].values() for b in p['bits'] if isinstance(b,int)]
    return max(bits)+1


def properties(design):
    return {mn:{n:c for n,c in m['cells'].items() if c['type'] in ('$check','$assert','$assume','$cover')}
            for mn,m in design['modules'].items() if any(c['type'] in ('$check','$assert','$assume','$cover') for c in m['cells'].values())}


def graft(original,abstract):
    result=copy.deepcopy(original)
    instances=[(mn,n,c) for mn,m in result['modules'].items() for n,c in m['cells'].items()
               if c['type'].split('$')[0]=='Fpu']
    if len(instances)!=1:raise ValueError('FPU instance is not unique')
    parent,name,instance=instances[0];module_name=instance['type']
    old=result['modules'][module_name];new=copy.deepcopy(abstract)
    if set(new['ports'])-set(old['ports'])!=set(CHOICES) or not set(old['ports'])<=set(new['ports']):
        raise ValueError('Wide FPU port inventory differs')
    for n,p in old['ports'].items():
        q=new['ports'][n]
        if p['direction']!=q['direction'] or len(p['bits'])!=len(q['bits']):raise ValueError('Existing FPU port changed')
    new['attributes']=copy.deepcopy(old['attributes'])
    result['modules'][module_name]=new;m=result['modules'][parent]
    added=[];start=fresh(m)
    for port,width in CHOICES.items():
        p=new['ports'][port]
        if p['direction']!='input' or len(p['bits'])!=width:raise ValueError('Choice port width changed')
        bits=list(range(start,start+width));start+=width
        key='__wide_choice_'+port
        if key in m['cells'] or key+'_wire' in m['netnames']:raise ValueError('Choice name collision')
        m['cells'][key]=dict(type='$anyseq',parameters={'WIDTH':format(width,'b')},attributes={},
            port_directions={'Y':'output'},connections={'Y':bits})
        m['netnames'][key+'_wire']=dict(bits=bits,attributes={})
        instance['connections'][port]=bits;instance['port_directions'][port]='input';added.append(key)
    # Prove construction changed nothing outside the named replacement boundary.
    restored=copy.deepcopy(result)
    restored['modules'][module_name]=copy.deepcopy(original['modules'][module_name])
    rm=restored['modules'][parent]
    rm['cells'][name]=copy.deepcopy(original['modules'][parent]['cells'][name])
    for key in added:del rm['cells'][key];del rm['netnames'][key+'_wire']
    if restored!=original:raise ValueError('Non-FPU hierarchy changed')
    if properties(result)!=properties(original):raise ValueError('Property inventory/expressions changed')
    return result,dict(parent=parent,instance=name,module=module_name,independent_choices=CHOICES)


def history_and_fault(design,fault):
    design=copy.deepcopy(design);m=design['modules'][TOP]
    bits=m['ports'].pop('checking')['bits'];m['netnames']['checking']['attributes']['init']='0'
    m['cells']['__history']=dict(type='$dff',attributes={},parameters=dict(WIDTH='1',CLK_POLARITY='1'),
        port_directions=dict(CLK='input',D='input',Q='output'),
        connections=dict(CLK=m['ports']['clk_i']['bits'],D=['1'],Q=bits))
    if fault:
        name='floatExecution.io_commitArithmetic';old=m['netnames'][name]['bits']
        cancel=m['netnames']['floatExecution.io_cancel']['bits'];bit=fresh(m)
        for c in m['cells'].values():
            for p,direction in c['port_directions'].items():
                if direction=='input':c['connections'][p]=[bit if b==old[0] else b for b in c['connections'][p]]
        m['netnames'][name]['bits']=[bit]
        m['cells']['__fault_commit']=dict(type='$or',attributes={},
            parameters=dict(A_SIGNED='0',B_SIGNED='0',A_WIDTH='1',B_WIDTH='1',Y_WIDTH='1'),
            port_directions=dict(A='input',B='input',Y='output'),connections=dict(A=old,B=cancel,Y=[bit]))
    return design


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',default='build/t13/formal-pdr')
    ap.add_argument('--qualification',default='build/t13/fpu-protocol-wide-qualified')
    ap.add_argument('--output',required=True);ap.add_argument('--prepare-only',action='store_true')
    args=ap.parse_args();base=local(args.baseline);qualified=local(args.qualification);out=output_dir(args.output)
    receipt=dict(status='running',scope='unchanged 28 integration safety assertions and eight abstract covers; ISA unresolved',results={});protected={}
    try:
        raw=qualified/'result.json';proof=json.loads(raw.read_text())
        if proof['status']!='pass (all-port FPU protocol trace inclusion); integration safety and ISA reruns pending':
            raise ValueError('Wide model trace inclusion unavailable')
        for role in ('base','control-step','outputs','step','no-instant-completion'):
            if proof['results'][role]['status']!='proved' or proof['results'][role+'-negative']['status']!='rejected':
                raise ValueError('Wide trace inclusion incomplete')
        protected=dict(proof['input_sha256'])
        protect(protected,[raw,Path(__file__),ROOT/'dv/core/qualify_fpu_protocol_wide.py',
            ROOT/'dv/core/common.py',ROOT/'dv/core/jalr_invariant.py',ROOT/'dv/core/jalr_receipts.py'])
        prior_path=base/'result.json';prior=json.loads(prior_path.read_text())
        if prior['status']!='pass':raise ValueError('Historical integration receipt incomplete')
        protect(protected,[prior_path])
        for name,value in prior['production_sha256'].items():
            p=local(name)
            if digest(p)!=value:raise ValueError('Historical bound production source changed')
            protect(protected,[p])
        binding=base/'normal/binding/result.json';binding_data=json.loads(binding.read_text())
        if binding_data['status']!='proved':raise ValueError('Historical production binding incomplete')
        protect(protected,[binding,local(binding_data['gold']),local(binding_data['candidate']),base/'normal/binding/compare.log'])
        abstract_path=qualified/'abstract.json'
        if str(abstract_path) not in protected:raise ValueError('Unauthenticated abstract netlist')
        abstract=json.loads(abstract_path.read_text())['modules']['Fpu']
        concrete_fpu=local('build/t13/exponent/candidate/Fpu.sv')
        if str(concrete_fpu) not in protected:raise ValueError('Missing qualified production FPU')
        receipt.update(timeout_seconds=120,assumptions=prior['assumptions'],
            qualification=dict(path=str(raw),sha256=digest(raw)),
            covers='eight original integration covers on the abstract model; concrete T12/lockstep and ISA covers remain distinct')
        for role in ('normal','fault','cover'):
            job=output_dir(out/role);emitted=base/role/'emit';sources=sorted(emitted.glob('*.sv'))
            old_prepared=base/role/'prepared.json';old_config=base/role/'check.sby'
            protect(protected,[*sources,old_prepared,old_config])
            if digest(emitted/'Fpu.sv')!=protected[str(concrete_fpu)]:raise ValueError('Scenario FPU differs from qualified concrete module')
            # Rebuild the original flat model exactly before changing hierarchy.
            reproduced=job/'original.json';reproduce=job/'original.ys'
            reproduce.write_text('read_slang --top '+TOP+' '+' '.join(map(str,sources))+
                f'\nprep -top {TOP} -flatten\nwrite_json {reproduced}\n')
            protect(protected,[reproduce]);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',reproduce],job,'original',timeout=120)
            verify_hashes(protected)
            if json.loads(reproduced.read_text())!=json.loads(old_prepared.read_text()):raise ValueError('Original scenario preparation changed')
            protect(protected,[reproduced])
            hierarchy=job/'hierarchy.json';ys=job/'hierarchy.ys'
            ys.write_text('read_slang --keep-hierarchy --top '+TOP+' '+' '.join(map(str,sources))+f'\nwrite_json {hierarchy}\n')
            protect(protected,[ys]);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',ys],job,'hierarchy',timeout=120)
            verify_hashes(protected);protect(protected,[hierarchy])
            original=json.loads(hierarchy.read_text());modified,changes=graft(original,abstract)
            grafted=job/'grafted.json';grafted.write_text(json.dumps(modified));flatten=job/'flatten.ys';flat=job/'flat.json'
            flatten.write_text(f'read_json {grafted}\nprep -top {TOP} -flatten\nwrite_json {flat}\n')
            protect(protected,[grafted,flatten]);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',flatten],job,'flatten',timeout=120)
            verify_hashes(protected);protect(protected,[flat])
            model=json.loads(flat.read_text());kinds={}
            for c in model['modules'][TOP]['cells'].values():
                if c['type']=='$check':
                    key=c['parameters']['FLAVOR'];kinds[key]=kinds.get(key,0)+1
            expected={'cover':8} if role=='cover' else {'assert':28}
            if kinds!=expected:raise ValueError('Original property counts changed')
            checked=job/'checked.json';checked.write_text(json.dumps(history_and_fault(model,role=='fault')))
            config=job/'check.sby';text=old_config.read_text()
            old_model=base/role/'checked.json'
            if text.count(str(old_model))!=1 or 'timeout 120' not in text:raise ValueError('Original configuration changed')
            config.write_text(text.replace(str(old_model),str(checked)))
            protect(protected,[checked,config]);verify_hashes(protected)
            receipt['results'][role]=dict(status='prepared',properties=kinds,changes=changes)
            if args.prepare_only:continue
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            status=job/'work/status';actual=status.read_text().split()[0]
            expected_status=('FAIL',2) if role=='fault' else ('PASS',0)
            receipt['results'][role].update(status=actual,returncode=result.returncode,seconds=result.elapsed_seconds,
                kind='unbounded safety proof' if role=='normal' else 'fault rejected' if role=='fault' else 'abstract model reachability')
            protect(protected,[status]);verify_hashes(protected)
            if (actual,result.returncode)!=expected_status:raise ValueError(role+': '+actual)
            if role!='normal':
                traces=list((job/'work').glob('engine_*/trace*.vcd'))
                if not traces:raise ValueError('Missing fault/cover witness')
                protect(protected,traces)
                receipt['results'][role]['witnesses']=[dict(path=str(p),sha256=digest(p)) for p in traces]
            print(role+': '+actual,flush=True)
        verify_hashes(protected)
        receipt['status']='prepared; no safety or cover run' if args.prepare_only else 'pass (28 integration safety assertions; eight abstract covers); ISA unresolved'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
