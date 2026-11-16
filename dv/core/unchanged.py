"""Rebuild the tagged pre-F profile and prove every untouched active module."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from common import ROOT, output_dir, run
from candidate import manifest, parameters

def check(tag,candidate,out):
    from equiv import elaborate, compare, negatives
    if tag!='t11-baseline' or not candidate: raise ValueError('T13 needs t11-baseline and a candidate')
    parameters(candidate); current=manifest(candidate)
    if current.get('implementation')!='rv32imfc-v1': raise ValueError('Expected F-enabled production profile')
    revision=subprocess.check_output(['git','rev-parse',tag+'^{commit}'],cwd=ROOT,text=True).strip()
    archive=out/'baseline.tar'; source=output_dir(ROOT/'build'/('tag-'+revision[:8]))
    run(['git','archive','--format=tar','--output='+str(archive),revision],out,'archive')
    with tarfile.open(archive) as stream: stream.extractall(source,filter='data')
    # Git archives use canonical LF; the pinned image preserves the Windows
    # lock's CRLF bytes. Qualify newline-only identity before restoring those
    # environment-lock bytes in this generated checkout (never RTL or pins).
    archived_lock=source/'tools/env/lock.json'; pinned_lock=Path('/opt/deadhorse-env/lock.json')
    if archived_lock.read_bytes().replace(b'\r\n',b'\n')!=pinned_lock.read_bytes().replace(b'\r\n',b'\n'):
        raise ValueError('Tagged baseline toolchain differs from installed pins')
    archived_lock.write_bytes(pinned_lock.read_bytes())
    run([sys.executable,source/'tools/sbt.py',
         'hw/runMain deadhorse.perf_core.EmitRegisteredCore build/registered-emit',
         'hw/runMain deadhorse.perf_core.EmitLeaves build/leaves'],out,'emit-baseline',timeout=180)
    emitted=source/'build/registered-emit/model'
    baseline=out/'baseline'
    run([sys.executable,'hw/ip/perf_core/formal/package_candidate.py','--registered',
         '--top',emitted,'--leaves',source/'build/leaves','--core',emitted,'--output',baseline],out,'package-baseline')
    # Match module filenames, then compare complete newline-normalized source
    # bytes to the tag. Changed modules remain separate proof obligations.
    directory=Path('hw/ip/perf_core/src/main/scala/deadhorse/perf_core')
    results={}; changed_modules=[]
    for name in current['source_sha256']:
        module=Path(name).stem
        matches=[p for p in (ROOT/directory).glob('*.scala')
                 if p.stem.lower()=={'ibex_register_file_ff':'ibexregisterfile'}.get(module,module.replace('_','').lower())]
        if len(matches)!=1: raise ValueError('Missing/ambiguous Chisel source: '+module)
        name_in_tree=matches[0].relative_to(ROOT).as_posix()
        old=subprocess.check_output(['git','show',revision+':'+name_in_tree],cwd=ROOT)
        # Canonical newline identity avoids host-dependent git autocrlf settings.
        if old.replace(b'\r\n',b'\n')!=matches[0].read_bytes().replace(b'\r\n',b'\n'):
            changed_modules.append(module); continue
        directory_out=output_dir(out/module)
        gold=elaborate(module,baseline,directory_out,'baseline')
        revised=elaborate(module,candidate,directory_out,'candidate')
        if compare(module,gold,revised,directory_out)!='proved': raise ValueError('Unchanged module differs: '+module)
        faults=negatives(module,gold,revised,output_dir(directory_out/'negative'))
        results[module]=dict(status='proved',negative_controls=faults)
    if not results or not changed_modules: raise ValueError('Empty unchanged/changed classification')
    receipt=dict(status='proved',baseline_commit=revision,
        archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        candidate_sha256=hashlib.sha256((ROOT/candidate/'candidate.json').read_bytes()).hexdigest(),
        modules=results,changed_modules_pending=changed_modules,
        scope='untouched active Ibex modules only (newline-normalized source identity); changed modules require separate refinement')
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS unchanged modules: {len(results)} proved with fault controls; changed-module obligations remain')
    return 0
