"""Validate pinned adoption bytes and license; this is provenance, not a behavior test."""
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[3]
BLOCK=Path(__file__).resolve().parent

def main():
    manifest=json.loads((BLOCK/'provenance.json').read_text())
    for item in manifest['files']:
        raw=subprocess.check_output(['git','-C',str(ROOT/'build/riscay-mcu'),'show',manifest['commit']+':'+item['source']])
        blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if blob!=item['blob']:raise ValueError('Pinned blob mismatch: '+item['source'])
        if item['source']!='LICENSE':
            raw=raw.replace(b'package riscay.clocked',b'package deadhorse.lite_core')
            raw=raw.replace(b'package riscay',b'package deadhorse.lite_core').replace(b'import riscay._',b'')
        for destination in item['destinations']:
            actual=(BLOCK/destination).read_bytes().replace(b'\r\n',b'\n')
            if actual!=raw.replace(b'\r\n',b'\n'):raise ValueError('Adoption differs: '+destination)
    for item in manifest['derivatives']:
        if not (BLOCK/item['destination']).is_file():raise ValueError('Missing derivative')
        if item['source'] not in {x['source'] for x in manifest['files']}:raise ValueError('Unpinned derivative source')
    print('PASS pinned baseline/oracle/license bytes; extension explicitly identified as derivative')
if __name__=='__main__':main()
