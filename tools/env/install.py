"""Image build only: install immutable inputs; never execute on the host."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'lock.json').read_text())


def fetch(item, dest):
    if dest.exists():
        with dest.open('rb') as cached:
            if hashlib.file_digest(cached, 'sha256').hexdigest() == item['sha256']:
                return
    with urllib.request.urlopen(item['url'], timeout=120) as src, dest.open('wb') as out:
        shutil.copyfileobj(src, out)
    with dest.open('rb') as downloaded:
        actual = hashlib.file_digest(downloaded, 'sha256').hexdigest()
    if actual != item['sha256']:
        raise RuntimeError(f"CHECKSUM: {item['name']}: {actual}")


def main():
    cache = Path('/opt/downloads'); cache.mkdir(exist_ok=True)
    for item in LOCK['archives']:
        dest = cache / item['name']; fetch(item, dest)
        if dest.suffix == '.zip':
            with zipfile.ZipFile(dest) as archive:
                binary = Path('/usr/local/bin/sv2v')
                binary.write_bytes(archive.read('sv2v-Linux/sv2v'))
                binary.chmod(0o755)
            continue
        with tarfile.open(dest) as tar:
            if item['name'].startswith('firrtl'):
                target = Path('/opt/firtool'); target.mkdir()
                # The release has one root directory; flatten only that component.
                for member in tar.getmembers():
                    parts = Path(member.name).parts
                    if len(parts) <= 1: continue
                    member.name = str(Path(*parts[1:]))
                    tar.extract(member, target, filter='data')
            else:
                tar.extractall('/opt', filter='data')
    sources = Path('/opt/sources'); sources.mkdir()
    for item in LOCK['sources']:
        dest = cache / item['name']; fetch(item, dest)
        target = sources / item['name'].split('.')[0]; target.mkdir()
        subprocess.run(['tar', 'xf', str(dest), '--strip-components=1', '-C', str(target)], check=True)
    subprocess.run(['./configure', '--prefix=/opt/cudd'], cwd=sources/'cudd', check=True)
    subprocess.run(['make', '-j2'], cwd=sources/'cudd', check=True)
    subprocess.run(['make', 'install'], cwd=sources/'cudd', check=True)
    subprocess.run(['cmake', '-S', str(sources/'opensta'), '-B', str(sources/'sta-build'),
                    '-DCUDD_DIR=/opt/cudd', '-DCMAKE_BUILD_TYPE=Release',
                    '-DCMAKE_INSTALL_PREFIX=/opt/opensta'], check=True)
    subprocess.run(['cmake', '--build', str(sources/'sta-build'), '-j2'], check=True)
    subprocess.run(['cmake', '--install', str(sources/'sta-build')], check=True)
    # OpenOCD's JimTcl submodule is fetched independently by its exact gitlink.
    # No network or unpinned submodule update is allowed during bootstrap.
    shutil.copytree(sources/'jimtcl', sources/'openocd/jimtcl', dirs_exist_ok=True)
    subprocess.run(['./bootstrap', 'nosubmodule'], cwd=sources/'openocd', check=True)
    subprocess.run(['./configure', *LOCK['openocd_configure']], cwd=sources/'openocd', check=True)
    subprocess.run(['make', '-j2'], cwd=sources/'openocd', check=True)
    subprocess.run(['make', 'install'], cwd=sources/'openocd', check=True)
    shutil.rmtree(sources)
    subprocess.run(['python3', '-m', 'venv', '--system-site-packages', '/opt/yowasp'], check=True)
    wheels = []
    for item in LOCK['wheels']:
        dest = cache / item['name']; fetch(item, dest); wheels.append(str(dest))
    subprocess.run(['/opt/yowasp/bin/pip', 'install', '--no-index', '--no-deps', *wheels], check=True)
    subprocess.run(['/opt/yowasp/bin/pip', 'check'], check=True)
    maven = Path('/opt/maven-pins'); maven.mkdir()
    for item in LOCK['maven']: fetch(item, maven / item['name'])
    # Record every Ubuntu dependency, including transitives, for runtime attestation.
    inventory = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}\t${Version}\n'], text=True)
    (HERE / 'apt-installed.txt').write_text(inventory)


if __name__ == '__main__': main()
