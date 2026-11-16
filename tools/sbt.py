"""Run the locked, direct Chisel build inside T08; all generated files stay in build/."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    lock_file = ROOT / 'tools/env/lock.json'
    installed = Path('/opt/deadhorse-env/lock.json')
    if not installed.is_file() or installed.read_bytes() != lock_file.read_bytes():
        raise RuntimeError('use the pinned T08 image via tools/env/run.py')
    lock = json.loads(lock_file.read_text())
    subprocess.run([sys.executable, str(ROOT / 'hw/vendor/hardfloat/prepare.py')],
                   cwd=ROOT, check=True)
    pins = lock['versions']
    if (ROOT / 'project/build.properties').read_text().strip() != 'sbt.version=' + pins['sbt']:
        raise RuntimeError('project/build.properties disagrees with T08 lock')
    # The build definition is mirrored so sbt's meta-build target/project directories
    # are output too. Sources are always read directly from the real repository.
    definitions = [ROOT / 'build.sbt', *sorted((ROOT / 'project').glob('*'))]
    if any(not source.is_file() for source in definitions):
        raise RuntimeError('project/ must contain only build-definition files')
    fingerprint = hashlib.sha256(b''.join(
        source.relative_to(ROOT).as_posix().encode() + b'\0' + source.read_bytes()
        for source in definitions)).hexdigest()
    work = ROOT / 'build/sbt/definitions' / fingerprint
    (work / 'project').mkdir(parents=True, exist_ok=True)
    for source in definitions:
        target = work / source.relative_to(ROOT)
        data = source.read_bytes()
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
    for item in lock['maven']:
        path = Path('/opt/maven-pins') / item['name']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError('locked Maven artifact mismatch: ' + item['name'])
    cache = ROOT / 'build/env/cache'
    command = ['java', '-Xmx2G', '-XX:ActiveProcessorCount=4',
               '-Dsbt.supershell=false', '-Dsbt.color=false', '-Dsbt.override.build.repos=true',
               '-Duser.home=' + str(ROOT / 'build/env/home'),
               '-Djava.io.tmpdir=' + str(ROOT / 'build/env/tmp'),
               '-Dsbt.global.base=' + str(cache / 'sbt'),
               '-Dsbt.boot.directory=' + str(cache / 'sbt-boot'),
               '-Dsbt.ivy.home=' + str(cache / 'ivy'),
               '-Dsbt.repository.config=' + str(ROOT / 'project/repositories'),
               '-Ddeadhorse.root=' + str(ROOT)]
    command += [f'-Ddeadhorse.{key}={value}' for key, value in pins.items()]
    command += ['-jar', '/opt/sbt/bin/sbt-launch.jar', *sys.argv[1:]]
    # All invocations share Zinc's class products, even when a formal emitter
    # temporarily adds unmanagedSources. Concurrent sbt processes can remove
    # each other's products between compilation and runMain. Serialize the
    # complete child lifetime across pinned-container invocations.
    import fcntl
    with (ROOT / 'build/sbt/compile.lock').open('a') as guard:
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        return subprocess.call(command, cwd=work)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        sys.exit(f'SBT: {exc}')
