"""Audit one receipt per original packet claim; retain unresolved obligations."""
import argparse
import copy
import json
from pathlib import Path
import sys

from packet_decompose import ROOT, PROPERTIES, STATEMENTS, NAMES, digest, save, fault, validate_job
from packet_partition import selected_model, qualified_assumptions, lemma_job
from memory_refinement import bind


def bound_receipt(path):
    path=Path(path).resolve();path.relative_to(ROOT/'build')
    row=json.loads(path.read_text())
    if row.get('status') not in ('pass','unresolved'):
        raise ValueError('Incomplete or failed receipt: '+str(path))
    for name,h in row['source_sha256'].items():
        if digest(ROOT/name)!=h:raise ValueError('Stale source: '+name)
    return row


def checked_job(row,kind):
    directory=Path(row['directory'])
    if digest(directory/'model.json')!=row['model_sha256'] or digest(directory/'job.sby')!=row['config_sha256']:
        raise ValueError('Changed proof artifacts')
    if digest(directory/'job/src/model.json')!=row['model_sha256']:
        raise ValueError('Solver used a different transition system')
    status=(directory/'job/status').read_text().split()[0]
    if status!=row['solver_status']:raise ValueError('Solver status differs from receipt')
    if kind=='proof' and row['mode']!='prove':raise ValueError('Bounded evidence cannot close an assertion')
    validate_job(directory/'job',kind,row['returncode'],status)
    return json.loads((directory/'model.json').read_text())


def legacy_job(row,directory,top):
    """Recover absent v1 metadata only after checking the archived exact recipe."""
    result=copy.deepcopy(row)
    expected='\n'.join(['[options]',f'mode {row["mode"]}','depth 48','timeout 120',
        '[engines]',row['engine'],'[script]','read_json model.json',f'hierarchy -check -top {top}',
        'select -assert-count 1 t:$assert','opt_clean -purge','stat -width','[files]',
        str((directory/'model.json').resolve())])+'\n'
    if (directory/'job.sby').read_text()!=expected:raise ValueError('Legacy job recipe changed')
    result.update(directory=str(directory),config_sha256=digest(directory/'job.sby'),metadata_recovered=True)
    return result


