"""Compile and run the observable-port FPU test in the pinned environment."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]

def simulate():
    out=ROOT/'build/t12/sim';out.mkdir(parents=True,exist_ok=True)
    sources=sorted((ROOT/'build/t12/emit').glob('*.sv'))
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator','--cc','--exe','--build','-j','4','-Wno-fatal',
                        '--top-module','Fpu','--Mdir',str(out),
                        *map(str,sources),str(ROOT/'dv/fpu/sim.cpp')],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    result=subprocess.run([str(out/'VFpu'),str(ROOT/'build/t12/vectors.txt')],
                          cwd=ROOT,capture_output=True,text=True,timeout=120)
    (out/'run.log').write_text(result.stdout+result.stderr)
    print(result.stdout+result.stderr,flush=True)
    result.check_returncode()

if __name__=='__main__': simulate()
