"""T17 I2C acceptance: generated registers, independent tests, formal and GF180."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]


def inputs():
    paths=[ROOT/'docs/spec/i2c-host.md',ROOT/'build.sbt',ROOT/'tools/env/lock.json',ROOT/'tools/sbt.py',ROOT/'tools/formal.py']
    for directory in ('hw/ip/i2c_host','hw/lib/src/main/scala','hw/regmap','tools/timing'):
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.py','.scala','.yaml','.json','.tcl','.md'))
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}


def accept_child(returncode, detail):
    if returncode or detail.get('status') not in ('pass','pass_with_deferrals'):
        raise RuntimeError(f'Failed child: exit{ returncode}, status{detail.get("status")}')
    deferred=detail.get('deferred',[])
    if not isinstance(deferred,list) or any(d.get('status')!='deferred_unproved' or not d.get('id') for d in deferred):
        raise ValueError('Invalid explicit deferral inventory')
    if bool(deferred)!=(detail['status']=='pass_with_deferrals'):
        raise ValueError('Deferral status and inventory disagree')
    return deferred


def run(output):
    output=Path(output).resolve();output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()):raise ValueError('Use fresh output; retain old receipts')
    output.mkdir(parents=True,exist_ok=True)
    before=inputs();start=time.monotonic()
    receipt=dict(status='running',task='T17',source_sha256=before,commands=[],deferred=[],timing={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        qualification_limits=['Standalone single-controller I2C byte engine; no loader, DMA, sensor firmware or physical qualification',
            '100/400kHz targets use assumed HF clocks; pull-ups, rise/fall, pads, oscillator tolerance and MTBF remain unqualified'],
        ci_tier='Not run by this command')
    def command(name, argv, child=None):
        then=time.monotonic();log=output/(name+'.log')
        with log.open('w') as stream:
            process=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=1800)
        row=dict(name=name,command=list(map(str,argv)),returncode=process.returncode,
                 seconds=time.monotonic()-then,log=log.relative_to(ROOT).as_posix())
        receipt['commands'].append(row)
        if child:
            detail=json.loads(child.read_text());row['child_status']=detail.get('status')
            row['receipt']=dict(path=child.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(child.read_bytes()).hexdigest())
            receipt['deferred'].extend(accept_child(process.returncode,detail))
            return detail
        if process.returncode:raise RuntimeError(name+' failed; see '+row['log'])
    try:
        command('runner-tests',[sys.executable,'-m','unittest','discover','-s','hw/ip/i2c_host','-p','test_*.py','-v'])
        command('regmap',[sys.executable,'hw/regmap/regmap.py','hw/ip/i2c_host/i2c_host.regmap.yaml','--out',output/'regmap'])
        command('simulation',[sys.executable,'tools/sbt.py','hw/testOnly deadhorse.i2c_host.*'])
        command('emit',[sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.i2c_host.EmitI2cHost {output}/regmap/i2c_host_regs.json {output}/emit'])
        for name,top in (('i2c_host','I2cHost'),):
            args=[sys.executable,'tools/timing/check.py','--top',top,'--clock','clk','--output',output/name]
            sources=sorted((output/'emit').glob('*.sv'))
            if not sources:raise ValueError('Missing production emission: '+name)
            for source in sources:args+=['--source',source]
            receipt['timing'][name]=command('timing-'+name,args,output/name/'result.json')
        receipt['formal']=command('formal',[sys.executable,'hw/ip/i2c_host/formal/check.py','--json',output/'regmap/i2c_host_regs.json',
            '--output',output/'formal'],output/'formal/result.json')
        receipt['qualification_limits'].extend(receipt['formal'].get('qualification_limits',[]))
        if inputs()!=before:raise RuntimeError('Inputs changed during I2C acceptance')
        receipt['status']='pass_with_deferrals' if receipt['deferred'] else 'pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['seconds']=time.monotonic()-start
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper()+f' T17 I2C; {receipt["seconds"]:.3f}s',flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    a=p.parse_args();sys.exit(0 if run(ROOT/a.output)['status'] in ('pass','pass_with_deferrals') else 1)
