"""T32 debug SBA/memory safety, ownership and witnesses; fixed 120s job cap, no CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import assertion_names,validate_job

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for parent in ('hw/lib','hw/ip/debug') for p in (ROOT/parent).rglob('*')
           if p.is_file() and p.suffix in ('.scala','.py','.yaml')]
    paths += [ROOT/p for p in ('build.sbt','tools/sbt.py','tools/formal.py','tools/env/lock.json',
                              'hw/vendor/riscv_dbg/riscv_dbg.lock.json')]
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),cases={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        assumptions=['Initial POR low; subsequent reset and inputs arbitrary; one local clock',
                     'targetQuiet is supplied as the integration old-epoch drain guarantee; no fairness/liveness assumption'])
    def command(argv,log):
        begin=time.monotonic()
        with log.open('w') as f:
            try:code=subprocess.run(argv,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=argv,returncode=code,seconds=time.monotonic()-begin,log=str(log.relative_to(out)))
    try:
        emission=command([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/debug/formal")',
            f'hw/runMain deadhorse.debug.EmitDebugFormal {out}/emit'],out/'emit.log')
        receipt['emission']=emission
        if emission['returncode']:raise RuntimeError('Debug formal emission failed')
        for case,top,asserts,covers,variants in [
                ('sba','DebugSbaFormal',8,5,('correct','duplicate','stale','wrong_route','late_route','cover')),
                ('memory','DebugMemoryFormal',6,3,('correct','wrong_hart','cover'))]:
            directory=out/case;directory.mkdir();entry=dict(jobs=[]);receipt['cases'][case]=entry
            for v in variants:
                mode='prove' if v=='correct' else 'cover' if v=='cover' else 'bmc'
                engine='abc pdr' if mode=='prove' else 'btor btormc'
                sv=sorted((out/'emit'/case/v).glob('*.sv'));assert sv
                job=directory/(v+'.sby')
                job.write_text('\n'.join(['[options]',f'mode {mode}','depth 24','timeout 120','[engines]',engine,
                    '[script]',f'read_slang --top {top} '+' '.join(p.name for p in sv),f'prep -top {top} -flatten',
                    "fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                    f'select -assert-count {covers if mode=="cover" else asserts} t:$'+('cover' if mode=='cover' else 'assert'),
                    'select -assert-count 1 t:$assume','[files]',*map(str,sv),'']))
                row=command(['sby','-d',str(directory/v),str(job)],directory/(v+'.log'))
                status=directory/v/'status';solver=status.read_text().split()[0] if status.exists() else 'ERROR'
                row.update(variant=v,mode=mode,engine=engine,solver_status=solver,
                    model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sv})
                entry['jobs'].append(row)
                if solver=='TIMEOUT':row['status']='unresolved'
                else:
                    faults=set(assertion_names(asserts)) if v not in ('correct','cover') else None
                    row['failed_properties']=validate_job(directory/v,
                        'proof' if mode=='prove' else 'cover' if mode=='cover' else 'negative',row['returncode'],solver,faults)
                    row['status']='proved' if mode=='prove' else 'covered' if mode=='cover' else 'fault_rejected'
                print(case,v,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Proof sources changed')
        receipt['status']='unresolved' if any(j['status']=='unresolved' for e in receipt['cases'].values() for j in e['jobs']) else 'pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();sys.exit(main(a.output))
