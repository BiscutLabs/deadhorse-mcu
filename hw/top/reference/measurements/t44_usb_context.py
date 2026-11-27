"""Audit the current production USB boundary against its historical fixture.

No timing exemption, source-hash substitution or new measurement is produced.
This is the prerequisite witness for a separately reviewed evidence derivation.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
from plan04_screen import clock_manifest
from plan05_usb_fixture import buffered_slot, faults
from plan04_usb_binding import bind_source


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def local(value):
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    path.relative_to(ROOT)
    return path


def check_hashes(values):
    assert values, 'Empty authenticated input inventory'
    for name, digest in values.items():
        assert sha(local(name)) == digest, ('Changed input', name)


def snapshot():
    names = subprocess.check_output(
        ['git', 'ls-files', '-c', '-o', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    return {name: sha(ROOT / name) for name in sorted(set(names))
            if name and not name.endswith('.md') and (ROOT / name).is_file()}


def unique_drivers(module):
    result = {}
    for name, cell in module['cells'].items():
        for pin, bits in cell['connections'].items():
            if cell['port_directions'][pin] != 'output':
                continue
            for value in bits:
                if isinstance(value, str):
                    continue
                assert value not in result, ('Ambiguous driver', value, result.get(value), name, pin)
                result[value] = (name, pin)
    return result


def reset_wiring(parent, usb_name, slot_name):
    """Locate releases by actual connectivity; names cannot qualify a reset."""
    usb = parent['cells'][usb_name]
    slot = parent['cells'][slot_name]
    unique_drivers(parent)
    assert usb['type'].startswith('Usb$') and slot['type'].startswith('SocResetSlot$')
    aliases = {c['connections']['Y'][0]: c['connections']['A'][0]
               for c in parent['cells'].values() if c['type'] == '$buf'
               and len(c['connections']['Y']) == len(c['connections']['A']) == 1}

    def bit(bits):
        assert len(bits) == 1
        value = bits[0]
        seen = set()
        while value in aliases:
            assert value not in seen, 'Alias cycle'
            seen.add(value)
            value = aliases[value]
        return value

    def release(output, raw):
        matches = [(name, c) for name, c in parent['cells'].items()
                   if c['type'].split('$')[0] == 'ResetRelease'
                   and bit(c['connections']['released']) == bit(output)]
        assert len(matches) == 1, 'Missing/ambiguous local USB reset release'
        name, cell = matches[0]
        assert set(cell['connections']) == {'clk', 'reset_n', 'released'}
        assert bit(cell['connections']['clk']) == bit(usb['connections']['appClock'])
        assert bit(cell['connections']['reset_n']) == bit(raw)
        return name, cell['type']

    assert bit(slot['connections']['clk']) == bit(usb['connections']['appClock'])
    main = release(slot['connections']['reset_n'], usb['connections']['appReset_n'])
    endpoint = slot['connections']['endpointReset_n']
    local_endpoint = release(slot['connections']['endpointReady'], endpoint)
    gates = [c for c in parent['cells'].values()
             if c['type'] in ('$and', '$logic_and')
             and len(c['connections']['Y']) == 1 and bit(c['connections']['Y']) == bit(endpoint)]
    assert len(gates) == 1
    assert {bit(gates[0]['connections'][p]) for p in ('A', 'B')} == {
        bit(usb['connections']['appReset_n']), bit(usb['connections']['usbReset_n'])}
    for name, values in usb['connections'].items():
        if name.startswith('bus_'):
            assert values == slot['connections']['target_' + name.removeprefix('bus_')], name
    return dict(slot_release=main, endpoint_release=local_endpoint)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--historical', default='build/plan05/usb-boundary08')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    base, old, out = map(local, (args.base, args.historical, args.output))
    for path in (base, old, out):
        path.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    begin = time.monotonic()
    frozen = snapshot()
    receipt = dict(status='running', command=sys.argv, commands=[],
                   runner_sha256=sha(__file__),
                   qualification='Current source/connection identity only; no fresh physical timing claim')
    dependencies = {}

    def bind(path):
        path = local(path)
        dependencies[str(path)] = sha(path)
        return read(path)

    try:
        mapping = bind(base / 'map/result.json')
        assert mapping['status'] == 'mapped'
        for key in ('input_sha256', 'emitted_sha256'):
            check_hashes(mapping[key])
            dependencies.update({str(local(p)): h for p, h in mapping[key].items()})
        mapped_path = base / 'map/canonical.json'
        assert sha(mapped_path) == mapping['mapped_sha256']
        mapped = bind(mapped_path)['modules']['DeadhorseSoc']
        fresh = out / 'fresh-emit'
        command = [sys.executable, 'tools/sbt.py',
                   f'hw/runMain deadhorse.top.EmitSoc {fresh.relative_to(ROOT).as_posix()} production 8']
        started = time.monotonic()
        with (out / 'emit.log').open('w') as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(command=command, returncode=process.returncode,
                                        seconds=time.monotonic()-started))
        assert process.returncode == 0
        emitted = {str(Path(p).relative_to(base / 'emit')): h
                   for p, h in ((local(p), h) for p, h in mapping['emitted_sha256'].items())}
        actual = {p.relative_to(fresh).as_posix(): sha(p) for p in fresh.rglob('*')
                  if p.suffix in ('.sv', '.v')}
        previous = {p.relative_to(base / 'emit').as_posix(): sha(p)
                    for p in (base / 'emit').rglob('*') if p.suffix in ('.sv', '.v')}
        assert actual == previous, 'Current production HDL tree differs from mapping inputs'
        filelist = [(fresh / line.strip()).resolve().relative_to(fresh.resolve()).as_posix()
                    for line in (fresh / 'filelist.f').read_text().splitlines() if line.strip()]
        assert len(filelist) == len(set(filelist)), 'Duplicate production filelist entry'
        assert {p: sha(fresh / p) for p in filelist} == emitted, 'Production filelist changed'
        dependencies.update({str(fresh / p): h for p, h in actual.items()})
        # Reconstruct the hierarchy from authenticated HDL and locked libraries;
        # a stored hierarchy hash or a success string is not source evidence.
        command = [sys.executable, 'hw/top/reference/measurements/reset_inventory.py',
                   '--emit', str(fresh), '--output', str(out / 'hierarchy')]
        started = time.monotonic()
        with (out / 'hierarchy.log').open('w') as stream:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(command=command, returncode=process.returncode,
                                        seconds=time.monotonic()-started))
        assert process.returncode == 0
        imported = bind(out / 'hierarchy/import-receipt.json')
        assert imported['exit_code'] == 0
        check_hashes(imported['sha256'])
        dependencies.update({str(local(p)): h for p, h in imported['sha256'].items()})
        hierarchy = out / 'hierarchy/hier.json'
        design = bind(hierarchy)['modules']
        certificate = bind(ROOT / 'build/t33/pre-fast03/fast/usb/timing/usb/certificate/result.json')
        assert certificate['status'] == 'pass'
        targets = [name for name in design if name.split('$')[0] == 'Usb']
        assert len(targets) == 1
        proof = bind_source(hierarchy, targets[0], certificate, out / 'usb-source-binding')
        check_hashes(proof['source_sha256'])
        dependencies.update({str(local(p)): h for p, h in proof['source_sha256'].items()})
        for path in (out / 'usb-source-binding').rglob('*'):
            if path.is_file():
                dependencies[str(path)] = sha(path)
        for name in ('plan04_usb_binding.py', 'plan05_usb_fixture.py', 'plan04_screen.py'):
            dependencies[str(Path(__file__).with_name(name))] = sha(Path(__file__).with_name(name))
        dependencies[str(ROOT / 'dv/core/state_equiv.py')] = sha(ROOT / 'dv/core/state_equiv.py')
        bound = bind(old / 'bus-source-qualified01/result.json')
        for key in ('hdl_sha256', 'artifact_sha256', 'library_sha256'):
            check_hashes(bound[key])
            dependencies.update({str(local(p)): h for p, h in bound[key].items()})
        # Old whole-project source hashes are deliberately NOT asserted current.
        # All relevant hardware and current production boundaries are checked below.
        for filename in ('SocResetSlot.sv', 'ResetRelease.sv'):
            historical = old / 'fresh-emit' / filename
            assert str(historical) in bound['hdl_sha256']
            assert sha(fresh / filename) == sha(historical) == bound['hdl_sha256'][str(historical)]
        parent = design[bound['production_parent']]
        wiring = reset_wiring(parent, bound['usb'], bound['source'])
        rejected = []
        for label in ('wrong-slot-reset', 'wrong-clock', 'wrong-bus-wire'):
            bad = copy.deepcopy(parent)
            port = {'wrong-slot-reset': 'reset_n', 'wrong-clock': 'clk', 'wrong-bus-wire': 'target_req'}[label]
            bad['cells'][bound['source']]['connections'][port] = ['0']
            try:
                reset_wiring(bad, bound['usb'], bound['source'])
            except (AssertionError, KeyError):
                rejected.append(label)
            else:
                raise AssertionError('Boundary fault escaped: ' + label)
        original_slot = bind(old / 'unbuffered-slot.json')['modules']['SocResetSlot']
        fixture, rows = buffered_slot(original_slot, mapped, bound)
        expected = bind(old / 'buffered-slot/mapped.json')['modules']['SocResetSlot']
        assert fixture == expected, 'Current fixture differs from the historical physical graph'
        rejected.extend(faults(fixture, original_slot, rows))
        domains = clock_manifest(mapped)
        drivers = unique_drivers(mapped)
        actual_ports = {}
        for row in rows:
            peer = row['peer']
            source = row['production_source']
            if isinstance(source, str):
                actual_ports[peer] = dict(constant=source)
                continue
            name, pin = drivers[source]
            cell = mapped['cells'][name]
            assert pin == 'Q' and cell['type'] == bound['ports'][peer]['type']
            assert domains[name + '/CLK'] == 'main'
            assert cell['connections']['CLK'] == mapped['netnames']['digital.subsystem.usb.appClock']['bits']
            actual_ports[peer] = dict(cell=name, pin=pin, type=cell['type'])
        assert len(actual_ports) == len(bound['ports']) == 73
        check_hashes(dependencies)
        assert snapshot() == frozen, 'Production sources changed during boundary audit'
        receipt.update(status='pass', wiring=wiring, mapped_ports=actual_ports,
                       topology=rows, negative_controls=rejected,
                       fixture_equality='Exact JSON including all cells, connections, constants and aliases',
                       input_sha256=dependencies, production_source_sha256=frozen)
    except Exception as error:
        receipt.update(status='failed', error=repr(error), input_sha256=dependencies)
        raise
    finally:
        receipt['seconds'] = time.monotonic() - begin
        (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS current USB boundary identity; historical timing remains separately scoped')


if __name__ == '__main__':
    main()
