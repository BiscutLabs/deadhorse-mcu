"""Generate the opt-in DMA profile's register contracts; no CI."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
def main():
    for args in ([sys.executable,'dv/soc/prepare_pwm.py'],
                 [sys.executable,'hw/regmap/regmap.py','hw/ip/dma/dma.regmap.yaml','--out','build/t23/dma']):
        subprocess.run(args,cwd=ROOT,check=True)
if __name__=='__main__':main()