def run(output,split,helpers):
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    original=bound_receipt(split);chain=bound_receipt(helpers)
    size=chain['packet_bytes']
    if size not in (8,16):raise ValueError('Unsupported proof geometry')
    if chain['original_split']!={'path':str(split.resolve()),'sha256':digest(split)}:
        raise ValueError('Different singleton baseline')
    # Archives authenticate the historical solver recipes without requiring an
    # unchanged current runner after a diagnosed tooling refinement.
    for receipt,path,runner in ((original,split,'packet_decompose.py'),(chain,helpers,'packet_partition.py')):
        key='hw/ip/usb/formal/'+runner
        if digest(path.parent/runner)!=receipt['flow_sha256'][key]:raise ValueError('Missing runner archive')
    result=dict(status='running',packet_bytes=size,source_sha256=chain['source_sha256'],jobs=[],
        inputs={str(p.resolve()):digest(p) for p in (split,helpers)},
        assumptions='Original common-reset harness; initial reset asserted, later resets arbitrary. No E1/E2.',
        qualification='Sparse proofs use independently proved memory containment and age-qualified observations; not full SIE/transport-reset composition.')
    save(output/'result.json',result)
    try:
        for role,top in [('in','UsbInFormal'),('out','UsbOutFormal')]:
            info=chain['roles'][role]
            canonical_path=Path(info['canonical']);model=json.loads(canonical_path.read_text())
            if digest(canonical_path)!=info['model_sha256']:raise ValueError('Changed canonical model')
            real_path=canonical_path.parent/'real.json';real=json.loads(real_path.read_text())
            if digest(real_path)!=info['real_model_sha256']:raise ValueError('Changed real model')
            real_count=18 if role=='in' else 14
            real_names=['assert__chisel3_builtin',*(f'assert__chisel3_builtin_{i}' for i in range(real_count-1))][-6:]
            for index,prop in enumerate(PROPERTIES):
                first=next(j for j in original['jobs'] if j['role']==role and j['property']==prop)
                later=next((j for j in chain['jobs'] if j['role']==role and j.get('property')==prop),None)
                row=dict(role=role,property=prop,statement=STATEMENTS[role][index],kind='unresolved')
                if size==16 and first['positive']['result']=='proved':
                    proof=legacy_job(first['positive'],split.parent/role/(prop+'-positive'),top)
                    actual=checked_job(proof,'proof')
                    prepared=split.parent/role/'prepared.json'
                    if digest(prepared)!=first['model_sha256']:raise ValueError('Changed original model')
                    expected=selected_model(json.loads(prepared.read_text()),top,{NAMES[index]},set())
                    if actual!=expected:raise ValueError('Singleton transition system changed')
                    negative=legacy_job(first['negative'],split.parent/role/(prop+'-negative'),top)
                    checked_job(negative,'negative')
                    row.update(kind='proved',positive=proof,negative=negative,assumptions=[])
                elif later and later['positive']['result']=='proved':
                    assumed=qualified_assumptions(later['dependencies'],model,top,info['model_sha256'])
                    proof=later['positive'];actual=checked_job(proof,'proof')
                    expected=selected_model(model,top,{info['originals'][prop]},assumed)
                    if actual!=expected:raise ValueError('Original proof uses unqualified assumptions')
                    # A fresh real-DUT mutation targets this exact original claim,
                    # with no good-DUT helper assumptions imposed on the fault.
                    bad=copy.deepcopy(real);mutation=fault(bad,top,role,prop)
                    negative=lemma_job(output/(role+'-'+prop+'-negative'),bad,top,{real_names[index]},
                                       mode='bmc',engine='btor btormc')
                    if negative['result']!='fault_rejected':raise ValueError('Original fault escaped: '+role+'.'+prop)
                    row.update(kind='proved' if size==16 else 'proved at small model',positive=proof,negative=negative,mutation=mutation,
                               assumptions=sorted(assumed),dependencies=later['dependencies'],abstracted=True)
                else:
                    if size==8 and not later:
                        row.update(positive=dict(result='unresolved',reason='Small-model helper did not qualify'),assumptions=[])
                    else:row.update(positive=(later or first)['positive'],
                               assumptions=(later or first)['positive'].get('assumed_assertions',[]),
                               dependencies=(later or first).get('dependencies',[]))
                result['jobs'].append(row);save(output/'result.json',result)
                print(role,prop,row['kind'],flush=True)
        identities=[(j['role'],j['property']) for j in result['jobs']]
        if len(identities)!=12 or set(identities)!={(r,p) for r in ('in','out') for p in PROPERTIES}:
            raise ValueError('Original assertions not accounted exactly once')
        result['status']='unresolved' # Terminal composition/real cover audit still required.
    except Exception as error:result.update(status='failed',error=str(error))
    save(output/'result.json',result)
    return result


