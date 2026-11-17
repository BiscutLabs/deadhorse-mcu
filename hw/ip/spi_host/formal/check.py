"""Scoped SPI properties; timed-out jobs stay explicitly deferred/unproved."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tools'))
from formal import validate_job

CASES={
    'frame0':dict(top='SpiFrameFormal',mode='bmc',depth=128,assertions=9,covers=2,
        scope='Bounded128 edges, FIFO2, mode0/CS0, H3, one arbitrary TX byte with scripted setup; constant MISO1; sleep may assert after start'),
    'frame3':dict(top='SpiFrameFormal',mode='bmc',depth=128,assertions=9,covers=2,
        scope='Bounded128 edges, FIFO2, mode3/CS1, H3, one arbitrary TX byte with scripted setup; constant MISO1; sleep may assert after start'),
    'denied':dict(top='SpiDeniedFormal',mode='prove',depth=32,assertions=11,covers=2,
        scope='Unbounded denied-only accesses: owner0, all non-owner tags1..7, arbitrary traffic and observable reset-state preservation, FIFO2'),
}


def run(output, regmap):
    output=Path(output).resolve(); output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()): raise ValueError('Use fresh output; preserve evidence')
    output.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='running',cases={},deferred=[],
        assumptions=['reset_n initially low, subsequently arbitrary; single digital clock with qualified HF reset',
            'Frame master writes specified configuration and captures arbitrary TX byte at grant; constant MISO1, timeNow0',
            'Sleep request is unconstrained after the first selected observation; initially run mode',
            'Ownership case maps tag0 to1, covering all denied tags1..7 against owner0',
            'Digital synchronization only; external delays, metastability and physical reset distribution excluded'],
        qualification_limits=[v['scope'] for v in CASES.values()])
    started=time.monotonic()
    def command(argv, log, timeout=180):
        before=time.monotonic()
        with log.open('w') as stream:
            p=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        return dict(command=list(map(str,argv)),returncode=p.returncode,seconds=time.monotonic()-before,
                    log=log.relative_to(ROOT).as_posix())
    try:
        for role,config in CASES.items():
            directory=output/role; directory.mkdir()
            entry=dict(**config,jobs=[],status='running'); receipt['cases'][role]=entry
            emission=command([sys.executable,'tools/sbt.py',
                f'hw/runMain deadhorse.spi_host.EmitSpiFormal {regmap} {role} {directory}/emit'],directory/'emit.log')
            entry['emission']=emission
            if emission['returncode']: raise RuntimeError(f'{role} emission failed')
            for variant in ('cover','corrupt','correct'):
                sources=sorted((directory/'emit'/variant).glob('*.sv'))
                if not sources: raise RuntimeError('Missing emitted property model')
                mode='cover' if variant=='cover' else 'bmc' if variant=='corrupt' else config['mode']
                engine='abc pdr' if mode=='prove' else 'btor btormc'
                expected=config['covers'] if variant=='cover' else config['assertions']
                script='\n'.join(['[options]',f'mode {mode}',f'depth {config["depth"]}','timeout 120','',
                    '[engines]',engine,'','[script]',
                    f'read_slang --top {config["top"]} '+' '.join(p.name for p in sources),
                    f'prep -top {config["top"]} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                    f'select -assert-count {expected} t:$'+('cover' if variant=='cover' else 'assert'),
                    '','[files]',*map(str,sources),''])
                path=directory/(variant+'.sby');path.write_text(script)
                row=command(['sby','-d',str(directory/variant),str(path)],directory/(variant+'.log'))
                row.update(id='T16-'+role.upper()+'-'+variant.upper(),mode=mode,engine=engine,
                    depth=config['depth'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
                status_file=directory/variant/'status'
                result=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
                row['solver_status']=result;entry['jobs'].append(row)
                if result=='TIMEOUT':
                    row['status']='deferred_unproved'
                    receipt['deferred'].append(dict(id=row['id'],status='deferred_unproved',
                        reason='120-second formal timeout; no retry per user direction',
                        receipt=status_file.relative_to(ROOT).as_posix(),scope=config['scope']))
                else:
                    validate_job(directory/variant,'cover' if variant=='cover' else 'negative' if variant=='corrupt' else 'proof',
                                 row['returncode'],result)
                    row['status']='covered' if variant=='cover' else 'fault_rejected' if variant=='corrupt' else 'bounded' if mode=='bmc' else 'proved'
                print(row['id']+': '+row['status'],flush=True)
            entry['status']='pass_with_deferrals' if any(j['status']=='deferred_unproved' for j in entry['jobs']) else 'pass'
        receipt['status']='pass_with_deferrals' if receipt['deferred'] else 'pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['seconds']=time.monotonic()-started
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--json',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=run(ROOT/a.output,ROOT/a.json)
    print(result['status'].upper()+' SPI formal')
    sys.exit(0 if result['status'] in ('pass','pass_with_deferrals') else 1)
