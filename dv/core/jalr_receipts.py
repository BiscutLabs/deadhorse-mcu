"""Immutable audit snapshots and exact historical evidence relocation.

No proof is rerun and no old receipt/hash/status is rewritten. A relocation is
accepted only when an archived file has exactly the originally recorded SHA256.
"""
import argparse
import hashlib
import json
from pathlib import Path

from common import ROOT, local, output_dir
from jalr_invariant import digest
from audit_jalr_invariant import active_witness


def verify_hashes(hashes,relocations=None):
    relocations=relocations or {}
    if not set(relocations)<=set(hashes): raise ValueError('Unknown relocated input')
    for original,expected in hashes.items():
        path=local(relocations.get(original,original))
        if digest(path)!=expected: raise ValueError('Proof input hash mismatch: '+original)


def combine_hashes(*inventories):
    merged={}
    for inventory in inventories:
        for path,digest_value in inventory.items():
            if path in merged and merged[path]!=digest_value: raise ValueError('Conflicting protected digest: '+path)
            merged[path]=digest_value
    return merged


def recover_audit_blob(current,commands,expected):
    # Reconstruction succeeds only by matching the previous receipt's digest.
    # The timing value comes from the preserved command log, never an estimate.
    for command in commands:
        if 'elapsed_seconds' not in command: continue
        candidate=json.loads(json.dumps(current))
        candidate['qualification_negative']['seconds']=command['elapsed_seconds']
        blob=(json.dumps(candidate,indent=2)+'\n').encode()
        if hashlib.sha256(blob).hexdigest()==expected: return blob
    raise ValueError('Cannot reconstruct exact historical audit bytes')


def atomic_write(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(data);temporary.replace(path)


def snapshot_baseline_audit(base,directory):
    base=local(base);directory=output_dir(directory)
    path=base/'audit.json';raw_path=base/'result.json'
    audit=json.loads(path.read_text());raw=json.loads(raw_path.read_text())
    if audit.get('status')!='pass' or raw.get('status')!='pass (lemma and original address partition only)':
        raise ValueError('Incomplete baseline audit/proof')
    if audit['raw_receipt_sha256']!=digest(raw_path): raise ValueError('Audit raw-receipt mismatch')
    hashes=combine_hashes(raw['input_sha256'],audit['audit_input_sha256'],{str(path):digest(path)})
    verify_hashes(hashes)
    for role,expected in [('prove','PASS'),('cover','PASS'),('fault','FAIL'),('original-source-address','PASS')]:
        if raw['results'][role]['status']!=expected or (base/role/'work/status').read_text().split()[0]!=expected:
            raise ValueError('Baseline role status mismatch: '+role)
    for role in ('cover','fault'):
        witnesses=audit['witnesses'][role]
        if not witnesses: raise ValueError('Missing baseline witness receipt')
        for witness in witnesses:
            trace=local(witness['path'])
            if digest(trace)!=witness['sha256'] or active_witness(trace.read_text(),role=='fault')!=witness['retirement']:
                raise ValueError('Baseline witness mismatch')
    negative=base/'qualification-negative/counterexample.json'
    if audit['qualification_negative']['status']!='rejected' or digest(negative)!=audit['qualification_negative']['counterexample_sha256']:
        raise ValueError('Baseline qualification fault evidence mismatch')
    blob=path.read_bytes();verify_hashes(hashes)
    destination=directory/'baseline-audit.json';atomic_write(destination,blob)
    if digest(destination)!=hashes[str(path)]: raise ValueError('Audit snapshot changed during copy')
    return destination


def requalify(directory,source_snapshot=None):
    out=local(directory);receipt_path=out/'result.json';before=digest(receipt_path)
    raw=json.loads(receipt_path.read_text());hashes=raw['input_sha256'];relocations={}
    audit_paths=[p for p in hashes if p.endswith('/jalr-address-strengthened/audit.json')]
    if len(audit_paths)!=1: raise ValueError('Expected unique historical shared audit input')
    original=audit_paths[0];base=local(original).parent;expected=hashes[original]
    current=local(original).read_bytes()
    if hashlib.sha256(current).hexdigest()==expected: blob=current
    else:
        commands=[json.loads(line) for line in (base/'qualification-negative/commands.jsonl').read_text().splitlines()]
        blob=recover_audit_blob(json.loads(current),commands,expected)
    archived=out/'baseline-audit.json';atomic_write(archived,blob)
    relocations[original]=str(archived)
    if source_snapshot:
        archived_source=local(source_snapshot)
        if not archived_source.name.endswith('.executed.py'): raise ValueError('Expected executed-source archive')
        original=str(ROOT/'dv/core'/archived_source.name.replace('.executed.py','.py'))
        if original not in hashes: raise ValueError('No recorded source for archive')
        relocations[original]=str(local(source_snapshot))
    verify_hashes(hashes,relocations)
    if digest(receipt_path)!=before: raise ValueError('Historical result changed')
    manifest=dict(status='reauthenticated',receipt_sha256=before,
        scope='metadata relocation only; no proof or status changed',
        relocations={p:dict(expected_sha256=hashes[p],snapshot=q) for p,q in relocations.items()})
    atomic_write(out/'input-relocations.json',(json.dumps(manifest,indent=2)+'\n').encode())
    print('PASS historical inputs reauthenticated: '+str(out.relative_to(ROOT)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--receipt');mode.add_argument('--snapshot-baseline')
    parser.add_argument('--source-snapshot');parser.add_argument('--output')
    args=parser.parse_args()
    if args.snapshot_baseline:
        if not args.output or args.source_snapshot: parser.error('Snapshot requires --output only')
        print('PASS immutable baseline audit snapshot: '+str(snapshot_baseline_audit(args.snapshot_baseline,args.output)))
    else:
        if args.output: parser.error('--output applies only to snapshot mode')
        requalify(args.receipt,args.source_snapshot)
