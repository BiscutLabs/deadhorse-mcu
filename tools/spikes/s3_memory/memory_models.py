"""S3 memory organization and assumed flash timing model checks."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from dv.memory.check_sram import run_sram
from dv.memory.check_flash import run_flash


def run(output):
    output = Path(output).resolve()
    output.relative_to(ROOT/'build')
    if (output/'result.json').exists():
        raise ValueError('Use a fresh output directory; retain prior evidence')
    output.mkdir(parents=True,exist_ok=True)
    sources = [Path(__file__),*sorted((ROOT/'dv/memory').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    result = dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  command='python3 tools/spikes/s3_memory/memory_models.py --output '+str(output.relative_to(ROOT)),
                  source_sha256=hashes,python=sys.version,scope='Model validation only; no SRAM hardware or flash controller qualification')
    started = time.monotonic()
    try:
        result['sram'] = run_sram()
        result['flash'] = run_flash()
        if hashes != {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}:
            raise RuntimeError('Sources changed during model run')
        result['status'] = 'pass'
    except Exception as exc:
        result.update(status='failed',error=str(exc))
    result['seconds'] = time.monotonic()-started
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args(argv)
    result = run(args.output)
    print(result['status'].upper()+': S3 memory models'+(': '+result['error'] if 'error' in result else ''))
    return 0 if result['status']=='pass' else 1


if __name__=='__main__':
    sys.exit(main())
