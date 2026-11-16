"""Prove exact whole-top equivalence between authenticated candidate revisions."""
import argparse
import hashlib
import json
import sys

from candidate import manifest, parameters
from common import ROOT, local, output_dir
from equiv import compare, elaborate, negatives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    revisions = {name: local(getattr(args, name)) for name in ('before', 'after')}
    manifests = {}
    for name, path in revisions.items():
        parameters(path)  # Authenticate the complete fixed source inventory.
        manifests[name] = manifest(path)
        if not manifests[name] or manifests[name].get('schema') != 2:
            raise ValueError('Revision comparison requires authenticated schema-2 candidates')
    for field in ('parameters', 'implementation', 'excluded'):
        if manifests['before'].get(field) != manifests['after'].get(field):
            raise ValueError('Revision configurations differ: ' + field)
    output = output_dir(args.output)
    netlists = {name: elaborate('ibex_top', path, output_dir(output/name), name)
                for name, path in revisions.items()}
    receipt_path = output/'result.json'
    try:
        if compare('ibex_top', netlists['before'], netlists['after'], output) != 'proved':
            return 1
        faults = negatives('ibex_top', netlists['before'], netlists['after'],
                           output_dir(output/'negative'))
    except Exception as exc:
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
        receipt.update(status='failed', error=str(exc))
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
        raise
    receipt = json.loads(receipt_path.read_text())
    receipt.update(
        scope='exact cycle/state/output equivalence between candidate revisions; not a new ISA proof',
        negative_controls=faults,
        revisions={name: dict(path=str(path.relative_to(ROOT)),
                             manifest_sha256=hashlib.sha256((path/'candidate.json').read_bytes()).hexdigest())
                   for name, path in revisions.items()})
    receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS revision equivalence: whole top, no added assumptions, all fault controls rejected')
    return 0


if __name__ == '__main__':
    sys.exit(main())
