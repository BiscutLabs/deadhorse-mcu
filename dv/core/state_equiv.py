"""Build a one-step inductive equivalence obligation from matched state.

Equal state is the induction relation, not an environmental assumption.
Every state element must match, including clock/reset semantics. Multipliers
are congruence cutpoints: all operand equalities remain proof obligations.
No multiply is passed to the bit-level solver.
"""
import copy
import json

STATE = {'$dff', '$dffe', '$adff', '$adffe', '$aldff', '$aldffe',
         '$sdff', '$sdffe', '$sdffce', '$dlatch', '$adlatch'}


class Mismatch(ValueError):
    """An actual interface/state/structural mismatch, not a tool failure."""


def named_pairs(gold, gate, predicate, output_port, names):
    remaining = {n: c for n, c in gate['cells'].items() if predicate(c)}
    pairs = []
    for gn, gc in gold['cells'].items():
        if not predicate(gc):
            continue
        bits = gc['connections'][output_port]
        aliases = {n: [wire['bits'].index(b) for b in bits]
                   for n, wire in gold['netnames'].items()
                   if all(b in wire['bits'] for b in bits) and not n.startswith('$')}
        matches = set()
        for alias, indices in aliases.items():
            # A translation map adds a spelling; it must not break comparison
            # against the unchanged reference. If both spellings identify
            # different state cells, retain the ambiguity and fail closed.
            for candidate_alias in {alias, names.get(alias, alias)}:
                wire = gate['netnames'].get(candidate_alias)
                if wire is not None and max(indices) < len(wire['bits']):
                    mapped = [wire['bits'][i] for i in indices]
                    matches.update(n for n, cell in remaining.items()
                                   if cell['connections'][output_port] == mapped)
        if not matches and output_port == 'Y':
            # Products may have unnamed/truncated results. Pair by recorded
            # cell name (or the sole remaining operator), then prove operands;
            # naming itself never discharges the congruence obligation.
            cell_name = names.get('@cell:' + gn, gn)
            if cell_name in remaining:
                matches.add(cell_name)
            elif len(remaining) == 1:
                matches.update(remaining)
        if len(matches) != 1:
            raise Mismatch(f'No unique named {output_port} match for {gn}: {aliases}; matches={sorted(matches)}')
        cn = matches.pop()
        pairs.append((gn, gc, cn, remaining.pop(cn)))
    if remaining:
        raise Mismatch(f'Unmatched candidate elements: {sorted(remaining)}')
    return pairs


def initials(module):
    result = {}
    for name, wire in module['netnames'].items():
        value = wire.get('attributes', {}).get('init')
        if value is not None:
            for bit, initial in zip(wire['bits'], reversed(value)):
                if bit in result and result[bit] != initial:
                    raise ValueError(f'Conflicting initial values: {name}')
                result[bit] = initial
    return result


def cut(gold_design, gate_design, module, mapping):
    gold_design, gate_design = copy.deepcopy(gold_design), copy.deepcopy(gate_design)
    gold, gate = [d['modules'][module] for d in (gold_design, gate_design)]
    if set(gold['ports']) != set(gate['ports']):
        raise Mismatch('Port names differ')
    for name, port in gold['ports'].items():
        other = gate['ports'][name]
        if port['direction'] != other['direction'] or len(port['bits']) != len(other['bits']):
            raise Mismatch(f'Port direction/width differs: {name}')
        if port['direction'] not in ('input', 'output'):
            raise ValueError(f'Unsupported port direction: {name}')
    for design in (gold, gate):
        for name, cell in design['cells'].items():
            if any(word in cell['type'].lower() for word in ('dff', 'latch', 'mem')) and cell['type'] not in STATE:
                raise ValueError(f'Unsupported state cell {name}: {cell["type"]}')
    states = named_pairs(gold, gate, lambda c: c['type'] in STATE, 'Q', mapping)
    products = named_pairs(gold, gate, lambda c: c['type'] == '$mul', 'Y', mapping)
    initial = [initials(d) for d in (gold, gate)]
    state_bits = [set() for _ in range(2)]
    for index, (gn, gc, cn, cc) in enumerate(states):
        if gc['type'] != cc['type'] or gc['parameters'] != cc['parameters']:
            raise Mismatch(f'State kind/reset/width/polarity differs: {gn} / {cn}')
        for side, cell in enumerate((gc, cc)):
            state_bits[side].update(cell['connections']['Q'])
        for a, b in zip(gc['connections']['Q'], cc['connections']['Q']):
            if initial[0].get(a, 'x') != initial[1].get(b, 'x'):
                raise Mismatch(f'Initial state differs: {gn} / {cn}')
    if any(set(values) - bits for values, bits in zip(initial, state_bits)):
        raise ValueError('Initial attribute outside matched state')
    for index, (gn, gc, cn, cc) in enumerate(products):
        if gc['parameters'] != cc['parameters']:
            raise Mismatch(f'Multiply width/signedness differs: {gn} / {cn}')
    for kind, pairs, out_port in (('state', states, 'Q'), ('product', products, 'Y')):
        for index, (gn, gc, cn, cc) in enumerate(pairs):
            if gc['port_directions'] != cc['port_directions']:
                raise Mismatch(f'Cell interface differs: {gn} / {cn}')
            for port, direction in gc['port_directions'].items():
                if len(gc['connections'][port]) != len(cc['connections'][port]):
                    raise Mismatch(f'Cell port width differs: {gn}.{port}')
                name = f'__equiv_{kind}_{index}_{port}'
                for design, cell in ((gold, gc), (gate, cc)):
                    if name in design['ports']:
                        raise ValueError('Reserved proof port collision')
                    design['ports'][name] = {'direction': 'input' if port == out_port else 'output',
                                             'bits': cell['connections'][port]}
            del gold['cells'][gn]
            del gate['cells'][cn]
    for design in (gold, gate):
        for wire in design['netnames'].values():
            wire.get('attributes', {}).pop('init', None)
    return gold_design, gate_design, {'state_elements': len(states), 'multiply_operators': len(products),
        'relation': 'equal named state; reset structure/values, clocks, enables, next state and outputs checked',
        'multiply': 'shared symbolic results, with every corresponding operand proved equal'}


def prepare(gold, candidate, module, output, mapping):
    designs = [json.loads(p.read_text()) for p in (gold, candidate)]
    a, b, evidence = cut(*designs, module, mapping)
    paths = [output/'gold-cut.json', output/'candidate-cut.json']
    for path, design in zip(paths, (a, b)):
        path.write_text(json.dumps(design))
    return *paths, evidence
