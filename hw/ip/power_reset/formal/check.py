"""T33 local selector/reset-demand proofs; not whole-chip composition acceptance."""
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
    paths=[p for area in ('hw/ip/power_reset','hw/ip/osc_ctrl','hw/lib')
           for p in (ROOT/area).rglob('*') if p.is_file() and p.suffix in ('.scala','.py','.yaml')]
    paths += [ROOT/p for p in ('tools/formal.py','tools/sbt.py','build.sbt','tools/env/lock.json')]
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        assumptions=['Initial reset asserted; later reset and all local inputs arbitrary; single AON clock'],
        scope='Atomic keyed selector and unmaskable internal-reset sleep cancellation only; no analog or CDC/ICG composition proof')
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/power_reset/formal")',
            f'hw/runMain deadhorse.power_reset.EmitPowerResetFormal unused {out}/emit'],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for name,top,count in (('selector','PowerResetFormal',4),('demand','ResetDemandFormal',3)):
            for kind in ('proof','negative','cover'):
                model=name+('-fault' if kind=='negative' else '')
                sources=sorted((out/'emit'/model).glob('*.sv'))
                if not sources:raise RuntimeError('Missing emitted source '+model)
                label=name+'-'+kind;mode=dict(proof='prove',negative='bmc',cover='cover')[kind]
                engine='abc pdr' if kind=='proof' else 'btor btormc'
                job=out/(label+'.sby')
                job.write_text('\n'.join(['[options]',f'mode {mode}','depth 24','timeout 120',
                    '[engines]',engine,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in sources),
                    f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                    f'select -assert-count {count} t:$assert','select -assert-count 2 t:$cover',
                    'select -assert-count 1 t:$assume','[files]',*map(str,sources),'']))
                row=run(['sby','-d',str(out/label),str(job)],label)
                statusfile=out/label/'status';status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
                row.update(name=label,engine=engine,solver_status=status,
                    model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
                receipt['jobs'].append(row)
                if status=='TIMEOUT':raise TimeoutError(label+' reached the existing 120-second cap')
                faults=set(assertion_names(count)[1:3]) if name=='selector' else set(assertion_names(count))
                row['failed_properties']=validate_job(out/label,kind,row['returncode'],status,faults if kind=='negative' else None)
                row['status']=dict(proof='proved',negative='fault_rejected',cover='covered')[kind]
                print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Sources changed during proof')
        receipt['status']='pass'
    except TimeoutError as error:receipt.update(status='unresolved',error=str(error))
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    sys.exit(main(parser.parse_args().output))
