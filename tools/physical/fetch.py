"""Fetch hash-pinned physical views into build; run inside the pinned T08 image."""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[2]

if __name__=='__main__':
    lock=json.loads((Path(__file__).parent/'lock.json').read_text())
    output=ROOT/'build/physical/pdk'/lock['pdk_revision'];output.mkdir(parents=True,exist_ok=True)
    for name,sha in lock['archives'].items():
        path=output/name
        if not path.exists():urllib.request.urlretrieve(lock['pdk_release']+'/'+name,path)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('PDK archive checksum mismatch: '+name)
        subprocess.run(['tar','--zstd','-xf',str(path),'-C',str(output)],check=True)
        print('VERIFIED '+name,flush=True)
