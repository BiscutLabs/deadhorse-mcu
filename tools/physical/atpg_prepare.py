"""Authenticate and unpack the separately pinned Quaigh source under build/."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def verify(archive, lock):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != lock['git_archive_sha256']:
        raise ValueError('Quaigh archive hash differs from lock')
    with tarfile.open(archive) as source:
        for name, expected in lock['files'].items():
            member = source.getmember(name)
            if not member.isfile() or hashlib.sha256(source.extractfile(member).read()).hexdigest() != expected:
                raise ValueError('Quaigh locked file mismatch: '+name)
        for member in source.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unexpected source archive member')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    lockfile = ROOT/'tools/physical/atpg.lock.json'
    lock = json.loads(lockfile.read_text())
    verify(args.archive, lock)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'build') or output.exists():
        raise ValueError('Use a new build/ source directory')
    output.mkdir(parents=True)
    with tarfile.open(args.archive) as source:
        source.extractall(output, filter='data')
    # Keep receipt beside, not inside, the immutable Nix source tree.
    output.with_suffix('.receipt.json').write_text(json.dumps(dict(result='pass_source_authentication',
        source_revision=lock['revision'], archive_sha256=lock['git_archive_sha256'],
        lock_sha256=hashlib.sha256(lockfile.read_bytes()).hexdigest()),indent=2)+'\n')
    print('PASS source authentication: '+lock['revision'])


if __name__ == '__main__':
    main()
