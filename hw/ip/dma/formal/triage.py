"""One unchanged-model portfolio rung after the recorded DMA safety timeout."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tools.formal import validate_job, assertion_names

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
    p.add_argument('--split',action='store_true');a=p.parse_args()
    base=(ROOT/a.baseline).resolve();base.relative_to(ROOT/'build')
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((base/'result.json').read_text())
    for f,h in baseline['source_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h,f
    prior=next(j for j in baseline['cases']['safety']['jobs'] if j['variant']=='correct')
    assert prior['solver_status']=='TIMEOUT'
    template=(base/'safety/correct.sby').read_text()
    original_sv=base/'safety/emit/correct'
    assert {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in original_sv.glob('*.sv')}==prior['model_sha256']
    with (out/'model-stat.log').open('w') as log:
        subprocess.run(['yosys','-Q','-T','-p',f'read_rtlil {base}/safety/correct/model/design.il; stat; write_json {out}/model.json'],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    model=json.loads((out/'model.json').read_text())
    cells=model['modules']['DmaSafetyFormal']['cells']
    sequential={n:c for n,c in cells.items() if 'dff' in c['type']}
    receipt=dict(status='running',baseline_sha256=hashlib.sha256((base/'result.json').read_bytes()).hexdigest(),
        model_sha256=prior['model_sha256'],source_sha256=baseline['source_sha256'],jobs=[],
        step0=dict(cells=len(cells),sequential_bits=sum(len(c['connections']['Q']) for c in sequential.values()),
          memories=sum(1 for c in cells.values() if c['type'].startswith('$mem')),depth_requested=36,
          reached='ABC PDR frame 20, 9 of 10 outputs reported proved; aggregate unresolved',
          irrelevant='No RAM. Payload data/PWM value logic is outside most safety cones; 32-bit cursor/range and 16-bit remaining count couple the memory-range property.',
          cover_depths=re.findall(r'Reached cover statement.*?step (\d+)',(base/'safety/cover/logfile.txt').read_text()),
          growth='Bounded 9/18-step measurements below are diagnostic, not substitutes for unbounded proof.'))
    try:
        jobs=([(f'property-{i}','prove',36,'abc pdr') for i in range(10)] if a.split else
              [('quarter','bmc',9,'btor btormc'),('half','bmc',18,'btor btormc'),
               ('portfolio','prove',36,'smtbmc yices\naiger suprove\nabc pdr')])
        receipt['partition']=list(assertion_names(10)) if a.split else None
        for name,mode,depth,engine in jobs:
            script=template.replace('mode prove','mode '+mode).replace('depth 36','depth '+str(depth)).replace('abc pdr',engine)
            prop=None
            if a.split:
                prop='d.'+assertion_names(10)[int(name.split('-')[1])]
                script=script.replace('select -assert-count 10 t:$assert',
                    f'select -assert-count 10 t:$assert\nselect -assert-count 1 c:{prop}\n'
                    f'delete t:$assert c:{prop} %d\nselect -assert-count 1 t:$assert\nselect *\nopt_clean')
            sby=out/(name+'.sby');sby.write_text(script)
            start=time.monotonic()
            with (out/(name+'.log')).open('w') as log:
                code=subprocess.run(['sby','-d',str(out/name),str(sby)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=150).returncode
            status=(out/name/'status').read_text().split()[0]
            row=dict(name=name,property=prop,mode=mode,depth=depth,engine=engine,status=status,seconds=time.monotonic()-start,returncode=code)
            receipt['jobs'].append(row)
            if status not in ('PASS','TIMEOUT'):raise RuntimeError(f'{name}: {status}')
            if status=='PASS':validate_job(out/name,'proof',code,status)
            print(name,status,flush=True)
        receipt['status']='proved' if all(j['status']=='PASS' for j in receipt['jobs']) else 'unresolved'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={f.relative_to(out).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
        for f in out.rglob('*') if f.is_file() and f!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='proved' else 1
if __name__=='__main__':sys.exit(main())
