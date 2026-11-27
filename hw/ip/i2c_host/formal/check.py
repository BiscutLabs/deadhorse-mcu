"""Scoped I2C properties; timed-out jobs stay explicitly deferred/unproved."""
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
from deferred import authenticate, digest, environment_digest, load_policy

CASES={
    'write':dict(top='I2cProtocolFormal',mode='bmc',depth=320,assertions=1,covers=2,
        scope='Bounded320 edges, HOLD1/LOW4/HIGH4/FREE4 timeout64; scripted START then arbitrary WRITE byte and ACK peer'),
    'read':dict(top='I2cProtocolFormal',mode='bmc',depth=320,assertions=1,covers=4,
        scope='Bounded320 edges, same timing; scripted START then arbitrary READ byte with symbolic ACK/NACK'),
    'recover':dict(top='I2cProtocolFormal',mode='bmc',depth=256,assertions=1,covers=2,
        scope='Bounded256 edges, same timing; nine recovery clocks then STOP/free on ideal released bus'),
    'timeout':dict(top='I2cProtocolFormal',mode='bmc',depth=160,assertions=1,covers=2,
        scope='Bounded160 edges, same timing but timeout8; START with one selected pin permanently stuck low'),
    'denied':dict(top='I2cDeniedFormal',mode='prove',depth=32,assertions=1,covers=2,
        scope='Unbounded denied-only accesses: owner0, all non-owner tags1..7, arbitrary traffic and observable disabled-state preservation'),
}


def run(output, regmap):
    output=Path(output).resolve(); output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()): raise ValueError('Use fresh output; preserve evidence')
    output.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='running',cases={},deferred=[],
        assumptions=['reset_n initially low, subsequently arbitrary; single digital clock with qualified HF reset',
            'Protocol master uses fixed MMIO setup and timing HOLD1/LOW4/HIGH4/FREE4; timeout64 except stuck-pin timeout8',
            'WRITE peer ACKs; READ peer supplies arbitrary captured byte and master chooses ACK/NACK; no stretching or external delays',
            'Recovery peer releases both lines; timeout peer holds exactly one captured-choice pin low',
            'Sleep request is unconstrained only after clockHold confirms work admitted; sleepEnable0',
            'Ownership case maps tag0 to1, covering all denied tags1..7 against owner0; external lines high',
            'Digital synchronization/filter behavior only; metastability and physical timing excluded'],
        qualification_limits=[v['scope'] for v in CASES.values()])
    started=time.monotonic()
    def command(argv, log, timeout=180):
        before=time.monotonic()
        with log.open('w') as stream:
            p=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
        return dict(command=list(map(str,argv)),returncode=p.returncode,seconds=time.monotonic()-before,
                    log=log.relative_to(ROOT).as_posix())
    try:
        policy_path=Path(__file__).with_name('deferrals.json')
        retained=load_policy(policy_path,{f'T17-{role.upper()}-{variant.upper()}' for role in CASES for variant in ('cover','corrupt','correct')})
        receipt['retained_policy_sha256']=digest(policy_path)
        for role,config in CASES.items():
            directory=output/role; directory.mkdir()
            entry=dict(**config,jobs=[],status='running'); receipt['cases'][role]=entry
            emission=command([sys.executable,'tools/sbt.py',
                f'hw/runMain deadhorse.i2c_host.EmitI2cFormal {regmap} {role} {directory}/emit'],directory/'emit.log')
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
                ident='T17-'+role.upper()+'-'+variant.upper()
                source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
                identity=dict(role=role,variant=variant,top=config['top'],mode=mode,engine=engine,
                    depth=config['depth'],timeout_seconds=120,expected_cells=expected,scope=config['scope'],
                    flow_sha256=hashlib.sha256(script.split('\n[files]')[0].encode()).hexdigest(),
                    environment_sha256=environment_digest(ROOT/'tools/env/lock.json'))
                if ident in retained:
                    row=dict(id=ident,mode=mode,engine=engine,depth=config['depth'],identity=identity,
                        source_sha256=source_hashes,seconds=0,
                        **authenticate(retained[ident],identity,source_hashes,ROOT,ROOT/'tools/env/lock.json',
                                       {p.name:p for p in sources}))
                    entry['jobs'].append(row)
                    receipt['deferred'].append(dict(id=ident,status='deferred_unproved',
                        reason='Reviewed matching-model timeout retained; solver not rerun',
                        scope=config['scope'],original_provenance=row['original_provenance'],
                        historical_artifacts_available=row['historical_artifacts_available'],
                        environment_compatibility=row['environment_compatibility'],
                        model_compatibility=row['model_compatibility']))
                    print(ident+': deferred_unproved (retained matching-model timeout)',flush=True)
                    continue
                row=command(['sby','-d',str(directory/variant),str(path)],directory/(variant+'.log'))
                row.update(id=ident,mode=mode,engine=engine,depth=config['depth'],identity=identity,
                    source_sha256=source_hashes,retained=False,solver_rerun=True)
                status_file=directory/variant/'status'
                result=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
                row['solver_status']=result;entry['jobs'].append(row)
                if result=='TIMEOUT':
                    if row['returncode']!=8:
                        raise RuntimeError(f'{ident}: TIMEOUT requires solver exit code8, got {row['returncode']}')
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
    print(result['status'].upper()+' I2C formal')
    sys.exit(0 if result['status'] in ('pass','pass_with_deferrals') else 1)
