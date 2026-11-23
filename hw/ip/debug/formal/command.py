"""Adopted two-hart command ownership/reset proof; 120-second jobs."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import validate_job,assertion_names

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    files=[ROOT/'hw/ip/debug/formal/DebugCommandFormal.scala',Path(__file__).resolve(),ROOT/'tools/env/lock.json',
           ROOT/'hw/vendor/riscv_dbg/riscv_dbg.lock.json',ROOT/'hw/vendor/riscv_dbg/patches/integration.patch',
           ROOT/'tools/formal.py',ROOT/'tools/sbt.py',ROOT/'hw/vendor/riscv_dbg/prepare.py',ROOT/'build.sbt']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],assumptions=['Initial POR; subsequent reset and all inputs arbitrary'],
                 scope='Production-parameter adopted dm_mem; sampled single-clock reset safety, not the complete DM CSR or CDC composition',
                 timeout_seconds=120,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    def run(cmd,name,timeout=180):
        begin=time.monotonic()
        with(out/(name+'.log')).open('w') as log:
            try:code=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=cmd,returncode=code,seconds=time.monotonic()-begin,log=name+'.log')
    try:
        receipt['prepare']=run([sys.executable,'hw/vendor/riscv_dbg/prepare.py'],'prepare')
        if receipt['prepare']['returncode']:raise RuntimeError('Vendor preparation failed')
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/debug/formal")',
            f'hw/runMain deadhorse.debug.EmitDebugCommandFormal {out}/emit'],'emit',600)
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for v in ('correct','wrong_hart','lost_reset','cross_reset','cover'):
            mode='prove' if v=='correct' else 'cover' if v=='cover' else 'bmc'
            engine='abc pdr' if mode=='prove' else 'btor btormc'
            folder=out/'emit'/v;sources=sorted(folder.glob('*.sv'));pkg=folder/'dm_pkg.sv';sources.remove(pkg);sources.insert(0,pkg)
            job=out/(v+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}','depth 24','timeout 120','[engines]',engine,'[script]',
                'read_slang --top DebugCommandFormal '+' '.join(p.name for p in sources),
                'prep -top DebugCommandFormal -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                f'select -assert-count {6 if mode=="cover" else 8} t:$'+('cover' if mode=='cover' else 'assert'),
                'select -assert-count 1 t:$assume','[files]',*map(str,sources),'']))
            row=run(['sby','-d',str(out/v),str(job)],v)
            status=out/v/'status';solver=status.read_text().split()[0] if status.exists() else 'ERROR'
            row.update(variant=v,mode=mode,engine=engine,solver_status=solver,model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
            receipt['jobs'].append(row)
            if solver=='TIMEOUT':row['status']='unresolved'
            else:
                failed=validate_job(out/v,'proof' if v=='correct' else 'cover' if v=='cover' else 'negative',row['returncode'],solver,
                    set(assertion_names(7)) if v in ('wrong_hart','lost_reset','cross_reset') else None)
                if v=='wrong_hart' and 'assert__chisel3_builtin' not in failed:
                    raise RuntimeError('Wrong-hart fault did not fail command selection')
                if v=='lost_reset' and not set(failed)&{'assert__chisel3_builtin_1','assert__chisel3_builtin_2','assert__chisel3_builtin_3','assert__chisel3_builtin_4'}:
                    raise RuntimeError('Lost-reset fault did not fail a reset property')
                if v=='cross_reset' and 'assert__chisel3_builtin_5' not in failed:
                    raise RuntimeError('Cross-reset fault did not fail other-hart survival')
                row['failed_properties']=failed
                row['status']='proved' if v=='correct' else 'covered' if v=='cover' else 'fault_rejected'
            print(v,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Proof sources changed')
        receipt['status']='unresolved' if any(j['status']=='unresolved' for j in receipt['jobs']) else 'pass'
    except Exception as exc:receipt.update(status='failed',error=str(exc))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True);sys.exit(main(ap.parse_args().output))
