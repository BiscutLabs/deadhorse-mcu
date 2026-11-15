"""Named-state inductive equivalence, with structural multiply congruence."""
import argparse
import json
from pathlib import Path
import re
import sys
import copy
import time

from common import CONFIG, ROOT, VENDOR, adapted_sources, inputs, local, output_dir, run, typed_parameter
from state_equiv import Mismatch, STATE, prepare


def elaborate(module, candidate, output, label, optimize=True):
    lock = inputs()
    sources = adapted_sources(output, lock)
    if candidate:
        replacement = local(candidate)
        if replacement.is_dir():
            from candidate import sources as candidate_sources
            sources = candidate_sources(replacement, lock, output)
        else:
            matches = [i for i, p in enumerate(sources) if Path(p).name == f'{module}.sv']
            if len(matches) != 1:
                raise ValueError(f'No unique reference source for {module}')
            sources[matches[0]] = str(replacement)
    script = output / (label + '.ys')
    parameters = CONFIG['parameters'] if module == 'ibex_top' else {}
    if candidate and module == 'ibex_top':
        from candidate import parameters as candidate_parameters
        parameters = candidate_parameters(candidate)
    script.write_text('read_slang --top ' + module + ' ' +
        ' '.join(f'-G{k}={typed_parameter(k,v)}' for k, v in parameters.items()) + ' ' +
        ' '.join('-D' + d for d in lock['defines']) + ' ' +
        ' '.join('-I' + str(VENDOR / p) for p in lock['include_dirs']) + ' ' +
        ' '.join(sources) + '\n' + (f'prep -top {module} -flatten\nmemory_map\nopt_clean\ncheck -assert\n' if optimize else '') +
        f'write_json {output}/{label}.json\n')
    run(['yosys', '-Q', '-T', '-s', script], output, label)
    return output / (label + '.json')


