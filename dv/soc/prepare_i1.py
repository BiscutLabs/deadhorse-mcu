"""Generate existing register models and the reviewed I1 map; no CI or RTL test."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def main():
    subprocess.run([sys.executable,'hw/top/reference/check_soc_map.py'],cwd=ROOT,check=True)
    out=ROOT/'build/t20/i1';out.mkdir(parents=True,exist_ok=True)
    for name in ('uart','spi_host','i2c_host','mailbox','usb','osc_ctrl','power_reset','sram'):
        subprocess.run([sys.executable,'hw/regmap/regmap.py',f'hw/ip/{name}/{name}.regmap.yaml',
                        '--out',str(out/name)],cwd=ROOT,check=True)
    for name in ('aon_spi','aon_gpio'):
        subprocess.run([sys.executable,'hw/regmap/regmap.py',f'hw/ip/{name}/{name}.regmap.yaml',
                        '--out',str(ROOT/'build/plan05'/name)],cwd=ROOT,check=True)

if __name__=='__main__':main()
