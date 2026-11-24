"""Reconcile every mapped crossing endpoint with source state; never waive it.

This is a connectivity inventory, not equivalence, CDC or RDC signoff. A unique
alias identity is not proof that mapping preserved the register's transition
function. Ambiguous, inverted, constant and missing identities remain explicit.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.timing.usb_boundary import groups


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_same_hierarchy(expected, regenerated):
    if expected != regenerated:
        raise ValueError('Hierarchy differs from sealed-emission replay')


def verify_hashes(base, hashes):
    for name, expected in hashes.items():
        path = (base / name).resolve()
        path.relative_to(base.resolve())
        if digest(path) != expected:
            raise ValueError('Changed authenticated input: ' + name)


def authenticate_hierarchy(base, output, mapping, lib):
    """Replay only the original frontend, from the sealed emitted file list."""
    files = [ROOT / name for name in mapping['emitted_sha256']]
    for name, expected in mapping['emitted_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Changed mapped emission: ' + name)
    definitions = {
        'LfRcMacro': {'vdd': ('inout', 1), 'vss': ('inout', 1), 'enable': ('input', 1),
                      'trim': ('input', 6), 'test': ('input', 1), 'clock': ('output', 1), 'ready': ('output', 1)},
        'PorBrownoutMacro': {'vdd': ('inout', 1), 'vss': ('inout', 1), 'threshold': ('input', 2),
                            'test': ('input', 1), 'supplyReset_n': ('output', 1),
                            'powerOn_n': ('output', 1), 'brownout': ('output', 1)}}
    analog = {'modules': {}}
    for name, ports in definitions.items():
        module = dict(attributes={'blackbox': '1'}, ports={}, cells={}, netnames={})
        bit = 2
        for pin, (direction, width) in ports.items():
            bits = list(range(bit, bit + width)); bit += width
            module['ports'][pin] = dict(direction=direction, bits=bits)
            module['netnames'][pin] = dict(hide_name=0, bits=bits, attributes={})
        analog['modules'][name] = module
    # Preserve the old import's source paths and order exactly; only the output
    # path changes. The analog port view is reconstructed and compared first.
    analog_path = base / 'map/analog-interfaces.json'
    if json.loads(analog_path.read_text()) != analog:
        raise ValueError('Analog interface differs from audited port view')
    script = output / 'import.ys'
    script.write_text('\n'.join([
        f'read_liberty -lib {lib.resolve()}', f'read_json {analog_path.resolve()}',
        'read_slang --keep-hierarchy -DSYNTHESIS --top DeadhorseSoc ' + ' '.join(map(str, files)),
        'hierarchy -check -top DeadhorseSoc', 'proc', 'chformal -remove', 'memory_collect',
        f'write_json {(output / "hier.json").resolve()}']) + '\n')
    command = ['yosys', '-Q', '-T', '-s', str(script)]
    tool = Path(shutil.which('yosys'))
    tool_hash = digest(tool)
    with (output / 'import.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    if digest(tool) != tool_hash:
        raise ValueError('Frontend changed during import')
    regenerated = json.loads((output / 'hier.json').read_text())
    require_same_hierarchy(json.loads((base / 'map/hier.json').read_text()), regenerated)
    if any(digest(ROOT / name) != h for name, h in mapping['emitted_sha256'].items()):
        raise ValueError('Emission changed during import')
    return dict(status='exact_frontend_replay', command=command, yosys_sha256=tool_hash,
                hierarchy_sha256=digest(output / 'hier.json'),
                source_sha256=mapping['emitted_sha256'], analog_view_sha256=digest(analog_path))


def local_reset_evidence(proof_dir, base, modules, reconciliation):
    """Attach the direct local property only; never promote it to a path waiver."""
    proof_dir.resolve().relative_to(ROOT / 'build')
    receipt = json.loads((proof_dir / 'result.json').read_text())
    if receipt['status'] != 'pass' or not receipt.get('artifact_sha256'):
        raise ValueError('Missing sealed successful local proof')
    verify_hashes(ROOT, receipt['source_sha256'])
    verify_hashes(proof_dir, receipt['artifact_sha256'])
    statuses = {Path(r['command'][2]).name: r['status'] for r in receipt['runs'] if 'status' in r}
    if statuses.get('side_correct') != 'PASS' or statuses.get('side_early_release') != 'FAIL' or statuses.get('side_cover') != 'PASS':
        raise ValueError('Missing direct reset proof, fault or cover')
    production = base / 'emit/ResetRelease.sv'
    proof_source = proof_dir / 'side_correct/src/ResetRelease.sv'
    if production.read_bytes() != proof_source.read_bytes():
        raise ValueError('Production ResetRelease differs from proved child HDL')
    matched = {}
    for key, instance in reconciliation['instances'].items():
        source = modules[instance['module']].get('attributes', {}).get('src', '').rsplit(':', 1)[0]
        if source and (ROOT / source).resolve() == production.resolve():
            state_ids = {s for s, v in reconciliation['states'].items() if v['instance'] == key}
            mapped_states = {name: b for name, b in reconciliation['bindings'].items()
                             if state_ids.intersection(b['states'])}
            matched[key] = dict(source_states=sorted(state_ids), mapped_candidates=mapped_states,
                bindings=instance['bindings'], status='local_source_property_only')
    if not matched:
        raise ValueError('No source ResetRelease instances found')
    return dict(status='direct_local_proof_bound_to_identical_child_hdl', instances=matched,
        receipt=str(proof_dir / 'result.json'), receipt_sha256=digest(proof_dir / 'result.json'),
        child_sha256=digest(production), model_sha256=digest(proof_dir / 'side_correct/model/design.json'),
        property='ResetRelease.released equals completion of two local rising edges since reset assertion',
        assumptions=receipt['assumptions'],
        limits='Local source property only. Mapped aliases do not prove transition equivalence. No analog metastability, reset distribution, clock readiness, reset epoch or whole-path CDC/RDC qualification. Other FIFO/Gray proofs are not applied to different parameters or inferred synchronizer guarantees.')


class Nets:
    """Identity-only union, with constants attached rather than globally joined."""
    def __init__(self):
        self.parent = {}
        self.constants = {}

    def root(self, node):
        parent = self.parent.setdefault(node, node)
        if parent != node:
            self.parent[node] = self.root(parent)
        return self.parent[node]

    def constant(self, node, value):
        root = self.root(node)
        if root in self.constants and self.constants[root] != value:
            raise ValueError('Conflicting constant bindings')
        self.constants[root] = value

    def join(self, left, right):
        a, b = self.root(left), self.root(right)
        if a == b:
            return
        ca, cb = self.constants.get(a), self.constants.get(b)
        if ca is not None and cb is not None and ca != cb:
            raise ValueError('Conflicting constant bindings')
        self.parent[b] = a
        if cb is not None:
            self.constants[a] = cb
        self.constants.pop(b, None)

    def connect(self, left_path, left, right_path, right):
        if isinstance(left, int) and isinstance(right, int):
            self.join((left_path, left), (right_path, right))
        elif isinstance(left, int):
            self.constant((left_path, left), right)
        elif isinstance(right, int):
            self.constant((right_path, right), left)
        elif left != right:
            raise ValueError('Conflicting constant ports')


def identity_cells(liberty):
    """Accept only the explicit two-pin, noninverting Liberty identity function."""
    result = {}
    for name, body in groups(liberty, 'cell'):
        pins = dict(groups(body, 'pin'))
        if set(pins) != {'I', 'Z'}:
            continue
        directions = {p: re.findall(r'\bdirection\s*:\s*(\w+)\s*;', b)
                      for p, b in pins.items()}
        functions = re.findall(r'\bfunction\s*:\s*"([^"]*)"\s*;', pins['Z'])
        if (directions == {'I': ['input'], 'Z': ['output']}
                and len(functions) == 1
                and re.sub(r'[\s()]', '', functions[0]) == 'I'
                and not list(groups(body, 'ff')) and not list(groups(body, 'latch'))):
            result[name] = ('I', 'Z')
    return result


def reconcile(modules, top, mapped, registers, identities):
    nets = Nets()
    instances, states, state_nodes, aliases = {}, {}, {}, defaultdict(list)
    sockets, other_storage = [], {}

    def visit(path, typ, ancestors):
        if typ in ancestors:
            raise ValueError('Recursive source hierarchy')
        module = modules[typ]
        key = json.dumps(path, separators=(',', ':'))
        instances[key] = dict(path=path, module=typ, ports=module.get('ports', {}), bindings={})
        if int(str(module.get('attributes', {}).get('blackbox', '0')), 2):
            sockets.append(key)
        for name, net in module.get('netnames', {}).items():
            if net.get('hide_name'):
                continue
            for index, bit in enumerate(net['bits']):
                if isinstance(bit, int):
                    aliases['.'.join((*path, name)) + f'[{index}]'].append((path, bit))
        for name, cell in module.get('cells', {}).items():
            kind, connections = cell['type'], cell['connections']
            child_path = (*path, name)
            if kind in modules:
                child = modules[kind]
                ports = child.get('ports', {})
                missing = set(ports) - set(connections)
                if set(connections) - set(ports) or any(ports[p]['direction'] != 'output' for p in missing):
                    raise ValueError('Incomplete instance port binding: ' + str(child_path))
                visit(child_path, kind, (*ancestors, typ))
                bindings = instances[json.dumps(child_path, separators=(',', ':'))]['bindings']
                for port in missing:
                    bindings[port] = dict(direction='output', formal=ports[port]['bits'],
                                          status='unconnected_output')
                for port, actual in connections.items():
                    formal = child['ports'][port]['bits']
                    if len(actual) != len(formal):
                        raise ValueError('Port width mismatch')
                    bindings[port] = dict(parent_path=path, actual=actual, formal=formal,
                                          direction=child['ports'][port]['direction'])
                    for a, b in zip(actual, formal):
                        nets.connect(path, a, child_path, b)
            elif kind in ('$buf', '$pos'):
                if len(connections['A']) != len(connections['Y']):
                    raise ValueError('Nonidentity source buffer width')
                for a, b in zip(connections['A'], connections['Y']):
                    nets.connect(path, a, path, b)
            elif re.fullmatch(r'\$(?:a|s)?dff(?:e|ce|sr|sre)?|\$aldff(?:e)?', kind):
                for index, bit in enumerate(connections['Q']):
                    identity = json.dumps((*child_path, 'Q', index), separators=(',', ':'))
                    state_nodes[identity] = (path, bit)
                    states[identity] = dict(instance=key, cell=name, kind=kind, bit=index,
                        local_aliases=[n + f'[{j}]' for n, net in module.get('netnames', {}).items()
                                       for j, b in enumerate(net['bits']) if b == bit and not net.get('hide_name')],
                        connections=connections, parameters=cell.get('parameters', {}),
                        src=cell.get('attributes', {}).get('src'))
            elif any(token in kind.lower() for token in ('latch', 'mem', 'ff', '$sr')):
                # Memories and retained vendor latch structures are not FF Q
                # identities. Preserve their complete bindings without inventing
                # a mapping to the optimized register-only inventory.
                other_storage[json.dumps(child_path, separators=(',', ':'))] = dict(
                    instance=key, cell=name, kind=kind, connections=connections,
                    parameters=cell.get('parameters', {}), attributes=cell.get('attributes', {}),
                    status='source_storage_unbound',
                    scope='Not FF-alias certified; cut/socket or mapped implementation requires separate mapping evidence')

    visit((), top, ())
    roots = defaultdict(set)
    for identity, node in state_nodes.items():
        roots[nets.root(node)].add(identity)
        states[identity]['constant'] = nets.constants.get(nets.root(node))
    catalog = {name: set().union(*(roots[nets.root(node)] for node in nodes))
               for name, nodes in aliases.items()}

    mnets = Nets()
    for cell in mapped['cells'].values():
        if cell['type'] in identities:
            a, b = identities[cell['type']]
            if (cell['port_directions'].get(a) != 'input'
                    or cell['port_directions'].get(b) != 'output'
                    or len(cell['connections'][a]) != 1 or len(cell['connections'][b]) != 1):
                raise ValueError('Mapped identity pin mismatch')
            mnets.connect((), cell['connections'][a][0], (), cell['connections'][b][0])
    mapped_aliases = defaultdict(list)
    for name, net in mapped.get('netnames', {}).items():
        if not net.get('hide_name'):
            for index, bit in enumerate(net['bits']):
                if isinstance(bit, int):
                    mapped_aliases[mnets.root(((), bit))].append(name + f'[{index}]')
    bindings = {}
    for name, register in registers.items():
        cell = mapped['cells'][name]
        candidates, matched, unsupported = set(), set(), {}
        for pin, bits in cell['connections'].items():
            if cell['port_directions'][pin] != 'output':
                continue
            if pin != 'Q':
                unsupported[pin] = bits  # QN is NOT a positive-polarity state alias.
                continue
            for bit in bits:
                for alias in mapped_aliases[mnets.root(((), bit))]:
                    if catalog.get(alias):
                        candidates.update(catalog[alias])
                        matched.add(alias)
        status = ('unsupported_output' if unsupported else 'unbound' if not candidates else
                  'merged_or_ambiguous' if len(candidates) != 1 else
                  'constant_state' if states[next(iter(candidates))]['constant'] is not None else 'unique')
        bindings[name] = dict(status=status, states=sorted(candidates), matched_aliases=sorted(matched),
                              unsupported_outputs=unsupported, clock_reset=register)
    used = {state for b in bindings.values() for state in b['states']}
    return dict(instances=instances, states=states, bindings=bindings, sockets=sockets,
                other_storage=other_storage,
                unmapped_source_states=sorted(set(states) - used))


def account_rows(rows, bindings, mapped):
    """Join ALL input rows; dictionary joins retain all merged endpoint owners."""
    counts, statuses = Counter(), Counter()
    missing_reset_origins = defaultdict(list)
    for row in rows:
        destination, pin = row['destination'].rsplit('/', 1)
        if destination not in bindings or pin not in mapped['cells'][destination]['connections']:
            raise ValueError('Uninventoried destination')
        if not 0 <= int(row['destination_bit']) < len(mapped['cells'][destination]['connections'][pin]):
            raise ValueError('Invalid destination bit')
        if row['destination_domain'] != bindings[destination]['clock_reset']['domain']:
            raise ValueError('Destination domain mismatch')
        source, source_pin = row['source'].rsplit('/', 1)
        if source in bindings:
            cell = mapped['cells'][source]
            if cell['port_directions'].get(source_pin) != 'output':
                raise ValueError('Not a register output')
            if row['source_domain'] != bindings[source]['clock_reset']['domain']:
                raise ValueError('Source domain mismatch')
            source_status = bindings[source]['status'] if source_pin == 'Q' else 'unsupported_output'
        else:
            port = mapped['ports'].get(source)
            if (not port or port['direction'] != 'input' or row['source_domain'] != 'external'
                    or not 0 <= int(source_pin) < len(port['bits'])):
                raise ValueError('Uninventoried source')
            source_status = 'external_port'
        counts[row['kind']] += 1
        statuses[(row['kind'], source_status, bindings[destination]['status'])] += 1
        if row['kind'] == 'reset':
            missing_reset_origins[row['destination']].append(row['source'])
    return dict(counts=dict(counts), statuses=[dict(kind=k[0], source=k[1], destination=k[2], count=v)
                for k, v in sorted(statuses.items())], reset_origins=dict(missing_reset_origins))


def run(base, output, cdc_proof=None):
    start = time.monotonic()
    base.resolve().relative_to(ROOT / 'build')
    output.resolve().relative_to(ROOT / 'build')
    if output.exists():
        raise ValueError('Output already exists')
    mapping = json.loads((base / 'map/result.json').read_text())
    prior = json.loads((base / 'crossing-inventory/result.json').read_text())
    lib = next(Path(p) for p, h in mapping['input_sha256'].items()
               if p.endswith('.lib') and h == mapping['liberty_sha256'])
    inputs = [base / 'map/hier.json', base / 'map/canonical.json', base / 'map/result.json', lib,
              base / 'crossing-inventory/result.json', Path(__file__),
              ROOT / 'tools/timing/usb_boundary.py']
    for name, expected in prior['artifact_sha256'].items():
        path = base / 'crossing-inventory' / name
        if digest(path) != expected:
            raise ValueError('Changed crossing artifact: ' + name)
        inputs.append(path)
    for name, expected in prior['input_sha256'].items():
        if digest(name) != expected:
            raise ValueError('Changed inventory input: ' + name)
    hashes = {str(p): digest(p) for p in inputs}
    output.mkdir(parents=True)
    hierarchy = authenticate_hierarchy(base, output, mapping, lib)
    modules = json.loads((base / 'map/hier.json').read_text())['modules']
    mapped = json.loads((base / 'map/canonical.json').read_text())['modules']['DeadhorseSoc']
    registers = json.loads((base / 'crossing-inventory/registers.json').read_text())
    result = reconcile(modules, 'DeadhorseSoc', mapped, registers, identity_cells(lib.read_text()))
    if cdc_proof:
        result['local_reset_evidence'] = local_reset_evidence(cdc_proof, base, modules, result)
    with (base / 'crossing-inventory/paths.csv').open(newline='') as stream:
        accounting = account_rows(csv.DictReader(stream), result['bindings'], mapped)
    measured = prior['counts_measured']
    expected = dict(cdc=measured['cdc_candidates'], rdc=measured['rdc_candidates'],
                    external=measured['external_data'], reset=measured['reset_origins'])
    if accounting['counts'] != expected or len(registers) != measured['registers']:
        raise ValueError('Crossing row conservation failed')
    for name, data in result.items():
        (output / (name + '.json')).write_text(json.dumps(data, indent=2) + '\n')
    (output / 'accounting.json').write_text(json.dumps(accounting, indent=2) + '\n')
    if any(digest(p) != h for p, h in hashes.items()):
        raise ValueError('Input changed during binding')
    receipt = dict(status='reconciled_not_qualified', input_sha256=hashes,
        counts_measured=dict(instances=len(result['instances']), source_states=len(result['states']),
            mapped_registers=len(registers), statuses=dict(Counter(b['status'] for b in result['bindings'].values())),
            rows=accounting['counts'], unmapped_source_states=len(result['unmapped_source_states']),
            other_storage=dict(Counter(s['kind'] for s in result['other_storage'].values()))),
        seconds=time.monotonic() - start, command=sys.argv,
        scope='All structural rows joined to full endpoint identity sets and reset cohorts. No CDC/RDC waiver, mapping equivalence or composition proof. Any attached local property retains its own exact scope.',
        hierarchy_provenance=hierarchy,
        artifact_sha256={p.name: digest(p) for p in output.iterdir() if p.is_file()})
    (output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(status=receipt['status'], counts=receipt['counts_measured'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cdc-proof', type=Path)
    args = parser.parse_args()
    run(args.base, args.output, args.cdc_proof)
