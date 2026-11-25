"""Authenticate physical views and prevent mixed-revision diagnostic runs."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.pdk import LOCK,root
VIEWS=ROOT/'phys/gf180-ws-1x1/physical-views.lock.json'


def manifest():
    active=json.loads(LOCK.read_text());views=json.loads(VIEWS.read_text())
    if active['revision']!=views['revision']:
        raise ValueError('Physical views and active PDK revisions differ')
    dependencies=[LOCK,VIEWS,ROOT/'tools/pdk.py',Path(__file__)]
    return dict(revision=active['revision'],input_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies})


def require_manifest(record):
    if record.get('pdk')!=manifest():
        raise ValueError('Missing, stale or mixed PDK physical input manifest')


def require_prepared(record):
    require_manifest(record)
    if not record.get('input_sha256'):
        raise ValueError('Missing prepared physical input inventory')
    for name,expected in record['input_sha256'].items():
        path=(ROOT/name).resolve();path.relative_to(ROOT)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Changed prepared physical input: '+name)


def view(relative):
    manifest()
    path=(root()/relative).resolve();path.relative_to(root())
    expected=json.loads(VIEWS.read_text())['files'][relative]
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        raise ValueError('Physical view hash mismatch: '+relative)
    return path
