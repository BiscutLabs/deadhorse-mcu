"""Retain reviewed TIMEOUT obligations without retrying an identical model."""
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment_digest(path):
    # Preserve the reviewed CRLF lock identity across LF/CRLF checkouts.
    # This normalization is solely for the environment lock, never evidence
    # or emitted models. Every other byte and final-newline presence is bound.
    content=Path(path).read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
    return hashlib.sha256(content).hexdigest()


def load_policy(path, allowed_ids):
    policy=json.loads(Path(path).read_text())
    if policy.get('version')!=1 or policy.get('task')!='T17' or not isinstance(policy.get('entries'),list):
        raise ValueError('Invalid retained I2C deferral policy')
    entries={}
    for entry in policy['entries']:
        ident=entry.get('id')
        if ident not in allowed_ids or ident in entries:
            raise ValueError('Unknown or duplicate retained deferral ID')
        if entry.get('solver_status')!='TIMEOUT' or entry.get('returncode')!=8:
            raise ValueError('Only an actual solver TIMEOUT may be retained')
        if not isinstance(entry.get('identity'),dict) or entry['identity'].get('timeout_seconds')!=120:
            raise ValueError('Invalid retained job identity or timeout budget')
        sources=entry.get('source_sha256')
        if not isinstance(sources,dict) or not sources or any(not re.fullmatch('[0-9a-f]{64}',v) for v in sources.values()):
            raise ValueError('Missing retained model source hashes')
        provenance=entry.get('provenance')
        if not isinstance(provenance,dict) or set(provenance)!={'receipt','status','log'}:
            raise ValueError('Missing original timeout provenance')
        for artifact in provenance.values():
            if not isinstance(artifact,dict) or set(artifact)!={'path','sha256'} or not re.fullmatch('[0-9a-f]{64}',artifact['sha256']):
                raise ValueError('Invalid original artifact identity')
        entries[ident]=entry
    return entries


def authenticate(entry, identity, sources, root):
    if entry['identity']!=identity or entry['source_sha256']!=sources:
        raise ValueError('Retained deferral model/job mismatch; focused review and a changed-model attempt required: '+entry['id'])
    root=Path(root).resolve(); available={}
    for name,artifact in entry['provenance'].items():
        relative=Path(artifact['path'])
        if relative.is_absolute(): raise ValueError('Original provenance must be repository relative')
        path=(root/relative).resolve()
        path.relative_to(root/'build')
        available[name]=path.exists()
        if path.exists() and (not path.is_file() or digest(path)!=artifact['sha256']):
            raise ValueError('Original timeout provenance hash mismatch: '+name)
    if available['status']:
        if (root/entry['provenance']['status']['path']).read_text().split()[0]!='TIMEOUT':
            raise ValueError('Original solver status is not TIMEOUT')
    if available['receipt']:
        original=json.loads((root/entry['provenance']['receipt']['path']).read_text())
        rows=[row for case in original.get('cases',{}).values() for row in case.get('jobs',[]) if row.get('id')==entry['id']]
        if len(rows)!=1 or rows[0].get('solver_status')!='TIMEOUT' or rows[0].get('returncode')!=8 or rows[0].get('retained',False) or rows[0].get('source_sha256')!=sources:
            raise ValueError('Original receipt does not contain the bound timeout attempt')
        if any(rows[0].get(key)!=identity[key] for key in ('mode','engine','depth')):
            raise ValueError('Original receipt solver identity differs')
        if 'identity' in rows[0] and rows[0]['identity']!=identity:
            raise ValueError('Original receipt full job identity differs')
    return dict(status='deferred_unproved',retained=True,solver_rerun=False,
                historical_artifacts_available=available,original_provenance=entry['provenance'])
