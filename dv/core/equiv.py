"""Named-state inductive equivalence, with structural multiply congruence."""
import argparse
import json
from pathlib import Path
import re
import sys
import copy
import time
import hashlib

from common import CONFIG, ROOT, VENDOR, adapted_sources, inputs, local, output_dir, run, typed_parameter
from state_equiv import Mismatch, STATE, prepare
from csr_priority import analysis_sources


def validate_child_usage(design, top, replacements):
    """Requested fixed-name Chisel children must exist in the compared hierarchy."""
    modules = design['modules']
    pending, reachable = [top], set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(c['type'] for c in modules[name]['cells'].values() if c['type'] in modules)
    # slang specializes hierarchy names as <declaration>$<instance path>.
    active_declarations = {name.split('$', 1)[0] for name in reachable - {top}}
    inactive = set(replacements) - active_declarations
    if inactive:
        raise ValueError(f'Incremental replacements absent from parent hierarchy: {sorted(inactive)}')


def elaborate(module, candidate, output, label, optimize=True, reference_parameters=None,
              replacements=None):
    if replacements and module == 'ibex_top':
        raise ValueError('Full candidate checks require the production manifest, not replacements')
    lock = inputs()
    sources = adapted_sources(output, lock)
    if candidate:
        replacement = local(candidate)
        if replacement.is_dir():
            from candidate import sources as candidate_sources
            sources = candidate_sources(replacement, lock, output, module=module)
        else:
            matches = [i for i, p in enumerate(sources) if Path(p).name == f'{module}.sv']
            if len(matches) != 1:
                raise ValueError(f'No unique reference source for {module}')
            sources[matches[0]] = str(replacement)
    if replacements:
        if not candidate or local(candidate).is_dir():
            raise ValueError('Incremental replacements require a single-file parent candidate')
        for name, path in replacements.items():
            if name == module or not re.fullmatch(r'ibex_[a-z0-9_]+', name):
                raise ValueError('Invalid incremental child replacement')
            replacement = local(path)
            matches = [i for i, p in enumerate(sources) if Path(p).name == f'{name}.sv']
            if len(matches) != 1 or not replacement.is_file():
                raise ValueError(f'No unique reference source or candidate file for {name}')
            sources[matches[0]] = str(replacement)
    script = output / (label + '.ys')
    parameters = CONFIG['parameters'] if module == 'ibex_top' else {}
    if reference_parameters is not None:
        if candidate or module == 'ibex_top':
            raise ValueError('Explicit leaf parameters apply only to reference elaboration')
        parameters = reference_parameters
    if candidate and module == 'ibex_top':
        from candidate import parameters as candidate_parameters
        parameters = candidate_parameters(candidate)
    sources, normalizations = analysis_sources(sources, output, label, module)
    hierarchy_json = output / (label + '-hierarchy.json')
    script.write_text('read_slang ' + ('--keep-hierarchy ' if replacements else '') + '--top ' + module + ' ' +
        ' '.join(f'-G{k}={typed_parameter(k,v)}' for k, v in parameters.items()) + ' ' +
        ' '.join('-D' + d for d in lock['defines']) + ' ' +
        ' '.join('-I' + str(VENDOR / p) for p in lock['include_dirs']) + ' ' +
        ' '.join(sources) + '\n' + (f'write_json {hierarchy_json}\n' if replacements else '') +
        (f'prep -top {module} -flatten\nmemory_map\nopt_clean\ncheck -assert\n' if optimize else '') +
        f'write_json {output}/{label}.json\n')
    run(['yosys', '-Q', '-T', '-s', script], output, label)
    netlist = output / (label + '.json')
    effective_parameters = parameters or ('fixed candidate emission' if candidate else 'reference module defaults')
    netlist.with_suffix('.elaboration.json').write_text(json.dumps(dict(
        module=module, parameters=effective_parameters, normalizations=normalizations,
        netlist_sha256=hashlib.sha256(netlist.read_bytes()).hexdigest(),
        source_sha256={str(Path(p).relative_to(ROOT)): hashlib.sha256(Path(p).read_bytes()).hexdigest()
                       for p in sources}), indent=2)+'\n')
    if replacements:
        validate_child_usage(json.loads(hierarchy_json.read_text()), module, replacements)
    (output / (label + '.replacements.json')).write_text(json.dumps({
        name: {'source': str(local(path).relative_to(ROOT)),
               'sha256': hashlib.sha256(local(path).read_bytes()).hexdigest(),
               'scope': 'incremental verification only; not a production candidate'}
        for name, path in (replacements or {}).items()}, indent=2) + '\n')
    return output / (label + '.json')


