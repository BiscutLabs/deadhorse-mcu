"""Verify reference-only, byte-exact imported sources and their provenance."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def verify():
    lock = json.loads((ROOT / 'ibex_ref.lock.json').read_text())
    if lock.get('reference_only') is not True:
        raise ValueError('Reference-only designation missing')
    for name, entry in lock['files'].items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT)
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError(f'Vendor hash mismatch: {name}')
        if not entry['original_path'] or entry['upstream'] not in lock['upstreams']:
            raise ValueError(f'Missing provenance: {name}')
    for name in lock['sources']:
        if name not in lock['files']:
            raise ValueError(f'Unlocked compile input: {name}')
    if len(lock['sources']) != len(set(lock['sources'])):
        raise ValueError('Duplicate compile input')
    for path in ROOT.rglob('*'):
        if path.is_file() and path.suffix in ('.v', '.sv', '.vh', '.svh') and path.relative_to(ROOT).as_posix() not in lock['files']:
            raise ValueError(f'Unlisted vendor RTL: {path}')
    print(f'PASS Ibex reference lock: {len(lock["files"])} unchanged files')
    return lock


if __name__ == '__main__':
    try:
        verify()
    except (OSError, ValueError, KeyError) as exc:
        print(f'FAIL reference lock: {exc}', file=sys.stderr)
        sys.exit(1)