def audit(output,accounting,helpers,baseline,small_covers=None):
    """Qualify partial results, without rerunning a solver or dropping open rows."""
    output=output.resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    result=bound_receipt(accounting);chain=bound_receipt(helpers)
    size=chain['packet_bytes']
    if result['packet_bytes']!=size or result['inputs'].get(str(helpers.resolve()))!=digest(helpers):
        raise ValueError('Mixed accounting/helper geometry or receipt')
    frozen={str(accounting.resolve()):digest(accounting),str(helpers.resolve()):digest(helpers)}
    flows={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'hw/ip/usb/formal/packet_partition.py',ROOT/'tools/formal.py')}
    result['audit']=dict(status='running',inputs=frozen,flow_sha256=flows)
    try:
        refinement=Path(chain['refinement']['path'])
        if digest(refinement)!=chain['refinement']['sha256']:raise ValueError('Changed refinement receipt')
        memory=bound_receipt(refinement)
        if memory['status']!='pass' or memory['expected_packet_bytes']!=size:raise ValueError('Wrong refinement geometry/status')
        frozen[str(refinement)]=digest(refinement)
        for row in memory['jobs']:
            variant=row['variant'];directory=refinement.parent/variant
            prepared=json.loads((directory/'prepared.json').read_text())
            if bind(prepared,size)!=json.loads((directory/'bound.json').read_text()):raise ValueError('Changed memory witness relation')
            if digest(directory/'bound.json')!=digest(directory/'job/src/bound.json'):
                raise ValueError('Memory solver used a different witness relation')
            status=(directory/'job/status').read_text().split()[0]
            if status!=row['status']:raise ValueError('Changed memory proof status')
            validate_job(directory/'job','cover' if variant=='cover' else 'negative' if variant=='corrupt' else 'proof',row['returncode'],status)
            for p in (directory/'bound.json',directory/'job.sby',directory/'job/status'):frozen[str(p)]=digest(p)
        covers={}
        if size==8:
            if not small_covers:raise ValueError('Missing D62 small-model covers')
            controls=bound_receipt(small_covers);frozen[str(small_covers)]=digest(small_covers)
            if controls['status']!='pass' or controls['packet_bytes']!=8 or controls['environment']!='original':
                raise ValueError('Wrong D62 cover model')
            for entry in controls['jobs']:
                row=entry['cover'];directory=Path(row['directory'])
                if row['depth']!=128 or digest(directory/'job.sby')!=row['config_sha256'] or any(digest(p)!=h for p,h in row['emitted_sha256'].items()):
                    raise ValueError('Changed small cover artifacts')
                validate_job(directory/'job','cover',row['returncode'],(directory/'job/status').read_text().split()[0])
                covers[entry['role']]=row
            if set(covers)!={'in','out'}:raise ValueError('Missing small-model direction')
        else:
            control_path=baseline/'packet-controls/result.json'
            controls=json.loads(control_path.read_text());frozen[str(control_path)]=digest(control_path)
            for p,h in controls['production_source_sha256'].items():
                if digest(ROOT/p)!=h:raise ValueError('Stale real controls')
            for role in ('in','out'):
                row=next(j for j in controls['cases'][role]['jobs'] if j['variant']=='cover')
                directory=control_path.parent/role
                if {p.name:digest(p) for p in (directory/'emit/cover').glob('*.sv')}!=row['source_sha256']:
                    raise ValueError('Changed real cover emission')
                status=(directory/'cover/status').read_text().split()[0]
                validate_job(directory/'cover','cover',row['returncode'],status)
                covers[role]=row
        for row in result['jobs']:
            if row['kind'] not in ('proved','proved at small model'):
                later=next((j for j in chain['jobs'] if j['role']==row['role'] and j.get('property')==row['property']),None)
                if later:
                    row.update(assumptions=later['positive'].get('assumed_assertions',[]),dependencies=later.get('dependencies',[]))
                continue
            checked_job(row['positive'],'proof');checked_job(row['negative'],'negative')
            if row.get('abstracted'):
                info=chain['roles'][row['role']];model=json.loads(Path(info['canonical']).read_text())
                qualified_assumptions(row['dependencies'],model,'UsbInFormal' if row['role']=='in' else 'UsbOutFormal',info['model_sha256'])
        result['audit'].update(status='pass',memory_refinement=str(refinement),real_covers=covers,
            reset_composition='Common reset: proved memoryAge==3 on every enable; IN observations in these original properties occur at enable, OUT captures RAM only at enable after warmup. Arbitrary later resets retained.')
        if any(digest(ROOT/p)!=h for p,h in result['source_sha256'].items()) or any(digest(p)!=h for p,h in frozen.items()):
            raise ValueError('Audit inputs changed')
        if any(digest(ROOT/p)!=h for p,h in flows.items()):raise ValueError('Audit flow changed')
    except Exception as error:result.update(status='failed',error=str(error));result['audit']['status']='failed'
    save(output/'result.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ('output','helpers'):parser.add_argument('--'+option,type=Path,required=True)
    parser.add_argument('--split',type=Path);parser.add_argument('--audit',type=Path);parser.add_argument('--baseline',type=Path)
    parser.add_argument('--small-cover-receipt',type=Path)
    args=parser.parse_args()
    if args.audit:
        if not args.baseline and not args.small_cover_receipt:parser.error('Audit requires real control baseline')
        receipt=audit(args.output,args.audit,args.helpers,args.baseline,args.small_cover_receipt)
    else:
        if not args.split:parser.error('Accounting requires original split')
        receipt=run(args.output,args.split,args.helpers)
    print(receipt['status'].upper()+' original packet assertion accounting',flush=True)
    sys.exit(0 if receipt['status']=='pass' else 1)
