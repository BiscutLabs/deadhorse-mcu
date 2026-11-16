"""Run the unchanged T09 timing/area measurement on standalone FPU output."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/timing'))
from check import measure

if __name__=='__main__':
    result=measure('Fpu',[str(p) for p in sorted((ROOT/'build/t12/emit').glob('*.sv'))],
                   'clock',ROOT/'build/t12/timing')
    sys.exit(result['status']!='pass')
