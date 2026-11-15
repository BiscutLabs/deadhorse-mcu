"""Verification source selection and a byte-exact reference-copy fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from common import CONFIG, ROOT, VENDOR, adaptation_entry, inputs, local, output_dir


def source_path(directory,source):
    options = [p for p in (directory/source,directory/Path(source).name) if p.is_file()]
    if len(options) != 1:
        raise ValueError(f'Candidate must supply one source for {source}; found {len(options)}')
    path = options[0].resolve()
    path.relative_to(directory)
    return path


def parameters(directory):
    """Only authenticated fixed emissions suppress SV parameter overrides."""
    if directory is None or not local(directory).is_dir():
        return CONFIG['parameters']
    directory = local(directory)
    manifest = directory/'candidate.json'
    if not manifest.exists():
        return CONFIG['parameters']
    data = json.loads(manifest.read_text())
    if data.get('schema') != 1 or data.get('kind') != 'fixed':
        raise ValueError('Unsupported candidate configuration schema/kind')
    if data.get('parameters') != CONFIG['parameters']:
        raise ValueError('Fixed candidate configuration differs from pinned configuration')
    lock = inputs()
    required = {p for p in lock['sources'] if p.startswith('rtl/') and not p.endswith('_pkg.sv')}
    if set(data.get('source_sha256',{})) != required:
        raise ValueError('Fixed candidate source hash set must exactly cover every Ibex module')
    for name,digest in data['source_sha256'].items():
        if hashlib.sha256(source_path(directory,name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Fixed candidate source hash mismatch: {name}')
    return {}


def sources(directory, lock, output):
    directory = local(directory)
    if not directory.is_dir():
        raise ValueError('Candidate must be a source directory')
    result, receipts = [], []
    effective_parameters = parameters(directory)
    for source in lock['sources']:
        reference = VENDOR/source
        if source.startswith('rtl/') and not source.endswith('_pkg.sv'):
            path = source_path(directory,source)
            data = path.read_bytes()
            receipts.append(dict(source=source, candidate=str(path.relative_to(ROOT)),
                                 sha256=hashlib.sha256(data).hexdigest()))
            entry = adaptation_entry('unused_initializer')
            if source == entry['source'] and hashlib.sha256(data).hexdigest() == entry['source_sha256']:
                old = entry['remove'].encode()
                if data.count(old) != 1:
                    raise ValueError('Candidate initializer adaptation must match exactly once')
                path = output/'candidate-adapted/ibex_top.sv'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data.replace(old,b'',1))
                receipts[-1]['adaptation'] = entry['id']
                receipts[-1]['adapted_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            # Immutable package constants and technology-neutral verification
            # primitives, never a fallback implementation of an Ibex module.
            path = reference
        result.append(str(path))
    (output/'candidate-sources.json').write_text(json.dumps(receipts,indent=2)+'\n')
    (output/'candidate-configuration.json').write_text(json.dumps(dict(
        declared_parameters=CONFIG['parameters'],sv_overrides=effective_parameters),indent=2)+'\n')
    return result


def reference_copy(destination):
    destination = output_dir(destination)
    lock = inputs()
    copied = {}
    for source in lock['sources']:
        if not source.startswith('rtl/') or source.endswith('_pkg.sv'):
            continue
        target = destination/source
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(VENDOR/source,target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != lock['files'][source]['sha256']:
            raise ValueError(f'Reference copy differs: {source}')
        copied[source] = digest
    (destination/'reference-copy.json').write_text(json.dumps(copied,indent=2)+'\n')
    print('PASS byte-identical reference candidate copy')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-copy', required=True)
    reference_copy(parser.parse_args().reference_copy)
