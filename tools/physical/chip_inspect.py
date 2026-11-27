"""Audit T38 physical graph preservation and measure placed inventory from ODB."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import sys
import odb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from usb_cells import signature
from usb_boundary import groups


def qualify_sizes(pairs, has_diodes=False, inserted_buffers=()):
    """Compare functions and sequential semantics, not just cell-name stems."""
    if not pairs and not has_diodes and not inserted_buffers:
        return {}
    lock = json.loads((ROOT / 'phys/gf180-ws-1x1/pdk-lock.json').read_text())
    directory = ROOT / 'build/t43/pdk-candidate/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib'
    libraries = sorted(directory.glob('*.lib'))
    assert len(libraries) == 15, 'Incomplete pinned cell corner inventory'
    inputs, signatures = {}, {}
    for library in libraries:
        raw = library.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert lock['files'][library.name] == digest, library
        inputs[str(library.relative_to(ROOT))] = digest
        cells = dict(groups(raw.decode(), 'cell'))
        for name in inserted_buffers:
            match = re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(clkbuf|buf|clkinv|inv|dlyb|dlyc)_([1-9][0-9]*)', name)
            assert match
            family = 'buf' if match[1] in ('dlyb', 'dlyc') else match[1]
            reference = 'gf180mcu_fd_sc_mcu7t5v0__' + family + '_1'
            assert signature(cells[name]) == signature(cells[reference]), ('Changed buffer function', name, library)
        if has_diodes:
            diode = signature(cells['gf180mcu_fd_sc_mcu7t5v0__antenna'])
            assert diode == dict(pins={'I': dict(direction='input', function=None,
                three_state=None, clock=None, signal_type=None)}, ff=[]), ('Active antenna cell', library)
        for old, new in pairs:
            a = re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(\w+)_([1-9][0-9]*)', old)
            b = re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(\w+)_([1-9][0-9]*)', new)
            assert a and b
            assert (a[1] == b[1] or {a[1], b[1]} <= {'buf', 'clkbuf', 'dlya', 'dlyb', 'dlyc'}
                    or {a[1], b[1]} <= {'inv', 'clkinv'}), ('Different cell families', old, new)
            left, right = signature(cells[old]), signature(cells[new])
            assert left == right, ('Changed logical/sequential semantics', old, new, library)
            assert (old, new) not in signatures or signatures[(old, new)] == left
            signatures[(old, new)] = left
    return inputs


def inspect(original, block):
    def logical_name(name):
        return name.replace(r'\[', '[').replace(r'\]', ']')
    actual = {logical_name(i.getName()): i for i in block.getInsts()}
    assert len(actual) == len(block.getInsts()), 'Ambiguous escaped instance alias'
    for n in block.getNets():
        if str(n.getSigType()) in ('POWER', 'GROUND'):
            continue
        drivers = [t for t in n.getITerms() if str(t.getMTerm().getIoType()) == 'OUTPUT']
        assert len(drivers) <= 1, ('Multiple physical drivers', n.getName())
    missing = set(original['cells']) - set(actual)
    assert not missing, ('Original cells removed', sorted(missing)[:5])
    def net(t):
        n = t.getNet()
        assert n is not None, ('Disconnected signal', t.getInst().getName(), t.getMTerm().getName())
        return n

    inserted = collections.Counter()
    extra_logic = {}
    passive = []
    for name, inst in actual.items():
        if name in original['cells']:
            continue
        kind = inst.getMaster().getName()
        inserted[kind] += 1
        pins = {t.getMTerm().getName(): t for t in inst.getITerms()
                if str(t.getMTerm().getSigType()) not in ('POWER', 'GROUND')}
        if not pins:
            continue
        short = kind.removeprefix('gf180mcu_fd_sc_mcu7t5v0__')
        if re.fullmatch(r'(?:clkbuf|buf|clkinv|inv|dlyb|dlyc)_[1-9][0-9]*', short):
            assert set(pins) == {'I', 'ZN' if 'inv_' in short else 'Z'}, (name, pins)
            extra_logic[name] = ('buffer', pins['I'], int('inv_' in short))
        elif short in ('tieh', 'tiel'):
            assert len(pins) == 1
            extra_logic[name] = ('constant', int(short == 'tieh'), 0)
        elif kind == 'gf180mcu_fd_sc_mcu7t5v0__antenna':
            assert set(pins) == {'I'} and str(pins['I'].getMTerm().getIoType()) == 'INPUT'
            power = {t.getMTerm().getName(): t for t in inst.getITerms()
                     if str(t.getMTerm().getSigType()) in ('POWER', 'GROUND')}
            supplies = {'VDD': ('VDD', 'POWER'), 'VNW': ('VDD', 'POWER'),
                        'VSS': ('VSS', 'GROUND'), 'VPW': ('VSS', 'GROUND')}
            assert set(power) == set(supplies), ('Unexpected diode supplies', name)
            for label, terminal in power.items():
                rail, kind = supplies[label]
                assert (net(terminal).getName() == rail and
                        str(net(terminal).getSigType()) == kind and
                        str(terminal.getMTerm().getSigType()) == kind), ('Wrong diode supply', name, label)
            passive.append(pins['I'])
        else:
            raise AssertionError(('Unexpected inserted signal cell', name, kind))
    # Directed roots: original outputs and external input/inout boundaries.
    # A bidirectional pad net legitimately has both the package boundary and
    # its original PAD terminal as possible sources; preserve that exact set.
    ignored = {'VDD', 'VSS', 'DVDD', 'DVSS', 'vdd', 'vss'}
    expected = collections.defaultdict(set)
    physical_pins = {}
    for name, cell in original['cells'].items():
        for pin, bits in cell['connections'].items():
            if pin in ignored:
                continue
            for index, bit in enumerate(bits):
                physical_pin = pin if len(bits) == 1 else f'{pin}[{index}]'
                physical_pins[(name, physical_pin)] = (name, pin, index)
                if cell['port_directions'][pin] in ('output', 'inout'):
                    expected[bit].add((('cell', name, pin, index), 0))
    boundaries = {}
    for name, port in original['ports'].items():
        if name in ignored:
            continue
        for index, bit in enumerate(port['bits']):
            terminal = name if len(port['bits']) == 1 else f'{name}[{index}]'
            boundaries[terminal] = (name, index, bit, port['direction'])
            if port['direction'] in ('input', 'inout'):
                expected[bit].add((('port', name, index), 0))
    bterms = {logical_name(t.getName()): t for t in block.getBTerms() if t.getName() not in ignored}
    assert set(bterms) == set(boundaries), 'Package boundary inventory changed'
    for name, (_, _, _, direction) in boundaries.items():
        assert str(bterms[name].getIoType()).lower() == direction, ('Package direction changed', name)
    cache = {}

    def trace(n, visiting=()):
        assert n is not None, 'Disconnected physical boundary'
        name = n.getName()
        assert name not in visiting, ('Physical buffer cycle', name)
        if name in cache:
            return cache[name]
        roots = set()
        for t in n.getBTerms():
            label = logical_name(t.getName())
            if label in boundaries and str(t.getIoType()) in ('INPUT', 'INOUT'):
                port, index, _, _ = boundaries[label]
                roots.add((('port', port, index), 0))
        for t in n.getITerms():
            if str(t.getMTerm().getIoType()) not in ('OUTPUT', 'INOUT'):
                continue
            inst = logical_name(t.getInst().getName())
            pin = t.getMTerm().getName()
            if inst in extra_logic:
                kind, source, parity = extra_logic[inst]
                if kind == 'constant':
                    roots.add((('constant',), source))
                else:
                    roots.update((r, v ^ parity) for r, v in trace(net(source), (*visiting, name)))
            elif (inst, pin) in physical_pins:
                old_name, old_pin, index = physical_pins[(inst, pin)]
                roots.add((('cell', old_name, old_pin, index), 0))
            else:
                raise AssertionError(('Unknown physical source', inst, pin))
        assert roots, ('Undriven physical branch', name)
        cache[name] = frozenset(roots)
        return cache[name]

    def matches(bit, n, label):
        wanted = frozenset({(('constant',), int(bit))}) if bit in ('0', '1') else frozenset(expected[bit])
        assert wanted and trace(n) == wanted, ('Original directed source changed', label, wanted, trace(n))

    for name, (_, _, bit, _) in boundaries.items():
        matches(bit, bterms[name].getNet(), name)
    for terminal in passive:
        trace(net(terminal))
    dummy_loads = []
    for name in extra_logic:
        for terminal in actual[name].getITerms():
            if str(terminal.getMTerm().getIoType()) == 'OUTPUT':
                if terminal.getNet() is None:
                    kind, source, parity = extra_logic[name]
                    assert re.fullmatch(r'clkload[0-9]+', name) and kind == 'buffer', (name, kind, parity)
                    assert terminal.getMTerm().getName() == ('ZN' if parity else 'Z')
                    trace(net(source))
                    dummy_loads.append(name)
                else:
                    trace(net(terminal))
    protected, unprotected = [], []
    replacements = {}
    for name, cell in original['cells'].items():
        inst = actual[name]
        if inst.getMaster().getName() != cell['type']:
            replacements[name] = dict(old=cell['type'], new=inst.getMaster().getName())
        if name.startswith('i_chip_core.soc.'):
            (protected if inst.isDoNotTouch() else unprotected).append(name)
        for pin, bits in cell['connections'].items():
            if pin in ('VDD', 'VSS', 'DVDD', 'DVSS', 'vdd', 'vss'):
                continue
            for index, bit in enumerate(bits):
                terminal = inst.findITerm(pin if len(bits) == 1 else f'{pin}[{index}]')
                assert terminal, ('Missing physical pin', name, pin, index)
                matches(bit, net(terminal), (name, pin, index))
    # Cell preservation is checked after collapsing only identified physical
    # buffers/inverters/ties. No setup/hold or analog guarantee follows.
    return dict(status='pass', original_cells=len(original['cells']),
                added_cells=dict(inserted), passive_diodes=len(passive), protected_cells=len(protected),
                clock_dummy_loads=len(dummy_loads),
                unprotected_cell_count=len(unprotected), replacements=replacements)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', required=True)
    p.add_argument('--map', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    state_path, mapped, out = [(ROOT / v).resolve() for v in (a.state, a.map, a.output)]
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    state = json.loads(state_path.read_text())
    odb_path = Path(state['odb'])
    db = odb.dbDatabase.create()
    odb.read_db(db, str(odb_path))
    block = db.getChip().getBlock()
    design = json.loads(mapped.read_text())['modules']['chip_top']
    audit = inspect(design, block)
    audit['sizing_library_sha256'] = qualify_sizes(
        {(v['old'], v['new']) for v in audit['replacements'].values()}, bool(audit['passive_diodes']),
        [name for name in audit['added_cells'] if re.fullmatch(
            r'gf180mcu_fd_sc_mcu7t5v0__(?:clkbuf|buf|clkinv|inv|dlyb|dlyc)_[1-9][0-9]*', name)])
    # An actual altered physical input must fail, not merely a JSON edit.
    victim = next(i for i in block.getInsts() if i.getName() in design['cells'] and i.findITerm('D'))
    pin = victim.findITerm('D')
    saved = pin.getNet()
    replacement = victim.findITerm('CLK').getNet()
    assert replacement.getName() != saved.getName()
    was_protected = victim.isDoNotTouch()
    victim.setDoNotTouch(False)
    pin.connect(replacement)
    try:
        inspect(design, block)
    except AssertionError:
        audit['wrong_physical_data_pin'] = 'rejected'
    else:
        raise AssertionError('Wrong physical D pin accepted')
    pin.connect(saved)
    victim.setDoNotTouch(was_protected)
    audit['negative_controls'] = ['wrong-physical-data-pin']

    def reject(label):
        try:
            inspect(design, block)
        except AssertionError:
            audit['negative_controls'].append(label)
        else:
            raise AssertionError('Physical fault accepted: ' + label)

    first, second = [block.findBTerm(n) for n in ('clk_PAD', 'rst_n_PAD')]
    fn, sn = first.getNet(), second.getNet()
    first.disconnect(); second.disconnect()
    first.connect(sn); second.connect(fn)
    reject('swapped-package-clock-reset')
    first.disconnect(); second.disconnect()
    first.connect(fn); second.connect(sn)
    buffer = next((i for i in block.getInsts() if i.getName() not in design['cells']
                   and re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:clkbuf|buf)_(1|2|4|8|16)', i.getMaster().getName())), None)
    if buffer is not None:
        inp, output = buffer.findITerm('I'), buffer.findITerm('Z')
        before_in, before_out = inp.getNet(), output.getNet()
        locked = buffer.isDoNotTouch()
        buffer.setDoNotTouch(False)
        inp.disconnect(); output.disconnect()
        inp.connect(before_out); output.connect(before_in)
        reject('reversed-inserted-buffer')
        inp.disconnect(); output.disconnect()
        inp.connect(before_in); output.connect(before_out)
        inp.connect(before_out)
        reject('inserted-buffer-cycle')
        inp.connect(before_in)
        buffer.setDoNotTouch(locked)
    else:
        audit['pending_faults'] = ['reversed-inserted-buffer', 'inserted-buffer-cycle']
    diode = next((i for i in block.getInsts() if i.getName() not in design['cells']
                  and i.getMaster().getName() == 'gf180mcu_fd_sc_mcu7t5v0__antenna'), None)
    if diode is not None:
        pin = diode.findITerm('I')
        saved = pin.getNet()
        pin.disconnect()
        reject('disconnected-passive-diode')
        pin.connect(saved)
        power = diode.findITerm('VDD')
        saved = power.getNet()
        power.disconnect()
        power.connect(diode.findITerm('VSS').getNet())
        reject('wrong-passive-diode-supply')
        power.disconnect()
        power.connect(saved)
    units = block.getDbUnitsPerMicron()
    area = collections.Counter()
    counts = collections.Counter()
    macros = []
    for inst in block.getInsts():
        master = inst.getMaster()
        kind = master.getName()
        group = ('sram' if 'ip_sram__' in kind else 'analog' if kind in ('LfRcMacro', 'PorBrownoutMacro')
                 else 'artwork' if '_ws_ip__' in kind else 'pads' if '_fd_io__' in kind
                 else 'tap_endcap' if kind.endswith(('__filltie', '__endcap'))
                 else 'filler_decap' if re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:fill|fillcap)_\d+', kind)
                 else 'standard_cells')
        counts[group] += 1
        area[group] += master.getWidth() * master.getHeight() / units ** 2
        if group in ('sram', 'analog'):
            b = inst.getBBox()
            macros.append(dict(name=inst.getName(), type=kind,
                box=[v / units for v in (b.xMin(), b.yMin(), b.xMax(), b.yMax())]))
    b = block.getCoreArea()
    box = [v / units for v in (b.xMin(), b.yMin(), b.xMax(), b.yMax())]
    inputs = [Path(__file__), state_path, odb_path, mapped,
              ROOT / 'tools/physical/usb_cells.py', ROOT / 'tools/timing/usb_boundary.py',
              ROOT / 'phys/gf180-ws-1x1/pdk-lock.json']
    result = dict(graph=audit, area_um2=dict(area), counts=dict(counts), core_box_um=box,
                  core_area_um2=(box[2] - box[0]) * (box[3] - box[1]), macros=macros,
                  input_sha256={str(q.relative_to(ROOT)): hashlib.sha256(q.read_bytes()).hexdigest() for q in inputs})
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS physical graph correspondence and wrong-D fault; inventory measured')


if __name__ == '__main__':
    main()
