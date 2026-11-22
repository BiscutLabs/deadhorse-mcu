"""Exact combinational equivalence of an isolated production MAC mapping.

No product cut, state, assumptions, input restrictions, or undefined-bit waiver
is permitted. The producer binds extraction to production; this checker binds
the complete isolated function before and after arithmetic-tree lowering.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
TOP = 'T20Mac'
CAP = 600
COMBINATIONAL = {
    '$macc', '$macc_v2', '$mul', '$add', '$sub', '$alu', '$fa', '$lcu',
    '$and', '$or', '$xor', '$not', '$pos', '$mux', '$reduce_or',
    '$_AND_', '$_OR_', '$_XOR_', '$_NOT_', '$_MUX_',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(value):
    value = str(value)
    if value.startswith('/work/'):
        value = value[6:]
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    if re.search(r'[\s;{}"$]', str(path)):
        raise ValueError('Unsupported path characters')
    return path


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def command(args, output, name, timeout=CAP):
    """Stream logs, preserve timeout evidence, and never interpret exit alone."""
    start = time.monotonic()
    log = output / (name + '.log')
    with log.open('w') as stream:
        try:
            result = subprocess.run([str(a) for a in args], cwd=ROOT,
                                    stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout)
            row = dict(command=[str(a) for a in args], returncode=result.returncode,
                       elapsed_seconds=time.monotonic() - start)
        except subprocess.TimeoutExpired:
            row = dict(command=[str(a) for a in args], status='timeout',
                       elapsed_seconds=time.monotonic() - start)
    with (output / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(row) + '\n')
    return row, log.read_text(errors='replace')


def validate(design):
    if set(design.get('modules', {})) != {TOP}:
        raise ValueError('Expected exactly the isolated T20Mac module')
    module = design['modules'][TOP]
    if module.get('memories') or module.get('processes'):
        raise ValueError('State/processes are forbidden')
    if module.get('attributes', {}).get('blackbox') not in (None, '0', 0):
        raise ValueError('Blackbox is forbidden')
    drivers, dependencies, inputs, outputs = {}, {}, set(), []
    for name, port in module['ports'].items():
        if port['direction'] not in ('input', 'output') or not port['bits']:
            raise ValueError('Bad interface port: ' + name)
        if port['direction'] == 'input':
            for bit in port['bits']:
                if not isinstance(bit, int) or bit in drivers:
                    raise ValueError('Input constant or ambiguous input alias')
                drivers[bit] = ('input', name)
                inputs.add(bit)
        else:
            outputs.extend(port['bits'])
    if not inputs or not outputs:
        raise ValueError('Empty function interface')
    for wire in module['netnames'].values():
        if 'init' in wire.get('attributes', {}):
            raise ValueError('Unexpected initialization')
    for name, cell in module['cells'].items():
        if cell['type'] not in COMBINATIONAL:
            raise ValueError('Unsupported or noncombinational cell: ' + cell['type'])
        if set(cell['connections']) != set(cell['port_directions']):
            raise ValueError('Missing cell pin directions')
        used = []
        for pin, bits in cell['connections'].items():
            if cell['port_directions'][pin] not in ('input', 'output'):
                raise ValueError('Invalid cell direction')
            if any(not isinstance(b, int) and b not in ('0', '1') for b in bits):
                raise ValueError('Undefined constants are forbidden')
            if cell['port_directions'][pin] == 'input':
                used.extend(bits)
        for pin, bits in cell['connections'].items():
            if cell['port_directions'][pin] == 'output':
                for bit in bits:
                    if not isinstance(bit, int) or bit in drivers:
                        raise ValueError('Ambiguous/constant cell output')
                    drivers[bit] = (name, pin)
                    dependencies[bit] = used
    visited, active = set(), set()
    def visit(bit):
        if bit in ('0', '1'):
            return
        if bit not in drivers:
            raise ValueError('Undriven signal: ' + str(bit))
        if bit in active:
            raise ValueError('Combinational cycle')
        if bit in visited:
            return
        active.add(bit)
        for other in dependencies.get(bit, []):
            visit(other)
        active.remove(bit)
        visited.add(bit)
    # Check all cells, including unused cones; no hidden unconstrained input.
    for bit in list(drivers) + outputs:
        visit(bit)
    return dict(cells=len(module['cells']), sequential_bits=0, memory_bits=0,
                input_bits=len(inputs), output_bits=len(outputs),
                cell_types={kind: sum(c['type'] == kind for c in module['cells'].values())
                            for kind in sorted({c['type'] for c in module['cells'].values()})})


def interface(module):
    return {n: {k: p.get(k, 0) for k in ('direction', 'offset', 'upto', 'signed')} |
               {'width': len(p['bits'])} for n, p in module['ports'].items()}


def authenticate(producer, before, after):
    """Producer must bind exact extraction and its complete source inventory."""
    receipt = json.loads(producer.read_text())
    if receipt.get('status') != 'pass_isolated_mac_variants':
        raise ValueError('Producer extraction/variants have not passed')
    tracked = {producer}
    sources = receipt.get('sources', {})
    artifacts = receipt.get('artifacts', {})
    if not sources or not artifacts:
        raise ValueError('Missing producer inventories')
    for name, expected in sources.items():
        path = local(name)
        if digest(path) != expected:
            raise ValueError('Stale producer source: ' + name)
        tracked.add(path)
    for name, expected in artifacts.items():
        path = (producer.parent / name).resolve()
        path.relative_to(producer.parent)
        if digest(path) != expected:
            raise ValueError('Stale producer artifact: ' + name)
        tracked.add(path)
    for path in (before, after):
        if path not in tracked:
            raise ValueError('Compared model absent from authenticated producer')
    return tracked


def prepare_reference(before, output):
    target = output / 'reference.json'
    script = output / 'reference.ys'
    script.write_text(f'read_json {before}\nhierarchy -check -top {TOP}\n'
                      f'maccmap -unmap\nopt_clean\ncheck -assert\nwrite_json {target}\n')
    row, log = command(['yosys', '-Q', '-T', '-s', script], output, 'reference')
    if row.get('returncode') != 0:
        raise ValueError('Reference arithmetic normalization failed')
    design = json.loads(target.read_text())
    validate(design)
    mults = [c for c in design['modules'][TOP]['cells'].values() if c['type'] == '$mul']
    if len(mults) != 1:
        raise ValueError('Expected exactly one real product')
    parameters = mults[0]['parameters']
    if any(int(parameters[k], 2) != v for k, v in
           dict(A_WIDTH=17, B_WIDTH=17, A_SIGNED=1, B_SIGNED=1).items()):
        raise ValueError('Not the production signed17x17 multiplier')
    return target


def carry_fault(after, output):
    design = json.loads(after.read_text())
    original = copy.deepcopy(design)
    module = design['modules'][TOP]
    candidates = []
    for name, cell in module['cells'].items():
        if cell['type'] == '$fa':
            for bit in cell['connections']['X']:
                loads = [(cn, pin, i) for cn, c in module['cells'].items()
                         for pin, bits in c['connections'].items()
                         if c['port_directions'][pin] == 'input'
                         for i, value in enumerate(bits) if value == bit]
                if loads:
                    candidates.append((name, bit, loads))
    if not candidates:
        raise ValueError('Missing live compressor carry for actual fault')
    name, bit, loads = candidates[len(candidates) // 2]
    all_bits = [b for c in module['cells'].values() for bits in c['connections'].values()
                for b in bits if isinstance(b, int)]
    all_bits += [b for table in ('ports', 'netnames') for w in module[table].values()
                 for b in w['bits'] if isinstance(b, int)]
    fresh = max(all_bits) + 1
    for cn, pin, index in loads:
        module['cells'][cn]['connections'][pin][index] = fresh
    fault_name = '__mapping_carry_fault'
    if fault_name in module['cells']:
        raise ValueError('Reserved fault cell already exists')
    module['cells'][fault_name] = dict(type='$_NOT_', parameters={}, attributes={},
        port_directions=dict(A='input', Y='output'), connections=dict(A=[bit], Y=[fresh]))
    validate(design)
    restored = copy.deepcopy(design)
    restored_module = restored['modules'][TOP]
    del restored_module['cells'][fault_name]
    for cn, pin, index in loads:
        restored_module['cells'][cn]['connections'][pin][index] = bit
    if restored != original:
        raise ValueError('Carry mutation did not restore exact original graph')
    path = output / 'carry-fault.json'
    write_json(path, design)
    return path, dict(driver=[name, 'X'], carry_bit=bit, replacement_bit=fresh, loads=loads)


def sign_fault(reference, output):
    design = json.loads(reference.read_text())
    matches = [(n, c) for n, c in design['modules'][TOP]['cells'].items() if c['type'] == '$mul']
    if len(matches) != 1:
        raise ValueError('No unique real multiplier for signedness fault')
    name, cell = matches[0]
    for key in ('A_SIGNED', 'B_SIGNED'):
        if int(cell['parameters'][key], 2) != 1:
            raise ValueError('Signedness fault requires signed production product')
        cell['parameters'][key] = '0'
    validate(design)
    path = output / 'sign-fault.json'
    write_json(path, design)
    return path, dict(cell=name, changed_parameters=['A_SIGNED', 'B_SIGNED'])


def accumulator_fault(reference, output):
    design = json.loads(reference.read_text())
    module = design['modules'][TOP]
    products = [c for c in module['cells'].values() if c['type'] == '$mul']
    if len(products) != 1:
        raise ValueError('Accumulator fault needs one real product')
    product_bits = set(products[0]['connections']['Y'])
    input_bits = {b for p in module['ports'].values() if p['direction'] == 'input'
                  for b in p['bits']}
    matches = []
    for name, cell in module['cells'].items():
        if cell['type'] == '$add':
            for product_pin, accumulator_pin in (('A', 'B'), ('B', 'A')):
                acc = cell['connections'][accumulator_pin]
                if (product_bits.intersection(cell['connections'][product_pin]) and
                    input_bits.intersection(acc) and set(acc) <= input_bits | {'0', '1'}):
                    matches.append((name, accumulator_pin))
    if len(matches) != 1:
        raise ValueError('No unique actual accumulator connection')
    name, pin = matches[0]
    old = module['cells'][name]['connections'][pin]
    module['cells'][name]['connections'][pin] = ['0'] * len(old)
    validate(design)
    path = output / 'accumulator-fault.json'
    write_json(path, design)
    return path, dict(cell=name, pin=pin, old_connection=old, replacement='zero')


def prove(before, after, output):
    output.mkdir()
    script = output / 'compare.ys'
    script.write_text(f'read_json {before}\nrename {TOP} gold\n'
        f'read_json {after}\nrename {TOP} gate\n'
        'miter -equiv -flatten -make_outputs gold gate miter\n'
        'hierarchy -check -top miter\ntechmap\nopt -full\ncheck -assert\nstat\n'
        f'write_json {output}/prepared.json\n'
        f'sat -timeout {CAP} -verify -prove trigger 0 -show-inputs -show-outputs '
        f'-dump_json {output}/counterexample.json\n')
    row, log = command(['yosys', '-Q', '-T', '-s', script], output, 'compare')
    if row.get('returncode') == 0 and 'SAT proof finished - no model found: SUCCESS!' in log:
        status = 'proved'
    elif row.get('returncode') == 1 and 'proof did fail' in log and (output / 'counterexample.json').is_file():
        status = 'counterexample'
    elif row.get('status') == 'timeout' or 'timeout' in log.lower():
        status = 'unresolved'
    else:
        status = 'error'
    execution = dict(row)
    if 'status' in execution:
        execution['execution_status'] = execution.pop('status')
    result = dict(status=status, kind='exact combinational equivalence',
                  engine='Yosys SAT', assumptions=[], abstracted_signals=[],
                  before_sha256=digest(before), after_sha256=digest(after), **execution)
    write_json(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('before', 'after', 'producer', 'output'):
        parser.add_argument('--' + arg, required=True)
    args = parser.parse_args()
    before, after, producer, output = (local(getattr(args, a)) for a in
                                      ('before', 'after', 'producer', 'output'))
    for path in (before, after, producer, output):
        path.relative_to(ROOT / 'build')
    output.mkdir(parents=True, exist_ok=False)
    result = dict(status='running', scope='Exact isolated fused MAC mapping only',
                  assumptions=[], abstracted_signals=[], timeout_seconds_per_tool=CAP,
                  rung='1: direct exact bit-level SAT',
                  not_proved=['whole SoC implementation equivalence', 'timing', 'physical signoff'])
    write_json(output / 'result.json', result)
    tracked = set()
    try:
        tracked = authenticate(producer, before, after)
        tracked.update((Path(__file__).resolve(), ROOT / 'tools/env/lock.json'))
        initial = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(tracked)}
        result['input_sha256'] = initial
        result['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        row, version = command(['yosys', '-V'], output, 'version')
        if row.get('returncode') != 0 or 'e419c4eef' not in version:
            raise ValueError('Not the reviewed pinned Yosys version')
        result['tool'] = version.strip()
        designs = [json.loads(p.read_text()) for p in (before, after)]
        result['models'] = {role: validate(d) for role, d in zip(('before', 'after'), designs)}
        before_cells = list(designs[0]['modules'][TOP]['cells'].values())
        after_types = {c['type'] for c in designs[1]['modules'][TOP]['cells'].values()}
        if len(before_cells) != 1 or before_cells[0]['type'] not in ('$macc', '$macc_v2'):
            raise ValueError('Before model must contain exactly one fused MAC')
        if '$fa' not in after_types or after_types & {'$macc', '$macc_v2', '$mul'}:
            raise ValueError('After model must contain the expanded compressor arithmetic')
        if interface(designs[0]['modules'][TOP]) != interface(designs[1]['modules'][TOP]):
            raise ValueError('Function interfaces differ')
        result['interface'] = interface(designs[0]['modules'][TOP])
        reference = prepare_reference(before, output)
        write_json(output / 'result.json', result)
        result['positive'] = prove(reference, after, output / 'positive')
        write_json(output / 'result.json', result)
        # Controls retain the complete real arithmetic; never symbolic-product mocks.
        carry, carry_detail = carry_fault(after, output)
        signed, sign_detail = sign_fault(reference, output)
        accumulator, accumulator_detail = accumulator_fault(reference, output)
        result['negative_controls'] = {
            'carry': dict(proof=prove(reference, carry, output / 'carry-negative'), mutation=carry_detail),
            'signedness': dict(proof=prove(reference, signed, output / 'sign-negative'), mutation=sign_detail),
            'accumulator': dict(proof=prove(reference, accumulator, output / 'accumulator-negative'),
                                mutation=accumulator_detail)}
        if {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(tracked)} != initial:
            raise ValueError('Bound inputs changed during proof')
        negatives = all(v['proof']['status'] == 'counterexample' for v in result['negative_controls'].values())
        if result['positive']['status'] == 'proved' and negatives:
            result['status'] = 'proved'
        elif result['positive']['status'] in ('counterexample', 'error'):
            result['status'] = 'failed'
        else:
            result['status'] = 'unresolved'
    except Exception as error:
        result.update(status='error', error=str(error))
    finally:
        result['artifacts'] = {p.relative_to(output).as_posix(): digest(p)
                               for p in sorted(output.rglob('*'))
                               if p.is_file() and p != output / 'result.json'}
        write_json(output / 'result.json', result)
    print(result['status'].upper() + ': exact MAC mapping; no product abstraction', flush=True)
    return 0 if result['status'] == 'proved' else 1


if __name__ == '__main__':
    sys.exit(main())
