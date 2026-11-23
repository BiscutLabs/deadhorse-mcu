"""Fresh HDL identity audit for existing debug proof evidence; runs no solver."""
from pathlib import Path
import hashlib,json,subprocess,time,sys
ROOT=Path.cwd();out=ROOT/'build/t32/current-binding01';out.mkdir(parents=True,exist_ok=False)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=[p for folder in ('hw/ip/debug','hw/lib','hw/ip/bus','hw/ip/bus_bridge','hw/top/reference')
    for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.scala','.py')]
sources += [ROOT/p for p in ('tools/sbt.py','tools/formal.py','tools/env/lock.json','build.sbt')]
hashes=lambda:{p.relative_to(ROOT).as_posix():digest(p) for p in sources}
r=dict(status='running',source_sha256=hashes(),solver_runs=0,claims=[],commands=[],producer_sha256=digest(Path(__file__)))
try:
    command=[sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/debug/formal")',
        f'hw/runMain deadhorse.debug.EmitDebugFormal {out}/local',f'hw/runMain deadhorse.debug.EmitDebugEpochFormal {out}/epoch']
    start=time.monotonic()
    with(out/'emit.log').open('w') as f:p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=600)
    r['commands'].append(dict(command=command,returncode=p.returncode,seconds=time.monotonic()-start))
    assert p.returncode==0,'Fresh emission failed'
    for label,origin in [('local',ROOT/'build/t32/area-investigation/formal-route02'),('epoch',ROOT/'build/t32/epoch05')]:
        inventory=lambda folder:{p.relative_to(folder).as_posix():digest(p) for p in folder.rglob('*.sv')}
        before=inventory(origin/'emit');after=inventory(out/label)
        assert before and before==after,(label,'Fresh emitted model differs',sorted(k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)))
        row=dict(scope=label,old_receipt=str(origin/'result.json'),old_receipt_sha256=digest(origin/'result.json'),
            emitted_sha256=after,identity='Exact file inventory and SHA-256 equality; no normalization or assertion edits',
            acceptance='Existing local proof/fault/cover receipts only; epoch data remains unresolved')
        r['claims'].append(row)
    assert hashes()==r['source_sha256'],'Sources changed'
    r['status']='pass'
except Exception as e:r.update(status='failed',error=str(e))
r['artifact_sha256']={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()}
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'],r.get('error',''),flush=True)
sys.exit(0 if r['status']=='pass' else 1)
