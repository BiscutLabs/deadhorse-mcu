"""Read-only USB acceptance evidence integration. No solver, synthesis or CI."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.append(str(Path(__file__).parent/'formal'))
from packet_epoch import audit_epoch
from packet_partition import selected_model
from packet_receipt import checked_job


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(name, build=False):
    path=Path(str(name).replace('\\','/'))
    path=(path if path.is_absolute() else ROOT/path).resolve()
    path.relative_to(ROOT/'build' if build else ROOT)
    return path


def check_hashes(values):
    if not isinstance(values,dict) or not values:raise ValueError('Missing source/artifact hashes')
    for name,h in values.items():
        if not isinstance(h,str) or len(h)!=64 or digest(local(name))!=h:
            raise ValueError('Missing or stale evidence: '+name)


def inventory(claims):
    expected={(r,p) for r in ('in','out') for p in ('capacity','read_nonempty','integrity','held_valid','held_data','progress')}
    if not isinstance(claims,list) or len(claims)!=len(expected):raise ValueError('Incomplete original assertion inventory')
    seen=set();closed=[];unresolved=[]
    for row in claims:
        key=(row.get('role'),row.get('property'))
        if key not in expected or key in seen:raise ValueError('Duplicate or unknown original assertion')
        seen.add(key);kind=row.get('kind')
        if kind=='unresolved':unresolved.append('.'.join(key));continue
        if kind not in ('proved','proved at small model'):raise ValueError('Bounded or unqualified result cannot close an assertion')
        if row.get('packet_bytes')!=(16 if kind=='proved' else 8):raise ValueError('Wrong proof geometry or acceptance label')
        closed.append(dict(row,qualification=kind if kind=='proved' else 'proved at small model, simulated at full size'))
    return dict(status='pass' if not unresolved else 'unresolved',closed=closed,unresolved=unresolved)


def wrapper_archive(binding_path,binding,archive):
    check_hashes(binding['current_source_sha256']);check_hashes(binding['emitted_sha256'])
    if digest(binding_path.parent/'wrapper.json')!=binding['wrapper_sha256']:
        raise ValueError('Missing or stale wrapper model')
    check_hashes(archive['source_sha256'])
    archived={str(local(p).relative_to(binding_path.parent/'simulation-archive/source')).replace('\\','/'):h
              for p,h in archive['source_sha256'].items()}
    if archived!={p.replace('\\','/'):h for p,h in binding['current_source_sha256'].items()}:
        raise ValueError('Archived SIE source differs from bound simulation source')
    for name,row in archive['files'].items():check_hashes({name:row['sha256']})
    artifacts={row['origin']:row['sha256'] for row in archive['files'].values()}
    expected=binding['simulation']['artifact_sha256']
    extras=set(artifacts)-set(expected)
    allowed={str(binding_path):digest(binding_path) if binding_path.exists() else None,
             str(binding_path.parent/'simulation.log'):binding['simulation'].get('log_sha256')}
    if any(artifacts.get(p)!=h for p,h in expected.items()) or any(artifacts[p]!=allowed.get(p) for p in extras):
        raise ValueError('Archived simulation artifact inventory differs')


def sie_source_inventory():
    paths=list((ROOT/'hw/ip/usb/src/main').rglob('*.scala'))
    paths += [ROOT/p for p in ('hw/ip/usb/formal/UsbSiePacketContract.scala',
        'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala','hw/ip/usb/formal/sie_packet_contract.py',
        'hw/ip/usb/formal/packet_partition.py','hw/ip/usb/formal/packet_decompose.py','tools/formal.py','build.sbt')]
    paths += [p for p in (ROOT/'hw/vendor/usb').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(ROOT).as_posix() for p in paths}


def same_vendor(source,emitted):
    # Chisel's resource export changes terminal LF count. No other byte may differ.
    if source.read_bytes().rstrip(b'\n')!=emitted.read_bytes().rstrip(b'\n'):
        raise ValueError('Applied vendor differs from proved SIE emission: '+source.name)
    return dict(source_sha256=digest(source),emitted_sha256=digest(emitted),comparison='bytes except terminal LF count')


def sie_evidence(proof_path,binding_path,archive_path):
    proof=json.loads(proof_path.read_text());binding=json.loads(binding_path.read_text());archive=json.loads(archive_path.read_text())
    if proof.get('status')!='safety-proved' or binding.get('status')!='pass' or archive.get('status')!='pass':
        raise ValueError('SIE proof/binding/archive is not qualified')
    if binding.get('proof_sha256')!=digest(proof_path) or archive.get('origin_receipt_sha256')!=digest(binding_path):
        raise ValueError('SIE binding belongs to a different proof')
    if binding['binder_sha256']!=digest(Path(__file__).parent/'formal/sie_packet_contract.py'):
        raise ValueError('Stale wrapper binder')
    if set(proof['source_sha256'])!=sie_source_inventory():raise ValueError('Incomplete SIE proof source inventory')
    required=set(proof['source_sha256'])|{'build/t19/regmap/usb_regs.json',
        'hw/ip/usb/src/test/scala/deadhorse/usb/UsbSieCompositionSpec.scala',
        'hw/ip/usb/src/test/scala/deadhorse/usb/UsbWireHost.scala'}
    if set(binding['current_source_sha256'])!=required:raise ValueError('Incomplete wrapper source inventory')
    wrapper_archive(binding_path,binding,archive)
    check_hashes(proof['emitted_sha256'])
    vendor={}
    for name in ('sie.v','phy_rx.v','phy_tx.v'):
        paths=[local(p) for p in proof['emitted_sha256'] if Path(p).name==name]
        if len(paths)!=1:raise ValueError('Ambiguous vendor emission: '+name)
        vendor[name]=same_vendor(ROOT/'build/vendor/usb/rtl'/name,paths[0])
    for name,h in proof['source_sha256'].items():
        path=proof_path.parent/'runner.py' if name=='hw/ip/usb/formal/sie_packet_contract.py' else local(name)
        if digest(path)!=h:raise ValueError('Stale SIE proof source')
    canonical=proof_path.parent/'canonical.json'
    if digest(canonical)!=proof['canonical_sha256']:raise ValueError('Changed SIE canonical')
    model=json.loads(canonical.read_text());top='UsbSiePacketContract'
    expected={'routing':{'assert__chisel3_builtin','assert__chisel3_builtin_0','assert__chisel3_builtin_2'},
              'valid-read':{'assert__chisel3_builtin_1'}}
    if len(proof['jobs'])!=2 or {j['property'] for j in proof['jobs']}!=set(expected):raise ValueError('Missing SIE assertion partition')
    for job in proof['jobs']:
        if checked_job(job['positive'],'proof')!=selected_model(model,top,expected[job['property']],set()):
            raise ValueError('SIE proof changed assertions or assumptions')
    simulation=binding.get('simulation',{})
    if simulation.get('status')!='pass' or simulation.get('returncode')!=0:raise ValueError('Missing real SIE traffic/fault qualification')
    log=binding_path.parent/'simulation-archive/simulation.log'
    if digest(log)!=simulation['log_sha256'] or 'Tests: succeeded 4, failed 0' not in log.read_text():
        raise ValueError('SIE traffic/fault log is incomplete')
    for scenario in ('positive','fault-1','fault-2','fault-3'):
        if not any('/'+scenario+'/' in name and name.endswith('.sv') for name in archive['files']):
            raise ValueError('Missing archived real SIE scenario: '+scenario)
    return dict(status='pass',proof_sha256=digest(proof_path),binding_sha256=digest(binding_path),archive_sha256=digest(archive_path),vendor=vendor)


def simulation_sources():
    paths=[ROOT/p for p in ('build.sbt','tools/sbt.py','tools/env/lock.json','build/t19/regmap/usb_regs.json')]
    for folder in ('project','hw/ip/usb/src','hw/lib/src/main','hw/top/stubs','hw/vendor/usb','build/vendor/usb/rtl'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(set(paths))}


SAMPLING_SCENARIOS={'positive','lookahead','outputs','spacing','outputs-phase','spacing-phase'}


def sampling_markers(simulation,log):
    faults=re.findall(r'USB_SAMPLING_FAULT ([\w-]+) violations=(\d+)',log)
    masks={'lookahead':15,'outputs':240,'spacing':1792,'outputs-phase':240,'spacing-phase':1792}
    actual={n:int(v) for n,v in faults}
    if (len(faults)!=len(masks) or set(actual)!=set(masks) or actual!=simulation.get('faults') or
            any(not actual[n]&mask for n,mask in masks.items())):
        raise ValueError('Missing or mixed detected sampling fault')
    covers=[list(row) for row in re.findall(
        r'USB_SAMPLING_COVER before_reset=(\d+) after_reset=(\d+) reset_release_after_traffic=1',log)]
    if len(covers)!=1 or covers!=simulation.get('cover_masks') or any(int(v)&63!=63 for v in covers[0]):
        raise ValueError('Missing or mixed actual-use guard cover')


def require_inventory(values,expected,label):
    if not isinstance(values,dict) or set(values)!={str(p) for p in expected}:
        raise ValueError('Incomplete or mixed '+label+' inventory')
    check_hashes(values)


def sampling_source_inventory(proof):
    maps=[p for p in proof['source_sha256'] if p.startswith('build/') and p.endswith('/usb_regs.json')]
    if len(maps)!=1:raise ValueError('Missing or mixed sampling regmap')
    required=set(maps)|{'build.sbt','tools/sbt.py','tools/env/lock.json','hw/ip/usb/formal/sampling.py',
        'hw/ip/usb/formal/UsbSampling.scala','hw/ip/usb/formal/packet_partition.py',
        'hw/ip/usb/formal/packet_decompose.py','tools/formal.py'}
    for folder in ('hw/ip/usb/src/main','hw/lib/src/main','hw/vendor/usb'):
        required.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts)
    if set(proof['source_sha256'])!=required:raise ValueError('Incomplete sampling proof source inventory')
    return required


def sampling_artifacts(directory):
    required={directory/name for name in ('cover-emit.log','cover-model.log','cover.ys','covers.json','covers/UsbSampling.sv')}
    for role in ('lookahead','outputs','spacing'):
        required.update(directory/('audit-'+role)/(stem+suffix) for stem in ('production','observer','canonical')
                        for suffix in ('.ys','.json','.log'))
        required.add(directory/('audit-'+role)/'combined.json')
    for scenario in SAMPLING_SCENARIOS:
        required.update(directory/scenario/name for name in ('model.json','emit.ys','emit.log','UsbSamplingEngine.v'))
    actual={p for p in directory.rglob('*') if p.is_file() and p.name not in ('result.json','simulation.log')}
    if not required<=actual:raise ValueError('Missing sampling witness artifact')
    return actual


def context_artifacts(directory):
    expected={directory/(side+suffix) for side in ('before','after') for suffix in
        ('.ys','.log','-raw.json','-ports.json','-prepare.ys','-prepare.log','.json','-cut.json')}
    expected.update(directory/name for name in ('equivalence.ys','equivalence.log','fault-cut.json',
                                               'wrong-next-cursor.ys','wrong-next-cursor.log'))
    return expected


def archive_sampling(witness_path,output):
    """Preserve observed runtime artifacts; never claim this runs simulation."""
    witness_path=local(witness_path,True);output=local(output,True);output.mkdir(parents=True,exist_ok=False)
    witness=json.loads(witness_path.read_text());runtime=ROOT/'build/plan03/usb-sampling-simulation'
    check_hashes(witness['current_source_sha256']);check_hashes(witness['artifact_sha256'])
    files={}
    for scenario in SAMPLING_SCENARIOS:
        source=runtime/scenario
        if (source/'primary-sources/UsbSamplingEngine.v').read_bytes().rstrip(b'\n')!=local(witness['scenarios'][scenario]['hdl']).read_bytes().rstrip(b'\n'):
            raise ValueError('Runtime HDL differs from sampling witness')
        for path in source.rglob('*'):
            # Compiler caches/objects are redundant; preserve source, executable,
            # compilation and execution records in a separate immutable archive.
            if not path.is_file() or path.suffix in ('.gch','.o','.a'):continue
            dest=output/'runtime'/path.relative_to(runtime);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,dest);files[str(dest)]=digest(dest)
    shutil.copyfile(witness_path.parent/'simulation.log',output/'simulation.log')
    files[str(output/'simulation.log')]=digest(output/'simulation.log')
    receipt=dict(status='archived',witness_sha256=digest(witness_path),files=files,
        qualification='Archived existing observed runtime artifacts; no simulation rerun or additional proof')
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def sampling_runtime_archive(path,witness_path,witness):
    archive=json.loads(path.read_text());directory=path.parent
    if archive.get('status')!='archived' or archive.get('witness_sha256')!=digest(witness_path):
        raise ValueError('Wrong sampling runtime archive')
    actual={p for p in directory.rglob('*') if p.is_file() and p!=path}
    require_inventory(archive['files'],actual,'sampling runtime artifact')
    if digest(directory/'simulation.log')!=witness['simulation']['log_sha256']:raise ValueError('Mixed runtime log')
    for scenario in SAMPLING_SCENARIOS:
        base=directory/'runtime'/scenario
        for name in ('primary-sources/UsbSamplingEngine.v','primary-sources/UsbSamplingBench.sv',
                     'generated-sources/testbench.sv','support-artifacts/filelist.f',
                     'generated-sources/c-dpi-bridge.cpp','generated-sources/simulation-driver.cpp',
                     'workdir-verilator/compilation-log.txt','workdir-verilator/execution-script.txt',
                     'workdir-verilator/simulation-log.txt','workdir-verilator/simulation'):
            if str(base/name) not in archive['files']:raise ValueError('Missing runtime build/execution artifact')
        if (base/'primary-sources/UsbSamplingEngine.v').read_bytes().rstrip(b'\n')!=local(witness['scenarios'][scenario]['hdl']).read_bytes().rstrip(b'\n'):
            raise ValueError('Mixed runtime HDL')
    return digest(path)


def sampling_evidence(manifest_path,top,sources):
    """Authenticate sampling safety and its exact standalone/wrapper contexts."""
    manifest_path=local(manifest_path,True);manifest=json.loads(manifest_path.read_text())
    if set(manifest)!={'schema','witness','witness_archive','context','sie_proof','sie_binding','sie_archive'} or manifest['schema']!=1:
        raise ValueError('Incomplete sampling manifest')
    if top not in ('UsbControl','UsbEngine','Usb'):raise ValueError('Unqualified sampling top')
    paths={k:local(v,True) for k,v in manifest.items() if k!='schema'}
    witness=json.loads(paths['witness'].read_text());context=json.loads(paths['context'].read_text())
    if witness.get('status')!='witnesses-pass' or witness.get('configuration')!={'vid':0,'pid':0,'bulk_packet_bytes':16}:
        raise ValueError('Missing/default-configuration sampling witnesses')
    check_hashes(witness['current_source_sha256']);check_hashes(witness['artifact_sha256']);check_hashes(witness['proofs'])
    if set(witness['scenarios'])!=SAMPLING_SCENARIOS:raise ValueError('Incomplete sampling scenario inventory')
    require_inventory(witness['artifact_sha256'],sampling_artifacts(paths['witness'].parent),'sampling witness artifact')
    for name,scenario in witness['scenarios'].items():
        base=paths['witness'].parent/name
        if (local(scenario['hdl'])!=base/'UsbSamplingEngine.v' or
                scenario['hdl_sha256']!=digest(base/'UsbSamplingEngine.v') or
                scenario['model_sha256']!=digest(base/'model.json')):
            raise ValueError('Mixed sampling scenario metadata')
    sampling_runtime_archive(paths['witness_archive'],paths['witness'],witness)
    simulation=witness['simulation'];log=paths['witness'].parent/'simulation.log'
    if (simulation['returncode']!=0 or simulation['log_sha256']!=digest(log) or
            simulation['command']!=[sys.executable,'tools/sbt.py','testOnly deadhorse.usb.UsbSamplingSpec'] or
            'Tests: succeeded 6, failed 0' not in log.read_text() or 'All tests passed.' not in log.read_text()):
        raise ValueError('Incomplete sampling witness execution')
    sampling_markers(simulation,log.read_text())
    if 'USB_SAMPLING_ROOT_RESET after_traffic=1 release=1' not in log.read_text():raise ValueError('Missing reset witness')
    roles={};emission=None;witness_sources={'hw/ip/usb/formal/sampling_witness.py','hw/ip/usb/formal/packet_receipt.py',
        'hw/ip/usb/src/test/scala/deadhorse/usb/UsbSamplingSpec.scala','hw/ip/usb/src/test/scala/deadhorse/usb/UsbWireHost.scala'}
    for name in witness['proofs']:
        path=local(name,True);proof=json.loads(path.read_text());role=proof.get('role')
        if role not in ('lookahead','outputs','spacing') or role in roles or proof.get('status')!='safety-proved':
            raise ValueError('Wrong sampling proof inventory')
        witness_sources.update(sampling_source_inventory(proof))
        for p,h in proof['source_sha256'].items():
            source=path.parent/'runner.py' if p=='hw/ip/usb/formal/sampling.py' else local(p)
            if digest(source)!=h:raise ValueError('Stale sampling proof source')
        emitted={p for folder in ('emit/engine','monitor') for p in (path.parent/folder).iterdir() if p.suffix in ('.sv','.v')}
        require_inventory(proof['emitted_sha256'],emitted,'sampling emission')
        canonical=path.parent/'canonical.json'
        if digest(canonical)!=proof['canonical_sha256']:raise ValueError('Stale sampling canonical')
        model=json.loads(canonical.read_text())
        count=3 if role=='spacing' else 4
        assertions={'sampling.assert__chisel3_builtin',*(f'sampling.assert__chisel3_builtin_{i}' for i in range(count-1))}
        if checked_job(proof['positive'],'proof')!=selected_model(model,'UsbEngine',assertions,set()):
            raise ValueError('Sampling solver used different claims or assumptions')
        replay=paths['witness'].parent/('audit-'+role)/'canonical.json'
        if json.loads(replay.read_text())!=model or str(replay) not in witness['artifact_sha256']:
            raise ValueError('No authenticated HDL-to-canonical replay')
        current={Path(p).name:h for p,h in proof['emitted_sha256'].items() if '/emit/engine/' in p}
        if emission is not None and current!=emission:raise ValueError('Mixed sampling production emissions')
        emission=current;roles[role]=dict(proof_sha256=digest(path),assertions=count)
    if set(roles)!={'lookahead','outputs','spacing'}:raise ValueError('Incomplete sampling roles')
    require_inventory(witness['current_source_sha256'],witness_sources,'sampling witness source')
    if (context.get('status')!='pass' or context.get('assumptions')!=[] or
            context.get('removed_observation_ports')!=['txEmpty','rxEmpty'] or
            context.get('jobs')!={'equivalence':'proved','wrong-next-cursor':'fault_rejected'} or
            context.get('checker_sha256')!=digest(ROOT/'hw/ip/usb/formal/resume_equivalence.py')):
        raise ValueError('Unqualified wrapper engine context')
    check_hashes(context['source_sha256']);require_inventory(context['artifact_sha256'],context_artifacts(paths['context'].parent),'context artifact')
    before={Path(p).name:h for p,h in context['source_sha256'].items() if '/emit/engine/' in p}
    if before!=emission or not context['state_bindings']:raise ValueError('Context proves a different engine')
    binding=json.loads(paths['sie_binding'].read_text())
    sie=sie_evidence(paths['sie_proof'],paths['sie_binding'],paths['sie_archive'])
    wrapper={Path(p).name:h for p,h in binding['emitted_sha256'].items()}
    after={Path(p).name:h for p,h in context['source_sha256'].items() if '/emit/usb/' in p}
    if after!=wrapper:raise ValueError('Wrapper context differs from qualified wrapper binding')
    if len(context['source_sha256'])!=len(before)+len(after):raise ValueError('Mixed context source inventory')
    actual={Path(p).name:digest(local(p)) for p in sources}
    expected=wrapper if top=='Usb' else emission if top=='UsbEngine' else {'UsbControl.sv':emission['UsbControl.sv']}
    if len(actual)!=len(sources) or actual!=expected:raise ValueError('Timing HDL differs from proved sampling context')
    return dict(status='pass',manifest_sha256=digest(manifest_path),roles=roles,wrapper=sie,
        context_sha256=digest(paths['context']),witness_sha256=digest(paths['witness']),
        assumptions=['Initial root reset; arbitrary later reset/VBUS/pad/application inputs'],
        unresolved_diagnostics=[witness['diagnostic_cover']],
        qualification='Eleven unbounded sampling assertions; actual-use guard and reset/error/abort witnesses plus five real DUT faults. Optional partial-header/new-SETUP coincidence remains unresolved.')


def full_size_evidence(path):
    row=json.loads(path.read_text())
    if row.get('status')!='pass':raise ValueError('Full-size simulation did not pass')
    if row.get('command')!=['python3','tools/sbt.py','testOnly deadhorse.usb.UsbThroughputSpec'] or row.get('returncode')!=0:
        raise ValueError('Wrong or incomplete full-size simulation command')
    if row.get('source_sha256')!=simulation_sources():raise ValueError('Incomplete or stale full-size source binding')
    check_hashes(row['source_sha256']);log=path.parent/'simulation.log'
    if digest(log)!=row['log_sha256'] or 'Tests: succeeded 2, failed 0' not in log.read_text() or 'All tests passed.' not in log.read_text():
        raise ValueError('Full-size seeded simulation receipt is incomplete')
    return dict(status='pass',receipt_sha256=digest(path),log_sha256=digest(log),qualification=row['qualification'])


def collect(manifest_path,output):
    manifest_path=local(manifest_path,True);output=local(output,True);output.mkdir(parents=True,exist_ok=False)
    result=dict(status='running',task='T19-packet-evidence',mode='read-only audit; no proof or CI execution',
                manifest_sha256=digest(manifest_path),collector_sha256=digest(Path(__file__)))
    try:
        flow=[Path(__file__),Path(__file__).with_name('check.py'),Path(__file__).with_name('test_evidence.py'),
              *(Path(__file__).parent/'formal').glob('*.py'),ROOT/'tools/formal.py']
        result['flow_sha256']={p.relative_to(ROOT).as_posix():digest(p) for p in flow}
        manifest=json.loads(manifest_path.read_text())
        required={'schema','receipts','anchors','sie_proof','sie_binding','sie_archive','full_size_simulation'}
        if set(manifest)!=required or manifest['schema']!=1:raise ValueError('Unknown/incomplete USB evidence manifest')
        if any(not isinstance(manifest[k],list) or not manifest[k] or not all(isinstance(p,str) for p in manifest[k]) for k in ('receipts','anchors')):
            raise ValueError('Missing packet evidence')
        paths=[local(p,True) for p in manifest['receipts']];anchors=[local(p,True) for p in manifest['anchors']]
        audit=audit_epoch(output/'packet-audit',paths,anchors)
        if audit.get('audit',{}).get('status')!='pass':raise ValueError('Packet artifact audit failed: '+audit.get('error','unknown error'))
        result['sie']=sie_evidence(*(local(manifest[k],True) for k in ('sie_proof','sie_binding','sie_archive')))
        result['full_size_simulation']=full_size_evidence(local(manifest['full_size_simulation'],True))
        result.update(inventory(audit['claims']))
        result['packet_audit_sha256']=digest(output/'packet-audit/result.json')
        result['inputs']={str(p):digest(p) for p in [*paths,*anchors,*(local(manifest[k],True) for k in
                       ('sie_proof','sie_binding','sie_archive','full_size_simulation'))]}
        check_hashes(result['flow_sha256'])
        if digest(manifest_path)!=result['manifest_sha256']:raise ValueError('Manifest changed during audit')
    except Exception as error:result.update(status='failed',error=str(error))
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=collect(a.manifest,a.output)
    print(r['status'].upper()+' USB evidence; closed='+str(len(r.get('closed',[])))+' unresolved='+str(r.get('unresolved',[])),flush=True)
    sys.exit(0 if r['status']=='pass' else 1)
