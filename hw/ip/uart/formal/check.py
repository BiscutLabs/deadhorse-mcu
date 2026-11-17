"""Scoped UART properties; timed-out jobs stay explicitly deferred/unproved."""
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
    'phase':dict(top='UartPhaseFormal',mode='prove',depth=4,assertions=1,covers=1,
        scope='Unbounded combinational equality of all 17 phase-adder result bits for every pair of 16-bit operands; negative control flips sum bit0'),
    'frame':dict(top='UartFrameFormal',mode='bmc',depth=160,assertions=6,covers=2,
        scope='Bounded to 160 edges: one symbolic TX byte, FIFO depth 2, increment 8192, normal polarity, scripted legal configuration; not arbitrary software or RX proof'),
    'wake':dict(top='UartWakeFormal',mode='prove',depth=24,assertions=3,covers=2,
        scope='Unbounded sticky AON wake, four settled active samples capture, wake/request equality; arbitrary pin/config/clear and reset'),
    'denied':dict(top='UartDeniedFormal',mode='prove',depth=32,assertions=8,covers=2,
        scope='Unbounded denied-only accesses for all non-owner tags 1..7 against owner0; response and externally visible reset-state preservation, FIFO depth2'),
}


def run(output, regmap):
    output=Path(output).resolve(); output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()): raise ValueError('Use fresh output; preserve evidence')
    output.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='running',cases={},deferred=[],
        assumptions=['reset_n initially low, subsequently arbitrary; single digital clock',
            'Frame harness drives specified configuration and captures symbolic data at bus grant',
            'Ownership case maps input tag0 to1, covering every denied tag1..7; owner fixed0',
            'Digital synchronizer only: analog metastability/MTBF and HF startup are excluded'],
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
                f'hw/runMain deadhorse.uart.EmitUartFormal {regmap} {role} {directory}/emit'],directory/'emit.log')
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
                row.update(id='T15-'+role.upper()+'-'+variant.upper(),mode=mode,engine=engine,
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
    print(result['status'].upper()+' UART formal')
    sys.exit(0 if result['status'] in ('pass','pass_with_deferrals') else 1)
