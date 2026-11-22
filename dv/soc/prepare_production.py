"""Prepare the single production SoC and all existing focused test firmware."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def main():
    for script in ('prepare_i0.py','prepare_xip.py'):
        subprocess.run([sys.executable,str(ROOT/'dv/soc'/script)],cwd=ROOT,check=True)
    print('PASS production SoC inputs prepared; no execution claimed')

if __name__=='__main__':main()
