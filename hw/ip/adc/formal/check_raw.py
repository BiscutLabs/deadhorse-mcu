"""T27 raw acquisition proof; one attempt per job, hard120s caps, no CI."""
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

def main(output,case):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for parent in ('hw/ip/adc/src/main','hw/ip/adc/formal') for p in (ROOT/parent).rglob('*')
           if p.is_file() and p.suffix in ('.scala','.py')]
    paths += [ROOT/'build.sbt',ROOT/'tools/sbt.py',ROOT/'tools/formal.py',ROOT/'tools/env/lock.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        assumptions=['Initial reset_n low, then arbitrary reset and all inputs; one sample clock'],
        scope='Raw engine halfPeriodCycles4' if case=='engine' else 'Full-width production publication state',case=case)
    top='AdcRawFormal' if case=='engine' else 'AdcPublicationFormal'
    asserts=7 if case=='engine' else 4
    def command(argv,log):
        start=time.monotonic()
        with log.open('w') as f:
            try:code=subprocess.run(argv,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=argv,returncode=code,seconds=time.monotonic()-start,log=log.relative_to(ROOT).as_posix())
    try:
        receipt['emission']=command([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/adc/formal")',
            f'hw/runMain deadhorse.adc.Emit{top} {out}/emit'],out/'emit.log')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for variant in (('correct','corrupt','cover') if case=='engine' else ('correct','corrupt','ack','cover')):
            mode={'correct':'prove','corrupt':'bmc','ack':'bmc','cover':'cover'}[variant]
            engine='abc pdr' if mode=='prove' else 'btor btormc'
            # Two complete16-clock frames at four sample edges per half-period,
            # plus reset/launch/completion edges; cover bound, not a proof bound.
            depth=270 if case=='engine' else 8
            sv=sorted((out/'emit'/variant).glob('*.sv'));assert sv
            job=out/(variant+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}',f'depth {depth}','timeout 120',
                '[engines]',engine,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in sv),
                f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                f'select -assert-count {3 if mode=="cover" else asserts} t:$'+('cover' if mode=='cover' else 'assert'),
                'select -assert-count 1 t:$assume','[files]',*map(str,sv),'']))
            row=command(['sby','-d',str(out/variant),str(job)],out/(variant+'.log'))
            status=out/variant/'status';solver=status.read_text().split()[0] if status.exists() else 'ERROR'
            row.update(variant=variant,engine=engine,mode=mode,depth=depth,solver_status=solver)
            receipt['jobs'].append(row)
            if solver=='TIMEOUT':row['status']='unresolved'
            else:
                negative=variant in ('corrupt','ack')
                fault=assertion_names(asserts)[5 if case=='engine' else 2 if variant=='ack' else 0]
                row['failed_properties']=validate_job(out/variant,'negative' if negative else 'cover' if mode=='cover' else 'proof',
                    row['returncode'],solver,{fault} if negative else None)
                row['status']='fault_rejected' if negative else 'covered' if mode=='cover' else 'proved'
            print(variant,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Sources changed during run')
        receipt['status']='unresolved' if any(r['status']=='unresolved' for r in receipt['jobs']) else 'pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--case',choices=('engine','publication'),default='engine')
    a=p.parse_args();sys.exit(main(a.output,a.case))
