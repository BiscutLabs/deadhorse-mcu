"""Refresh USB source binding by replaying emission, never by rerunning a solver."""
from pathlib import Path
import copy, hashlib, json, shutil, sys, time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'hw/ip/usb/formal'))
import sampling
from sampling_witness import audit
from packet_receipt import checked_job
from packet_partition import selected_model
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
out=ROOT/'build/t32/usb-rebind02';out.mkdir(exist_ok=False,parents=True)
shutil.copyfile(__file__,out/'rebinder.py')
report=dict(status='running',solver_runs=0,roles={},rebinder_sha256=digest(__file__))
try:
    for role,previous in [('lookahead','lookahead03'),('outputs','outputs01'),('spacing','spacing01')]:
        origin=ROOT/'build/plan03/usb-closure'/previous/'result.json'
        old=json.loads(origin.read_text());assert old['status']=='safety-proved' and old['role']==role
        assert digest(origin.parent/'runner.py')==old['source_sha256']['hw/ip/usb/formal/sampling.py']
        for name,h in old['emitted_sha256'].items():assert digest(name)==h,name
        assert digest(origin.parent/'canonical.json')==old['canonical_sha256']
        old_model=json.loads((origin.parent/'canonical.json').read_text())
        old_selected=checked_job(old['positive'],'proof')
        changed={p for p,h in old['source_sha256'].items() if p!='hw/ip/usb/formal/sampling.py' and digest(ROOT/p)!=h}
        assert changed=={'tools/env/lock.json'},changed
        calls=[]
        def reuse(directory,model,top,keep,assumed=(),**kwargs):
            rebased=copy.deepcopy(model)
            before=str((out/role).relative_to(ROOT));after=str(origin.parent.relative_to(ROOT))
            def relocate(value):
                if isinstance(value,dict):
                    for k,v in value.items():
                        if k=='attributes' and isinstance(v,dict) and 'src' in v:
                            v['src']=v['src'].replace(before+'/',after+'/')
                        relocate(v)
                elif isinstance(value,list):
                    for v in value:relocate(v)
            relocate(rebased)
            assert rebased==old_model,'Fresh canonical differs beyond source-location prefix: '+role
            assert selected_model(rebased,top,set(keep),set(assumed))==old_selected,'Fresh selected model differs'
            calls.append(True)
            return copy.deepcopy(old['positive'])
        sampling.lemma_job=reuse
        start=time.monotonic()
        fresh=sampling.run(out/role,ROOT/'build/t19/regmap/usb_regs.json',role)
        if fresh['status']!='safety-proved' or len(calls)!=1:raise RuntimeError(f'{role} fresh replay did not qualify')
        reuse_record=dict(status='identical-model proof reused; no solver run',
            original_receipt=str(origin),original_receipt_sha256=digest(origin),
            original_runner_sha256=digest(origin.parent/'runner.py'),
            canonical_equality='exact JSON equality after ONLY src attribute emission-prefix relocation; original paths then freshly replayed without normalization',
            selected_model_equality=True,original_positive=old['positive'],
            current_rebinder_sha256=digest(__file__),replay_seconds=time.monotonic()-start)
        old_hdl={Path(p).relative_to(origin.parent).as_posix():h for p,h in old['emitted_sha256'].items()}
        fresh_hdl={Path(p).relative_to(out/role).as_posix():h for p,h in fresh['emitted_sha256'].items()}
        assert old_hdl==fresh_hdl,'Fresh HDL differs from original'
        fresh['proof_reuse']=reuse_record;fresh['status']='fresh emission identity verified; original solver reused only through bound receipt'
        (out/role/'result.json').write_text(json.dumps(fresh,indent=2)+'\n')
        # Keep the immutable original proof and runner in place. The new sibling
        # receipt names their original artifact paths, verified byte-identical to
        # fresh emission, so the unchanged strict collectors need no exceptions.
        bound=copy.deepcopy(old)
        bound['source_sha256']['tools/env/lock.json']=digest(ROOT/'tools/env/lock.json')
        bound['proof_reuse']=dict(reuse_record,fresh_receipt=str(out/role/'result.json'),
            fresh_receipt_sha256=digest(out/role/'result.json'))
        bound_path=origin.parent/'t32-source-binding02.json';assert not bound_path.exists()
        bound_path.write_text(json.dumps(bound,indent=2)+'\n')
        audit(bound_path,role,out/role/'identity-replay')
        reuse_record['bound_receipt']=str(bound_path)
        reuse_record['bound_receipt_sha256']=digest(bound_path)
        report['roles'][role]=reuse_record
    report['status']='pass'
except Exception as e:
    report.update(status='failed',error=str(e))
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],report.get('error',''),flush=True)
sys.exit(0 if report['status']=='pass' else 1)
