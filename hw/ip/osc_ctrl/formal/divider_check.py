"""Source-edge divider pulse proof; no functional reset or phase assumption."""
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
    sources=[ROOT/p for p in ('hw/ip/osc_ctrl/formal/DividerFormal.scala',
        'hw/ip/osc_ctrl/formal/divider_check.py','hw/ip/osc_ctrl/src/main/scala/deadhorse/osc_ctrl/OscClockBoundary.scala',
        'tools/formal.py','tools/env/lock.json')]
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        assumptions=['Monitor reset high initially, then low; DUT reset and initial phase remain arbitrary'],
        scope='Logical source-edge pulse widths after first observed transition; physical glitch behavior remains cell/clock qualification')
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            try:code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitDividerFormal {out}/emit'],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for label,mode in [('correct','prove'),('fault','bmc'),('cover','cover')]:
            files=sorted((out/'emit'/('fault' if label=='fault' else 'correct')).glob('*.sv'))
            assert files
            engine='abc pdr' if mode=='prove' else 'btor btormc'
            job=out/(label+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}','depth 24','timeout 120','[engines]',engine,
                '[script]','read_slang --top DividerFormal '+' '.join(p.name for p in files),
                'prep -top DividerFormal -flatten','fminit -seq monitorReset 1,0','async2sync','chformal -lower',
                'select -assert-count 6 t:$assert','select -assert-count 2 t:$assume','select -assert-count 2 t:$cover',
                '[files]',*map(str,files),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            statusfile=out/label/'status';status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
            row.update(name=label,engine=engine,solver_status=status,
                model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            receipt['jobs'].append(row)
            row['failed_properties']=validate_job(out/label,'proof' if mode=='prove' else 'negative' if mode=='bmc' else 'cover',
                row['returncode'],status,set(assertion_names(6)) if mode=='bmc' else None)
            row['status']='proved' if mode=='prove' else 'fault_rejected' if mode=='bmc' else 'covered'
            print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Divider proof sources changed')
        receipt['status']='pass'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    sys.exit(main(parser.parse_args().output))
