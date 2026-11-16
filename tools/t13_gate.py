"""Focused T13 local gate using fresh checks and authenticated prior evidence.

Requires the completed evidence tree under --evidence-root. This is deliberately
not a fresh full-repository CI run: expensive unchanged proofs/timing are reused
only with exact input fingerprints, current emission equality and negative checks.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import local, output_dir, run
from qualify_fpu_protocol_wide import protect
from jalr_receipts import verify_hashes
from assertion_partitions import assertions, validate_union
from complete_jalr_inventory import checker_witness
from critical_isa_witness import active_witness

UNCHANGED={'ibex_alu','ibex_controller','ibex_csr','ibex_counter','ibex_decoder',
 'ibex_ex_block','ibex_wb_stage','ibex_load_store_unit','ibex_multdiv_fast',
 'ibex_prefetch_buffer','ibex_fetch_fifo','ibex_register_file_ff'}
CHANGED={'ibex_compressed_decoder','ibex_cs_registers','ibex_id_stage','ibex_if_stage','ibex_core','ibex_top'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expect(condition,message):
    if not condition:raise ValueError(message)


def add_recorded(protected,hashes):
    expect(bool(hashes),'Empty required fingerprint inventory')
    for name,value in hashes.items():
        path=local(name)
        if str(path) in protected:
            expect(protected[str(path)]==value,'Conflicting evidence input: '+name)
            continue
        expect(sha(path)==value,'Stale evidence input: '+name)
        protect(protected,[path])


def read_receipt(path,protected,status):
    protect(protected,[path]);data=json.loads(path.read_text())
    expect(data.get('status')==status,'Incomplete receipt: '+str(path))
    return data


def authenticated(path,protected,status):
    data=read_receipt(path,protected,status)
    add_recorded(protected,data['input_sha256'])
    return data


def inventory(directory):
    files=sorted(p for p in directory.rglob('*') if p.is_file())
    expect(bool(files),'Missing emission directory: '+str(directory))
    expect(all(p.suffix in ('.sv','.f') for p in files),'Unexpected emission file')
    return {p.relative_to(directory).as_posix():sha(p) for p in files}


def equal_emission(fresh,prior,protected):
    a=inventory(fresh);b=inventory(prior)
    expect(a==b,'Fresh emission differs: '+str(prior))
    protect(protected,[fresh/n for n in a]+[prior/n for n in b])
    return a


def candidate_mapping(directory,emission,protected):
    manifest=directory/'candidate.json';protect(protected,[manifest]);data=json.loads(manifest.read_text())
    expect(data['schema']==2 and data['kind']=='fixed','Unexpected candidate format')
    maps={**data['source_sha256'],**data['extra_sources']}
    for name,value in maps.items():
        path=directory/name;expect(sha(path)==value,'Candidate mapping mismatch: '+str(path));protect(protected,[path])
        emitted=emission/Path(name).name
        # These standalone formal leaf views are inlined in the production emitter.
        if name in ('rtl/ibex_csr.sv','rtl/ibex_counter.sv'):continue
        expect(emitted.is_file() and sha(emitted)==value,'Candidate not bound to emission: '+name)
    return data


def equivalence(path,protected,expected='proved',negatives=None,original_gold=None):
    data=read_receipt(path,protected,expected)
    expect(set(data['elaborations'])=={'gold','candidate'},'Incomplete elaboration binding roles')
    netlists={'gold':data.get('gold',original_gold),'candidate':data.get('candidate',str(path.parent/'fault.json'))}
    for role,meta in data['elaborations'].items():
        expect(role in ('gold','candidate'),'Unexpected elaboration role')
        add_recorded(protected,meta['source_sha256'])
        netlist=local(netlists[role]);expect(sha(netlist)==meta['netlist_sha256'],'Netlist fingerprint differs')
        protect(protected,[netlist])
    if data['engine']=='Yosys SAT':
        log=path.parent/'compare.log';protect(protected,[log,path.parent/'compare.ys'])
        marker='SAT proof finished - no model found: SUCCESS!' if expected=='proved' else 'SAT proof finished - model found: FAIL!'
        expect(marker in log.read_text(),'Equivalence solver outcome missing')
    else:
        expect(expected=='failed' and data['engine']=='state/interface correspondence' and
               data['reason'].startswith('State kind/reset/width/polarity differs:'),'Unexpected structural rejection')
    if expected=='proved':
        faults=negatives if negatives is not None else data.get('negative_controls',[])
        expect(bool(faults),'Missing equivalence negative controls')
        for fault in faults:
            equivalence(path.parent/'negative'/fault/'result.json',protected,'failed',original_gold=data['gold'])
    return data


def source_snapshot():
    roots=['tools','dv/core','dv/fpu','hw/ip/perf_core','hw/ip/fpu','hw/lib','hw/vendor','sw','project']
    files=[ROOT/n for n in ('build.sbt','.scalafmt.conf') if (ROOT/n).exists()]
    for name in roots:
        files += [p for p in (ROOT/name).rglob('*') if p.is_file() and
                  not any(x in p.parts for x in ('__pycache__','.git','target'))]
    return sorted(set(files))


def validate_prior(base,protected):
    summary={}
    timing=read_receipt(base/'timing-exponent/result.json',protected,'pass')
    add_recorded(protected,timing['source_sha256']);add_recorded(protected,timing['flow_sha256'])
    expect(len(timing['flow_sha256'])==6 and timing['budget_ns']==24.96,'Timing flow/budget changed')
    expect(timing['worst']['delay_ns']<=timing['budget_ns'],'Timing budget missed')
    expect(timing['electrical']['max_capacitance_and_slew_violations']==0,'Electrical violation')
    expect(all(x['slack_ns']>=0 for x in timing['clock_gate_checks']),'Clock gate timing violation')
    for filename,key in [('mapping.abc','script_sha256'),('mapping.constr','constraints_sha256')]:
        path=base/'timing-exponent'/filename
        expect(sha(path)==timing['mapping'][key],'Timing mapping configuration changed');protect(protected,[path])
    budget=ROOT/'phys/gf180-ws-1x1/block-timing.json'
    expect(json.loads(budget.read_text())==timing['assumptions'],'Timing assumption inventory changed')
    library=ROOT/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    expect(sha(library)==timing['assumptions']['sha256'],'Timing library changed');protect(protected,[library,budget])
    summary['timing']='authenticated prior; unchanged sources, library and six flow digests'
    unchanged=read_receipt(base/'unchanged/result.json',protected,'proved')
    expect(set(unchanged['modules'])==UNCHANGED and set(unchanged['changed_modules_pending'])==CHANGED,'Module classification changed')
    archive=base/'unchanged/baseline.tar'
    expect(sha(archive)==unchanged['archive_sha256'],'Tagged baseline archive mismatch');protect(protected,[archive])
    tag=subprocess.check_output(['git','rev-parse','t11-baseline^{commit}'],cwd=ROOT,text=True).strip()
    expect(tag==unchanged['baseline_commit'],'T11 baseline tag changed')
    directory=ROOT/'hw/ip/perf_core/src/main/scala/deadhorse/perf_core'
    observed=set()
    for module in UNCHANGED|CHANGED:
        stem={'ibex_register_file_ff':'ibexregisterfile'}.get(module,module.replace('_',''))
        matches=[p for p in directory.glob('*.scala') if p.stem.lower()==stem]
        expect(len(matches)==1,'Missing/ambiguous Chisel module source')
        source=matches[0];old=subprocess.check_output(['git','show',tag+':'+source.relative_to(ROOT).as_posix()],cwd=ROOT)
        if old.replace(b'\r\n',b'\n')==source.read_bytes().replace(b'\r\n',b'\n'):observed.add(module)
    expect(observed==UNCHANGED,'Current untouched-module classification differs')
    manifest=base/'exponent/candidate/candidate.json'
    expect(sha(manifest)==unchanged['candidate_sha256'],'Unchanged proof candidate manifest changed')
    for module in sorted(UNCHANGED):
        faults=unchanged['modules'][module]['negative_controls']
        expected={'output'} if module in ('ibex_alu','ibex_decoder','ibex_wb_stage') else {'output','reset-value','next-state'}
        if module=='ibex_multdiv_fast':expected.add('division-sign')
        if module in ('ibex_prefetch_buffer','ibex_fetch_fifo'):expected.add('gained-reset')
        expect(set(faults)==expected,'Unchanged negative inventory differs')
        equivalence(base/'unchanged'/module/'result.json',protected,negatives=faults)
    baseline=equivalence(base/'baseline-equivalence/result.json',protected)
    expect(set(baseline['negative_controls'])=={'output','reset-value','next-state','gained-reset'},'Default baseline negative inventory differs')
    expect(baseline['correspondence']['state_elements']==246,'Default baseline state inventory changed')
    for role in ('before','after'):
        revision=baseline['revisions'][role];manifest=local(revision['path'])/'candidate.json'
        expect(sha(manifest)==revision['manifest_sha256'],'Default baseline manifest changed');protect(protected,[manifest])
    summary['unchanged']='authenticated prior 12 modules and every negative'
    summary['default_baseline']='authenticated prior exact 246-state equivalence and every negative'
    for name,status in (
        ('if-conditional-confirmed','proved (local conditional IF equivalence); independent review pending'),
        ('fpu-protocol-wide-confirmed','pass (all-port FPU protocol trace inclusion); integration safety and ISA reruns pending'),
        ('jalr-original-complete','pass (all33 original JALR assertions with qualification; other ISA unresolved)'),
        ('integration-wide','pass (28 integration safety assertions; eight abstract covers); ISA unresolved')):
        data=authenticated(base/name/'result.json',protected,status)
        validate_shape(name,base/name,data,protected)
        summary[name]={'kind':'authenticated prior','inputs':len(data['input_sha256'])}
    # Required fresh companion and bounded lw/c_add acceptance are validated below;
    # missing or unresolved evidence always prevents gate acceptance.
    verify_hashes(protected)
    return summary


def actual_status(directory,record,expected,returncode,protected):
    status=directory/'work/status';protect(protected,[status])
    expect(record['status']==expected and record['returncode']==returncode and
           status.read_text().split()[0]==expected,'Proof role status/return code mismatch')


def validate_shape(name,directory,data,protected):
    results=data['results']
    if name=='integration-wide':
        expect(set(results)=={'normal','fault','cover'},'Integration role inventory differs')
        for role,status,rc,properties in [('normal','PASS',0,{'assert':28}),('fault','FAIL',2,{'assert':28}),('cover','PASS',0,{'cover':8})]:
            actual_status(directory/role,results[role],status,rc,protected)
            expect(results[role]['properties']==properties,'Integration property inventory differs')
            if role!='normal':
                witnesses=results[role]['witnesses'];expect(len(witnesses)>=(8 if role=='cover' else 1),'Integration witness inventory incomplete')
                for w in witnesses:
                    expect(sha(local(w['path']))==w['sha256'],'Integration witness changed')
    elif name=='fpu-protocol-wide-confirmed':
        roles={'base','control-step','outputs','step','no-instant-completion'}
        expect(set(results)==roles|{r+'-negative' for r in roles},'Wide protocol role inventory differs')
        for role,item in results.items():
            negative=role.endswith('-negative');expect(item['status']==('rejected' if negative else 'proved'),'Wide protocol role failed')
            log=directory/role/'check.log';protect(protected,[log])
            marker='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
            expect(marker in log.read_text(),'Wide protocol solver outcome missing')
    elif name=='jalr-original-complete':
        original=local('build/t13/jalr-address-strengthened/original.json')
        expect(str(original) in protected,'Original JALR model unbound')
        model=json.loads(original.read_text());names=assertions(model)
        expect(len(names)==33 and data['assertions']=={n:model['modules']['rvfi_testbench']['cells'][n] for n in names},'Original JALR assertion object inventory differs')
        validate_union(names,data['groups'])
        expect(set(results)=={'original-cover','original-fault'},'JALR witness role inventory differs')
        for role,status,rc in [('original-cover','PASS',0),('original-fault','FAIL',2)]:
            actual_status(directory/role,results[role],status,rc,protected)
            expect(bool(results[role]['witnesses']),'Missing concrete JALR witness')
            for w in results[role]['witnesses']:
                trace=local(w['path']);expect(sha(trace)==w['sha256'] and checker_witness(trace.read_text(),role=='original-fault')==w['event'],'JALR active witness differs')
    elif name=='if-conditional-confirmed':
        expected={'integrated-binding':'proved','integrated-binding-negative':'rejected','normal':'proved','input-equality':'proved',
            'active-transfer-cover':'covered','output-fault':'rejected','transition-fault':'rejected','reset-fault':'rejected'}
        expect({k:v['status'] for k,v in results.items()}==expected,'Conditional IF proof role inventory differs')


def validate_critical(path,protected):
    data=authenticated(path,protected,'pass (bounded critical ISA only); no unbounded ISA proof')
    expect(set(data['results'])=={'lw','c_add'},'Critical ISA inventory changed')
    expect(data['depth']==144 and data['check_cycle']==64 and data['timeout_seconds']==120,'Critical ISA limits changed')
    for name,item in data['results'].items():
        expect(set(item['checks'])=={'bmc','cover','negative'},'Critical ISA role missing')
        for role,want in [('bmc','PASS'),('cover','PASS'),('negative','FAIL')]:
            result=item['checks'][role]
            actual_status(path.parent/name/role,result,want,2 if role=='negative' else 0,protected)
            expect(result['concrete']==(role!='bmc'),'Critical cover/fault not concrete')
            if role!='bmc':
                expect(bool(result['witnesses']),'Missing concrete critical witness')
                for w in result['witnesses']:
                    trace=local(w['path'])
                    expect(sha(trace)==w['sha256'] and active_witness(trace.read_text(),name,role=='negative')==w['event'],'Critical active witness differs')
    return data


def validate_fpu(protected):
    path=ROOT/'build/t13/fpu-revalidation/result.json';data=read_receipt(path,protected,'pass')
    replaced={'hw/ip/fpu/formal/check.py','hw/ip/fpu/formal/receipt.py','hw/ip/fpu/formal/test_receipt.py'}
    expect(replaced<=set(data['sources']),'Unexpected old FPU source inventory')
    add_recorded(protected,{k:v for k,v in data['sources'].items() if k not in replaced})
    spec=importlib.util.spec_from_file_location('t13_fpu_receipt',ROOT/'hw/ip/fpu/formal/receipt.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    authenticated=module.authenticate(ROOT,ROOT/'build/t12/formal')
    add_recorded(protected,authenticated['artifacts']);add_recorded(protected,authenticated['protected'])
    vectors_path=ROOT/'build/t12/vectors.json';vectors=json.loads(vectors_path.read_text())
    expect(sha(ROOT/'build/t12/vectors.txt')==vectors['sha256'],'FPU vector data differs from reference receipt')
    expect(vectors['count']==184380 and vectors['rounding_modes']==list(range(5)) and len(vectors['operations'])==24,'FPU reference coverage changed')
    expect(all(c['returncode']==0 for c in data['commands']),'Historical T12 command failed')
    expect(data['checker_controls']['positive']=='pass' and all(v=='rejected' for k,v in data['checker_controls'].items() if k!='positive'),'Historical FPU checker fault escaped')
    protect(protected,[ROOT/'build/t12/formal/result.json',ROOT/'build/t12/vectors.txt',vectors_path,ROOT/'build/t12/oracle'])
    return 'unchanged T12 inputs authenticated; three replaced protocol helpers covered by current schema2 protocol plus fresh unit tests'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence-root',default='build/t13');ap.add_argument('--output',default='build/t13/gate')
    ap.add_argument('--binding',default='build/t13/integration-production-binding/result.json')
    ap.add_argument('--critical',default='build/t13/critical-wide/result.json')
    args=ap.parse_args();base=local(args.evidence_root);out=output_dir(args.output)
    receipt=dict(status='running',scope='focused T13; authenticated prior proofs/timing plus fresh critical checks; not full repository CI',fresh=[],prior={})
    protected={}
    try:
        initial_sources=source_snapshot();protect(protected,initial_sources);verify_hashes(protected)
        receipt['prior']=validate_prior(base,protected)
        # Fresh production binding is mandatory alongside the raw safety receipt.
        binding=authenticated(local(args.binding),protected,'pass (fresh concrete integration instrumentation-to-production binding; no safety proof rerun)')
        expect(binding['safety_receipt']=={'path':str(base/'integration-wide/result.json'),'sha256':sha(base/'integration-wide/result.json')},'Integration companion targets different proof')
        expect({k:v['status'] for k,v in binding['results'].items()}=={'positive':'proved','output':'rejected','reset-value':'rejected','next-state':'rejected','clock':'rejected'},'Integration binding fault inventory incomplete')
        validate_critical(local(args.critical),protected)
        receipt['prior']['fpu']=validate_fpu(protected)
        for label,emit in [('float','exponent/emit'),('no-f','no-f-current')]:
            protect(protected,[p for p in (base/emit).rglob('*') if p.is_file()])
        hardfloat=ROOT/'hw/vendor/hardfloat';lock=hardfloat/'hardfloat.lock.json'
        for name,value in json.loads(lock.read_text())['files'].items():
            expect(sha(hardfloat/name)==value,'HardFloat lock mismatch')
        def execute(label,argv,timeout=180):
            expect(source_snapshot()==initial_sources,'Source inventory changed during gate')
            verify_hashes(protected)
            result=run(argv,out,label,timeout=timeout)
            expect(source_snapshot()==initial_sources,'Source inventory changed during gate')
            verify_hashes(protected)
            receipt['fresh'].append(dict(name=label,command=list(map(str,argv)),status='pass',seconds=result.elapsed_seconds))
            (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        py=sys.executable
        commands=[('environment',[py,'tools/env/check.py']),
            ('ibex-lock',[py,'hw/vendor/ibex_ref/verify_lock.py']),
            ('tool-units',[py,'-m','unittest','discover','-s','tools','-p','test_*.py']),
            ('core-units',[py,'-m','unittest','discover','-s','dv/core','-p','test_*.py']),
            ('fpu-receipt-units',[py,'-m','unittest','discover','-s','hw/ip/fpu/formal','-p','test_*.py']),
            ('structure',[py,'tools/check_structure.py','--include-untracked']),
            ('perf-core-tests',[py,'tools/sbt.py','hw/testOnly deadhorse.perf_core.*'])]
        for label,argv in commands:execute(label,argv,timeout=None if label=='perf-core-tests' else 180)
        for label,emitter,old in [('float','EmitFloatCore','exponent/emit'),('no-f','EmitRegisteredCore','no-f-current')]:
            emitted=out/(label+'-emit')
            expect(not emitted.exists(),'Fresh emitter destination already exists')
            execute(label+'-emit',[py,'tools/sbt.py',f'hw/runMain deadhorse.perf_core.{emitter} {emitted.relative_to(ROOT).as_posix()}'])
            receipt['fresh'].append(dict(name=label+'-emission-equality',status='pass',inventory=equal_emission(emitted,base/old,protected)))
        candidate_mapping(base/'exponent/candidate',out/'float-emit/model',protected)
        candidate_mapping(base/'current-baseline',out/'no-f-emit/model',protected)
        execute('lockstep',[py,'dv/core/lockstep.py','--candidate',str(base/'exponent/candidate'),'--isa','rv32imfc','--suite','arch,random,flight-float','--output',str(out/'lockstep')])
        execute('no-f-local',[py,'hw/ip/perf_core/formal/check_no_f.py','--baseline',str(base/'unchanged/baseline'),'--candidate',str(base/'exponent/candidate'),'--output',str(out/'no-f-local')])
        execute('fpu-iss',[py,'dv/fpu/iss.py'])
        execute('fpu-vectors',[py,'dv/fpu/sim.py'])
        expect(source_snapshot()==initial_sources,'Source inventory changed during gate')
        verify_hashes(protected);receipt['status']='pass (focused T13 gate; cached proof prerequisites authenticated)'
        print('PASS focused T13 gate; full repository CI was not run',flush=True)
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
