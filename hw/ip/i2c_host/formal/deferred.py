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


# T41 RegBlock local bindings renamed only eight internal pulse registers.
# Fresh T44 WRITE/READ/RECOVER emissions were compared to every retained model.
# Keep this exact transition, not a generic emitted-model normalization.
REGBLOCK_RENAMES = {
    f'readFields_hw_command_{name}_pulse_REG': 'readFields_pulse'+suffix
    for name,suffix in zip(('start','write','read','stop','recover','apply','ack','pop'),
                          ('','_1','_2','_3','_4','_5','_6','_7'))
}
REGBLOCK_HASH_PAIRS = {
    '4baca86cf60ecc26b6c64cc358414ca124727e01704e9a0bc1d024b51d150f8c':
        '728fba7f4393998b6dfa58480231712cdafc39754d99162ecf91a15ff3b4fa4c',
    '6720d2abb7a2ff83836dd7974fc8938806ddbc6cc1cdfd801760c4a30b6af411':
        '7c173c372fbeeaa3ec53cde9a8169e83b91b2cc16e48944ea4e624a9fe7b1e01',
    'e7bb513185362ae5288aaf10623cde757faa6c8fadf40ba0a903929e8a81b402':
        'e3153d51fc855d26421c57120de34aa0adf8347859c8a1c90f050977096fa28d',
}


def reviewed_regblock_rename(original, current, files, root):
    if set(original)!=set(current) or files is None or set(files)!=set(current):
        return None
    if {name for name in original if original[name]!=current[name]}!={'RegBlock.sv'}:
        return None
    if REGBLOCK_HASH_PAIRS.get(original['RegBlock.sv'])!=current['RegBlock.sv']:
        return None
    root=Path(root).resolve()
    for name,path in files.items():
        path=Path(path).resolve();path.relative_to(root/'build')
        if path.name!=name or digest(path)!=current[name]:
            raise ValueError('Changed actual emitted model: '+name)
    content=Path(files['RegBlock.sv']).read_bytes()
    reverse={v.encode():k.encode() for k,v in REGBLOCK_RENAMES.items()}
    if len(reverse)!=len(REGBLOCK_RENAMES):raise ValueError('Non-bijective rename witness')
    token=re.compile(rb'[A-Za-z_$][A-Za-z_0-9$]*')
    identifiers=set(token.findall(content))
    if not set(reverse)<=identifiers or set(reverse.values())&identifiers:
        raise ValueError('Missing or colliding rename identity')
    restored=token.sub(lambda m:reverse.get(m[0],m[0]),content)
    if hashlib.sha256(restored).hexdigest()!=original['RegBlock.sv']:
        raise ValueError('Changed model beyond reviewed internal-register renaming')
    return dict(kind='T44 exact RegBlock internal-identifier bijection',
                original_source_sha256=original,actual_source_sha256=current,
                identifiers=REGBLOCK_RENAMES,
                qualification='Byte-identical after the explicit identifier bijection; '
                              'historical TIMEOUT remains unproved, no solver rerun.')


def reviewed_openocd_extension(path, original, current):
    """Exact T32 additive lock transition; never a generic tool-change waiver.

    Only TIMEOUT bookkeeping is reused. No claim of identical rebuilt binaries
    or a newly proved property follows from this compatibility record.
    """
    old_hash='f71eedeba5148822a8fd95764f3f931c6ea96f6c370d3aac1dc8ee14e8b51e2a'
    new_hash='250c90edb13f33ae22b48c1bb39f1c3ea311b1bd6154b14cb548e8c8c108d924'
    if original!=old_hash or current!=new_hash or environment_digest(path)!=new_hash:
        return None
    lock=json.loads(Path(path).read_text())
    added_packages=['automake','libtool','pkg-config']
    if lock['apt_packages'][-3:]!=added_packages or lock['versions'].pop('openocd')!='0.12.0':
        raise ValueError('Reviewed OpenOCD lock additions differ')
    lock['apt_packages']=lock['apt_packages'][:-3]
    archives=lock['sources'][-2:]
    if [(a['name'],a['commit'],a['sha256']) for a in archives]!=[
        ('openocd.tar.gz','9ea7f3d647c8ecf6b0f1424002dfc3f4504a162c','704995583c5132bfeefd341585d6fc797940cd9c619c83c4971757720829db8a'),
        ('jimtcl.tar.gz','a77ef1a6218fad4c928ddbdc03c1aedc41007e70','fd111331a08ef7bad4eaa6e20f8c122977b5a26aeeac29873e0b19bb719048f3')]:
        raise ValueError('Reviewed OpenOCD source pins differ')
    lock['sources']=lock['sources'][:-2]
    flags=lock.pop('openocd_configure')
    if flags!=['--prefix=/opt/openocd','--enable-remote-bitbang','--enable-internal-jimtcl',
               '--disable-internal-libjaylink','--disable-doxygen-html','--disable-doxygen-pdf']:
        raise ValueError('Reviewed OpenOCD configuration differs')
    reconstructed=(json.dumps(lock,indent=2)+'\n').replace('\n','\r\n').encode()
    if hashlib.sha256(reconstructed).hexdigest()!=old_hash:
        raise ValueError('Pre-existing environment entry changed')
    return dict(kind='T32 exact additive OpenOCD lock compatibility',
                actual_environment_sha256=new_hash,original_environment_sha256=old_hash,
                added_packages=added_packages,added_sources=archives,added_openocd_version='0.12.0',
                added_openocd_configure=flags,
                qualification='All pre-existing lock entries identical; historical TIMEOUT remains unproved. '
                              'No solver rerun and no claim of identical rebuilt tool binaries.')


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


def authenticate(entry, identity, sources, root, environment_lock=None, source_files=None):
    original_identity=identity
    compatibility=None
    differences={k for k in entry['identity'].keys() | identity.keys() if entry['identity'].get(k)!=identity.get(k)}
    if differences=={'environment_sha256'} and environment_lock is not None:
        compatibility=reviewed_openocd_extension(environment_lock,
            entry['identity']['environment_sha256'],identity['environment_sha256'])
        if compatibility:
            original_identity=dict(identity,environment_sha256=entry['identity']['environment_sha256'])
    model_compatibility=None
    if entry['identity']==original_identity and entry['source_sha256']!=sources:
        model_compatibility=reviewed_regblock_rename(entry['source_sha256'],sources,source_files,root)
    if entry['identity']!=original_identity or (entry['source_sha256']!=sources and not model_compatibility):
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
        if len(rows)!=1 or rows[0].get('solver_status')!='TIMEOUT' or rows[0].get('returncode')!=8 or rows[0].get('retained',False) or rows[0].get('source_sha256')!=entry['source_sha256']:
            raise ValueError('Original receipt does not contain the bound timeout attempt')
        if any(rows[0].get(key)!=original_identity[key] for key in ('mode','engine','depth')):
            raise ValueError('Original receipt solver identity differs')
        if 'identity' in rows[0] and rows[0]['identity']!=original_identity:
            raise ValueError('Original receipt full job identity differs')
    return dict(status='deferred_unproved',retained=True,solver_rerun=False,
                historical_artifacts_available=available,original_provenance=entry['provenance'],
                original_identity=entry['identity'],environment_compatibility=compatibility,
                model_compatibility=model_compatibility)
