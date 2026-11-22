"""Prove a shared-MAC carry revision against archived production emissions.

No protocol assumptions or state exclusions are added. The existing checker
proves all named transitions and output functions, including multiplier operand
equality before sharing a symbolic product. Unchanged emitted parents establish
composition into the SoC; a separate whole-core revision proof is also required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'dv/core'))
from common import local, output_dir, run
from equiv import compare, elaborate, negatives
from state_equiv import STATE

MODULE = 'ibex_multdiv_fast'
LEAF = MODULE + '.sv'
SOURCE = 'hw/ip/perf_core/src/main/scala/deadhorse/perf_core/IbexMultdivFast.scala'
GATE = ROOT / 'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {str(p.relative_to(directory)): digest(p)
            for p in sorted(directory.rglob('*.sv'))}


def same_parents(before, after):
    a, b = inventory(before), inventory(after)
    if not a or set(a) != set(b):
        raise ValueError('Emitted module inventories differ')
    changed = sorted(n for n in a if a[n] != b[n])
    if changed != [LEAF]:
        raise ValueError('Expected only the shared MAC leaf to change: ' + repr(changed))
    return dict(before=a, after=b, changed=changed,
                unchanged_parent_files=len(a) - 1)


def authenticate_soc(directory, before_source=None):
    """Bind to the existing emitter receipt, including its production sources."""
    receipt_path = directory.parent / 'result.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('status') != 'pass_boundary_projection':
        raise ValueError('SoC emission receipt is not complete')
    expected = receipt['sources']
    files = list(directory.rglob('*.sv'))
    for path in files:
        bound = expected.get(path.relative_to(ROOT).as_posix())
        if bound is None:
            bound = receipt['artifact_sha256'].get(path.relative_to(directory.parent).as_posix())
        if bound != digest(path):
            raise ValueError('SoC emitted source does not match receipt: ' + str(path))
    production = receipt['production_source_sha256']
    if SOURCE not in production:
        raise ValueError('SoC receipt omits MAC production source')
    for name, value in production.items():
        path = before_source if name == SOURCE and before_source else local(name)
        if digest(path) != value:
            raise ValueError('SoC production source does not match receipt: ' + name)
    return receipt_path, production


def carry_fault(candidate, output):
    """Invert the actual low-nibble carry at every input load, not an oracle."""
    design = json.loads(candidate.read_text())
    module = design['modules'][MODULE]
    alias = 'mac_res_signed_sums_carry'
    bits = module['netnames'][alias]['bits']
    if len(bits) != 1 or not isinstance(bits[0], int):
        raise ValueError('Missing scalar emitted MAC carry')
    original = bits[0]
    drivers = [(name, pin) for name, cell in module['cells'].items()
               for pin, direction in cell['port_directions'].items()
               if direction == 'output' and original in cell['connections'][pin]]
    if len(drivers) != 1 or module['cells'][drivers[0][0]]['type'] != '$add':
        raise ValueError('Carry must have one actual adder driver')
    all_bits = [b for table in (module['ports'], module['netnames'])
                for wire in table.values() for b in wire['bits'] if isinstance(b, int)]
    all_bits += [b for cell in module['cells'].values()
                 for values in cell['connections'].values() for b in values if isinstance(b, int)]
    fresh = max(all_bits) + 1
    loads = []
    for name, cell in module['cells'].items():
        for pin, direction in cell['port_directions'].items():
            if direction == 'input' and original in cell['connections'][pin]:
                loads.append([name, pin])
                cell['connections'][pin] = [fresh if b == original else b
                                            for b in cell['connections'][pin]]
    if not loads:
        raise ValueError('Carry fault has no actual loads')
    module['cells']['__mac_carry_fault'] = dict(type='$not',
        parameters=dict(A_SIGNED='0', A_WIDTH='1', Y_WIDTH='1'), attributes={},
        port_directions=dict(A='input', Y='output'), connections=dict(A=[original], Y=[fresh]))
    fault = output / 'fault.json'
    fault.write_text(json.dumps(design) + '\n')
    metadata = json.loads(candidate.with_suffix('.elaboration.json').read_text())
    metadata.update(negative_control='actual-low-nibble-carry',
                    unmodified_netlist_sha256=digest(candidate), netlist_sha256=digest(fault))
    fault.with_suffix('.elaboration.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return fault, dict(alias=alias, driver=drivers[0], inverted_loads=loads,
                       original_bit=original, replacement_bit=fresh)


def elaborate_top(directory, output, role):
    """Use the complete actual top emission plus its pinned model clock gate."""
    sources = sorted(directory.glob('*.sv')) + [GATE]
    target = output / (role + '.json')
    script = output / (role + '.ys')
    script.write_text('read_slang --top ibex_top ' + ' '.join(map(str, sources)) +
        '\nprep -top ibex_top -flatten\nmemory_map\nopt_clean\ncheck -assert\n' +
        f'write_json {target}\n')
    run(['yosys', '-Q', '-T', '-s', script], output, role)
    target.with_suffix('.elaboration.json').write_text(json.dumps(dict(
        module='ibex_top', parameters='actual faithful RV32IMFC model emission with RVFI',
        normalizations=[], netlist_sha256=digest(target),
        source_sha256={p.relative_to(ROOT).as_posix(): digest(p) for p in sources}), indent=2) + '\n')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'before-soc', 'after-soc', 'before-source', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    paths = {name: local(getattr(args, name)) for name in
             ('before', 'after', 'before_soc', 'after_soc', 'before_source')}
    for path in paths.values():
        path.relative_to(ROOT / 'build')
    out = local(args.output)
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='running',
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        scope='Shared-MAC revision: full leaf and whole-core cycle/state/output equivalence; unchanged SoC parents',
        assumptions=[], timeout_seconds_per_tool=600,
        not_proved=['new ISA correctness', 'physical timing', 'subcycle reset pulse behavior'],
        negative_controls={})
    tracked = set()
    def save():
        (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    save()
    try:
        run([sys.executable, 'tools/env/check.py'], out, 'environment')
        for role in ('before', 'after'):
            source = paths['before_source'] if role == 'before' else None
            emitter_receipt, production = authenticate_soc(paths[role + '_soc'], source)
            tracked.add(emitter_receipt)
            tracked.update(local(n) if n != SOURCE or source is None else source for n in production)
        receipt['composition'] = {
            'core': same_parents(paths['before'], paths['after']),
            'soc': same_parents(paths['before_soc'], paths['after_soc'])}
        for role in ('before', 'after'):
            if digest(paths[role] / LEAF) != digest(paths[role + '_soc'] / LEAF):
                raise ValueError('Core/SoC shared-MAC emission differs: ' + role)
            tracked.update(paths[role].rglob('*.sv'))
            tracked.update(paths[role + '_soc'].rglob('*.sv'))
        tracked.update(ROOT / name for name in (
            'hw/ip/perf_core/formal/check_mac_revision.py',
            'dv/core/equiv.py', 'dv/core/state_equiv.py', 'dv/core/common.py',
            'dv/core/module_map.json', 'dv/core/config.json',
            'dv/core/candidate.py', 'dv/core/csr_priority.py', 'dv/core/adaptations.json',
            'hw/vendor/ibex_ref/verify_lock.py', 'hw/vendor/ibex_ref/ibex_ref.lock.json',
            'tools/env/lock.json'))
        tracked.add(GATE)
        receipt['input_sha256'] = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(tracked)}
        save()
        leaf_dir = output_dir(out / 'leaf')
        designs = [elaborate(MODULE, paths[role] / LEAF, leaf_dir, role)
                   for role in ('before', 'after')]
        shared_ports = {'sharedMac_owner': ('input', 1), 'sharedMac_a': ('input', 12),
                        'sharedMac_b': ('input', 12), 'sharedMac_addend': ('input', 24),
                        'sharedMac_result': ('output', 25)}
        for design in designs:
            module = json.loads(design.read_text())['modules'][MODULE]
            for name, (direction, width) in shared_ports.items():
                port = module['ports'].get(name, {})
                if port.get('direction') != direction or len(port.get('bits', [])) != width:
                    raise ValueError('Not the production shared-MAC profile: ' + name)
            if sum(c['type'] == '$mul' for c in module['cells'].values()) != 1:
                raise ValueError('Expected exactly one preserved multiplier')
            if sum(c['type'] in STATE for c in module['cells'].values()) != 6:
                raise ValueError('Expected all six original control state elements')
        if compare(MODULE, *designs, leaf_dir) != 'proved':
            raise RuntimeError('Shared MAC transition equivalence failed')
        receipt['leaf'] = json.loads((leaf_dir / 'result.json').read_text())
        controls = negatives(MODULE, *designs, output_dir(out / 'leaf-negative'))
        if not {'output', 'reset-value', 'next-state', 'multiply-sign'} <= set(controls):
            raise ValueError('Required original negative controls were not executed')
        receipt['negative_controls']['leaf'] = controls
        fault_dir = output_dir(out / 'carry-negative')
        fault, detail = carry_fault(designs[1], fault_dir)
        if compare(MODULE, designs[0], fault, fault_dir) != 'failed':
            raise RuntimeError('Actual carry mutation escaped comparison')
        receipt['negative_controls']['carry'] = dict(status='rejected', **detail)
        save()
        whole_dir = output_dir(out / 'whole-core')
        whole_designs = [elaborate_top(paths[role], whole_dir, role)
                         for role in ('before', 'after')]
        if compare('ibex_top', *whole_designs, whole_dir) != 'proved':
            raise RuntimeError('Whole-core revision equivalence failed')
        receipt['whole_core'] = json.loads((whole_dir / 'result.json').read_text())
        controls = negatives('ibex_top', *whole_designs, output_dir(out / 'whole-negative'))
        if not {'output', 'reset-value', 'next-state', 'gained-reset'} <= set(controls):
            raise ValueError('Required whole-core negative controls were not executed')
        receipt['negative_controls']['whole_core'] = controls
        current = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(tracked)}
        if current != receipt['input_sha256']:
            raise RuntimeError('Inputs changed during proof')
        receipt['status'] = 'proved'
        print('PASS shared MAC revision: all leaf/whole-core state and outputs, reset, ownership, and faults', flush=True)
    except Exception as error:
        receipt.update(status='failed', error=str(error))
        raise
    finally:
        receipt['artifact_sha256'] = {p.relative_to(out).as_posix(): digest(p)
            for p in sorted(out.rglob('*')) if p.is_file() and p != out / 'result.json'}
        save()


if __name__ == '__main__':
    main()
