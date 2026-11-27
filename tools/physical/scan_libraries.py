"""Authenticate each STA library against the existing physical/source locks."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def authenticate(paths):
    locks={name:ROOT/path for name,path in {
        'pdk':'phys/gf180-ws-1x1/pdk-lock.json',
        'candidate':'phys/gf180-ws-1x1/pdk-candidate.lock.json',
        'sram':'hw/vendor/gf180_sram/gf180_sram.lock.json',
        'template':'phys/gf180-ws-1x1/template.lock.json',
        'physical':'phys/gf180-ws-1x1/physical-views.lock.json'}.items()}
    records={n:json.loads(p.read_text()) for n,p in locks.items()}
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    dependencies=list(locks.values());archive=None;members=[]
    for p in paths:
        if 'gf180mcu_fd_sc_mcu7t5v0__' in p.name:
            expected=records['pdk']['files'][p.name]
        elif 'gf180mcu_ocd_ip_sram__' in p.name:
            expected=records['sram']['files'][p.relative_to(ROOT/'build/vendor/gf180_sram').as_posix()]
        elif p.is_relative_to(ROOT/'build/t43/template-default03'):
            expected=records['template']['files'][p.relative_to(ROOT/'build/t43/template-default03').as_posix()]
        elif p.name.startswith('gf180mcu_fd_io__'):
            if archive is None:
                archive=ROOT/'build/t43/pdk-candidate/gf180mcu_fd_io.tar.zst'
                assert sha(archive)==records['candidate']['archives'][archive.name]['sha256']
                zstd=Path('/nix/store/gxxyccld1qfy1v98hbzv8g9yk1saqx82-zstd-1.5.7-bin/bin/zstd')
                dependencies.extend([archive,zstd])
                compressor='--use-compress-program='+str(zstd)
                members=subprocess.run(['tar',compressor,'-tf',str(archive)],check=True,capture_output=True,text=True).stdout.splitlines()
            selected=[name for name in members if name==p.relative_to(ROOT/'build/t43/pdk-candidate').as_posix()]
            assert len(selected)==1
            data=subprocess.run(['tar',compressor,'-xOf',str(archive),selected[0]],check=True,capture_output=True).stdout
            expected=hashlib.sha256(data).hexdigest()
        else:raise ValueError('Unpinned timing library '+str(p))
        assert sha(p)==expected,'Changed timing library '+str(p)
    # The physical ODB retains authenticated technology layers. Also bind all
    # corner techLEF/RC collateral available to the pinned placement estimator.
    pdk=ROOT/records['pdk']['root']
    assert records['pdk']['revision']==records['physical']['revision']
    for name,expected in records['physical']['files'].items():
        path=pdk/name;assert sha(path)==expected;dependencies.append(path)
    return dependencies
