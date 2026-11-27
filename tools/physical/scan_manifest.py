"""Bind T37 scan eligibility to exact production state and pad identities.

The manifest contains cell/pin identities, not a manually maintained FF list.
Changing a source alias, clock partition or access-controller state fails closed.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'gf180mcu_fd_sc_mcu7t5v0__'
HIER = 'i_chip_core.soc.'
ACCESS = {
    'testAccess.armed_position': 5,
    'testAccess.armed': 1,
    'testAccess.armed_closed': 1,
    '_testAccess_testMode': 1,
    'testAccess._fallingRelease_released': 1,
    'testAccess.fallingRelease.first': 1,
    'testAccess._release_released': 1,
    'testAccess.release_0.first': 1,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(core, physical):
    cells = core['cells']
    ff = {n: c for n, c in cells.items() if re.fullmatch(
        PREFIX + r'dff(q|rnq|snq|nrnq)_[1248]', c['type'])}
    outputs = defaultdict(list)
    for n, c in ff.items():
        if len(c['connections']['Q']) != 1:
            raise ValueError('Non-scalar state')
        outputs[c['connections']['Q'][0]].append(n)
    excluded = {}
    for alias, width in ACCESS.items():
        bits = core['netnames'][alias]['bits']
        if len(bits) != width:
            raise ValueError('Changed access state width: ' + alias)
        for index, bit in enumerate(bits):
            names = outputs[bit]
            if len(names) != 1 or names[0] in excluded:
                raise ValueError('Missing/mixed/ambiguous access state: ' + alias)
            excluded[names[0]] = f'{alias}[{index}]'
    # Every sequential primitive must be a recognized FF or one of the two
    # existing clock gates. The library check in the insertion runner also
    # rejects unrecognized state primitives outside this canonical core.
    if len(excluded) != 12:
        raise ValueError('Changed unscanned access inventory')
    clocks = defaultdict(list)
    for name, c in ff.items():
        if name in excluded:
            continue
        pin = 'CLKN' if 'CLKN' in c['connections'] else 'CLK'
        bits = c['connections'][pin]
        if len(bits) != 1 or not isinstance(bits[0], int):
            raise ValueError('Invalid clock identity')
        clocks[bits[0], pin].append(name)
    if len(clocks) != 7:
        raise ValueError('Changed seven-lane root/edge partition')

    # A port is bound through an actual mapped input pin. No integer net ID
    # survives between Yosys and OpenDB; cell/pin identities do.
    def endpoint(bit):
        found = [(HIER+n, p) for n, c in cells.items()
                 for p, bits in c['connections'].items()
                 if bits == [bit] and c['port_directions'][p] == 'input']
        if not found:
            raise ValueError('No actual sink for input')
        return list(sorted(found)[0])

    def port(name, width=1):
        p = core['ports'][name]
        if (p['direction'] != 'input' or len(p['bits']) != width or
                any(not isinstance(b, int) for b in p['bits']) or len(set(p['bits'])) != width):
            raise ValueError('Wrong input port shape: ' + name)
        return [endpoint(b) for b in p['bits']]

    si_bits = core['ports']['pins_inactive_gpioIn']['bits'] + core['ports']['pins_inactive_timerIn']['bits']
    if len(set(si_bits)) != 7:
        raise ValueError('Overlapping scan inputs')
    gates = [HIER+n for n, c in cells.items() if c['type'].startswith(PREFIX+'icgtp_')]
    if sorted(gates) != [HIER+'clocks.executor.gate.cell_0.cell_0', HIER+'digital.core.core_clock_gate_i.cell_0']:
        raise ValueError('Changed clock-gate inventory')
    for lane in range(7):
        hook = cells[f'scanHooks.lane_{lane}']
        if (hook['type'] != PREFIX+'buf_1' or set(hook['connections']) != {'I', 'Z'} or
                hook['connections']['I'] != ['0'] or len(hook['connections']['Z']) != 1):
            raise ValueError('Wrong output hook')

    lanes = []
    for lane, ((bit, pin), names) in enumerate(sorted(clocks.items())):
        names = sorted(names)
        aliases = sorted(n for n, v in core['netnames'].items() if v['bits'] == [bit])
        lanes.append(dict(lane=lane, original_clock_aliases=aliases,
            clock_pin=pin, clock_endpoint=[HIER+names[0], pin],
            cells=[HIER+n for n in names], output_hook=HIER+f'scanHooks.lane_{lane}'))
    # The physical assembly must contain the same cell type and named pins.
    for name, cell in cells.items():
        pc = physical['cells'][HIER+name]
        if pc['type'] != cell['type'] or set(pc['connections']) != set(cell['connections']):
            raise ValueError('Physical/canonical cell mismatch: ' + name)
    return dict(excluded={HIER+n: a for n, a in excluded.items()}, lanes=lanes,
        mode=[HIER+outputs[core['netnames']['_testAccess_testMode']['bits'][0]][0], 'Q'],
        enable=port('pins_uartRx_2')[0], reset_n=port('pins_uartRx_1')[0],
        osc=port('oscIn')[0], tck=port('pins_inactive_jtagTck')[0],
        inputs=port('pins_inactive_gpioIn', 3)+port('pins_inactive_timerIn', 4),
        clock_gates=gates,
        eligible=sum(len(r['cells']) for r in lanes),
        scope='Exact source-state/pad binding; not insertion or timing acceptance')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', type=Path, required=True)
    ap.add_argument('--chip', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    core_path = args.map/'canonical.json'
    phys_path = args.chip/'physical.json'
    core = json.loads(core_path.read_text())['modules']['DeadhorseSoc']
    physical = json.loads(phys_path.read_text())['modules']['chip_top']
    result = plan(core, physical)
    receipt = json.loads((args.chip/'result.json').read_text())
    if receipt['status'] != 'pass' or sha(phys_path) != receipt['artifact_sha256']['physical.json']:
        raise ValueError('Unauthenticated physical graph')
    if sha(core_path) != receipt['input_sha256'][str(core_path.as_posix())]:
        raise ValueError('Wrong canonical map')
    result['input_sha256'] = {str(p.as_posix()): sha(p) for p in (
        core_path, phys_path, args.chip/'chip_top.v', args.chip/'result.json',
        Path(__file__).relative_to(ROOT))}
    # Wrongly classifying an arbitrary input alias as the mode register must fail.
    import copy
    wrong = copy.deepcopy(core)
    wrong['netnames']['_testAccess_testMode']['bits'] = core['ports']['oscIn']['bits']
    try:
        plan(wrong, physical)
    except ValueError:
        result['negative_controls'] = ['non-state-alias-rejected']
    else:
        raise ValueError('Wrong state alias escaped')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('PASS scan manifest:', result['eligible'], 'eligible;', len(result['excluded']), 'excluded; seven lanes')


if __name__ == '__main__':
    main()
