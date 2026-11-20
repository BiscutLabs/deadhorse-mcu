"""D52 one-attempt exhaustive partition of the unchanged packet assertions."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from packet_decompose import digest, execute, save, fault, PROPERTIES, validate_job, REVIEWED_HARNESS_SHA256


def predicate_hash(model,top,names):
    cells=model['modules'][top]['cells']
    return hashlib.sha256(json.dumps({n:cells[n]['connections'] for n in sorted(names)},sort_keys=True).encode()).hexdigest()


def selected_model(model,top,keep,assumed):
    result=copy.deepcopy(model);cells=result['modules'][top]['cells']
    actual={n for n,c in cells.items() if c['type']=='$assert'}
    if not keep or keep & assumed or not (keep|assumed)<=actual:
        raise ValueError('Missing/overlapping assertion partition')
    for n in actual-keep:
        if n in assumed:cells[n]['type']='$assume' # Preserve both A and EN, including reset guards.
        else:del cells[n]
    return result


def lemma_job(directory,canonical,top,keep,assumed=(),mode='prove',engine='abc pdr'):
    directory.mkdir()
    model=directory/'model.json';save(model,selected_model(canonical,top,set(keep),set(assumed)))
    config=directory/'job.sby'
    config.write_text('\n'.join(['[options]',f'mode {mode}','depth 48','timeout 120',
        '[engines]',engine,'[script]',f'read_json {model.name}',f'hierarchy -check -top {top}',
        f'select -assert-count {len(keep)} t:$assert','opt_clean -purge',
        'write_json ../model/reduced.json','stat -width','[files]',str(model.resolve())])+'\n')
    started=time.monotonic()
    try:
        process=execute(['sby','-d',directory/'job',config],directory/'run.log',180)
        statusfile=directory/'job/status'
        status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
        rc=process.returncode
    except subprocess.TimeoutExpired:
        status='TIMEOUT';rc=None
    row=dict(mode=mode,engine=engine,depth=48,cap_seconds=120,seconds=time.monotonic()-started,
        solver_status=status,returncode=rc,result='unresolved' if status in ('TIMEOUT','UNKNOWN') else 'failed',
        directory=str(directory),model_sha256=digest(model),config_sha256=digest(config),
        assertions=sorted(keep),assumed_assertions=sorted(assumed))
    if (mode=='prove' and status=='PASS') or (mode=='bmc' and status=='FAIL'):
        validate_job(directory/'job','proof' if mode=='prove' else 'negative',rc,status)
        row['result']='proved' if mode=='prove' else 'fault_rejected'
    return row


def require_lemma(entry,model,top,names,canonical_hash,expected_assumptions=()):
    if (entry.get('canonical_model_sha256')!=canonical_hash or
        set(entry.get('assertions',[]))!=set(names) or
        entry.get('predicate_sha256')!=predicate_hash(model,top,names)):
        raise ValueError('Lemma model/predicate identity mismatch')
    proof=entry.get('positive',{});negative=entry.get('negative',{})
    if (proof.get('result')!='proved' or proof.get('mode')!='prove' or proof.get('solver_status')!='PASS' or
        proof.get('returncode')!=0 or negative.get('result')!='fault_rejected'):
        raise ValueError('Lemma has no qualified unbounded PASS receipt')
    if set(proof.get('assumed_assertions',[]))!=set(expected_assumptions):
        raise ValueError('Lemma uses unproved or circular assumptions')
    if entry.get('real_negative',{}).get('result')!='fault_rejected':
        raise ValueError('Missing real-model helper fault')
    for job,kind in ((proof,'proof'),(negative,'negative'),(entry['real_negative'],'negative')):
        path=Path(job['directory'])
        if digest(path/'model.json')!=job['model_sha256'] or digest(path/'job.sby')!=job['config_sha256']:
            raise ValueError('Lemma artifact changed')
        if digest(path/'job/src/model.json')!=job['model_sha256'] or (path/'job/status').read_text().split()[0]!=job['solver_status']:
            raise ValueError('Lemma solver input/status changed')
        validate_job(path/'job',kind,job['returncode'],job['solver_status'])
    expected=selected_model(model,top,set(names),set(proof['assumed_assertions']))
    actual=json.loads((Path(proof['directory'])/'model.json').read_text())
    if actual!=expected:raise ValueError('Lemma proof used a different transition system or assumptions')


def qualified_assumptions(dependencies,model,top,canonical_hash):
    proved=set()
    for dependency in dependencies:
        path=Path(dependency['path'])
        if not path.is_file() or digest(path)!=dependency['sha256']:
            raise ValueError('Missing/changed lemma receipt')
        entry=json.loads(path.read_text())
        names=set(dependency['assertions'])
        require_lemma(entry,model,top,names,canonical_hash,proved)
        proved|=names
    return proved


def replace_loads(model,top,net,value):
    module=model['modules'][top];old=module['netnames'][net]['bits']
    if len(old)!=len(value) or not all(isinstance(b,int) for b in old):raise ValueError('Ambiguous helper fault')
    mapping=dict(zip(old,value));changed=0
    for cell in module['cells'].values():
        for p,bits in cell['connections'].items():
            if cell['port_directions'][p]=='input':
                new=[mapping.get(b,b) for b in bits];changed+=new!=bits;cell['connections'][p]=new
    if not changed:raise ValueError('Disconnected helper fault')


def phase_guarantee(base):
    """Authenticate the production flag guarantee; do not infer data stability."""
    root=Path(__file__).resolve().parents[4]
    cert_path=base/'timing/engine/certificate/result.json'
    equiv_path=base/'preenable-equivalence/result.json';cadence_path=base/'formal/result.json'
    cert=json.loads(cert_path.read_text());equiv=json.loads(equiv_path.read_text());cadence=json.loads(cadence_path.read_text())
    if cert['status']!='pass' or cert['pre_enable']['status']!='pass' or equiv['status']!='pass' or cadence['status']!='pass':
        raise ValueError('Missing production phase guarantee')
    if cert['pre_enable']['equivalence_sha256']!=hashlib.sha256(json.dumps(equiv,sort_keys=True).encode()).hexdigest():
        raise ValueError('Wrong phase equivalence receipt')
    bound={**equiv['production_source_sha256'],**cadence['production_source_sha256'],**cert['proof_source_sha256'],**cert['sources']}
    for p,h in bound.items():
        path=root/p.removeprefix('/work/')
        if digest(path)!=h:raise ValueError('Stale producer guarantee: '+p)
    module=json.loads((cert_path.parent/'source.json').read_text())['modules']['UsbEngine']
    flags=['in.request','in.consume','in.acknowledge','out.receiveValid','out.receiveReady','out.receiveError']
    identities={}
    for flag in flags:
        bits=module['netnames'][flag]['bits']
        drivers=[n for n,c in module['cells'].items() if c['connections'].get('Q')==bits]
        if len(drivers)!=1 or drivers[0] not in cert['pre_enable']['source_registers']:
            raise ValueError('Uncertified/mixed phase flag: '+flag)
        identities[flag]=drivers[0]
    return dict(receipts={str(p):digest(p) for p in (cert_path,equiv_path,cadence_path)},flags=identities,
        scope='D58 pre-enable flag phase. Encoded-operation harness remains a conditional E1 environment, not a new SIE composition proof.')


def cover_job(directory,hdl,top,count,depth):
    directory.mkdir();config=directory/'job.sby'
    config.write_text('\n'.join(['[options]','mode cover',f'depth {depth}','timeout 120','[engines]','btor btormc',
        '[script]','read_slang --top '+top+' '+' '.join(p.name for p in hdl),f'prep -top {top} -flatten',
        "fminit -seq reset_n 0,'z",'async2sync','chformal -lower',f'select -assert-count {count} t:$cover',
        '[files]',*map(str,hdl)])+'\n')
    started=time.monotonic();process=execute(['sby','-d',directory/'job',config],directory/'run.log',180)
    status=(directory/'job/status').read_text().split()[0]
    row=dict(mode='cover',depth=depth,cap_seconds=120,engine='btor btormc',solver_status=status,
        returncode=process.returncode,seconds=time.monotonic()-started,directory=str(directory),
        emitted_sha256={str(p):digest(p) for p in hdl},config_sha256=digest(config),result='unresolved')
    if status=='PASS':validate_job(directory/'job','cover',process.returncode,status);row['result']='covered'
    return row


def run_followup(output,split,base,small_covers=False):
    """One E1 attempt for remaining integrity/progress, or mandatory D62 covers."""
    root=Path(__file__).resolve().parents[4]
    output=output.resolve();output.relative_to(root/'build');output.mkdir(parents=True,exist_ok=False)
    prior=json.loads(split.read_text())
    if prior['status']!='unresolved':raise ValueError('Expected audited unresolved original inventory')
    bound={**prior['source_sha256'],'hw/ip/usb/formal/UsbPacketProof.scala':digest(root/'hw/ip/usb/formal/UsbPacketProof.scala')}
    if any(digest(root/p)!=h for p,h in bound.items()):raise ValueError('Stale packet source')
    receipt=dict(status='running',source_sha256=bound,prior=dict(path=str(split),sha256=digest(split)),jobs=[],
        packet_bytes=8 if small_covers else 16,environment='original' if small_covers else 'E1',
        assumptions='Original arbitrary-later-reset harness; data, choose and application inputs unrestricted.')
    receipt['flow_sha256']={str(Path(__file__).relative_to(root)):digest(Path(__file__))}
    (output/'packet_partition.py').write_bytes(Path(__file__).read_bytes())
    save(output/'result.json',receipt)
    try:
        if not small_covers:receipt['guarantee']=phase_guarantee(base.resolve())
        for role in ('in','out'):
            remaining=[j['property'] for j in prior['jobs'] if j['role']==role and j['kind']=='unresolved' and j['property'] in ('integrity','progress')]
            if not small_covers and not remaining:continue
            profile='small-covers' if small_covers else 'real';environment='original' if small_covers else 'E1'
            command=[sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbPacketProof {output}/emit/{role} {role} {receipt["packet_bytes"]} {profile} {environment}']
            execute(command,output/(role+'-emit.log'),600).check_returncode()
            top=('UsbSmallInCovers' if role=='in' else 'UsbSmallOutCovers') if small_covers else 'UsbAlignedPacketFormal'
            hdl=sorted((output/'emit'/role/'cover').glob('*.sv'))
            count=(10 if role=='in' else 9) if small_covers else (4 if role=='in' else 3)
            cover=cover_job(output/(role+'-covers'),hdl,top,count,128 if small_covers else 48)
            receipt['jobs'].append(dict(role=role,cover=cover));save(output/'result.json',receipt)
            if cover['result']!='covered':
                receipt.update(status='unresolved',error='Required real covers unresolved/unreachable; stop this environment')
                return receipt
            if small_covers:continue
            hdl=sorted((output/'emit'/role/'correct').glob('*.sv'));prepared=output/(role+'-canonical.json')
            ys=output/(role+'-prepare.ys');total=18 if role=='in' else 14
            ys.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,hdl)),f'prep -top {top} -flatten',
                "fminit -seq reset_n 0,'z",'async2sync','chformal -lower',f'select -assert-count {total} t:$assert',f'write_json {prepared}'])+'\n')
            execute(['yosys','-Q','-T','-s',ys],output/(role+'-prepare.log')).check_returncode()
            model=json.loads(prepared.read_text());prefix='subject.'
            names=[prefix+'assert__chisel3_builtin',*(prefix+f'assert__chisel3_builtin_{i}' for i in range(total-1))]
            if {n for n,c in model['modules'][top]['cells'].items() if c['type']=='$assert'}!=set(names):raise ValueError('E1 assertion identities changed')
            for prop in remaining:
                name=names[-6:][PROPERTIES.index(prop)]
                bad=copy.deepcopy(model)
                net=prefix+('d.valid' if role=='in' else 'd.appValid') if prop=='progress' else prefix+('d.data' if role=='in' else 'd.appData')
                replace_loads(bad,top,net,['0'] if prop=='progress' else model['modules'][top]['ports']['data']['bits'])
                negative=lemma_job(output/(role+'-'+prop+'-negative'),bad,top,{name},mode='bmc',engine='btor btormc')
                if negative['result']!='fault_rejected':raise ValueError('E1 makes required original fault unreachable')
                positive=lemma_job(output/(role+'-'+prop+'-positive'),model,top,{name},
                    engine='smtbmc z3' if prop=='progress' else 'abc pdr\nsmtbmc z3')
                row=dict(role=role,property=prop,positive=positive,negative=negative,model_sha256=digest(prepared),
                    emitted_sha256={str(p):digest(p) for p in hdl},
                    kind='proved under environment assumptions E1' if positive['result']=='proved' else 'unresolved')
                receipt['jobs'].append(row);save(output/'result.json',receipt)
                print(role,prop,row['kind'],flush=True)
                if positive['solver_status']=='FAIL':raise ValueError('Original assertion counterexample under E1')
        receipt['status']='pass' if small_covers else 'unresolved'
    except Exception as error:receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(root/p)!=h for p,h in bound.items()):receipt.update(status='failed',error='Sources changed during follow-up')
        if any(digest(root/p)!=h for p,h in receipt['flow_sha256'].items()):receipt.update(status='failed',error='Flow changed during follow-up')
        save(output/'result.json',receipt)
    return receipt


def finish_small_originals(output,prior_path):
    """Attempt only unattempted originals with the proved prefix of helpers.

    A data-lemma timeout must not prevent control claims from using the already
    proved storage/ownership facts. No failed/timed-out original is rerun.
    """
    root=Path(__file__).resolve().parents[4]
    prior_path=prior_path.resolve();prior_path.relative_to(root/'build')
    output=output.resolve();output.relative_to(root/'build');output.mkdir(parents=True,exist_ok=False)
    receipt=json.loads(prior_path.read_text())
    if receipt['status']!='unresolved' or receipt['packet_bytes']!=8:raise ValueError('Expected terminal small-model attempt')
    if digest(prior_path.parent/'packet_partition.py')!=receipt['flow_sha256']['hw/ip/usb/formal/packet_partition.py']:
        raise ValueError('Missing original small-model runner archive')
    if any(digest(root/p)!=h for p,h in receipt['source_sha256'].items()):raise ValueError('Stale small model')
    receipt['continued_from']=dict(path=str(prior_path),sha256=digest(prior_path))
    receipt['flow_sha256']['hw/ip/usb/formal/packet_partition.py']=digest(Path(__file__))
    (output/'packet_partition.py').write_bytes(Path(__file__).read_bytes())
    receipt['status']='running';save(output/'result.json',receipt)
    try:
        for role,top in [('in','UsbInFormal'),('out','UsbOutFormal')]:
            info=receipt['roles'][role];path=Path(info['canonical'])
            if digest(path)!=info['model_sha256']:raise ValueError('Changed canonical model')
            model=json.loads(path.read_text());dependencies=[]
            for group in ('storage','ownership','data'):
                dependency_path=path.parent/(group+'-receipt.json')
                if not dependency_path.exists():break
                entry=json.loads(dependency_path.read_text())
                dependencies.append(dict(group=group,path=str(dependency_path),sha256=digest(dependency_path),assertions=entry['assertions']))
            for prop,name in info['originals'].items():
                if any(j['role']==role and j.get('property')==prop for j in receipt['jobs']):continue
                assumed=qualified_assumptions(dependencies,model,top,info['model_sha256'])
                row=dict(role=role,property=prop,canonical_model_sha256=info['model_sha256'],dependencies=list(dependencies))
                row['positive']=lemma_job(output/(role+'-'+prop+'-positive'),model,top,{name},assumed,
                    engine='smtbmc z3' if prop=='progress' else 'abc pdr\nsmtbmc z3')
                receipt['jobs'].append(row);save(output/'result.json',receipt)
                print(role,prop,row['positive']['result'],flush=True)
                if row['positive']['solver_status']=='FAIL':raise ValueError('Original assertion has a counterexample')
        receipt['status']='unresolved'
    except Exception as error:receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(root/p)!=h for p,h in {**receipt['source_sha256'],**receipt['flow_sha256']}.items()):
            receipt.update(status='failed',error='Proof inputs changed during remaining originals')
        save(output/'result.json',receipt)
    return receipt


def run_helpers(output,split,refinement,packet_bytes=16,helper_portfolio=False):
    root=Path(__file__).resolve().parents[4]
    for p in (output,split,refinement):p.resolve().relative_to(root/'build')
    output=output.resolve();split=split.resolve();refinement=refinement.resolve()
    output.mkdir(parents=True,exist_ok=False)
    (output/'packet_partition.py').write_bytes(Path(__file__).read_bytes())
    prior=json.loads(split.read_text());memory=json.loads(refinement.read_text())
    if prior['status'] not in ('pass','unresolved') or any(j['positive']['solver_status']=='FAIL' for j in prior['jobs']):
        raise ValueError('Singleton step unfinished or has an original counterexample')
    if digest(root/'hw/ip/usb/formal/UsbBufferFormal.scala')!=REVIEWED_HARNESS_SHA256:
        raise ValueError('Assertion/helper semantic mapping requires renewed review')
    if memory.get('status')!='pass' or memory.get('expected_packet_bytes')!=packet_bytes:
        raise ValueError('Missing or wrong-size memory refinement')
    if any(memory['source_sha256'][p]!=h for p,h in prior['source_sha256'].items() if p in memory['source_sha256']):
        raise ValueError('Conflicting source guarantees')
    if digest(split.parent/'packet_decompose.py')!=prior['flow_sha256']['hw/ip/usb/formal/packet_decompose.py']:
        raise ValueError('Original split runner archive does not match receipt')
    for p,h in {**prior['source_sha256'],**memory['source_sha256']}.items():
        if digest(root/p)!=h:raise ValueError('Stale source/refinement binding: '+p)
    sources={**prior['source_sha256'],
        'hw/ip/usb/formal/UsbPacketProof.scala':digest(root/'hw/ip/usb/formal/UsbPacketProof.scala')}
    receipt=dict(status='running',packet_bytes=packet_bytes,helper_portfolio=helper_portfolio,source_sha256=sources,jobs=[],roles={},
        original_split=dict(path=str(split),sha256=digest(split)),
        refinement=dict(path=str(refinement),sha256=digest(refinement)),
        flow_sha256={str(p.relative_to(root)):digest(p) for p in (Path(__file__),root/'hw/ip/usb/formal/packet_decompose.py',root/'tools/formal.py')},
        assumptions='Original common-reset packet harness; arbitrary later resets. No E1/E2. Only previously proved exact-model helper predicates may be assumed.',
        qualification='Sparse memory containment with age-qualified observations; not independent transport-reset/SIE composition')
    save(output/'result.json',receipt)
    try:
        emitted=output/'emit/sparse';real_emitted=output/'emit/real'
        # Build the exact requested geometry ourselves; supplied assertion counts
        # or directory labels cannot authenticate an 8-byte versus 16-byte model.
        emit_command=[sys.executable,'tools/sbt.py',*[f'runMain deadhorse.usb.EmitUsbPacketProof {output}/emit/{profile}/{role} {role} {packet_bytes} {profile}'
            for profile in ('real','sparse') for role in ('in','out')]]
        execute(emit_command,output/'emit.log',600).check_returncode()
        receipt['emission_command']=emit_command
        for role,top,total,nctrl,tag in [('in','UsbInFormal',26,12,17),('out','UsbOutFormal',21,8,12)]:
            directory=output/role;directory.mkdir()
            hdl=sorted((emitted/role/'correct').glob('*.sv'));prepared=directory/'canonical.json'
            if not hdl:raise ValueError('Missing canonical sparse emission')
            script=directory/'prepare.ys'
            script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,hdl)),
                f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                f'select -assert-count {total} t:$assert',f'write_json {prepared}'])+'\n')
            execute(['yosys','-Q','-T','-s',script],directory/'prepare.log').check_returncode()
            model=json.loads(prepared.read_text());canonical_hash=digest(prepared)
            real_sources=sorted((real_emitted/role/'correct').resolve().glob('*.sv'))
            real_prepared=directory/'real.json';real_script=directory/'real.ys'
            real_total=nctrl+6
            real_script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,real_sources)),
                f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                f'select -assert-count {real_total} t:$assert',f'write_json {real_prepared}'])+'\n')
            execute(['yosys','-Q','-T','-s',real_script],directory/'real.log').check_returncode()
            real=json.loads(real_prepared.read_text())
            real_names=['assert__chisel3_builtin',*(f'assert__chisel3_builtin_{i}' for i in range(real_total-1))]
            names=['assert__chisel3_builtin',*(f'assert__chisel3_builtin_{i}' for i in range(total-1))]
            if {n for n,c in model['modules'][top]['cells'].items() if c['type']=='$assert'}!=set(names):
                raise ValueError('Canonical assertion mapping changed')
            control=set(names[:nctrl])|{names[tag]};data=set(names[:-6])-control
            boundary=8 if role=='in' else 4
            storage=set(names[:boundary])|{names[tag]}
            ownership=set(names[boundary:nctrl])
            receipt['roles'][role]=dict(canonical=str(prepared),model_sha256=canonical_hash,
                emitted_sha256={str(p):digest(p) for p in hdl},control_helpers=sorted(control),data_helpers=sorted(data),
                real_model_sha256=digest(real_prepared),real_emitted_sha256={str(p):digest(p) for p in real_sources},
                originals=dict(zip(PROPERTIES,names[-6:])))
            assumed=set();dependencies=[]
            for group,chosen in [('storage',storage),('ownership',ownership),('data',data)]:
                assumed=qualified_assumptions(dependencies,model,top,canonical_hash)
                entry=dict(role=role,group=group,canonical_model_sha256=canonical_hash,
                    assertions=sorted(chosen),predicate_sha256=predicate_hash(model,top,chosen),dependencies=list(dependencies))
                entry['positive']=lemma_job(directory/(group+'-positive'),model,top,chosen,assumed,
                    engine='abc pdr\nsmtbmc z3' if helper_portfolio else 'abc pdr')
                if group!='data':
                    reduced_path=directory/(group+'-positive')/'job/model/reduced.json'
                    if reduced_path.exists():
                        reduced=json.loads(reduced_path.read_text())['modules'][top]
                        forbidden=[n for n in reduced['netnames'] if n in ('watched','priorData','oldData') or
                            n.startswith('d.memory.') and any(s in n for s in ('trackedValue','cacheValue','pendingData','r1','readData'))]
                        memories=[n for n,c in reduced['cells'].items() if c['type'].startswith('$mem')]
                        if forbidden or memories:raise ValueError('Control helper retained RAM/data cone: '+str(forbidden+memories))
                        entry['cone_audit']=dict(status='pass',remaining_cells=len(reduced['cells']),memory_cells=0)
                    else:raise ValueError('Missing reduced control model for cone audit')
                if entry['positive']['result']=='proved':
                    bad=copy.deepcopy(model)
                    net='d.tail' if group=='storage' else ('d.tail' if role=='in' else 'd.speculative') if group=='ownership' else ('d.stagingData' if role=='in' else 'd.memory.pendingData')
                    width=len(model['modules'][top]['netnames'][net]['bits'])
                    replacement=(['1']+['0']*(width-1)) if group=='storage' else ['1']*width if group=='ownership' else ['0']*width
                    replace_loads(bad,top,net,replacement)
                    entry['negative']=lemma_job(directory/(group+'-negative'),bad,top,chosen,(),mode='bmc',engine='btor btormc')
                    entry['mutation']=dict(net=net,description='Corrupt real state/data path; no good-DUT lemma assumptions')
                    real_bad=copy.deepcopy(real)
                    real_net='d.tail' if group=='storage' else ('d.tail' if role=='in' else 'd.speculative') if group=='ownership' else ('d.stagingData' if role=='in' else 'd.memory.wordData')
                    real_width=len(real['modules'][top]['netnames'][real_net]['bits'])
                    real_replacement=(['1']+['0']*(real_width-1)) if group=='storage' else ['1']*real_width if group=='ownership' else ['0']*real_width
                    replace_loads(real_bad,top,real_net,real_replacement)
                    real_targets=set(real_names[:boundary]) if group=='storage' else set(real_names[boundary:nctrl]) if group=='ownership' else {real_names[-4]}
                    entry['real_negative']=lemma_job(directory/(group+'-real-negative'),real_bad,top,real_targets,(),mode='bmc',engine='btor btormc')
                receipt['jobs'].append(entry);save(output/'result.json',receipt)
                print(role,group,entry['positive']['result'],entry.get('negative',{}).get('result','not attempted'),flush=True)
                if entry['positive']['result']!='proved' or entry.get('negative',{}).get('result')!='fault_rejected':break
                # Read the serialized receipt, never infer a PASS from the intended job.
                persisted=json.loads((output/'result.json').read_text())['jobs'][-1]
                require_lemma(persisted,model,top,chosen,canonical_hash,assumed)
                for key,bad_value in [('canonical_model_sha256','wrong-model'),('positive',{})]:
                    wrong=copy.deepcopy(persisted);wrong[key]=bad_value
                    try:require_lemma(wrong,model,top,chosen,canonical_hash,assumed)
                    except ValueError:pass
                    else:raise ValueError('Unqualified lemma negative control escaped')
                dependency_path=directory/(group+'-receipt.json');save(dependency_path,persisted)
                dependencies.append(dict(group=group,path=str(dependency_path),sha256=digest(dependency_path),assertions=sorted(chosen)))
            else:
                closed={j['property'] for j in prior['jobs'] if packet_bytes==16 and j['role']==role and j['positive']['result']=='proved' and j.get('negative',{}).get('result')=='fault_rejected'}
                for prop,name in zip(PROPERTIES,names[-6:]):
                    if prop in closed:continue
                    assumed=qualified_assumptions(dependencies,model,top,canonical_hash)
                    row=dict(role=role,property=prop,canonical_model_sha256=canonical_hash,dependencies=list(dependencies))
                    row['positive']=lemma_job(directory/(prop+'-positive'),model,top,{name},assumed,
                        engine='smtbmc z3' if prop=='progress' else 'abc pdr\nsmtbmc z3' if helper_portfolio else 'abc pdr')
                    receipt['jobs'].append(row);save(output/'result.json',receipt)
                    print(role,prop,row['positive']['result'],flush=True)
                    if row['positive']['solver_status']=='FAIL':raise ValueError('Original assertion has a counterexample')
        receipt['status']='unresolved' # All real-model faults/coverage/composition must be audited before acceptance.
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    finally:
        if any(digest(root/p)!=h for p,h in sources.items()):receipt.update(status='failed',error='Sources changed during helper proof')
        bound_artifacts={**receipt['flow_sha256'],str(split):receipt['original_split']['sha256'],str(refinement):receipt['refinement']['sha256']}
        for role in receipt['roles'].values():
            bound_artifacts.update(role['emitted_sha256']);bound_artifacts.update(role['real_emitted_sha256'])
            bound_artifacts[role['canonical']]=role['model_sha256']
        if any(digest(root/p)!=h for p,h in bound_artifacts.items()):receipt.update(status='failed',error='Proof/emission/flow artifact changed')
        save(output/'result.json',receipt)
    return receipt

ALL = {'assert__chisel3_builtin', *(f'assert__chisel3_builtin_{n}' for n in range(5))}
DATA = {'assert__chisel3_builtin_1', 'assert__chisel3_builtin_3'}


def run(output, regmap):
    root = Path(__file__).resolve().parents[4]
    output = output.resolve(); output.relative_to(root/'build')
    regmap = regmap.resolve(); regmap.relative_to(root)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    bound = [Path(__file__),Path('hw/ip/usb/formal/UsbBufferFormal.scala'),
        Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketSizing.scala'),
        Path('hw/ip/usb/formal/UsbFormal.scala'),Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbPacketBuffer.scala'),
        Path('hw/ip/usb/src/main/scala/deadhorse/usb/UsbBitEnable.scala')]
    hashes = lambda: {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in bound}
    receipt = dict(status='unresolved',source_sha256=hashes(),jobs=[],
        scope='Exhaustive original assertion partition; no added assumptions; original real-model covers/faults and SIE composition remain required')
    assert DATA < ALL and (ALL-DATA)|DATA == ALL and not (ALL-DATA)&DATA
    for role, top in [('in','UsbInFormal'),('out','UsbOutFormal')]:
        directory = output/role
        directory.mkdir()
        with (directory/'emit.log').open('w') as log:
            subprocess.run([sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsbFormal {regmap} {role} {directory}/emit'],
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
        sources = sorted((directory/'emit/correct').glob('*.sv'))
        prepared = directory/'prepared.json'
        script = directory/'prepare.ys'
        script.write_text('\n'.join(['read_slang --top '+top+' '+' '.join(map(str,sources)),
            f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
            'select -assert-count 6 t:$assert',f'write_json {prepared}'])+'\n')
        with (directory/'prepare.log').open('w') as log:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        original = json.loads(prepared.read_text())
        cells = original['modules'][top]['cells']
        actual = {n for n,c in cells.items() if c['type']=='$assert'}
        if actual != ALL:
            raise ValueError('Original assertion identities changed; partition requires review')
        emitted_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        for kind, selected in [('control',ALL-DATA),('data',DATA)]:
            model = copy.deepcopy(original)
            for name in ALL-selected:
                del model['modules'][top]['cells'][name]
            source = directory/(kind+'.json')
            source.write_text(json.dumps(model))
            job = directory/(kind+'.sby')
            job.write_text('\n'.join(['[options]','mode prove','depth 48','timeout 120',
                '[engines]','abc pdr','[script]',f'read_json {source.name}',f'hierarchy -check -top {top}',
                f'select -assert-count {len(selected)} t:$assert','opt_clean -purge','stat -width',
                '[files]',str(source.resolve())])+'\n')
            then = time.monotonic()
            with (directory/(kind+'.log')).open('w') as log:
                process = subprocess.run(['sby','-d',str(directory/kind),str(job)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
            status = (directory/kind/'status').read_text().split()[0]
            row = dict(role=role,partition=kind,assertions=sorted(selected),solver_status=status,
                returncode=process.returncode,seconds=time.monotonic()-then,source_sha256=emitted_hashes,
                result='proved' if status=='PASS' and process.returncode==0 else 'unresolved' if status=='TIMEOUT' else 'failed')
            receipt['jobs'].append(row)
            receipt['seconds']=time.monotonic()-started
            (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(role,kind,status,flush=True)
    if hashes()!=receipt['source_sha256']:
        raise ValueError('Packet sources changed during partition attempt')
    receipt['status']='failed' if any(j['result']=='failed' for j in receipt['jobs']) else 'unresolved'
    receipt['seconds']=time.monotonic()-started
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--json',type=Path)
    parser.add_argument('--helpers',action='store_true')
    parser.add_argument('--split',type=Path)
    parser.add_argument('--refinement',type=Path)
    parser.add_argument('--packet-bytes',type=int,choices=(8,16),default=16)
    parser.add_argument('--helper-portfolio',action='store_true')
    parser.add_argument('--environment-attempt',action='store_true')
    parser.add_argument('--small-covers',action='store_true')
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--finish-small',type=Path)
    args=parser.parse_args()
    if args.finish_small:
        receipt=finish_small_originals(args.output,args.finish_small)
    elif args.environment_attempt or args.small_covers:
        if not args.split or (args.environment_attempt and not args.baseline):parser.error('Follow-up requires split and E1 producer baseline')
        receipt=run_followup(args.output,args.split,args.baseline,args.small_covers)
    elif args.helpers:
        if not all((args.split,args.refinement)):parser.error('Helper mode requires split/refinement')
        receipt=run_helpers(args.output,args.split,args.refinement,args.packet_bytes,args.helper_portfolio)
    else:
        if not args.json:parser.error('Original partition requires --json')
        receipt=run(args.output,args.json)
    print(receipt['status'].upper()+' packet assertion partitions',flush=True)
    sys.exit(0 if receipt['status']=='pass' else 1)
