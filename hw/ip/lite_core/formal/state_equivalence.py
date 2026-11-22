"""Exact pinned baseline correspondence using the existing whole-state checker; no CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
import equiv
from common import run as core_run
from check import prepare_reference

# Preserve T25's existing per-job cap when reusing the general core checker.
def capped_run(*args,**kwargs):
    kwargs['timeout']=120
    return core_run(*args,**kwargs)
equiv.run=capped_run

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    prepare_reference()
    paths=[p for root in ('hw/ip/lite_core/src/main','hw/ip/lite_core/formal','hw/lib','build/t25/reference')
        for p in (ROOT/root).rglob('*') if p.is_file() and p.suffix in ('.scala','.py')]
    paths += [ROOT/p for p in ('hw/ip/lite_core/provenance.json','dv/core/equiv.py','dv/core/state_equiv.py',
        'dv/core/common.py','dv/core/module_map.json','build.sbt','tools/sbt.py','tools/env/lock.json')]
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result=dict(status='running',source_sha256=hashes(),assumptions=[],state_exclusions=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[])
    def command(argv,label):
        before=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            code=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
        result['commands'].append(dict(command=list(map(str,argv)),returncode=code,seconds=time.monotonic()-before))
        if code:raise RuntimeError(label+' failed')
    try:
        command([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/lite_core/formal")',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/build/t25/reference")',
            f'hw/runMain deadhorse.lite_core.EmitLiteStateModels {out}/emit'],'emit')
        for side in ('gold','candidate'):
            files=sorted((out/'emit'/side).glob('*.sv'))
            script=out/(side+'.ys')
            script.write_text('read_slang --top LiteStateModel '+' '.join(map(str,files))+'\n'+
                'prep -top LiteStateModel -flatten\nopt_clean\ncheck -assert\n'+
                f'write_json {out}/{side}.json\nstat\n')
            command(['yosys','-Q','-T','-s',str(script)],side)
            model=out/(side+'.json')
            model.with_suffix('.elaboration.json').write_text(json.dumps(dict(
                netlist_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),parameters='full RV32E; asynchronous reset',
                source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})))
        positive=out/'positive';positive.mkdir()
        if equiv.compare('LiteStateModel',out/'gold.json',out/'candidate.json',positive)!='proved':
            raise RuntimeError('Baseline state equivalence unresolved')
        result['positive']=json.loads((positive/'result.json').read_text())
        negative=out/'negative';negative.mkdir()
        result['faults']=equiv.negatives('LiteStateModel',out/'gold.json',out/'candidate.json',negative)
        if hashes()!=result['source_sha256']:raise RuntimeError('Sources changed')
        result['status']='pass'
    except Exception as e:result.update(status='failed',error=str(e))
    result['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'].upper(),result.get('error',''),flush=True)
    return 0 if result['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())