def compare(module, gold, candidate, output):
    started = time.monotonic()
    source_paths = (gold, candidate)
    elaborations = {}
    for role, path in zip(('gold','candidate'),source_paths):
        sidecar = path.with_suffix('.elaboration.json')
        if sidecar.is_file():
            metadata = json.loads(sidecar.read_text())
            if metadata['netlist_sha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError('Elaboration receipt does not match netlist')
            elaborations[role] = metadata
    mapping = json.loads((ROOT/'dv/core/module_map.json').read_text())['modules'].get(module, {})
    try:
        gold, candidate, evidence = prepare(gold, candidate, module, output, mapping)
    except Mismatch as exc:
        (output/'result.json').write_text(json.dumps(dict(status='failed', module=module,
            reason=str(exc), engine='state/interface correspondence', assumptions=[],
            elaborations=elaborations), indent=2)+'\n')
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
                   parameters=elaborations.get('gold',{}).get('parameters',
                       CONFIG['parameters'] if module=='ibex_top' else 'not recorded by model producer'),
                   elaborations=elaborations,
                   gold=str(source_paths[0].relative_to(ROOT)), candidate=str(source_paths[1].relative_to(ROOT)))
    replacement_receipt = source_paths[1].with_suffix('.replacements.json')
    if replacement_receipt.is_file():
        receipt['incremental_replacements'] = json.loads(replacement_receipt.read_text())
    (output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{status.upper()} equivalence: {module}', flush=True)
    return status


def negatives(module, gold, candidate, output):
    design = json.loads(candidate.read_text())
    mod = design['modules'][module]
    cases = {}
    bad = copy.deepcopy(design)
    target = bad['modules'][module]
    port_name = 'result_o' if module == 'ibex_alu' else next(
        (n for n,p in target['ports'].items() if p['direction']=='output' and p['bits']), None)
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
        products=[c for c in target['cells'].values() if c['type']=='$mul']
        bit = max(b for w in target['netnames'].values() for b in w['bits'] if isinstance(b,int))+1
        if products:
            operand=products[0]['connections']['A']; original=operand[-1]; operand[-1]=bit
            fault_name='multiply-sign'
        else:
            # Registered execution specializes this child to division only;
            # its unused multiplier disappears. Corrupt a live divide sign.
            original=target['ports']['signed_mode_i']['bits'][0]
            for cell in target['cells'].values():
                for port,direction in cell['port_directions'].items():
                    if direction=='input':
                        cell['connections'][port]=[bit if value==original else value for value in cell['connections'][port]]
            fault_name='division-sign'
        target['cells']['__sign_fault'] = dict(type='$not', parameters={'A_SIGNED':'0','A_WIDTH':'1','Y_WIDTH':'1'},
            attributes={},port_directions={'A':'input','Y':'output'},connections={'A':[original],'Y':[bit]})
        cases[fault_name] = bad
    for name, bad in cases.items():
        directory = output_dir(output/name)
        fault = directory/'fault.json'
        fault.write_text(json.dumps(bad))
        origin = candidate.with_suffix('.elaboration.json')
        if origin.is_file():
            metadata = json.loads(origin.read_text())
            metadata.update(negative_control=name,
                unmodified_netlist_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
                netlist_sha256=hashlib.sha256(fault.read_bytes()).hexdigest())
            fault.with_suffix('.elaboration.json').write_text(json.dumps(metadata,indent=2)+'\n')
        if compare(module, gold, fault, directory) != 'failed':
            raise ValueError(f'{module}: {name} fault escaped checker')
    return list(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', default='ibex_alu')
    parser.add_argument('--candidate')
    parser.add_argument('--replace', action='append', default=[], metavar='MODULE=PATH',
                        help='Replace a child while comparing a single-file parent candidate')
    parser.add_argument('--self-check', action='store_true')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--all-modules', action='store_true')
    modes.add_argument('--top', action='store_true')
    modes.add_argument('--unchanged-since', metavar='TAG')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output / 'result.json').write_text('{"status":"blocked"}\n')
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    if args.unchanged_since:
        from unchanged import check
        return check(args.unchanged_since,args.candidate,output)
    if not re.fullmatch(r'ibex_[a-z0-9_]+', args.module):
        raise ValueError('Invalid module name')
    replacements = {}
    for value in args.replace:
        name, separator, path = value.partition('=')
        if not separator or name in replacements or not path:
            raise ValueError('Invalid or duplicate incremental replacement')
        replacements[name] = path
    if replacements and (args.top or args.all_modules or args.module == 'ibex_top'):
        raise ValueError('Full candidate checks require the production manifest, not replacements')
    modules = ([Path(p).stem for p in inputs()['sources'] if p.startswith('rtl/ibex_') and not p.endswith('_pkg.sv')]
               if args.all_modules else ['ibex_top'] if args.top else [args.module])
    candidate_manifest={}
    if args.candidate and local(args.candidate).is_dir():
        from candidate import manifest, parameters as validate_parameters
        validate_parameters(args.candidate)
        candidate_manifest=manifest(args.candidate) or {}
    results = {}
    for module in modules:
        exclusion=candidate_manifest.get('excluded',{}).get('rtl/'+module+'.sv')
        if exclusion:
            results[module]=dict(status='excluded',reason=exclusion,configuration=CONFIG['parameters'])
            continue
        directory = output_dir(output/module) if args.all_modules or args.top else output
        reference_parameters=None
        if candidate_manifest.get('schema')==2 and module in ('ibex_core','ibex_cs_registers'):
            reference_parameters={'DbgTriggerEn':CONFIG['parameters']['DbgTriggerEn'],
                                  'MHPMCounterNum':CONFIG['parameters']['MHPMCounterNum']}
        gold = elaborate(module, None, directory, 'gold',reference_parameters=reference_parameters)
        candidate = elaborate(module, args.candidate, directory, 'candidate', replacements=replacements)
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
        observed = {n for r in results.values() for n in r.get('negative_controls',[])}
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
