"""PLAN05 AON SPI safety/order/framing: one 120s attempt per distinct job."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import validate_job,assertion_names

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for folder in ('hw/lib','hw/ip/aon_spi') for p in (ROOT/folder).rglob('*')
           if p.is_file() and p.suffix in ('.scala','.yaml','.py')]
    paths += [ROOT/'build/plan05/aon_spi/aon_spi_regs.json',ROOT/'tools/env/lock.json',ROOT/'tools/formal.py']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],assumptions=['Initial reset_n low, arbitrary thereafter; arbitrary LocalBus requests and MISO; one AON clock'],
        scope='FIFO capacity/order and CS framing; wire bit sampling covered by independent simulation',timeout_seconds=120)
    def run(command,log):
        begin=time.monotonic()
        with log.open('w') as f:
            try:code=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-begin,log=log.relative_to(out).as_posix())
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/aon_spi/formal")',f'hw/runMain deadhorse.aon_spi.EmitAonSpiFormal {out}/emit'],out/'emit.log')
        assert receipt['emission']['returncode']==0,'Emission failed'
        for variant,mode,depth in [('correct','prove',32),('tx','bmc',64),('rx','bmc',128),('frame','bmc',64),('correct','cover',512)]:
            name=variant+'-'+mode;sv=sorted((out/'emit'/variant).glob('*.sv'));job=out/(name+'.sby')
            engine='abc pdr' if mode=='prove' else 'btor btormc'
            job.write_text('\n'.join(['[options]',f'mode {mode}',f'depth {depth}','timeout 120','[engines]',engine,'[script]',
                'read_slang --top AonSpiFormal '+' '.join(p.name for p in sv),'prep -top AonSpiFormal -flatten',
                "fminit -seq reset_n 0,'z",'async2sync','chformal -lower','select -assert-count 24 t:$assert',
                'select -assert-count 3 t:$cover','select -assert-count 1 t:$assume','[files]',*map(str,sv),'']))
            row=run(['sby','-d',str(out/name),str(job)],out/(name+'.log'));receipt['jobs'].append(row)
            status=out/name/'status';solver=status.read_text().split()[0] if status.exists() else 'ERROR'
            row.update(name=name,mode=mode,depth=depth,engine=engine,solver_status=solver)
            if solver=='TIMEOUT':row['status']='deferred_unproved'
            else:
                validate_job(out/name,'proof' if mode=='prove' else 'cover' if mode=='cover' else 'negative',row['returncode'],solver,
                    set(assertion_names(24)) if mode=='bmc' else None)
                row['status']='proved' if mode=='prove' else 'covered' if mode=='cover' else 'fault_rejected'
            print(name,row['status'],flush=True)
        assert hashes()==receipt['source_sha256'],'Sources changed'
        receipt['status']='pass_with_deferrals' if any(j['status']=='deferred_unproved' for j in receipt['jobs']) else 'pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'],receipt.get('error',''),flush=True)
    return 0 if receipt['status'].startswith('pass') else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);sys.exit(main(p.parse_args().output))