def compare(module, gold, candidate, output):
    started = time.monotonic()
    source_paths = (gold, candidate)
    mapping = json.loads((ROOT/'dv/core/module_map.json').read_text())['modules'].get(module, {})
    try:
        gold, candidate, evidence = prepare(gold, candidate, module, output, mapping)
    except Mismatch as exc:
        (output/'result.json').write_text(json.dumps(dict(status='failed', module=module,
            reason=str(exc), engine='state/interface correspondence', assumptions=[]), indent=2)+'\n')
        print(f'FAILED equivalence: {module}: {exc}', flush=True)
        return 'failed'
    script = output / 'compare.ys'
    script.write_text(f'read_json {gold}\nrename {module} gold\n' +
        f'read_json {candidate}\nrename {module} gate\n' +
        'miter -equiv -flatten gold gate miter\nhierarchy -top miter\n' +
        'opt_expr\nopt_merge\nopt_clean\nsat -verify -prove trigger 0 -show-inputs -show-outputs\n')
    result = run(['yosys', '-Q', '-T', '-s', script], output, 'compare', allowed=(0, 1))
    if result.returncode == 0 and 'SAT proof finished - no model found: SUCCESS!' in result.stdout:
        status = 'proved'
    elif result.returncode == 1 and 'proof did fail' in result.stdout:
        status = 'failed'
    else:
        raise ValueError('Inconclusive or broken SAT run')
    receipt = dict(status=status, module=module, engine='Yosys SAT',
                   elapsed_seconds=time.monotonic()-started,
                   kind='unbounded named-state induction' if evidence['state_elements'] else 'unbounded combinational',
                   assumptions=[], correspondence=evidence,
                   parameters=CONFIG['parameters'] if module=='ibex_top' else 'reference module defaults',
                   gold=str(source_paths[0].relative_to(ROOT)), candidate=str(source_paths[1].relative_to(ROOT)))
    (output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{status.upper()} equivalence: {module}', flush=True)
    return status


def negatives(module, gold, candidate, output):
    design = json.loads(candidate.read_text())
    mod = design['modules'][module]
    cases = {}
    if module == 'ibex_alu':
        bad = copy.deepcopy(design)
        bad['modules'][module]['ports']['result_o']['bits'][0] = '0'
        cases['output'] = bad
    else:
        bad = copy.deepcopy(design)
        target = bad['modules'][module]
        port_name = next((n for n,p in target['ports'].items() if p['direction']=='output' and p['bits']), None)
        if port_name is None:
            raise ValueError(f'{module}: no observable output for negative control')
        port = target['ports'][port_name]
        bit = max(b for w in target['netnames'].values() for b in w['bits'] if isinstance(b,int))+1
        target['cells']['__output_fault'] = dict(type='$not', parameters={'A_SIGNED':'0','A_WIDTH':'1','Y_WIDTH':'1'},
            attributes={},port_directions={'A':'input','Y':'output'},connections={'A':[port['bits'][0]],'Y':[bit]})
        port['bits'][0] = bit
        # JSON's port and same-named wire must agree; retain the original wire
        # under a separate name so this is a real driven output mutation.
        target['netnames']['__prior_output'] = copy.deepcopy(target['netnames'][port_name])
        target['netnames'][port_name]['bits'] = list(port['bits'])
        cases['output'] = bad
    reset = next((n for n,c in mod['cells'].items() if c['type']=='$aldff'
                  and all(b in ('0','1') for b in c['connections']['AD'])), None)
    if reset:
        bad = copy.deepcopy(design)
        bits = bad['modules'][module]['cells'][reset]['connections']['AD']
        bits[0] = '1' if bits[0]=='0' else '0'
        cases['reset-value'] = bad
    state = next((n for n,c in mod['cells'].items() if c['type'] in STATE), None)
    if state:
        bad = copy.deepcopy(design)
        target = bad['modules'][module]
        bit = max(b for w in target['netnames'].values() for b in w['bits'] if isinstance(b,int))+1
        con = target['cells'][state]['connections']
        target['cells']['__fault_not'] = dict(type='$not', parameters={'A_SIGNED':'0','A_WIDTH':'1','Y_WIDTH':'1'},
            attributes={},port_directions={'A':'input','Y':'output'},connections={'A':[con['D'][0]],'Y':[bit]})
        con['D'][0] = bit
        cases['next-state'] = bad
    unreset = next((n for n,c in mod['cells'].items() if c['type']=='$dff'), None)
    if unreset:
        bad = copy.deepcopy(design)
        cell = bad['modules'][module]['cells'][unreset]
        cell['type'] = '$aldff'
        cell['parameters']['ALOAD_POLARITY']='1'
        cell['port_directions'].update(AD='input', ALOAD='input')
        cell['connections'].update(AD=['0']*len(cell['connections']['Q']), ALOAD=['1'])
        cases['gained-reset'] = bad
    if module == 'ibex_multdiv_fast':
        bad = copy.deepcopy(design)
        target = bad['modules'][module]
        cell = next(c for c in target['cells'].values() if c['type']=='$mul')
        operand = cell['connections']['A']
        bit = max(b for w in target['netnames'].values() for b in w['bits'] if isinstance(b,int))+1
        target['cells']['__sign_fault'] = dict(type='$not', parameters={'A_SIGNED':'0','A_WIDTH':'1','Y_WIDTH':'1'},
            attributes={},port_directions={'A':'input','Y':'output'},connections={'A':[operand[-1]],'Y':[bit]})
        operand[-1] = bit
        cases['multiply-sign'] = bad
    for name, bad in cases.items():
        directory = output_dir(output/name)
        fault = directory/'fault.json'
        fault.write_text(json.dumps(bad))
        if compare(module, gold, fault, directory) != 'failed':
            raise ValueError(f'{module}: {name} fault escaped checker')
    return list(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', default='ibex_alu')
    parser.add_argument('--candidate')
    parser.add_argument('--self-check', action='store_true')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--all-modules', action='store_true')
    modes.add_argument('--top', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output / 'result.json').write_text('{"status":"blocked"}\n')
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    if not re.fullmatch(r'ibex_[a-z0-9_]+', args.module):
        raise ValueError('Invalid module name')
    modules = ([Path(p).stem for p in inputs()['sources'] if p.startswith('rtl/ibex_') and not p.endswith('_pkg.sv')]
               if args.all_modules else ['ibex_top'] if args.top else [args.module])
    results = {}
    for module in modules:
        directory = output_dir(output/module) if args.all_modules or args.top else output
        gold = elaborate(module, None, directory, 'gold')
        candidate = elaborate(module, args.candidate, directory, 'candidate')
        if compare(module, gold, candidate, directory) != 'proved':
            results[module] = json.loads((directory/'result.json').read_text())
            (output/'result.json').write_text(json.dumps(dict(status='failed',modules=results),indent=2)+'\n')
            return 1
        result = json.loads((directory/'result.json').read_text())
        if args.self_check:
            result['negative_controls'] = negatives(module, gold, candidate, output_dir(directory/'negative'))
        results[module] = result
        (output/'result.json').write_text(json.dumps(dict(status='running',modules=results),indent=2)+'\n')
    if args.self_check and args.all_modules:
        required = {'reset-value','gained-reset','next-state','multiply-sign'}
        observed = {n for r in results.values() for n in r['negative_controls']}
        if not required <= observed:
            raise ValueError(f'Missing required negative controls: {required-observed}')
    (output/'result.json').write_text(json.dumps(dict(status='proved',modules=results),indent=2)+'\n')
    print('PASS equivalence: all selected modules proved; requested negative controls rejected', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'BLOCKED equivalence: {exc}', file=sys.stderr)
        sys.exit(2)
