"""Verify immutable inputs and apply reviewed patches only to build output."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
VENDOR = Path(__file__).resolve().parent


def prepare():
    lock = json.loads((VENDOR / 'hardfloat.lock.json').read_text())
    out = ROOT / 'build/vendor/hardfloat'
    out.mkdir(parents=True, exist_ok=True)
    allowed={Path(name).name for name in lock['files'] if name.startswith('upstream/')}
    for directory in (VENDOR/'upstream', out):
        if any(p.name not in allowed for p in directory.glob('*.scala')):
            raise ValueError('Unexpected HardFloat compile source in '+str(directory))
    for name, digest in lock['files'].items():
        data = (VENDOR / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('HardFloat locked source mismatch: ' + name)
        if name.startswith('upstream/'):
            (out / Path(name).name).write_bytes(data)
    for patch in sorted((VENDOR / 'patches').glob('*.patch')):
        subprocess.run(['git', 'apply', '--whitespace=error',
                        '--directory=build/vendor/hardfloat', str(patch)],
                       cwd=ROOT, check=True)
    print('PASS HardFloat locked sources and patches')


if __name__ == '__main__':
    prepare()
