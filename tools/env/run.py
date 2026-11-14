"""Host-side Docker orchestration; checks themselves run only in the image."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / 'tools/env'
STATE = ROOT / 'build/env'


def fingerprint():
    files = sorted(p for p in ENV.iterdir() if p.is_file() and p.name != 'README.md')
    return hashlib.sha256(b''.join(p.name.encode() + b'\0' + p.read_bytes() for p in files)).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'run'))
    parser.add_argument('--clean', action='store_true', help='Rebuild without layer cache')
    parser.add_argument('--network', choices=('none', 'bridge'), default='none')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ENV / 'lock.json').read_text())
    dockerfile = (ENV / 'Dockerfile').read_text()
    if lock['base'] not in dockerfile or lock['certificate_base'] not in dockerfile or lock['apt_snapshot'] not in dockerfile:
        parser.error('Dockerfile disagrees with locked bases/snapshot')
    receipt_path = STATE / 'image.json'
    if args.action == 'build':
        inputs = fingerprint()
        options = args.command
        clean = args.clean or options == ['--clean']
        if options and options != ['--clean']: parser.error('build accepts only --clean')
        cmd = ['docker', 'build', '--platform', lock['platform'], '--progress', 'plain',
               '--iidfile', 'build/env/image-id.txt', '-f', 'tools/env/Dockerfile',
               '-t', 'deadhorse-env:local']
        if clean: cmd.append('--no-cache')
        cmd.append('.')
        with (STATE / 'build.log').open('w', encoding='utf-8') as log:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                print(line, end='', flush=True); log.write(line); log.flush()
            if proc.wait(): return proc.returncode
        image = (STATE / 'image-id.txt').read_text().strip()
        if fingerprint() != inputs:
            raise RuntimeError('environment inputs changed during build; rebuild before running')
        receipt = {'image': image, 'inputs_sha256': inputs, 'platform': lock['platform']}
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        print(f'IMAGE {image}')
        return 0
    if args.clean: parser.error('--clean applies only to build')
    if not receipt_path.exists(): parser.error('build the environment first')
    receipt = json.loads(receipt_path.read_text())
    if receipt['inputs_sha256'] != fingerprint(): parser.error('environment inputs changed; rebuild first')
    command = args.command
    if command[:1] == ['--']: command = command[1:]
    if not command: command = ['python3', 'tools/ci.py']
    # Use immutable local image ID, never the mutable convenience tag. Mount no
    # host home, Docker socket, credential directory or other repository.
    cmd = ['docker', 'run', '--rm', '--platform', lock['platform'], '--network', args.network,
           '--mount', f'type=bind,source={ROOT},target=/work', '-w', '/work',
           receipt['image'], *command]
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f'ENV_RUN: {exc}')
