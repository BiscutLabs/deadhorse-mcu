"""Compare one named combinational module using an exhaustive SAT miter."""
import argparse
import json
from pathlib import Path
import re
import sys

from common import ROOT, VENDOR, adapted_sources, inputs, local, output_dir, run


def elaborate(module, candidate, output, label):
    lock = inputs()
    sources = adapted_sources(output, lock)
    if candidate:
        replacement = local(candidate)
        original = str(VENDOR / f'rtl/{module}.sv')
        if original not in sources:
            raise ValueError(f'No unique reference source for {module}')
        sources[sources.index(original)] = str(replacement)
    script = output / (label + '.ys')
    script.write_text('read_slang --top ' + module + ' ' +
        ' '.join('-D' + d for d in lock['defines']) + ' ' +
        ' '.join('-I' + str(VENDOR / p) for p in lock['include_dirs']) + ' ' +
        ' '.join(sources) + '\n' + f'prep -top {module} -flatten\n' +
        f'write_json {output}/{label}.json\n')
    run(['yosys', '-Q', '-T', '-s', script], output, label)
    return output / (label + '.json')


def compare(module, gold, candidate, output):
    for path in (gold, candidate):
        design = json.loads(path.read_text())['modules'][module]
        if any(re.search('dff|latch|mem', c['type'], re.I) for c in design['cells'].values()):
            raise ValueError('Sequential equivalence requires a reset/state contract; not a combinational proof')
    script = output / 'compare.ys'
    script.write_text(f'read_json {gold}\nrename {module} gold\n' +
        f'read_json {candidate}\nrename {module} gate\n' +
        'miter -equiv -flatten gold gate miter\nhierarchy -top miter\n' +
        'opt_clean\nsat -verify -prove trigger 0 -show-inputs -show-outputs\n')
    result = run(['yosys', '-Q', '-T', '-s', script], output, 'compare', allowed=(0, 1))
    if result.returncode == 0 and 'SAT proof finished - no model found: SUCCESS!' in result.stdout:
        status = 'proved'
    elif result.returncode == 1 and 'proof did fail' in result.stdout:
        status = 'failed'
    else:
        raise ValueError('Inconclusive or broken SAT run')
    receipt = dict(status=status, module=module, engine='Yosys SAT',
                   elapsed_seconds=result.elapsed_seconds,
                   kind='unbounded combinational', assumptions=[],
                   gold=str(gold.relative_to(ROOT)), candidate=str(candidate.relative_to(ROOT)))
    (output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{status.upper()} equivalence: {module}', flush=True)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', default='ibex_alu')
    parser.add_argument('--candidate')
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output / 'result.json').write_text('{"status":"blocked"}\n')
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    if not re.fullmatch(r'ibex_[a-z0-9_]+', args.module):
        raise ValueError('Invalid module name')
    gold = elaborate(args.module, None, output, 'gold')
    candidate = elaborate(args.module, args.candidate, output, 'candidate')
    if compare(args.module, gold, candidate, output) != 'proved':
        return 1
    if args.self_check:
        bad = json.loads(candidate.read_text())
        bad['modules'][args.module]['ports']['result_o']['bits'][0] = '0'
        fault = output / 'fault.json'
        fault.write_text(json.dumps(bad))
        negative = output_dir(output / 'negative')
        if compare(args.module, gold, fault, negative) != 'failed':
            raise ValueError('Output corruption escaped equivalence checker')
        print('PASS equivalence self-check: reference proved; output fault rejected', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'BLOCKED equivalence: {exc}', file=sys.stderr)
        sys.exit(2)
