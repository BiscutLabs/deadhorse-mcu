"""Verification source selection and a byte-exact reference-copy fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from common import CONFIG, ROOT, VENDOR, adaptation_entry, inputs, local, output_dir

# These declarations cannot be active under CONFIG. Missing active modules
# always fail closed; this table is not a general omission mechanism.
INACTIVE = {
    'rtl/ibex_branch_predict.sv': 'BranchPredictor=0',
    'rtl/ibex_dummy_instr.sv': 'SecureIbex=0; DummyInstructions=0',
    'rtl/ibex_icache.sv': 'ICache=0',
    'rtl/ibex_lockstep.sv': 'SecureIbex=0; Lockstep=0',
    'rtl/ibex_multdiv_slow.sv': 'RV32M=RV32MFast',
    'rtl/ibex_register_file_fpga.sv': 'RegFile=RegFileFF',
    'rtl/ibex_register_file_latch.sv': 'RegFile=RegFileFF',
    'rtl/ibex_pmp.sv': 'PMPEnable=0',
}


def manifest(directory):
    path=local(directory)/'candidate.json'
    return json.loads(path.read_text()) if path.exists() else None


def authenticated_path(directory,name,digest):
    path=(directory/name).resolve()
    path.relative_to(directory)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
        raise ValueError('Candidate extra/view source hash mismatch: '+name)
    return path


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
    if data.get('schema') not in (1,2) or data.get('kind') != 'fixed':
        raise ValueError('Unsupported candidate configuration schema/kind')
    if data['schema']==1 and any(name in data for name in ('excluded','extra_sources','module_views')):
        raise ValueError('Schema 1 cannot declare exclusions, extras or module views')
    if data.get('parameters') != CONFIG['parameters']:
        raise ValueError('Fixed candidate configuration differs from pinned configuration')
    lock = inputs()
    required = {p for p in lock['sources'] if p.startswith('rtl/') and not p.endswith('_pkg.sv')}
    excluded=data.get('excluded',{}) if data['schema']==2 else {}
    if excluded and excluded!=INACTIVE:
        raise ValueError('Only the exact pinned inactive-module set may be excluded')
    if set(data.get('source_sha256',{})) != required-set(excluded):
        raise ValueError('Fixed candidate source hash set must exactly cover every Ibex module')
    for name,digest in data['source_sha256'].items():
        if hashlib.sha256(source_path(directory,name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Fixed candidate source hash mismatch: {name}')
    if data['schema']==2:
        extras=data.get('extra_sources',{})
        required_extras={'ClockGate.sv'}
        if data.get('implementation')=='registered-execution-v1':
            required_extras.update(('ClockedExecute.sv','IterativeMultiply.sv'))
            if data.get('module_views'):
                raise ValueError('Registered candidate cannot substitute baseline module views')
        if set(extras)!=required_extras:
            raise ValueError('Fixed Chisel candidate requires exactly its declared profile extras')
        for name,digest in extras.items(): authenticated_path(directory,name,digest)
        for module,view in data.get('module_views',{}).items():
            if module=='ibex_top':
                raise ValueError('Top-level checks must use primary candidate sources, never a module view')
            if 'rtl/'+module+'.sv' not in data['source_sha256']:
                raise ValueError('Module view names an inactive/unknown module')
            if 'rtl/'+module+'.sv' not in view:
                raise ValueError('Module view must provide its own module')
            for source,item in view.items():
                if source not in data['source_sha256'] or set(item)!={'path','sha256'}:
                    raise ValueError('Unknown or malformed module view source')
                authenticated_path(directory,item['path'],item['sha256'])
    return {}


def sources(directory, lock, output, module='ibex_top'):
    directory = local(directory)
    if not directory.is_dir():
        raise ValueError('Candidate must be a source directory')
    result, receipts = [], []
    effective_parameters = parameters(directory)
    data=manifest(directory) or {}
    excluded=data.get('excluded',{})
    view={} if module=='ibex_top' else data.get('module_views',{}).get(module,{})
    for source in lock['sources']:
        if source in excluded:
            receipts.append(dict(source=source,status='excluded',reason=excluded[source]))
            continue
        reference = VENDOR/source
        if source.startswith('rtl/') and not source.endswith('_pkg.sv'):
            path = (authenticated_path(directory,view[source]['path'],view[source]['sha256'])
                    if source in view else source_path(directory,source))
            contents = path.read_bytes()
            receipts.append(dict(source=source, candidate=str(path.relative_to(ROOT)),
                                 sha256=hashlib.sha256(contents).hexdigest()))
            entry = adaptation_entry('unused_initializer')
            if source == entry['source'] and hashlib.sha256(contents).hexdigest() == entry['source_sha256']:
                old = entry['remove'].encode()
                if contents.count(old) != 1:
                    raise ValueError('Candidate initializer adaptation must match exactly once')
                path = output/'candidate-adapted/ibex_top.sv'
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents.replace(old,b'',1))
                receipts[-1]['adaptation'] = entry['id']
                receipts[-1]['adapted_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            # Immutable package constants and technology-neutral verification
            # primitives, never a fallback implementation of an Ibex module.
            path = reference
        result.append(str(path))
    for name,digest in data.get('extra_sources',{}).items():
        path=authenticated_path(directory,name,digest)
        result.append(str(path)); receipts.append(dict(source=name,candidate=str(path.relative_to(ROOT)),sha256=digest))
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
