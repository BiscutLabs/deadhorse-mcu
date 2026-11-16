"""Unbounded combinational addition proof for every FPU prefix-adder width."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]

def check():
    out=ROOT/'build/t12/adder';out.mkdir(parents=True,exist_ok=True)
    with (out/'emit.log').open('w') as log:
        subprocess.run([sys.executable,'tools/sbt.py',
            f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/fpu/formal/FpuAddFormal.scala")',
            f'hw/runMain deadhorse.fpu.EmitFpuAddFormal {out}/emit'],cwd=ROOT,
            stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    results=[]
    for width in (25,26,28,32,51):
        for fault in (False,True):
            name=f'{width}-'+('fault' if fault else 'normal')
            script=out/(name+'.ys');source=out/'emit'/name/'FpuAddFormal.sv'
            script.write_text(f'read_slang --top FpuAddFormal {source}\n'
                'prep -top FpuAddFormal -flatten\n'
                'sat -verify -prove equal 1 -show-inputs -show-outputs\n')
            result=subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,
                                   capture_output=True,text=True,timeout=30)
            (out/(name+'.log')).write_text(result.stdout+result.stderr)
            expected='proof did fail' if fault else 'SUCCESS!'
            if result.returncode!=(1 if fault else 0) or expected not in result.stdout+result.stderr:
                raise ValueError('FPU adder proof/fault did not give expected result: '+name)
            results.append(dict(width=width,fault=fault,status='rejected' if fault else 'proved'))
    (out/'result.json').write_text(json.dumps(dict(status='pass',kind='unbounded combinational',
        assumptions=[],results=results),indent=2)+'\n')
    print('PASS exact prefix addition: five widths, five rejected carry faults',flush=True)

if __name__=='__main__': check()
