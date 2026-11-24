"""Materialize the byte-exact SRAM views pinned by gf180_sram.lock.json under build/."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def prepare(output='build/vendor/gf180_sram', source=None):
    lock = json.loads((HERE / 'gf180_sram.lock.json').read_text())
    out = (ROOT / output).resolve()
    out.relative_to(ROOT / 'build')
    upstream = (ROOT / (source or 'build/vendor/gf180_sram-upstream')).resolve()
    upstream.relative_to(ROOT / 'build')
    if not upstream.exists():
        subprocess.run(['git', 'clone', '--no-checkout', lock['repository'], str(upstream)], check=True)
        subprocess.run(['git', 'checkout', '--detach', lock['revision']], cwd=upstream, check=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=upstream, text=True).strip()
    if revision != lock['revision']:
        raise ValueError('SRAM upstream revision differs from lock')
    for name, expected in lock['files'].items():
        # Git blobs are canonical upstream bytes, independent of host autocrlf.
        raw = subprocess.check_output(['git', 'show', revision + ':' + name], cwd=upstream)
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('SRAM view hash mismatch: ' + name)
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    receipt = dict(status='views_verified_not_qualified', revision=revision,
                   files=lock['files'], command=' '.join(__import__('sys').argv))
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f"PASS {len(lock['files'])} pinned SRAM views; physical qualification not claimed")
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/vendor/gf180_sram')
    parser.add_argument('--source')
    args = parser.parse_args()
    prepare(args.output, args.source)
