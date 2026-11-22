"""Generate the production GPIO and timer maps, without invoking CI."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

def main():
    subprocess.run([sys.executable, 'dv/soc/prepare_i1.py'], cwd=ROOT, check=True)
    for name in ('gpio', 'timers', 'aon_timer'):
        subprocess.run([sys.executable, 'hw/regmap/regmap.py',
                        f'hw/ip/{name}/{name}.regmap.yaml', '--out', f'build/t21/{name}'],
                       cwd=ROOT, check=True)

if __name__ == '__main__':
    main()
