"""OpenROAD Python scan-replacement qualification; no chain/coverage claim.

Run with T37_SCAN_CONFIG naming a JSON config under build/. The original ODB
is read only. A generated candidate is deliberately not treated as placed.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from scan_cells import PREFIX, groups, qualify


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(block):
    result = {}
    for inst in block.getInsts():
        pins, power = {}, {}
        for term in inst.getITerms():
            net = term.getNet()
            if str(term.getMTerm().getSigType()) in ('POWER', 'GROUND'):
                power[term.getMTerm().getName()] = (str(term.getMTerm().getSigType()), net.getName() if net else None)
                continue
            pins[term.getMTerm().getName()] = net.getName() if net else None
        result[inst.getName()] = dict(type=inst.getMaster().getName(), pins=pins, power=power)
    return result


def boundary(block):
    return {p.getName(): (str(p.getIoType()), str(p.getSigType()), p.getNet().getName() if p.getNet() else None)
            for p in block.getBTerms()}


def audit(before, after, inversions):
    if set(after) != set(before) | {r['cell'] for r in inversions.values()}:
        raise ValueError('Added or removed unrelated cells')
    pairs = Counter()
    for name, old in before.items():
        new = after[name]
        if not re.fullmatch(re.escape(PREFIX) + r'dff(?:q|rnq|snq|nrnq)_[1248]', old['type']):
            if new != old:
                raise ValueError('Changed non-FF: ' + name)
            continue
        expected = dict(old['pins'])
        if name in inversions:
            row = inversions[name]
            source = expected.pop('CLKN')
            expected['CLK'] = row['net']
            if after[row['cell']] != dict(type=PREFIX + 'clkinv_4', pins={'I': source, 'ZN': row['net']}, power=old['power']):
                raise ValueError('Wrong negative-edge clock inverter')
        if new['power'] != old['power']:
            raise ValueError('Changed supply/well connection: ' + name)
        if {p: n for p, n in new['pins'].items() if p not in ('SI', 'SE')} != expected:
            raise ValueError('Changed functional D/clock/reset/Q pin: ' + name)
        if set(new['pins']) != set(expected) | {'SI', 'SE'}:
            raise ValueError('Missing scan pins: ' + name)
        if any(new['pins'][p] is not None for p in ('SI', 'SE')):
            raise ValueError('Replacement-only pilot unexpectedly connected scan')
        pairs[old['type'], new['type']] += 1
    return pairs


def main():
    import odb
    import openroad
    config_path = Path(os.environ['T37_SCAN_CONFIG']).resolve()
    config_path.relative_to(ROOT / 'build')
    config = json.loads(config_path.read_text())
    out = (ROOT / config['output']).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    receipt = dict(result='error', scope='Replacement pilot only; no stitching, placement, timing or ATPG coverage',
                   source_commit=config['source_commit'], config_sha256=sha(config_path),
                   scripts={str(p.relative_to(ROOT)): sha(p) for p in (
                       Path(__file__), Path(__file__).with_name('scan_cells.py'),
                       Path(__file__).with_name('usb_cells.py'), ROOT / 'tools/timing/usb_boundary.py',
                       ROOT / 'phys/gf180-ws-1x1/pdk-lock.json')})
    try:
        source = ROOT / config['odb']
        if sha(source) != config['odb_sha256']:
            raise ValueError('Unauthenticated ODB')
        executable = Path(config['openroad'])
        if sha(executable) != config['openroad_sha256']:
            raise ValueError('Unauthenticated OpenROAD')
        lock = json.loads((ROOT / 'phys/gf180-ws-1x1/pdk-lock.json').read_text())
        libdir = ROOT / config['libdir']
        libraries = sorted(libdir.glob('*.lib'))
        if len(libraries) != 15:
            raise ValueError('Incomplete library corner inventory')
        receipt['inputs'] = {str(source): sha(source), str(executable): sha(executable)}
        for library in libraries:
            digest = sha(library)
            if digest != lock['files'][library.name]:
                raise ValueError('Unauthenticated Liberty: ' + library.name)
            receipt['inputs'][str(library)] = digest
        tech = openroad.Tech()
        tech.readLiberty(str(libdir / (PREFIX + 'tt_025C_3v30.lib')))
        design = openroad.Design(tech)
        design.readDb(str(source))
        db, block = tech.getDB(), design.getBlock()
        before = snapshot(block)
        before_boundary = boundary(block)
        inversions = {}
        for name, cell in before.items():
            match = re.fullmatch(re.escape(PREFIX) + r'dffnrnq_([1248])', cell['type'])
            if not match:
                continue
            inst = block.findInst(name)
            nets = {t.getMTerm().getName(): t.getNet() for t in inst.getITerms()}
            # Preserve every signal and supply connection. The temporary positive
            # FF is then replaced by OpenROAD, just like every other scan FF.
            row = dict(cell=name + '_t37_clock_inverter', net=name + '_t37_inverted_clock')
            if block.findInst(row['cell']) or block.findNet(row['net']):
                raise ValueError('Reserved inverter name collision')
            net = odb.dbNet.create(block, row['net'])
            net.setSigType('CLOCK')
            inverter = odb.dbInst.create(block, db.findMaster(PREFIX + 'clkinv_4'), row['cell'])
            inverter.findITerm('I').connect(nets['CLKN'])
            inverter.findITerm('ZN').connect(net)
            odb.dbInst.destroy(inst)
            replacement = odb.dbInst.create(block, db.findMaster(PREFIX + 'dffrnq_' + match[1]), name)
            for p, n in nets.items():
                if p == 'CLKN':
                    replacement.findITerm('CLK').connect(net)
                elif n is not None:
                    replacement.findITerm(p).connect(n)
                    if inverter.findITerm(p) and p in ('VDD', 'VSS', 'VNW', 'VPW'):
                        inverter.findITerm(p).connect(n)
            inversions[name] = row
        for command in ('set_dft_config -clock_mixing no_mix -max_chains 1', 'scan_replace'):
            design.evalTclString(command)
        after = snapshot(block)
        if boundary(block) != before_boundary:
            raise ValueError('Changed package boundary connection')
        receipt['boundary_ports_preserved'] = len(before_boundary)
        pairs = audit(before, after, inversions)
        receipt['replacement_counts'] = [{'old': a, 'new': b, 'count': n} for (a, b), n in sorted(pairs.items())]
        receipt['inversions'] = inversions
        receipt['qualified_views'] = {}
        for library in libraries:
            cells = dict(groups(library.read_text(), 'cell'))
            qualified = [qualify(cells, a, b) for a, b in pairs]
            # The inverter equation is part of the negative-edge proof.
            from usb_cells import signature
            inv = signature(cells[PREFIX + 'clkinv_4'])
            if inv['ff'] or inv['pins']['ZN']['function'] not in ('!I', '(!I)'):
                raise ValueError('Inverter is not clock complement')
            receipt['qualified_views'][library.name] = qualified
        victim = next(n for n, c in before.items() if c['type'].startswith(PREFIX + 'dffrnq_'))
        receipt['negative_controls'] = {}
        for pin in ('D', 'RN'):
            term = block.findInst(victim).findITerm(pin)
            original_net = term.getNet()
            wrong_net = block.findInst(victim).findITerm('Q').getNet()
            if original_net == wrong_net:
                raise ValueError('Ineffective fault selection')
            term.connect(wrong_net)
            try:
                audit(before, snapshot(block), inversions)
            except ValueError as error:
                receipt['negative_controls'][pin] = dict(error=str(error), instance=victim,
                    original_net=original_net.getName(), injected_net=wrong_net.getName())
            else:
                raise ValueError('Fault escaped functional pin audit: ' + pin)
            finally:
                term.connect(original_net)
        if audit(before, snapshot(block), inversions) != pairs:
            raise ValueError('Fault restoration changed candidate')
        # Same inventory multiplied by cell areas: measured mapped replacement
        # delta only, not placed-fit or routed-headroom evidence.
        cells = dict(groups((libdir / (PREFIX + 'tt_025C_3v30.lib')).read_text(), 'cell'))
        def area(n):
            return float(re.search(r'\barea\s*:\s*([\d.]+)\s*;', cells[n])[1])
        receipt['replacement_area_delta_um2'] = sum(n * (area(b) - area(a)) for (a, b), n in pairs.items()) + len(inversions) * area(PREFIX + 'clkinv_4')
        target = out / 'replacement.odb'
        design.writeDb(str(target))
        receipt['output_sha256'] = sha(target)
        receipt['result'] = 'pass_replacement_only'
        print('PASS scan replacement and functional cell/pin qualification:', sum(pairs.values()), 'FFs')
    except Exception as error:
        receipt['error'] = repr(error)
        raise
    finally:
        receipt['wall_seconds'] = time.monotonic() - started
        (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
