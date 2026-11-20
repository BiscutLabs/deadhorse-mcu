"""Focused independent-reset packet composition diagnostics; never runs CI."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from packet_decompose import ROOT, REVIEWED_HARNESS_SHA256, PROPERTIES, digest, execute, save, validate_job
from packet_partition import lemma_job, cover_job, qualified_assumptions, replace_loads, selected_model, require_lemma
from packet_remaining import names, append_lemma, prepare, bind_position_monitor
from packet_receipt import checked_job, bound_receipt


def bind_upper(base, top, observer):
    """Connect a source-emitted combinational monitor; preserve every DUT bit."""
    result=copy.deepcopy(base);target=result['modules'][top];monitor=observer['modules']['UsbEpochOwnership']
    expected={'clock':1,'reset_n':1,'watching':1,'inPacket':1,'reject':1,'position':5,'queued':5,'packet':4}
    if set(monitor['ports'])!=set(expected):raise ValueError('Unexpected ownership monitor ports')
    if any(c['type'] not in ('$assert','$and','$not','$lt','$add','$mux') for c in monitor['cells'].values()):
        raise ValueError('Ownership observer contains state, assumptions or unknown logic')
    if sum(c['type']=='$assert' for c in monitor['cells'].values())!=1:raise ValueError('Ambiguous ownership assertion')
    input_bits={b for p in monitor['ports'].values() for b in p['bits']};driven=set()
    for c in monitor['cells'].values():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]!='output':continue
            if any(not isinstance(b,int) or b in input_bits or b in driven for b in bits):
                raise ValueError('Monitor drives input or duplicates a driver')
            driven.update(bits)
    used={b for c in target['cells'].values() for bits in c['connections'].values() for b in bits if isinstance(b,int)}
    used|={b for n in target['netnames'].values() for b in n['bits'] if isinstance(b,int)}
    next_bit=max(used)+1;mapping={}
    for name,width in expected.items():
        port=monitor['ports'][name];net='subject.'+('d.reject' if name=='reject' else name)
        bits=target['netnames'][net]['bits']
        if port['direction']!='input' or len(port['bits'])!=width or len(bits)!=width or not all(isinstance(b,int) for b in bits):
            raise ValueError('Wrong ownership monitor binding: '+name)
        for source,destination in zip(port['bits'],bits):
            if source in mapping and mapping[source]!=destination:raise ValueError('Ambiguous monitor alias')
            mapping[source]=destination
    def translated(bits):
        nonlocal next_bit
        values=[]
        for b in bits:
            if isinstance(b,int):
                if b not in mapping:mapping[b]=next_bit;next_bit+=1
                b=mapping[b]
            values.append(b)
        return values
    for name,c in monitor['cells'].items():
        if 'ownership_upper.'+name in target['cells']:raise ValueError('Observer name collision')
        added=copy.deepcopy(c);added['connections']={p:translated(b) for p,b in c['connections'].items()}
        target['cells']['ownership_upper.'+name]=added
    projected=copy.deepcopy(result)
    projected['modules'][top]['cells']={k:c for k,c in target['cells'].items() if not k.startswith('ownership_upper.')}
    if projected!=base:raise ValueError('Ownership monitor altered transition system')
    return result


def bind_occupancy(base, top, observer):
    """Attach only two eight-byte occupancy assertions to exact DUT nets."""
    result=copy.deepcopy(base);target=result['modules'][top]
    monitor=observer['modules']['UsbOutOccupancyLemma']
    expected={'clock':1,'reset_n':1,'head':4,'tail':4,'speculative':4,'reject':1,'queued':5,'packet':4,'appValid':1}
    if set(monitor['ports'])!=set(expected):raise ValueError('Unexpected occupancy ports')
    if any(c['type'] not in ('$assert','$and','$not','$le','$lt','$ge','$add','$sub','$mux') for c in monitor['cells'].values()):
        raise ValueError('Occupancy observer contains state, assumptions or unknown logic')
    if {n for n,c in monitor['cells'].items() if c['type']=='$assert'}!=set(names(2)):
        raise ValueError('Wrong occupancy assertion inventory')
    inputs={b for p in monitor['ports'].values() for b in p['bits']};driven=set()
    for c in monitor['cells'].values():
        for p,bits in c['connections'].items():
            if c['port_directions'][p]!='output':continue
            if any(not isinstance(b,int) or b in inputs or b in driven for b in bits):raise ValueError('Occupancy drives input or duplicate driver')
            driven.update(bits)
    used={b for c in target['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    used|={b for n in target['netnames'].values() for b in n['bits'] if isinstance(b,int)}
    used|={b for p in target['ports'].values() for b in p['bits'] if isinstance(b,int)}
    next_bit=max(used)+1;mapping={}
    for name,width in expected.items():
        net='subject.'+('d.' if name in ('head','tail','speculative','reject','appValid') else '')+name
        port=monitor['ports'][name];bits=target['netnames'][net]['bits']
        if port['direction']!='input' or len(port['bits'])!=width or len(bits)!=width or not all(isinstance(b,int) for b in bits):
            raise ValueError('Wrong occupancy binding: '+name)
        for source,destination in zip(port['bits'],bits):
            if source in mapping and mapping[source]!=destination:raise ValueError('Ambiguous occupancy alias')
            mapping[source]=destination
    def translated(bits):
        nonlocal next_bit
        result=[]
        for b in bits:
            if isinstance(b,int):
                if b not in mapping:mapping[b]=next_bit;next_bit+=1
                b=mapping[b]
            result.append(b)
        return result
    for name,c in monitor['cells'].items():
        key='occupancy.'+name
        if key in target['cells']:raise ValueError('Occupancy name collision')
        added=copy.deepcopy(c);added['connections']={p:translated(b) for p,b in c['connections'].items()}
        target['cells'][key]=added
    projected=copy.deepcopy(result)
    projected['modules'][top]['cells']={k:c for k,c in target['cells'].items() if not k.startswith('occupancy.')}
    if projected!=base:raise ValueError('Occupancy monitor changed transition system')
    return result


def run(output, role, packet_bytes, properties, sparse=False, prior_audit=None, upper=False, occupancy=False):
    if len(set(properties)) != len(properties): raise ValueError('Duplicate original property')
    if occupancy and (role!='out' or packet_bytes!=8 or not sparse or not upper):raise ValueError('Occupancy requires eight-byte sparse OUT with upper observer')
    output = output.resolve(); output.relative_to(ROOT/'build')
    output.mkdir(parents=True, exist_ok=False)
    paths = [ROOT/'hw/ip/usb/formal/UsbBufferFormal.scala', ROOT/'hw/ip/usb/formal/UsbPacketEpoch.scala',
             ROOT/'hw/ip/usb/formal/UsbSparsePacketMemory.scala', ROOT/'hw/ip/usb/formal/UsbOutPositionLemma.scala',
             ROOT/'hw/ip/usb/formal/UsbEpochOwnership.scala',
             ROOT/'hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketBuffer.scala',
             ROOT/'hw/ip/usb/src/main/scala/deadhorse/usb/UsbBitEnable.scala',
             ROOT/'hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketSizing.scala', ROOT/'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',
             Path(__file__), *[Path(__file__).with_name(n+'.py') for n in
                              ('packet_decompose','packet_partition','packet_remaining','packet_receipt')], ROOT/'tools/formal.py']
    if occupancy:paths.append(ROOT/'hw/ip/usb/formal/UsbOutOccupancyLemma.scala')
    bound = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    if digest(paths[0]) != REVIEWED_HARNESS_SHA256: raise ValueError('Original assertions changed')
    receipt = dict(status='running', role=role, packet_bytes=packet_bytes, sparse=sparse, upper=upper, source_sha256=bound, jobs=[], originals=[],
                   commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                   assumptions='Initial root reset only; subsequent root/transport resets and inputs arbitrary. '
                   'IN reads require valid; zero-byte ACK allowed. OUT packet length unrestricted. No E1/E2.',
                   qualification='Independent-reset packet-interface diagnostic; actual SIE producer composition still required.',
                   ci='not run, user instruction')
    if occupancy:receipt['occupancy']=True
    (output/'runner.py').write_bytes(Path(__file__).read_bytes())
    for p in paths:
        target=output/'source'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
    save(output/'result.json',receipt)
    inherited={}
    try:
        if sparse:
            if packet_bytes!=8 or prior_audit is None:raise ValueError('Sparse attempt requires audited eight-byte refinement')
            prior=bound_receipt(prior_audit)
            if prior.get('audit',{}).get('status')!='pass' or prior['packet_bytes']!=8:
                raise ValueError('Missing same-size audited refinement')
            inherited={**prior['inputs'],**prior['audit']['inputs'],str(prior_audit.resolve()):digest(prior_audit)}
            if any(digest(p)!=h for p,h in inherited.items()):raise ValueError('Changed refinement/audit artifact')
            receipt['refinement_audit']=dict(path=str(prior_audit.resolve()),sha256=digest(prior_audit))
        command=[sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbPacketEpoch {output}/emit {role} {packet_bytes} '+('sparse' if sparse else 'real')]
        if sparse:command.append(f'runMain deadhorse.usb.EmitUsbPacketEpoch {output}/real-emit {role} {packet_bytes} real')
        execute(command,output/'emit.log',600).check_returncode(); receipt['emission_command']=command
        hdl=sorted((output/'emit/correct').glob('*.sv')); top='UsbPacketEpochFormal'
        receipt['emitted_sha256']={str(p):digest(p) for p in hdl}
        total=(29 if role=='in' else 27) if sparse else (20 if role=='in' else 19)
        script=output/'prepare.ys'; canonical=output/'canonical.json'
        script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,hdl)),
            f'prep -top {top} -flatten', "fminit -seq reset_n 0,'z", 'async2sync','chformal -lower',
            f'select -assert-count {total} t:$assert', f'write_json {canonical}'])+'\n')
        execute(['yosys','-Q','-T','-s',script],output/'prepare.log').check_returncode()
        model=json.loads(canonical.read_text()); h=digest(canonical)
        n=['subject.'+s for s in names(total)]
        if {k for k,c in model['modules'][top]['cells'].items() if c['type']=='$assert'}!=set(n):
            raise ValueError('Assertion identity inventory changed')
        real=None;rn=None
        if sparse:
            real_hdl=sorted((output/'real-emit/correct').glob('*.sv'))
            receipt['emitted_sha256'].update({str(p):digest(p) for p in real_hdl})
            realpath=output/'real.json';realscript=output/'real.ys'
            realscript.write_text(script.read_text().replace(' '.join(map(str,hdl)),' '.join(map(str,real_hdl)))
                .replace(f'count {total}',f'count {20 if role=="in" else 19}').replace(str(canonical),str(realpath)))
            execute(['yosys','-Q','-T','-s',realscript],output/'real.log').check_returncode()
            real=json.loads(realpath.read_text());rn=['subject.'+s for s in names(20 if role=='in' else 19)]
            if {k for k,c in real['modules'][top]['cells'].items() if c['type']=='$assert'}!=set(rn):
                raise ValueError('Real assertion inventory changed')
            if role=='out':
                execute([sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbOutPositionLemma {output}/position-emit'],
                        output/'position-emit.log',600).check_returncode()
                monitor,_=prepare(output/'position',sorted((output/'position-emit').glob('*.sv')),'UsbOutPositionLemma',1,False)
                def bind_subject(base):
                    aliased=copy.deepcopy(base)
                    for name in monitor['modules']['UsbOutPositionLemma']['ports']:
                        aliased['modules'][top]['netnames'][name]=base['modules'][top]['netnames']['subject.'+name]
                    result=bind_position_monitor(aliased,top,monitor)
                    result['modules'][top]['netnames']=copy.deepcopy(base['modules'][top]['netnames'])
                    projected=copy.deepcopy(result)
                    projected['modules'][top]['cells']={k:c for k,c in projected['modules'][top]['cells'].items() if not k.startswith('position_monitor.')}
                    if projected!=base:raise ValueError('Position monitor changed epoch model')
                    return result
                model=bind_subject(model);real=bind_subject(real)
                if upper:
                    execute([sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbEpochOwnership {output}/upper-emit'],
                            output/'upper-emit.log',600).check_returncode()
                    observer,_=prepare(output/'upper',sorted((output/'upper-emit').glob('*.sv')),'UsbEpochOwnership',1,False)
                    model=bind_upper(model,top,observer);real=bind_upper(real,top,observer)
                if occupancy:
                    execute([sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbOutOccupancyLemma {output}/occupancy-emit'],
                            output/'occupancy-emit.log',600).check_returncode()
                    observer,_=prepare(output/'occupancy',sorted((output/'occupancy-emit').glob('*.sv')),'UsbOutOccupancyLemma',2,False)
                    model=bind_occupancy(model,top,observer);real=bind_occupancy(real,top,observer)
                save(canonical,model);save(realpath,real);h=digest(canonical)
            receipt['real_sha256']=digest(realpath)
        receipt['canonical_sha256']=h
        # This common-reset-only helper is retained in the canonical model but
        # never assumed: CE can occur before the independently reset age is 3.
        receipt['inapplicable_common_reset_helper']=n[0]
        deps=[]
        if sparse:
            chosen=set(n[1:8])|set(n[26:29]) if role=='in' else set(n[1:4])|set(n[21:27])
            receipt['inapplicable_tag_helper']=n[17 if role=='in' else 12]
        else:chosen=set(n[1:8])|{n[18],n[19]} if role=='in' else set(n[1:4])|set(n[14:19])
        mutations=[('subject.d.pending',['1'])] if role=='in' else [('subject.d.tail',['1']+['0']*(packet_bytes.bit_length()-1))]
        real_chosen=(set(rn[1:8])|{rn[18],rn[19]} if role=='in' else set(rn[1:4])|set(rn[14:19])) if sparse else None
        if not append_lemma(output,receipt,model,top,h,'storage-warmup',chosen,deps,mutations,real,top,real_chosen,mutations):
            receipt['status']='unresolved';return receipt
        if sparse:
            groups=[]
            if occupancy:
                # Prove each claim before its exact-model receipt becomes a
                # premise. Real overflow faults have no good-DUT assumptions.
                overflow=[('subject.d.full',['0'])]
                for label,claim in zip(('occupancy-geometry','occupancy-count'),names(2)):
                    groups.append((label,{'occupancy.'+claim},overflow,{'occupancy.'+claim},overflow))
            if role=='out':groups.append(('position',{'position_monitor.assert__chisel3_builtin'},[('subject.d.appValid',['1'])],
                                          {'position_monitor.assert__chisel3_builtin'},[('subject.d.appValid',['1'])]))
            if upper:
                mutation=[('subject.cadence.enable',['1']),('subject.d.reject',['0'])] if occupancy else [('subject.d.reject',['0'])]
                groups.append(('position-upper',{'ownership_upper.assert__chisel3_builtin'},mutation,
                               {'ownership_upper.assert__chisel3_builtin'},mutation))
            ownership=set(n[8:12]) if role=='in' else set(n[4:8])
            real_ownership=set(rn[8:12]) if role=='in' else set(rn[4:8])
            pointer=[('subject.d.speculative',['1']*packet_bytes.bit_length())]
            groups.append(('ownership',ownership,pointer,real_ownership,pointer))
            integrity={rn[14 if role=='in' else 10]};word=[('subject.d.memory.wordData',['0']*8)]
            groups += [('owned-data',set(n[12:17]) if role=='in' else set(n[8:12]),[('subject.d.memory.pendingData',['0']*8)],integrity,word),
                       ('read-pipeline',set(n[18:20]) if role=='in' else set(n[13:15]),[('subject.d.memory.r1',['0']*8)],integrity,word)]
            for label,keep,mutation,real_keep,real_mutation in groups:
                if not append_lemma(output,receipt,model,top,h,label,keep,deps,mutation,real,top,real_keep,real_mutation):
                    receipt['status']='unresolved';return receipt
        offset=(20 if role=='in' else 15) if sparse else (12 if role=='in' else 8)
        for prop in properties:
            assertion=n[offset+PROPERTIES.index(prop)]
            assumed=qualified_assumptions(deps,model,top,h)
            row=dict(property=prop,assertion=assertion,dependencies=copy.deepcopy(deps))
            row['positive']=lemma_job(output/(prop+'-positive'),model,top,{assertion},assumed,
                                     engine='smtbmc z3' if prop=='progress' else 'abc pdr\nsmtbmc z3')
            receipt['originals'].append(row);save(output/'result.json',receipt)
            print(role,prop,row['positive']['solver_status'],flush=True)
            if row['positive']['solver_status']=='FAIL':
                raise ValueError('Reachable original assertion failure: '+prop)
            if row['positive']['result']!='proved':continue
            bad=copy.deepcopy(real if sparse else model)
            valid='subject.d.'+('valid' if role=='in' else 'appValid')
            payload='subject.d.'+('data' if role=='in' else 'appData')
            if prop=='capacity': net,value=('subject.d.appReady',['1']) if role=='in' else (valid,['1'])
            elif prop=='read_nonempty': net,value=valid,['1']
            elif prop in ('integrity','held_data'):net,value=payload,bad['modules'][top]['ports']['data']['bits']
            elif prop=='held_valid':net,value=valid,[bad['modules'][top]['ports']['data']['bits'][0]]
            else:net,value=valid,['0']
            replace_loads(bad,top,net,value);row['mutation']=dict(net=net,value=value)
            fault_assertion=rn[(12 if role=='in' else 8)+PROPERTIES.index(prop)] if sparse else assertion
            row['negative']=lemma_job(output/(prop+'-negative'),bad,top,{fault_assertion},mode='bmc',engine='btor btormc')
            if checked_job(row['positive'],'proof')!=selected_model(model,top,{assertion},assumed):
                raise ValueError('Original proof changed model')
            checked_job(row['negative'],'negative')
        # E3 permits 128-step covers only at the eight-byte configuration.
        if packet_bytes==8 or role=='in':
            receipt['covers']=cover_job(output/'covers',sorted((output/('real-emit' if sparse else 'emit')/'cover').glob('*.sv')),top,
                                        12 if role=='in' else 11,128 if packet_bytes==8 else 48)
        receipt['status']='pass' if (set(properties)==set(PROPERTIES) and
            receipt.get('covers',{}).get('result')=='covered' and all(j['positive']['result']=='proved' and
            j.get('negative',{}).get('result')=='fault_rejected' for j in receipt['originals'])) else 'unresolved'
    except Exception as error: receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(ROOT/p)!=h for p,h in bound.items()):receipt.update(status='failed',error='Source changed during proof')
        if any(digest(p)!=h for p,h in receipt.get('emitted_sha256',{}).items()):
            receipt.update(status='failed',error='Emission changed during proof')
        if receipt.get('canonical_sha256') and digest(output/'canonical.json')!=receipt['canonical_sha256']:
            receipt.update(status='failed',error='Canonical model changed during proof')
        if any(digest(p)!=h for p,h in inherited.items()):receipt.update(status='failed',error='Inherited refinement changed')
        receipt['inherited_sha256']=inherited
        save(output/'result.json',receipt)
    return receipt


def resume_upper(output, prior_path):
    """Repair only an unreachable fault; never rerun the proved upper lemma."""
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    prior_path=prior_path.resolve();prior=json.loads(prior_path.read_text())
    receipt=dict(status='running',role='out',packet_bytes=8,sparse=True,upper=True,jobs=[],originals=[],
        resumed_from=dict(path=str(prior_path),sha256=digest(prior_path)),
        source_sha256=copy.deepcopy(prior['source_sha256']),inherited_sha256=copy.deepcopy(prior['inherited_sha256']),
        ci='not run by user instruction',qualification=prior['qualification'],assumptions=prior['assumptions'])
    receipt['source_sha256'][str(Path(__file__).relative_to(ROOT))]=digest(Path(__file__))
    (output/'runner.py').write_bytes(Path(__file__).read_bytes())
    save(output/'result.json',receipt)
    try:
        if prior['status']!='failed' or not prior['upper'] or prior['role']!='out':raise ValueError('Wrong continuation')
        for p,h in prior['source_sha256'].items():
            source=prior_path.parent/'runner.py' if p==str(Path(__file__).relative_to(ROOT)) else ROOT/p
            if digest(source)!=h:raise ValueError('Changed previous proof source: '+p)
        modelpath=prior_path.parent/'canonical.json';realpath=prior_path.parent/'real.json'
        if digest(modelpath)!=prior['canonical_sha256'] or digest(realpath)!=prior['real_sha256']:
            raise ValueError('Changed previous canonical')
        model=json.loads(modelpath.read_text());real=json.loads(realpath.read_text());top='UsbPacketEpochFormal';h=digest(modelpath)
        save(output/'canonical.json',model);save(output/'real.json',real)
        receipt.update(canonical_sha256=h,real_sha256=digest(realpath),emitted_sha256=prior['emitted_sha256'])
        entry=copy.deepcopy(next(j for j in prior['jobs'] if j['group']=='position-upper'))
        deps=copy.deepcopy(entry['dependencies']);assumed=qualified_assumptions(deps,model,top,h)
        if checked_job(entry['positive'],'proof')!=selected_model(model,top,set(entry['assertions']),assumed):
            raise ValueError('Upper positive differs from the exact canonical')
        mutation=[('subject.cadence.enable',['1']),('subject.d.reject',['0'])]
        entry['mutation']=mutation;entry['fault_qualification']='Joint real cadence/overflow fault; reject-only was not detected within 48 steps.'
        for label,base,key in [('upper-negative',model,'negative'),('upper-real-negative',real,'real_negative')]:
            bad=copy.deepcopy(base)
            for net,value in mutation:replace_loads(bad,top,net,value)
            entry[key]=lemma_job(output/label,bad,top,set(entry['assertions']),mode='bmc',engine='btor btormc')
        path=output/'position-upper-receipt.json';save(path,entry)
        require_lemma(entry,model,top,set(entry['assertions']),h,assumed)
        deps.append(dict(group='position-upper',path=str(path),sha256=digest(path),assertions=entry['assertions']))
        receipt['jobs'].append(entry);save(output/'result.json',receipt)
        n=['subject.'+s for s in names(27)];rn=['subject.'+s for s in names(19)]
        pointer=[('subject.d.speculative',['1']*4)];word=[('subject.d.memory.wordData',['0']*8)]
        groups=[('ownership',set(n[4:8]),pointer,set(rn[4:8]),pointer),
                ('owned-data',set(n[8:12]),[('subject.d.memory.pendingData',['0']*8)],{rn[10]},word),
                ('read-pipeline',set(n[13:15]),[('subject.d.memory.r1',['0']*8)],{rn[10]},word)]
        for label,chosen,mutation,real_chosen,real_mutation in groups:
            if not append_lemma(output,receipt,model,top,h,label,chosen,deps,mutation,real,top,real_chosen,real_mutation):
                receipt['status']='unresolved';return receipt
        assumed=qualified_assumptions(deps,model,top,h)
        row=dict(property='integrity',assertion=n[17],dependencies=copy.deepcopy(deps))
        row['positive']=lemma_job(output/'integrity-positive',model,top,{n[17]},assumed,engine='abc pdr\nsmtbmc z3')
        receipt['originals'].append(row);save(output/'result.json',receipt)
        if row['positive']['result']!='proved':receipt['status']='unresolved';return receipt
        bad=copy.deepcopy(real);replace_loads(bad,top,'subject.d.appData',real['modules'][top]['ports']['data']['bits'])
        row['negative']=lemma_job(output/'integrity-negative',bad,top,{rn[10]},mode='bmc',engine='btor btormc')
        checked_job(row['negative'],'negative')
        if checked_job(row['positive'],'proof')!=selected_model(model,top,{n[17]},assumed):raise ValueError('Changed integrity proof')
        receipt['covers']=cover_job(output/'covers',sorted((prior_path.parent/'real-emit/cover').glob('*.sv')),top,11,128)
        receipt['status']='property-proved' if receipt['covers']['result']=='covered' else 'unresolved'
    except Exception as error:receipt.update(status='failed',error=str(error))
    finally:
        for p,h in receipt['source_sha256'].items():
            if digest(ROOT/p)!=h:receipt.update(status='failed',error='Source changed during continuation')
        for p,h in {**receipt['inherited_sha256'],**receipt.get('emitted_sha256',{})}.items():
            if digest(p)!=h:receipt.update(status='failed',error='Inherited artifact changed')
        save(output/'result.json',receipt)
    return receipt


def audit_epoch(output, paths, anchors):
    """Audit accepted partial claims, without launching a solver or CI."""
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    result=dict(status='running',audit=dict(status='running'),claims=[],inputs={},monitors={},
                auditor_sha256=digest(Path(__file__)),ci='not run by user instruction')
    own=str(Path(__file__).relative_to(ROOT));harness='hw/ip/usb/formal/UsbPacketEpoch.scala'
    try:
        authentic=[]
        for path in anchors:
            path=path.resolve();row=json.loads(path.read_text())
            for p,h in row['source_sha256'].items():
                source=path.parent/'runner.py' if p==own else ROOT/p
                if digest(source)!=h:raise ValueError('Changed emission anchor: '+p)
            for p,h in row['emitted_sha256'].items():
                if digest(p)!=h:raise ValueError('Changed anchor HDL')
            authentic.append(row);result['inputs'][str(path)]=digest(path)
        inventory={(r,p):None for r in ('in','out') for p in PROPERTIES}
        for path in paths:
            path=path.resolve();row=json.loads(path.read_text());result['inputs'][str(path)]=digest(path)
            for p,h in row['source_sha256'].items():
                source=path.parent/'runner.py' if p==own else ROOT/p
                if digest(source)==h:continue
                if p!=harness:raise ValueError('Changed proof source: '+p)
                emitted={Path(p).name:h for p,h in row['emitted_sha256'].items() if '/emit/correct/' in p}
                if not emitted:raise ValueError('Missing historical positive emission')
                if not any(a['role']==row['role'] and a['packet_bytes']==row['packet_bytes'] and
                    any(emitted=={Path(p).name:h for p,h in a['emitted_sha256'].items() if part in p}
                        for part in ('/emit/correct/','/real-emit/correct/')) for a in authentic):
                    raise ValueError('Historical harness differs from current emission')
            for p,h in {**row.get('emitted_sha256',{}),**row.get('inherited_sha256',{})}.items():
                if digest(p)!=h:raise ValueError('Changed bound proof artifact')
            canonical=path.parent/'canonical.json';model=json.loads(canonical.read_text());h=digest(canonical)
            if h!=row['canonical_sha256']:raise ValueError('Changed canonical')
            top='UsbPacketEpochFormal';real=model
            if row.get('sparse'):
                realpath=path.parent/'real.json'
                if digest(realpath)!=row['real_sha256']:raise ValueError('Changed real model')
                real=json.loads(realpath.read_text())
            for job in row['originals']:
                if job['positive']['result']!='proved':continue
                prop=job['property'];role=row['role'];offset=(20 if role=='in' else 15) if row.get('sparse') else (12 if role=='in' else 8)
                assertion='subject.'+names(offset+6)[offset+PROPERTIES.index(prop)]
                if job['assertion']!=assertion:raise ValueError('Original semantic inventory changed')
                assumed=qualified_assumptions(job['dependencies'],model,top,h)
                if checked_job(job['positive'],'proof')!=selected_model(model,top,{assertion},assumed):
                    raise ValueError('Original solver model or assumptions differ')
                bad=copy.deepcopy(real)
                mutation=job.get('mutation')
                if mutation is None:
                    if prop!='integrity':raise ValueError('Unrecorded negative mutation')
                    mutation=dict(net='subject.d.appData',value=real['modules'][top]['ports']['data']['bits'])
                replace_loads(bad,top,mutation['net'],mutation['value'])
                real_offset=12 if role=='in' else 8
                target='subject.'+names(real_offset+6)[real_offset+PROPERTIES.index(prop)]
                if checked_job(job['negative'],'negative')!=selected_model(bad,top,{target},set()):
                    raise ValueError('Real original negative differs or assumes helpers')
                key=(role,prop)
                if inventory[key] is not None:raise ValueError('Duplicate accepted original claim')
                inventory[key]=dict(role=role,property=prop,kind='proved' if row['packet_bytes']==16 else 'proved at small model',
                    packet_bytes=row['packet_bytes'],receipt=str(path),engine=job['positive']['engine'],
                    seconds=job['positive']['seconds'],assumed_assertions=sorted(assumed))
            # Preserve exact observer artifacts too, including continuations.
            directory=path.parent
            if row.get('resumed_from'):directory=Path(row['resumed_from']['path']).parent
            for name in ('position','upper','occupancy'):
                prepared=directory/name/'canonical.json'
                if prepared.exists():
                    result['monitors'][str(prepared)]=digest(prepared)
                    for source in (directory/(name+'-emit')).glob('*.sv'):result['monitors'][str(source)]=digest(source)
            if (directory/'upper/canonical.json').exists():
                observer=json.loads((directory/'upper/canonical.json').read_text())
                base=copy.deepcopy(model)
                base['modules'][top]['cells']={n:c for n,c in base['modules'][top]['cells'].items() if not n.startswith('ownership_upper.')}
                # Occupancy was attached after upper; preserve its allocation
                # when authenticating the earlier observer independently.
                upper_model=copy.deepcopy(model)
                if row.get('occupancy'):
                    for m in (base,upper_model):
                        m['modules'][top]['cells']={n:c for n,c in m['modules'][top]['cells'].items() if not n.startswith('occupancy.')}
                if bind_upper(base,top,observer)!=upper_model:raise ValueError('Upper monitor binding differs')
            if row.get('occupancy'):
                observer=json.loads((directory/'occupancy/canonical.json').read_text())
                base=copy.deepcopy(model)
                base['modules'][top]['cells']={n:c for n,c in base['modules'][top]['cells'].items() if not n.startswith('occupancy.')}
                if bind_occupancy(base,top,observer)!=model:raise ValueError('Occupancy monitor binding differs')
        required={(v['role'],v['packet_bytes']) for v in inventory.values() if v}
        result['covers']=[]
        for role,size in sorted(required):
            candidates=[]
            for path in [*paths,*anchors]:
                row=json.loads(path.read_text())
                if row['role']==role and row['packet_bytes']==size and row.get('covers',{}).get('result')=='covered':
                    candidates.append((path,row))
            if not candidates:raise ValueError('Missing real epoch covers')
            path,row=candidates[-1];cover=row['covers'];directory=Path(cover['directory'])
            hdl=[Path(p) for p in cover['emitted_sha256']]
            for p,h in cover['emitted_sha256'].items():
                if digest(p)!=h:raise ValueError('Changed real cover HDL')
            if row['source_sha256'][harness]!=digest(ROOT/harness):
                hashes={Path(p).name:h for p,h in cover['emitted_sha256'].items()}
                matching=[]
                for anchor in anchors:
                    a=json.loads(anchor.read_text())
                    if a['role']==role and a['packet_bytes']==size:
                        base=anchor.parent/('real-emit' if a.get('sparse') else 'emit')/'cover'
                        matching.append({p.name:digest(p) for p in sorted(base.glob('*.sv'))})
                if hashes not in matching:raise ValueError('Historical cover differs from current emission')
            count=12 if role=='in' else 11;depth=128 if size==8 else 48
            expected='\n'.join(['[options]','mode cover',f'depth {depth}','timeout 120','[engines]','btor btormc',
                '[script]','read_slang --top UsbPacketEpochFormal '+' '.join(p.name for p in hdl),
                'prep -top UsbPacketEpochFormal -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                f'select -assert-count {count} t:$cover','[files]',*map(str,hdl)])+'\n'
            if (directory/'job.sby').read_text()!=expected or digest(directory/'job.sby')!=cover['config_sha256']:
                raise ValueError('Changed epoch cover recipe')
            status=(directory/'job/status').read_text().split()[0]
            if status!=cover['solver_status']:raise ValueError('Changed epoch cover status')
            validate_job(directory/'job','cover',cover['returncode'],status)
            witnesses={str(p):digest(p) for p in (directory/'job').glob('engine_*/*.vcd')}
            if len(witnesses)!=count:raise ValueError('Missing epoch cover witnesses')
            result['covers'].append(dict(role=role,packet_bytes=size,receipt=str(path.resolve()),
                config_sha256=cover['config_sha256'],emitted_sha256=cover['emitted_sha256'],witness_sha256=witnesses,status='pass'))
        result['claims']=[value or dict(role=key[0],property=key[1],kind='unresolved') for key,value in inventory.items()]
        result['audit']['status']='pass';result['status']='pass' if all(inventory.values()) else 'unresolved'
    except Exception as error:result.update(status='failed',error=str(error));result['audit']['status']='failed'
    save(output/'result.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--role',choices=('in','out'))
    p.add_argument('--packet-bytes',type=int,choices=(8,16),default=16)
    p.add_argument('--properties',nargs='+',choices=PROPERTIES,default=PROPERTIES)
    p.add_argument('--sparse',action='store_true');p.add_argument('--prior-audit',type=Path)
    p.add_argument('--upper',action='store_true')
    p.add_argument('--occupancy',action='store_true')
    p.add_argument('--resume-upper',type=Path)
    p.add_argument('--audit-receipts',type=Path,nargs='+');p.add_argument('--anchors',type=Path,nargs='+')
    a=p.parse_args()
    if a.upper and (not a.sparse or a.role!='out'):p.error('--upper requires sparse OUT')
    if not a.role and not a.resume_upper and not a.audit_receipts:p.error('--role, --resume-upper or --audit-receipts required')
    if a.audit_receipts:
        if not a.anchors:p.error('--anchors required for audit')
        r=audit_epoch(a.output,a.audit_receipts,a.anchors)
    else:r=resume_upper(a.output,a.resume_upper) if a.resume_upper else run(a.output,a.role,a.packet_bytes,a.properties,a.sparse,a.prior_audit,a.upper,a.occupancy)
    print(r['status'].upper()+' independent-reset packet '+r.get('role','audit'),flush=True)
    sys.exit(0 if r['status'] in ('pass','property-proved') else 1)
