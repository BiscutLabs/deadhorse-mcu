"""Check the adopted reference's pinned blob and license, not RTL behavior."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[3]
BLOCK=Path(__file__).resolve().parent

def main():
    m=json.loads((BLOCK/'PROVENANCE.json').read_text())
    def source(path):
        return subprocess.check_output(['git','-C',str(ROOT/'build/riscay-mcu'),'show',m['commit']+':'+path])
    raw=source(m['source'])
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==m['blob']
    assert (BLOCK/'LICENSE').read_bytes().replace(b'\r\n',b'\n')==source('LICENSE').replace(b'\r\n',b'\n')
    assert (BLOCK/m['destination']).is_file()
    print('PASS pinned clocked-watchdog source/license; adaptations require their own verification')
if __name__=='__main__':main()
