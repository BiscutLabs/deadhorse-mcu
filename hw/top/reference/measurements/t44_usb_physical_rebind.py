"""Derive historical USB physical bindings after an exact current-context audit.

No timing result is recomputed or changed. Original receipts remain immutable;
the unchanged physical collector still audits all corners, graphs and faults.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / 'hw/ip/usb')]
from physical_evidence import collect


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(path):
    path = Path(path)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    path.relative_to(ROOT)
    return path


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def hashes(values):
    for p, h in values.items():
        assert sha(local(p)) == h, ('Changed dependency', p)


def run(context, emission, output):
    output.mkdir(parents=True, exist_ok=False)
    old = ROOT / 'build/plan05/usb-boundary08'
    result = dict(status='running', runner_sha256=sha(__file__),
        qualification='Historical standalone USB and separate routed bus fixture only; '
                      'exact current boundary identity; no fresh STA or whole-chip reset closure')
    try:
        current = read(context)
        assert current['status'] == 'pass'
        assert current['runner_sha256'] == sha(Path(__file__).with_name('t44_usb_context.py'))
        hashes(current['input_sha256'])
        hashes(current['production_source_sha256'])
        assert len(current['mapped_ports']) == 73 and len(current['negative_controls']) == 7
        original = old / 'bus-source-qualified01/result.json'
        source = read(original)
        for key in ('hdl_sha256', 'artifact_sha256', 'library_sha256'):
            hashes(source[key])
        metadata = dict(context=str(context), context_sha256=sha(context),
                        original=str(original), original_sha256=sha(original),
                        qualification=result['qualification'])
        source['source_sha256'] = {**current['production_source_sha256'], str(context): sha(context),
                                   **current['input_sha256']}
        source['current_mapped_ports'] = current['mapped_ports']
        source['current_context_binding'] = metadata
        binding = output / 'bus-source-qualified01/result.json'
        write(binding, source)
        # Fixture geometry, timing tables, input-CQ assumptions and measured
        # numbers stay byte-identical. Only receipt references are derived.
        copied = {}
        for folder in ('bus-physical01', 'bus-hold01'):
            shutil.copytree(old / folder, output / folder)
            for path in (output / folder).rglob('*'):
                if path.is_file():
                    relative = path.relative_to(output)
                    assert sha(path) == sha(old / relative)
                    copied[str(relative)] = sha(path)
        composition = read(output / 'bus-physical01/composition.json')
        hashes(composition['input_sha256'])
        keys = [p for p in composition['input_sha256'] if local(p) == original]
        assert len(keys) == 1
        del composition['input_sha256'][keys[0]]
        composition['input_sha256'][str(binding)] = sha(binding)
        composition['current_context_binding'] = metadata
        write(output / 'bus-physical01/composition.json', composition)
        hold = read(output / 'bus-hold01/result.json')
        assert hold['binding_sha256'] == sha(original)
        hashes(hold['artifact_sha256'])
        hold['binding_sha256'] = sha(binding)
        hold['current_context_binding'] = metadata
        write(output / 'bus-hold01/result.json', hold)
        # Archive only exact old source bytes. This authenticates historical
        # tooling, while the fresh context witness binds current USB behavior.
        archived_path = ROOT / 'build/t44/seal-source-archive01/result.json'
        archive = read(archived_path)
        seal_path = old / 'derived-internal-seal.json'
        assert archive['status'] == 'pass' and sha(seal_path) == archive['seal_sha256']
        seal = read(seal_path)
        records = {str(local(r['path'])): r for r in archive['rows']}
        replacements = {}
        for name, expected in list(seal['file_sha256'].items()):
            path = local(name)
            if sha(path) == expected:
                continue
            row = records[str(path)]
            assert expected == row['original_sha256'] == sha(local(row['archive']))
            original_bytes = subprocess.check_output(['git', 'show', row['commit'] + ':' + row['path']], cwd=ROOT)
            candidates = [original_bytes, original_bytes.replace(b'\r\n', b'\n'),
                          original_bytes.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')]
            assert any(hashlib.sha256(raw).hexdigest() == expected for raw in candidates)
            del seal['file_sha256'][name]
            seal['file_sha256'][str(local(row['archive']))] = expected
            replacements[name] = row
        assert len(replacements) == 11
        seal['historical_source_archives'] = replacements
        seal['current_context_binding'] = metadata
        seal['file_sha256'][str(context)] = sha(context)
        seal['file_sha256'][str(archived_path)] = sha(archived_path)
        write(output / 'derived-internal-seal.json', seal)
        manifest = read(old / 'physical-manifest.json')
        manifest.update(source=str(binding), hold=str(output / 'bus-hold01/result.json'),
                        bus=str(output / 'bus-physical01'), seal=str(output / 'derived-internal-seal.json'))
        write(output / 'physical-manifest.json', manifest)
        result.update(original_copy_sha256=copied, historical_source_archives=replacements,
                      current_context_binding=metadata)
        audit = collect(output / 'physical-manifest.json', emission, output / 'physical-audit')
        assert audit['status'] == 'pass'
        hashes(current['input_sha256'])
        hashes(current['production_source_sha256'])
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='failed', error=repr(error))
        raise
    finally:
        result['artifact_sha256'] = {str(p.relative_to(output)): sha(p) for p in output.rglob('*')
                                    if p.is_file() and p != output / 'result.json'}
        write(output / 'result.json', result)
    print('PASS historical physical evidence with exact current USB context; no fresh timing claim')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('context', 'emission', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    output = local(args.output)
    output.relative_to(ROOT / 'build')
    run(local(args.context), local(args.emission), output)
