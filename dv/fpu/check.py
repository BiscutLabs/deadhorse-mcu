"""Focused T12 acceptance; never launches the unrelated core formal sweep."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]

def checker_controls(output):
    rows=(ROOT/'build/t12/vectors.txt').read_text().splitlines()
    pairs={}
    for row in rows:
        f=row.split();pairs.setdefault((int(f[0]),int(f[1])),row)
    if len(pairs)!=120: raise ValueError('Reference coverage missing operation/rm')
    baseline=list(pairs.values())
    executable=ROOT/'build/t12/sim/VFpu'
    tests={
        'positive':(baseline,None),
        'missing_operation':([r for r in baseline if r.split()[0]!='23'],'missing operation/rounding mode pair'),
        'missing_rounding_mode':([r for r in baseline if r.split()[1]!='4'],'missing operation/rounding mode pair'),
        'invalid_operation':(['31 0 00000000 00000000 00000000 00000000 00'],'invalid operation/rounding mode'),
        'invalid_rounding_mode':(['0 5 00000000 00000000 00000000 00000000 00'],'invalid operation/rounding mode'),
        'empty':([],'empty vectors'),
        'malformed':(['bad vector'],'malformed vector')}
    for name,index in [('result',5),('flags',6)]:
        f=baseline[0].split();f[index]=f'{int(f[index],16)^1:x}'
        tests[name+'_mismatch']=([' '.join(f)]+baseline[1:],'result/flags mismatch')
    controls={}
    for name,(data,error) in tests.items():
        path=output/(name+'.txt');path.write_text('\n'.join(data)+('\n' if data else ''))
        run=subprocess.run([str(executable),str(path)],cwd=ROOT,capture_output=True,text=True,timeout=30)
        (output/(name+'.log')).write_text(run.stdout+run.stderr)
        if (error is None and run.returncode) or (error is not None and
            (run.returncode!=1 or 'FAIL '+error not in run.stderr)):
            raise ValueError('FPU checker control escaped or crashed: '+name)
        controls[name]='pass' if error is None else 'rejected'
    return controls

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args();output=(ROOT/args.output).resolve()
    output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=True)
    receipt=dict(status='running',commands=[]);path=output/'result.json'
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    commands=[
        [sys.executable,'tools/env/check.py'],
        [sys.executable,'tools/sbt.py','hw/runMain deadhorse.fpu.EmitFpu build/t12/emit'],
        [sys.executable,'tools/sbt.py','hw/testOnly deadhorse.fpu.*'],
        [sys.executable,'dv/fpu/iss.py'],
        [sys.executable,'dv/fpu/sim.py'],
        [sys.executable,'dv/fpu/arithmetic.py'],
        [sys.executable,'hw/ip/fpu/formal/check_add.py'],
        [sys.executable,'hw/ip/fpu/formal/check.py'],
        [sys.executable,'hw/ip/fpu/check_timing.py']]
    for i,command in enumerate(commands):
        start=time.monotonic(); print('RUN',' '.join(command),flush=True)
        logpath=output/f'acceptance-{i}.log'
        with logpath.open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        receipt['commands'].append(dict(command=command,returncode=result.returncode,
                                        seconds=time.monotonic()-start,log=str(logpath.relative_to(ROOT))))
        receipt['status']='failed' if result.returncode else 'running'
        path.write_text(json.dumps(receipt,indent=2)+'\n')
        if result.returncode:
            print(logpath.read_text()[-6000:]);return result.returncode
    controls=output/'checker_controls';controls.mkdir(exist_ok=True)
    receipt['checker_controls']=checker_controls(controls)
    files=[p for directory in ['hw/ip/fpu','hw/vendor/hardfloat','dv/fpu']
           for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [ROOT/'tools/env/fpu.lock.json',ROOT/'tools/env/lock.json',ROOT/'build.sbt',ROOT/'tools/sbt.py']
    receipt['sources']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    receipt['commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    receipt['status']='pass';path.write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS T12: complete RV32F vectors, protocol/fault tests, QEMU, control formal and GF180 timing',flush=True)
    return 0

if __name__=='__main__': sys.exit(main())
