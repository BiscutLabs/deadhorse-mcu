"""Combinational functional transparency and persistent manufacturing-pad safety."""
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


def main():
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--output', required=True)
    a = p.parse_args();out = (ROOT / a.output).resolve();out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), Path(__file__).with_name('SocTestPadsFormal.scala')]
    paths += [ROOT / s for s in ('hw/top/reference/src/main/scala/deadhorse/top/SocTestPads.scala',
        'hw/top/reference/src/main/scala/deadhorse/top/SocClockedTop.scala',
        'hw/top/stubs/src/main/scala/deadhorse/top/SocInactivePads.scala',
        'tools/formal.py', 'tools/sbt.py', 'build.sbt', 'tools/env/lock.json')]
    def hashes():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    r = dict(status='running', sources=hashes(), assumptions=[], jobs=[],
        scope='Pad adapter combinational contract only; not scan-chain, SRAM isolation or physical electrical qualification',
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
    def run(command, label):
        start=time.monotonic()
        with (out / (label+'.log')).open('w') as log:
            try: code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired: code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        r['emission']=run([sys.executable,'tools/sbt.py',
            f'set hw / Compile / unmanagedSourceDirectories += file("{ROOT}/hw/top/reference/formal")',
            f'hw/runMain deadhorse.top.EmitSocTestPadsFormal {out}/emit'],'emit')
        if r['emission']['returncode']: raise RuntimeError('Emission failed')
        for name,variant,mode,engine in (('correct','correct','prove','abc pdr'),
            ('cover','correct','cover','smtbmc yices'),('fault','fault','bmc','smtbmc yices')):
            files=sorted((out/'emit'/variant).glob('*.sv'))
            if not files: raise RuntimeError('Missing model')
            job=out/(name+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}','depth 4','timeout 120','[engines]',engine,
                '[script]','read_slang --top SocTestPadsFormal '+' '.join(p.name for p in files),
                'prep -top SocTestPadsFormal -flatten','async2sync','chformal -lower',
                'select -assert-count 2 t:$assert','select -assert-count 0 t:$assume',
                'select -assert-count 1 t:$cover','[files]',*map(str,files),'']))
            row=run(['sby','-d',str(out/name),str(job)],name)
            status_path=out/name/'status';status=status_path.read_text().split()[0] if status_path.exists() else 'ERROR'
            row.update(name=name,solver_status=status,engine=engine);r['jobs'].append(row)
            if status=='TIMEOUT' or row['returncode']==124: row['status']='unresolved'
            else:
                kind='negative' if name=='fault' else mode
                row['failed_properties']=validate_job(out/name,kind,row['returncode'],status,
                    {assertion_names(2)[1]} if kind=='negative' else None)
                row['status']={'negative':'fault_rejected','prove':'proved','cover':'covered'}[kind]
            print(name,row['status'],flush=True)
        if hashes()!=r['sources']: raise RuntimeError('Source changed during run')
        r['status']='unresolved' if any(j['status']=='unresolved' for j in r['jobs']) else 'pass'
    except Exception as error: r.update(status='failed',error=str(error))
    r['artifacts']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    print(r['status'].upper(),r.get('error',''));return 0 if r['status']=='pass' else 1


if __name__=='__main__': sys.exit(main())
