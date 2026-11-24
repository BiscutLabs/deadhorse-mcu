"""Unbounded equivalence of the segmented stability countdown and original RTL."""
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
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build')
    out.mkdir(parents=True,exist_ok=False)
    paths=[ROOT/p for p in ('hw/ip/osc_ctrl/formal/StabilityEquivalence.scala',
        'hw/ip/osc_ctrl/formal/stability_equivalence.py',
        'hw/ip/osc_ctrl/src/main/scala/deadhorse/osc_ctrl/OscClockBoundary.scala',
        'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala','tools/formal.py','tools/env/lock.json')]
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        assumptions=['Initial reset asserted, thereafter arbitrary reset, enable, request and count'],
        scope='Output-cycle equivalence to original full-width decrement; not CDC/analog qualification',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitStabilityEquivalence {out}/emit'],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for label,mode in [('correct','prove'),('fault','bmc'),('cover','cover')]:
            sources=sorted((out/'emit'/('fault' if label=='fault' else 'correct')).glob('*.sv'))
            if not sources:raise RuntimeError('Missing model')
            engine='abc pdr' if mode=='prove' else 'btor btormc'
            job=out/(label+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}','depth 24','timeout 120',
                '[engines]',engine,'[script]',
                'read_slang --top StabilityEquivalence '+' '.join(p.name for p in sources),
                'prep -top StabilityEquivalence -flatten',"fminit -seq reset_n 0,'z",
                'async2sync','chformal -lower','select -assert-count 1 t:$assert',
                'select -assert-count 1 t:$assume','select -assert-count 1 t:$cover',
                '[files]',*map(str,sources),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            status_path=out/label/'status'
            status=status_path.read_text().split()[0] if status_path.exists() else 'ERROR'
            row.update(name=label,engine=engine,solver_status=status,
                model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
            receipt['jobs'].append(row)
            row['failed_properties']=validate_job(out/label,
                'proof' if mode=='prove' else 'negative' if mode=='bmc' else 'cover',
                row['returncode'],status,set(assertion_names(1)) if mode=='bmc' else None)
            row['status']='proved' if mode=='prove' else 'fault_rejected' if mode=='bmc' else 'covered'
            print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Proof sources changed')
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
