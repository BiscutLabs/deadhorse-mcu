"""Compose mapped production USB and its registered bus slot for boundary STA.

This is a physical measurement fixture, not another production configuration.
The three slot control inputs name upstream production boundaries; their reset
sequencing is not signed off by this fixture. No logic is synthesized here.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compose(usb, slot):
    result = copy.deepcopy(usb)
    integers = {b for n in (usb, slot) for c in n['cells'].values()
                for bs in c['connections'].values() for b in bs if isinstance(b, int)}
    integers.update(b for n in (usb, slot) for p in n['ports'].values()
                    for b in p['bits'] if isinstance(b, int))
    next_bit = max(integers) + 1
    mapping = {}
    bindings = {}
    for name, port in slot['ports'].items():
        if name == 'clk':
            bits = usb['ports']['appClock']['bits']
        elif name.startswith('target_'):
            peer = 'bus_' + name.removeprefix('target_')
            other = usb['ports'][peer]
            if other['direction'] == port['direction']:
                raise ValueError('Bus directions do not oppose')
            bits = other['bits']
            bindings[name] = peer
        else:
            continue
        if len(bits) != len(port['bits']):
            raise ValueError('Port width differs')
        for old, new in zip(port['bits'], bits):
            if old in mapping and mapping[old] != new:
                raise ValueError('Conflicting shared port alias')
            mapping[old] = new

    boundary_mapping = dict(mapping)

    def remap(bit):
        nonlocal next_bit
        if not isinstance(bit, int):
            return bit
        if bit not in mapping:
            mapping[bit] = next_bit
            next_bit += 1
        return mapping[bit]

    for name, cell in slot['cells'].items():
        key = 'source_slot_' + name
        if key in result['cells']:
            raise ValueError('Cell name collision')
        new = copy.deepcopy(cell)
        new['connections'] = {p: list(map(remap, bs)) for p, bs in cell['connections'].items()}
        result['cells'][key] = new
    for name, net in slot['netnames'].items():
        key = 'source_slot_' + name
        if key in result['netnames']:
            raise ValueError('Net name collision')
        result['netnames'][key] = dict(copy.deepcopy(net), bits=list(map(remap, net['bits'])))
    for name in list(result['ports']):
        if name.startswith('bus_'):
            del result['ports'][name]
    for name, port in slot['ports'].items():
        if name == 'clk' or name.startswith('target_'):
            continue
        result['ports']['source_slot_' + name] = dict(copy.deepcopy(port), bits=list(map(remap, port['bits'])))

    # Exact reversible projections, including every cell pin. No hidden merge
    # of source nets is permitted, beyond the explicitly connected ports.
    allocated = {k: v for k, v in mapping.items() if k not in boundary_mapping}
    if (len(set(allocated.values())) != len(allocated) or
            set(allocated.values()) & set(boundary_mapping.values())):
        raise ValueError('Internal source nets were merged')
    for name, cell in usb['cells'].items():
        if result['cells'][name] != cell:
            raise ValueError('USB logic changed')
    for name, cell in slot['cells'].items():
        restored = copy.deepcopy(result['cells']['source_slot_' + name])
        expected = {p: list(map(remap, bs)) for p, bs in cell['connections'].items()}
        if restored['connections'] != expected:
            raise ValueError('Slot pin mapping changed')
        restored['connections'] = copy.deepcopy(cell['connections'])
        if restored != cell:
            raise ValueError('Slot logic changed')
    if len(result['cells']) != len(usb['cells']) + len(slot['cells']):
        raise ValueError('Cell inventory mismatch')
    return result, dict(bindings=bindings, source_bit_map=mapping, boundary_bit_map=boundary_mapping,
                        usb_cells=len(usb['cells']), slot_cells=len(slot['cells']),
                        projection='Exact original USB and reversible slot cell/pin graphs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('usb', 'slot', 'binding', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.binding.read_text())
    if receipt['status'] != 'source-bound-hold-model':
        raise ValueError('Missing production bus binding')
    for group in ('source_sha256', 'hdl_sha256', 'artifact_sha256', 'library_sha256'):
        for path, expected in receipt[group].items():
            if digest(path) != expected:
                raise ValueError('Changed production binding input: ' + path)
    if str(args.slot.resolve()) not in receipt['artifact_sha256']:
        raise ValueError('Source slot is not the authenticated mapped model')
    usb = json.loads(args.usb.read_text())['modules']['Usb']
    slot = json.loads(args.slot.read_text())['modules']['SocResetSlot']
    model, audit = compose(usb, slot)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'composed.json').write_text(json.dumps({'modules': {'Usb': model}}) + '\n')
    audit.update(status='composed', input_sha256={str(p): digest(p) for p in (args.usb, args.slot, args.binding, Path(__file__))},
                 qualification='Boundary-only physical fixture; source control reset sequencing and whole-chip placement remain separate obligations.')
    (args.output / 'composition.json').write_text(json.dumps(audit, indent=2) + '\n')
    print('COMPOSED exact USB and registered source graphs')


if __name__ == '__main__':
    main()
