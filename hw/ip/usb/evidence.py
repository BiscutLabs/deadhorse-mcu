"""Read-only USB acceptance evidence integration. No solver, synthesis or CI."""
import argparse
import hashlib
import json
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
