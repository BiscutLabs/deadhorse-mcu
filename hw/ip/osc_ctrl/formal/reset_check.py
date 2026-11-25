"""PLAN04 D83/D84 digital reset/strap checks; analog quality is outside scope."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.formal import assertion_names, validate_job


def main(output,shared=False):
    out = (ROOT / output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / p for p in (
        'hw/ip/osc_ctrl/formal/ResetFormal.scala', 'hw/ip/osc_ctrl/formal/PorBootstrapInitial.scala',
        'hw/ip/osc_ctrl/formal/reset_check.py',
        'hw/ip/osc_ctrl/src/main/scala/deadhorse/osc_ctrl/ResetBootstrap.scala',
        'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala', 'tools/formal.py', 'tools/env/lock.json')]
    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt = dict(status='running',shared=shared, source_sha256=hashes(), jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        assumptions=['Normal/bypass cases exhaust static D84 strap choices',
            'Both AON source inputs use one proof clock; analog mux/clock quality is not proved',
            'Reset/strap jobs: initial external reset asserted, thereafter both reset sources and AON selection arbitrary',
            'POR initial job: external reset released, POR asserted, normal straps; no state initialization assumption'],
        scope='Digital reset routing, minimum release sequence and frozen AON selection only')
    def run(command, label, cap=180):
        before=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try:
                code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=cap).returncode
            except subprocess.TimeoutExpired:
                code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-before,log=label+'.log')
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitResetFormal {out}/emit {"shared" if shared else ""}'],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        jobs=[('por-initial','prove')]
        for case in ('normal','bypass'):
            jobs += [(case+'-'+variant,'prove' if variant=='correct' else 'bmc')
                     for variant in ('correct','cold','strap','early')]
            jobs += [(case+'-cover','cover')]
        for label,mode in jobs:
            initial=label=='por-initial'
            variant=label.rsplit('-',1)[-1]
            model=label.replace('-cover','-correct')
            sources=sorted((out/'emit'/model).glob('*.sv'))
            if not sources:raise RuntimeError('Missing emitted model')
            top='PorBootstrapInitial' if initial else 'ResetFormal'
            engine='abc pdr' if mode=='prove' else 'btor btormc'
            job=out/(label+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}','depth 24','timeout 120',
                '[engines]',engine,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in sources),
                f'prep -top {top} -flatten',*([] if initial else ["fminit -seq externalReset_n 0,'z"]),
                'async2sync','chformal -lower',f'select -assert-count {2 if initial else 4} t:$assert',
                f'select -assert-count {0 if initial else 1} t:$assume',
                *(['select -assert-count 2 t:$cover'] if mode=='cover' else []),
                '[files]',*map(str,sources),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            status_file=out/label/'status'
            status=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
            row.update(name=label,mode=mode,engine=engine,solver_status=status,
                       model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
            receipt['jobs'].append(row)
            faults={'cold':set(assertion_names(4)[2:]),'strap':{assertion_names(4)[0]},
                    'early':{assertion_names(4)[1]}}.get(variant)
            row['failed_properties']=validate_job(out/label,
                'negative' if mode=='bmc' else 'proof' if mode=='prove' else 'cover',
                row['returncode'],status,faults)
            row['status']='proved' if mode=='prove' else 'fault_rejected' if mode=='bmc' else 'covered'
            print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Reset sources changed during checks')
        receipt['status']='pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--shared',action='store_true')
    args=parser.parse_args();sys.exit(main(args.output,args.shared))
