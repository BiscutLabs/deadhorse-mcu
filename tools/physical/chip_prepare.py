"""T38: preserve the qualified production map inside the T43 pad assembly.

Only the pad glue is synthesized. Analog sockets are restored by named ports,
never by the obsolete pre-mapping integer bit identities in their receipt.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'i_chip_core.soc.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def restore(mod, sockets):
    result = copy.deepcopy(mod)
    used = [b for net in mod['netnames'].values() for b in net['bits'] if isinstance(b, int)]
    next_bit = max(used) + 1
    for name in ('vdd', 'vss'):
        result['ports'][name] = dict(direction='inout', bits=[next_bit])
        result['netnames'][name] = dict(hide_name=0, bits=[next_bit], attributes={})
        next_bit += 1
    assert {r['module'] for r in sockets} == {'LfRcMacro', 'PorBrownoutMacro'}
    expected = {
        'lf': ('LfRcMacro', {'clock': 'analog_lf_clock'},
               {'vdd': 1, 'vss': 1, 'enable': 1, 'trim': 6, 'test': 1, 'clock': 1}, ['ready']),
        'por': ('PorBrownoutMacro', {'threshold': 'analog_por_threshold',
                'supplyReset_n': 'analog_por_supplyReset_n', 'brownout': 'analog_por_brownout'},
                {'vdd': 1, 'vss': 1, 'threshold': 2, 'test': 1, 'supplyReset_n': 1, 'brownout': 1}, ['powerOn_n'])}
    assert {r['instance'] for r in sockets} == set(expected)
    for row in sockets:
        kind, ports, widths, unused = expected[row['instance']]
        assert row['module'] == kind and row['ports'] == ports
        assert {n: len(v) for n, v in row['connections'].items()} == widths
        assert row['unused_outputs'] == unused
        connections, directions = {}, {}
        for pin, old_bits in row['connections'].items():
            if pin in row['ports']:
                port = result['ports'].pop(row['ports'][pin])
                connections[pin] = port['bits'][:]
                directions[pin] = 'output' if port['direction'] == 'input' else 'input'
            elif pin in ('vdd', 'vss'):
                connections[pin] = result['ports'][pin]['bits'][:]
                directions[pin] = 'inout'
            else:
                constant = ['1'] if row['module'] == 'LfRcMacro' and pin == 'enable' else ['0'] * len(old_bits)
                assert old_bits == constant, ('Nonconstant analog control', pin)
                connections[pin] = constant
                directions[pin] = 'input'
        assert row['instance'] not in result['cells']
        result['cells'][row['instance']] = dict(hide_name=0, type=row['module'],
            parameters={}, attributes={}, port_directions=directions, connections=connections)
    # Exact reverse projection, including every digital pin, parameter and alias.
    reverse = copy.deepcopy(result)
    for row in sockets:
        del reverse['cells'][row['instance']]
        for name in row['ports'].values():
            reverse['ports'][name] = copy.deepcopy(mod['ports'][name])
    for name in ('vdd', 'vss'):
        del reverse['ports'][name]
        del reverse['netnames'][name]
    assert reverse == mod, 'Analog restoration is not reversible'
    return result


def audit(before, after, prefix=PREFIX):
    """Bijective digital net/cell correspondence, independent of numeric IDs."""
    bits = {'0': '0', '1': '1', 'x': 'x', 'z': 'z'}
    inverse = {}

    def bind(a, b):
        assert len(a) == len(b), 'Pin width changed'
        for x, y in zip(a, b):
            if x in bits:
                assert bits[x] == y, ('Net split/rewire', x, y)
            else:
                assert isinstance(y, int) and y not in inverse, ('Net merged/constant', x, y)
                bits[x], inverse[y] = y, x

    for name, old in before['cells'].items():
        assert prefix + name in after['cells'], ('Missing retained cell', name)
        new = after['cells'][prefix + name]
        for key in ('type', 'parameters', 'port_directions'):
            assert old[key] == new[key], ('Cell changed', name, key)
        assert set(old['connections']) == set(new['connections']), ('Pin set', name)
        for pin, bs in old['connections'].items():
            bind(bs, new['connections'][pin])
    for name, port in before['ports'].items():
        assert prefix + name in after['netnames'], ('Missing boundary alias', name)
        bind(port['bits'], after['netnames'][prefix + name]['bits'])
    return bits


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--map', default='build/t43/new02/map')
    p.add_argument('--assembly', default='build/t43/chip-elaboration03/design.json')
    p.add_argument('--fresh-emit', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    mapped, assembly, out = [(ROOT / v).resolve() for v in (a.map, a.assembly, a.output)]
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    receipt = json.loads((mapped / 'result.json').read_text())
    assert receipt['status'] == 'mapped'
    assert sha(mapped / 'canonical.json') == receipt['mapped_sha256']
    assert sha(mapped / 'mapped.v') == receipt['verilog_sha256']
    fresh = (ROOT / a.fresh_emit).resolve()
    for name, expected in receipt['emitted_sha256'].items():
        relative = name.split('/emit/', 1)[1]
        assert sha(fresh / relative) == expected, ('Fresh production emission differs', relative)
    assembly_receipt_path = assembly.parent / 'result.json'
    assembly_receipt = json.loads(assembly_receipt_path.read_text())
    assert assembly_receipt['status'] == 'elaborated_not_physical'
    assert sha(assembly) == assembly_receipt['artifact_sha256'][assembly.name]
    for name, expected in assembly_receipt['input_sha256'].items():
        assert sha(ROOT / name) == expected, ('T43 assembly input changed', name)
    sources = {}
    for name, expected in receipt['input_sha256'].items():
        relative = name.removeprefix('/work/')
        if relative.startswith(('hw/', 'sw/')):
            assert sha(ROOT / relative) == expected, ('Changed production input', relative)
            sources[relative] = expected
    canonical = json.loads((mapped / 'canonical.json').read_text())
    mod = canonical['modules']['DeadhorseSoc']
    sockets = json.loads((mapped / 'analog-sockets.json').read_text())
    core = restore(mod, sockets)
    swapped = copy.deepcopy(sockets)
    por = next(r for r in swapped if r['instance'] == 'por')
    por['ports']['brownout'], por['ports']['supplyReset_n'] = por['ports']['supplyReset_n'], por['ports']['brownout']
    try:
        restore(mod, swapped)
    except AssertionError:
        pass
    else:
        raise AssertionError('Swapped analog outputs accepted')
    design = json.loads(assembly.read_text())
    socket = design['modules'][design['modules']['chip_top']['cells']['i_chip_core']['type']]
    core_type = socket['cells']['soc']['type']
    original = design['modules'][core_type]
    assert {n: (p['direction'], len(p['bits'])) for n, p in original['ports'].items()} == {
        n: (p['direction'], len(p['bits'])) for n, p in core['ports'].items()}
    # No optimizer may silently remove a certified register or status observation.
    for c in core['cells'].values():
        c.setdefault('attributes', {})['keep'] = '1'
    for n in core['netnames'].values():
        n.setdefault('attributes', {})['keep'] = '1'
    design['modules'][core_type] = core
    for name, definition in canonical['modules'].items():
        if name != 'DeadhorseSoc':
            design['modules'][name] = definition
    (out / 'assembly.json').write_text(json.dumps(design))
    lib = ROOT / 'build/t43/pdk-candidate/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    assert sha(lib) == receipt['liberty_sha256']
    script = out / 'map.ys'
    script.write_text('\n'.join([
        f'read_json {out}/assembly.json', 'hierarchy -check -top chip_top',
        'flatten', 'synth -top chip_top -noabc', f'abc -liberty {lib}',
        'clean', 'check -assert', f'write_json {out}/mapped.json',
        f'write_verilog -noattr -noexpr {out}/chip_top.v',
        # Verilog assigns printable names to hidden pad-glue cells. Re-import
        # that exact physical file for subsequent OpenDB correspondence.
        'delete chip_top', f'read_verilog {out}/chip_top.v',
        'hierarchy -check -top chip_top', 'check -assert',
        f'write_json {out}/physical.json']) + '\n')
    run = subprocess.run(['yosys', '-Q', '-T', '-s', str(script)], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / 'yosys.log').write_text(run.stdout)
    assert run.returncode == 0, run.stdout[-2000:]
    result = json.loads((out / 'mapped.json').read_text())['modules']['chip_top']
    correspondence = audit(core, result)
    physical = json.loads((out / 'physical.json').read_text())['modules']['chip_top']
    audit(core, physical)
    faults = ['swapped-analog-outputs']
    missing = copy.deepcopy(result)
    victim = next(n for n, c in core['cells'].items() if 'D' in c['connections'])
    del missing['cells'][PREFIX + victim]
    wrong = copy.deepcopy(result)
    wrong['cells'][PREFIX + victim]['connections']['D'] = ['1']
    for label, mutated in [('missing-cell', missing), ('wrong-data-pin', wrong)]:
        try:
            audit(core, mutated)
        except AssertionError:
            faults.append(label)
        else:
            raise AssertionError('Mutation accepted: ' + label)
    (out / 'correspondence.json').write_text(json.dumps(correspondence))
    inputs = [Path(__file__), mapped / 'result.json', mapped / 'canonical.json',
              mapped / 'analog-sockets.json', assembly, assembly_receipt_path, lib]
    inputs += [fresh / name.split('/emit/', 1)[1] for name in receipt['emitted_sha256']]
    result_receipt = dict(status='pass', source_sha256=sources,
        input_sha256={str(q.relative_to(ROOT)): sha(q) for q in inputs},
        artifact_sha256={q.name: sha(q) for q in out.iterdir() if q.is_file()},
        digital_cells=len(mod['cells']), analog_cells=len(sockets),
        retained_status=sorted(n for n in mod['ports'] if n.startswith('status_')),
        negative_controls=faults, seconds=time.monotonic() - start,
        scope='Exact canonical digital graph plus restored analog and existing pad assembly; no electrical or final netlist signoff')
    (out / 'result.json').write_text(json.dumps(result_receipt, indent=2) + '\n')
    print('PASS reversible analog restoration and every mapped digital cell/pin; faults rejected')


if __name__ == '__main__':
    main()
