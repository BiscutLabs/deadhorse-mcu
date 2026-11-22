"""Prepare T29 command-mode QSPI profile; no CI."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
if __name__=='__main__':
    for args in ([sys.executable,'dv/soc/prepare_boot_control.py'],
                 [sys.executable,'hw/regmap/regmap.py','hw/ip/qspi/qspi.regmap.yaml','--out','build/t29/qspi']):
        subprocess.run(args,cwd=ROOT,check=True)
