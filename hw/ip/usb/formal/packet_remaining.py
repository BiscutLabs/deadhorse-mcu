"""Focused remaining packet claims; no CI, new environment or changed cap."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from packet_decompose import ROOT, REVIEWED_HARNESS_SHA256, digest, execute, save, fault
from packet_partition import (lemma_job, cover_job, predicate_hash, replace_loads,
                              qualified_assumptions, require_lemma, selected_model)
from packet_receipt import bound_receipt, checked_job


def names(count):
    return ['assert__chisel3_builtin', *(f'assert__chisel3_builtin_{i}' for i in range(count-1))]


def prepare(directory, hdl, top, count, initial_reset=True):
    directory.mkdir()
    model = directory/'canonical.json'; script = directory/'prepare.ys'
    script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str, hdl)),
        f'prep -top {top} -flatten', *(["fminit -seq reset_n 0,'z"] if initial_reset else []), 'async2sync', 'chformal -lower',
        *([] if initial_reset else ['chformal -early','opt_clean']),
        f'select -assert-count {count} t:$assert', f'write_json {model}'])+'\n')
    execute(['yosys', '-Q', '-T', '-s', script], directory/'prepare.log').check_returncode()
    result = json.loads(model.read_text())
    if {n for n,c in result['modules'][top]['cells'].items() if c['type']=='$assert'} != set(names(count)):
        raise ValueError('Assertion inventory changed; semantic review required')
    return result, digest(model)


def bind_position_monitor(base, top, monitor):
    """Add only a source-emitted combinational assertion, no state/assumptions."""
    result=copy.deepcopy(base);target=result['modules'][top]
    observer=monitor['modules']['UsbOutPositionLemma']
    expected={'clock':1,'reset_n':1,'watching':1,'inPacket':1,'position':5,'queued':5}
    if set(observer['ports'])!=set(expected):raise ValueError('Unexpected monitor ports')
    if any(c['type'] not in ('$assert','$and','$ge','$mux') for c in observer['cells'].values()):
        raise ValueError('Position monitor must be combinational and assumption-free')
    if sum(c['type']=='$assert' for c in observer['cells'].values())!=1:
        raise ValueError('Missing/ambiguous position assertion')
    input_bits={b for p in observer['ports'].values() for b in p['bits']}
    driven=set()
    for cell in observer['cells'].values():
        for port,bits in cell['connections'].items():
            if cell['port_directions'][port]!='output':continue
            if any(not isinstance(b,int) or b in input_bits or b in driven for b in bits):
                raise ValueError('Monitor drives a bound input or has multiple drivers')
            driven.update(bits)
    validate_position_predicate(observer)
    allocated={b for c in target['cells'].values() for bits in c['connections'].values() for b in bits if isinstance(b,int)}
    allocated|={b for n in target['netnames'].values() for b in n['bits'] if isinstance(b,int)}
    mapping={};next_bit=max(allocated)+1
    for name,width in expected.items():
        port=observer['ports'][name];bits=target['netnames'][name]['bits']
        if port['direction']!='input' or len(port['bits'])!=width or len(bits)!=width or not all(isinstance(b,int) for b in bits):
            raise ValueError('Wrong position-monitor binding: '+name)
        for source,destination in zip(port['bits'],bits):
            if source in mapping and mapping[source]!=destination:raise ValueError('Aliased monitor port')
            mapping[source]=destination
    def translate(bits):
        nonlocal next_bit
        translated=[]
        for bit in bits:
            if isinstance(bit,int):
                if bit not in mapping:mapping[bit]=next_bit;next_bit+=1
                translated.append(mapping[bit])
            else:translated.append(bit)
        return translated
    for name,cell in observer['cells'].items():
        added=copy.deepcopy(cell);added['connections']={p:translate(b) for p,b in cell['connections'].items()}
        if 'position_monitor.'+name in target['cells']:raise ValueError('Monitor cell collision')
        target['cells']['position_monitor.'+name]=added
    # Removing the newly emitted monitor must reproduce the exact old model.
    projected=copy.deepcopy(result)
    projected['modules'][top]['cells']={n:c for n,c in target['cells'].items() if not n.startswith('position_monitor.')}
    if projected!=base:raise ValueError('Monitor altered the DUT/original assertions')
    return result


def validate_position_predicate(observer):
    """Check exact predicate after removing only formal sampling stages."""
    ports=observer['ports'];cells=list(observer['cells'].values())
    assertions=[c for c in cells if c['type']=='$assert'];comparisons=[c for c in cells if c['type']=='$ge']
    if len(assertions)!=1 or len(comparisons)!=1:raise ValueError('Ambiguous position predicate')
    compare=comparisons[0];con=compare['connections'];params=compare['parameters']
    if (con['A']!=ports['position']['bits'] or con['B']!=ports['queued']['bits'] or
        int(params['A_SIGNED'],2)!=0 or int(params['B_SIGNED'],2)!=0 or
        int(params['A_WIDTH'],2)!=5 or int(params['B_WIDTH'],2)!=5 or
        assertions[0]['connections']['A']!=con['Y']):
        raise ValueError('Wrong position predicate or unsigned width')
    leaves={tuple(ports[n]['bits']):n for n in ('reset_n','watching','inPacket')}
    visited=set()
    def factors(bits):
        key=tuple(bits)
        if key in leaves:return {leaves[key]}
        if key in visited:raise ValueError('Cyclic position guard')
        visited.add(key)
        drivers=[c for c in cells if c['connections'].get('Y')==bits]
        if len(drivers)!=1:raise ValueError('Ambiguous position guard')
        c=drivers[0];p=c['connections']
        if c['type']=='$and' and len(p['Y'])==1:return factors(p['A'])|factors(p['B'])
        if c['type']=='$mux' and p['A']==['0'] and p['B']==['1']:return factors(p['S'])
        raise ValueError('Changed reset/selection guard')
    if factors(assertions[0]['connections']['EN'])!={'reset_n','watching','inPacket'}:
        raise ValueError('Missing reset/selection guard')


def append_lemma(output, receipt, model, top, canonical_hash, label, chosen, dependencies,
                 mutation, real=None, real_top=None, real_chosen=None, real_mutation=None):
    assumed = qualified_assumptions(dependencies, model, top, canonical_hash)
    entry = dict(group=label, canonical_model_sha256=canonical_hash, assertions=sorted(chosen),
                 predicate_sha256=predicate_hash(model,top,chosen), dependencies=list(dependencies))
    entry['positive'] = lemma_job(output/(label+'-positive'), model, top, chosen, assumed,
                                  engine='abc pdr\nsmtbmc z3')
    if entry['positive']['result']=='proved':
        bad = copy.deepcopy(model)
        for net,value in mutation: replace_loads(bad,top,net,value)
        entry['mutation'] = mutation
        entry['negative'] = lemma_job(output/(label+'-negative'),bad,top,chosen,
                                      mode='bmc',engine='btor btormc')
        if real is None:
            entry['real_negative'] = entry['negative']  # Positive and fault use production RAM.
        else:
            bad = copy.deepcopy(real)
            for net,value in real_mutation: replace_loads(bad,real_top,net,value)
            entry['real_negative'] = lemma_job(output/(label+'-real-negative'),bad,real_top,real_chosen,
                                               mode='bmc',engine='btor btormc')
    receipt['jobs'].append(entry); save(output/'result.json',receipt)
    print(label,entry['positive']['solver_status'],flush=True)
    if entry['positive']['result']!='proved': return False
    # Only serialized, authenticated, exact-model PASS results become premises.
    path = output/(label+'-receipt.json'); save(path,entry)
    require_lemma(json.loads(path.read_text()),model,top,chosen,canonical_hash,assumed)
    dependencies.append(dict(group=label,path=str(path),sha256=digest(path),assertions=sorted(chosen)))
    return True


def original(output, receipt, model, top, canonical_hash, prop, assertion, dependencies,
             real=None, real_top=None, real_assertion=None):
    assumed = qualified_assumptions(dependencies,model,top,canonical_hash)
    row = dict(property=prop, assertion=assertion, canonical_model_sha256=canonical_hash,
               dependencies=list(dependencies))
    row['positive'] = lemma_job(output/(prop+'-positive'),model,top,{assertion},assumed,
                                engine='smtbmc z3' if prop=='progress' else 'abc pdr\nsmtbmc z3')
    if row['positive']['solver_status']=='FAIL':
        receipt['original']=row;save(output/'result.json',receipt)
        raise ValueError('Original assertion has a reachable counterexample')
    if row['positive']['result']=='proved':
        bad = copy.deepcopy(real if real is not None else model)
        target_top = real_top or top; target_assertion = real_assertion or assertion
        row['mutation'] = fault(bad,target_top,'in' if prop=='progress' else 'out',prop)
        row['negative'] = lemma_job(output/(prop+'-negative'),bad,target_top,{target_assertion},
                                    mode='bmc',engine='btor btormc')
        actual = checked_job(row['positive'],'proof')
        if actual != selected_model(model,top,{assertion},assumed):
            raise ValueError('Original proof changed model or assumptions')
        checked_job(row['negative'],'negative')
    receipt['original'] = row; save(output/'result.json',receipt)
    print(prop,row['positive']['solver_status'],flush=True)
    return row['positive']['result']=='proved' and row.get('negative',{}).get('result')=='fault_rejected'


def run(output, role, prior_path=None, position_bridge=False):
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    if digest(ROOT/'hw/ip/usb/formal/UsbBufferFormal.scala') != REVIEWED_HARNESS_SHA256:
        raise ValueError('Original assertion semantic mapping changed')
    production = ['hw/ip/usb/formal/UsbBufferFormal.scala','hw/ip/usb/formal/UsbSparsePacketMemory.scala',
        'hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketBuffer.scala',
        'hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketSizing.scala',
        'hw/ip/usb/src/main/scala/deadhorse/usb/UsbBitEnable.scala']
    flows = [Path(__file__),ROOT/'hw/ip/usb/formal/packet_partition.py',ROOT/'hw/ip/usb/formal/packet_decompose.py',
             ROOT/'hw/ip/usb/formal/packet_receipt.py',ROOT/'tools/formal.py']
    bound = {p:digest(ROOT/p) for p in production}
    if role=='in': bound['hw/ip/usb/formal/UsbPacketProgress.scala']=digest(ROOT/'hw/ip/usb/formal/UsbPacketProgress.scala')
    if position_bridge:bound['hw/ip/usb/formal/UsbOutPositionLemma.scala']=digest(ROOT/'hw/ip/usb/formal/UsbOutPositionLemma.scala')
    receipt = dict(status='running',role=role,packet_bytes=16 if role=='in' else 8,jobs=[],source_sha256=bound,
        flow_sha256={str(p.relative_to(ROOT)):digest(p) for p in flows},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        assumptions='Original common-reset packet harness, arbitrary later reset. No E1/E2. Only proved exact-model helpers.',
        ci='not run by user instruction')
    (output/'runner.py').write_bytes(Path(__file__).read_bytes());save(output/'result.json',receipt)
    frozen={}
    try:
        if role=='in':
            top='UsbInProgressFormal'
            command=[sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbPacketProgress {output}/emit 16']
            execute(command,output/'emit.log',600).check_returncode();receipt['emission_command']=command
            hdl=sorted((output/'emit/correct').glob('*.sv'))
            receipt['emitted_sha256']={str(p):digest(p) for p in hdl}
            model,h=prepare(output/'model',hdl,top,19);receipt['canonical_sha256']=h
            frozen[str(output/'model/canonical.json')]=h
            receipt['cover']=cover_job(output/'covers',sorted((output/'emit/cover').glob('*.sv')),top,5,48)
            if receipt['cover']['result']!='covered':raise ValueError('Real IN covers did not close')
            n=names(19);deps=[]
            # Existing storage predicates plus the newly asserted ownership fact.
            chosen=set(n[:8])|{n[18]}
            if append_lemma(output,receipt,model,top,h,'storage-pending',chosen,deps,[('d.pending',['1'])]):
                receipt['status']='pass' if original(output,receipt,model,top,h,'progress',n[17],deps) else 'unresolved'
            else: receipt['status']='unresolved'
            receipt['qualification']='Real production-size RAM/control; original service assertion unchanged.'
        else:
            if prior_path is None:raise ValueError('OUT requires audited small-model receipt')
            prior_path=prior_path.resolve();prior=bound_receipt(prior_path)
            if prior.get('audit',{}).get('status')!='pass' or prior['packet_bytes']!=8:
                raise ValueError('Missing audited small-model refinement/covers')
            frozen.update(prior['audit']['inputs']);frozen.update(prior['inputs'])
            frozen[str(prior_path)]=digest(prior_path)
            for p,h in frozen.items():
                if digest(p)!=h:raise ValueError('Changed inherited audit input: '+p)
            receipt['prior_audit']=dict(path=str(prior_path),sha256=digest(prior_path))
            helper_paths=[Path(p) for p in prior['inputs'] if Path(p).parent.name=='packet-small-originals-01']
            if len(helper_paths)!=1:raise ValueError('Ambiguous prior exact-model chain')
            helper_path=helper_paths[0]
            if digest(helper_path)!=prior['inputs'][str(helper_path)]:raise ValueError('Changed helper receipt')
            chain=bound_receipt(helper_path);info=chain['roles']['out'];top='UsbOutFormal'
            canonical=Path(info['canonical']);real_path=canonical.parent/'real.json'
            if digest(canonical)!=info['model_sha256'] or digest(real_path)!=info['real_model_sha256']:
                raise ValueError('Changed canonical/real model')
            for p,h in {**info['emitted_sha256'],**info['real_emitted_sha256']}.items():
                if digest(p)!=h:raise ValueError('Changed emission')
            model=json.loads(canonical.read_text());real=json.loads(real_path.read_text());h=info['model_sha256']
            deps=copy.deepcopy(next(j for j in chain['jobs'] if j.get('property')=='integrity' and j['role']=='out')['dependencies'])
            qualified_assumptions(deps,model,top,h)
            frozen[str(canonical)]=h;frozen[str(real_path)]=info['real_model_sha256']
            frozen.update(info['emitted_sha256']);frozen.update(info['real_emitted_sha256'])
            receipt['canonical_sha256']=h;receipt['initial_dependencies']=copy.deepcopy(deps)
            n=names(21);rn=names(14)
            if position_bridge:
                command=[sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbOutPositionLemma {output}/monitor-emit']
                execute(command,output/'monitor-emit.log',600).check_returncode()
                hdl=sorted((output/'monitor-emit').glob('*.sv'))
                frozen.update({str(p):digest(p) for p in hdl})
                monitor,mh=prepare(output/'monitor',hdl,'UsbOutPositionLemma',1,False)
                frozen[str(output/'monitor/canonical.json')]=mh
                model=bind_position_monitor(model,top,monitor);real=bind_position_monitor(real,top,monitor)
                save(output/'canonical.json',model);save(output/'real.json',real)
                h=digest(output/'canonical.json');frozen[str(output/'canonical.json')]=h
                frozen[str(output/'real.json')]=digest(output/'real.json')
                receipt['monitor_binding']=dict(command=command,monitor_sha256=mh,
                    original_model_sha256=info['model_sha256'],canonical_model_sha256=h,
                    statement='watching && inPacket implies position >= queued',
                    qualification='Original transition system/assertions unchanged; monitor adds no state or assumptions.')
                receipt['canonical_sha256']=h;deps=[]
                # All premises reprove on this identical augmented canonical hash.
                extra='position_monitor.assert__chisel3_builtin'
                controls=[('storage',set(n[:4])|{n[12]},[('d.tail',['1','0','0','0'])],set(rn[:4])),
                          ('position-lower',{extra},[('d.appValid',['1'])],{extra}),
                          ('ownership',set(n[4:8]),[('d.speculative',['1']*4)],set(rn[4:8]))]
                for label,chosen,mutation,real_chosen in controls:
                    if not append_lemma(output,receipt,model,top,h,label,chosen,deps,mutation,
                                        real,top,real_chosen,mutation):
                        receipt['status']='unresolved';return receipt
            real_mutation=[('d.memory.wordData',['0']*8)]
            # The four storage-lifetime facts are mutually inductive. Read-stage
            # reachability is a separate obligation, including rejected packets.
            groups=[('owned-data',set(n[8:12]),[('d.memory.pendingData',['0']*8)]),
                    ('read-pipeline',set(n[13:15]),[('d.memory.r1',['0']*8)])]
            for label,chosen,mutation in groups:
                if not append_lemma(output,receipt,model,top,h,label,chosen,deps,mutation,
                                    real,top,{rn[10]},real_mutation):
                    receipt['status']='unresolved';break
            else:
                receipt['status']='pass' if original(output,receipt,model,top,h,'integrity',n[17],deps,
                                                       real,top,rn[10]) else 'unresolved'
            receipt['qualification']='Small eight-byte sparse model; inherited audited refinement and real covers. No full-size proof claim.'
        for dep in receipt.get('original',{}).get('dependencies',[]):
            if digest(dep['path'])!=dep['sha256']:raise ValueError('Changed dependency')
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(ROOT/p)!=h for p,h in {**bound,**receipt['flow_sha256']}.items()):
            receipt.update(status='failed',error='Proof inputs changed during focused run')
        frozen.update(receipt.get('emitted_sha256',{}))
        if any(digest(p)!=h for p,h in frozen.items()):
            receipt.update(status='failed',error='Inherited/emitted/canonical artifact changed')
        receipt['artifact_sha256']=frozen
        save(output/'result.json',receipt)
    return receipt


def audit_focused(output, path):
    """Recheck finished proof artifacts, without invoking any solver or CI."""
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    path=path.resolve();path.relative_to(ROOT/'build');result=json.loads(path.read_text())
    audit=dict(status='running',receipt=dict(path=str(path),sha256=digest(path)),
               auditor_sha256=digest(Path(__file__)),jobs=[])
    try:
        if result['status']!='pass':raise ValueError('Original claim remains unresolved')
        for p,h in result['source_sha256'].items():
            if digest(ROOT/p)!=h:raise ValueError('Changed proof source: '+p)
        for p,h in result['flow_sha256'].items():
            current=path.parent/'runner.py' if p==str(Path(__file__).relative_to(ROOT)) else ROOT/p
            if digest(current)!=h:raise ValueError('Changed archived/current flow: '+p)
        for p,h in {**result.get('artifact_sha256',{}),**result.get('emitted_sha256',{})}.items():
            if digest(p)!=h:raise ValueError('Changed evidence: '+p)
        role=result['role'];top='UsbInProgressFormal' if role=='in' else 'UsbOutFormal'
        canonical=path.parent/('model/canonical.json' if role=='in' else 'canonical.json')
        model=json.loads(canonical.read_text());h=digest(canonical)
        if h!=result['canonical_sha256']:raise ValueError('Changed canonical model')
        if role=='in':
            cover=result['cover'];directory=Path(cover['directory'])
            for p,expected in cover['emitted_sha256'].items():
                if digest(p)!=expected:raise ValueError('Changed IN cover emission')
            if digest(directory/'job.sby')!=cover['config_sha256']:raise ValueError('Changed cover recipe')
            from packet_decompose import validate_job
            validate_job(directory/'job','cover',cover['returncode'],(directory/'job/status').read_text().split()[0])
        else:
            prior_path=Path(result['prior_audit']['path'])
            if digest(prior_path)!=result['prior_audit']['sha256']:raise ValueError('Changed memory/cover audit')
            prior=bound_receipt(prior_path)
            if prior.get('audit',{}).get('status')!='pass':raise ValueError('Memory/cover audit not qualified')
            chain_path=next(Path(p) for p in prior['inputs'] if Path(p).parent.name=='packet-small-originals-01')
            chain=bound_receipt(chain_path);info=chain['roles']['out']
            base=json.loads(Path(info['canonical']).read_text())
            real=json.loads((Path(info['canonical']).parent/'real.json').read_text())
            monitor=json.loads((path.parent/'monitor/canonical.json').read_text())
            if bind_position_monitor(base,top,monitor)!=model:raise ValueError('Sparse monitor binding changed')
            if bind_position_monitor(real,top,monitor)!=json.loads((path.parent/'real.json').read_text()):
                raise ValueError('Real monitor binding changed')
        for entry in result['jobs']:
            assumed=qualified_assumptions(entry['dependencies'],model,top,h)
            require_lemma(entry,model,top,set(entry['assertions']),h,assumed)
            audit['jobs'].append(dict(group=entry['group'],status='pass'))
        original=result['original'];assumed=qualified_assumptions(original['dependencies'],model,top,h)
        if checked_job(original['positive'],'proof')!=selected_model(model,top,{original['assertion']},assumed):
            raise ValueError('Original assertion/model mismatch')
        checked_job(original['negative'],'negative')
        audit.update(status='pass',role=role,packet_bytes=result['packet_bytes'],
                     property=original['property'],assumed_assertions=sorted(assumed),
                     qualification=result['qualification'])
    except Exception as error:audit.update(status='failed',error=str(error))
    save(output/'result.json',audit)
    return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--role',choices=('in','out'))
    parser.add_argument('--prior-audit',type=Path)
    parser.add_argument('--position-bridge',action='store_true')
    parser.add_argument('--audit-result',type=Path)
    args=parser.parse_args()
    if args.audit_result:result=audit_focused(args.output,args.audit_result)
    else:
        if not args.role or args.position_bridge and args.role!='out':parser.error('Choose IN or OUT; position bridge is OUT-only')
        result=run(args.output,args.role,args.prior_audit,args.position_bridge)
    print(result['status'].upper()+' focused packet '+(args.role or 'audit'),flush=True)
    sys.exit(0 if result['status']=='pass' else 1)
