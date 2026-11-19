"""Verify pristine USB source and materialize the recorded patch under build/."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(output):
    output = (ROOT / output).resolve()
    output.relative_to(ROOT / 'build')
    lock = json.loads((HERE / 'usb.lock.json').read_text())
    if digest(HERE / 'LICENSE') != lock['license_sha256']:
        raise ValueError('USB license hash mismatch')
    for name, entry in lock['files'].items():
        if digest(HERE / name) != entry['sha256']:
            raise ValueError('USB pristine source mismatch: ' + name)
    for entry in lock['patches']:
        if digest(HERE / entry['path']) != entry['sha256']:
            raise ValueError('USB patch mismatch: ' + entry['path'])
    # Recreate files, never mutate or remove the pristine import.
    for name in lock['files']:
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / name, output / name)
    for entry in lock['patches']:
        subprocess.run(['git', 'apply', '--check', str(HERE / entry['path'])], cwd=output, check=True)
        subprocess.run(['git', 'apply', str(HERE / entry['path'])], cwd=output, check=True)
    for name, entry in lock['files'].items():
        if digest(output / name) != entry['applied_sha256']:
            raise ValueError('USB applied source mismatch: ' + name)
    print('PASS USB pristine/patch/applied hashes')
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='build/vendor/usb')
    prepare(parser.parse_args().output)
