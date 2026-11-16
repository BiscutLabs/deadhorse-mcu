"""Authenticate the exact production/proof snapshots used by FPU composition."""
import hashlib
import json
from pathlib import Path

ROLES=('normal','cover_operations','cover_protocol','cover_division',
       'cancel_fault','hold_fault','progress_fault')

def required(root, out):
    production=sorted((root/'build/t12/emit').glob('*.sv'))
    if not production: raise ValueError('Missing FPU production snapshot')
    paths=list(production)
    for role in ROLES:
        directory=out/role
        paths += [directory/name for name in ('prepared.json','abstraction.json','check.sby',
                   'proof/status','proof/engine_0/logfile.txt')]
        paths += sorted((out/'emit'/role).glob('*.sv'))
        status=(directory/'proof/status').read_text().split()[0]
        if status!=('FAIL' if role.endswith('fault') else 'PASS'):
            raise ValueError('Unsuccessful FPU proof role: '+role)
    paths += [out/'normal'/name for name in ('projected-canonical.json',
        'production-canonical.json','binding/result.json','binding/negative-controls.json')]
    binding=json.loads((out/'normal/binding/result.json').read_text())
    if binding.get('status')!='proved': raise ValueError('FPU production binding missing')
    paths += [root/'hw/ip/fpu/formal'/name for name in ('check.py','FpuFormal.scala','receipt.py')]
    return sorted(set(paths)),production

def fingerprints(root,paths):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def unchanged(root,protected):
    for name,digest in protected.items():
        path=(root/name).resolve();path.relative_to(root)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('FPU artifact changed while proof was running: '+name)

def snapshot(root,out,protected):
    paths,production=required(root,out)
    unchanged(root,protected)
    for role in ROLES:
        recorded=json.loads((out/role/'abstraction.json').read_text())['sources']
        actual=fingerprints(root,sorted((out/'emit'/role).glob('*.sv')))
        if actual!=recorded: raise ValueError('FPU monitor emission changed during proof: '+role)
    artifacts=fingerprints(root,paths)
    expected=set(p.relative_to(root).as_posix() for p in production)
    expected.update('hw/ip/fpu/formal/'+name for name in ('check.py','FpuFormal.scala','receipt.py'))
    for role in ROLES:
        expected.update((out/role/name).relative_to(root).as_posix()
            for name in ('prepared.json','abstraction.json','check.sby'))
        expected.update(p.relative_to(root).as_posix() for p in (out/'emit'/role).glob('*.sv'))
    if set(protected)!=expected: raise ValueError('Protected proof input inventory is incomplete or unexpected')
    production_names=[p.relative_to(root).as_posix() for p in production]
    if any(name not in protected for name in production_names):
        raise ValueError('Unbound FPU production source')
    return dict(schema=2,production=production_names,protected=protected,artifacts=artifacts)

def authenticate(root,out):
    receipt=json.loads((out/'result.json').read_text())
    if receipt.get('status')!='pass': raise ValueError('FPU protocol proof is not PASS')
    expected=receipt.get('authentication')
    if not expected or expected.get('schema')!=2 or expected!=snapshot(root,out,expected['protected']):
        raise ValueError('FPU protocol proof snapshot mismatch or unauthenticated receipt')
    return expected
