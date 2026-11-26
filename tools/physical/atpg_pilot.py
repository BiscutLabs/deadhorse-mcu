"""Small ATPG interface pilot on an extracted production cone, not scan signoff.

Uses only real primary inputs / FF Q as cut inputs and one capture D as output.
No automatic FF exposure, SRAM cut or production fault-coverage claim.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def primitive(cell):
    match = re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__((?:nand|and|nor|or|xnor|xor)[234]|inv|buf)_\d+', cell['type'])
    if not match:
        raise ValueError('Not a pilot primitive')
    inputs = sorted(p for p, d in cell['port_directions'].items() if d == 'input')
    outputs = [p for p, d in cell['port_directions'].items() if d == 'output']
    if len(outputs) != 1 or any(len(v) != 1 for v in cell['connections'].values()):
        raise ValueError('Non-scalar primitive')
    return re.sub(r'\d', '', match[1]).upper().replace('INV', 'NOT'), inputs, outputs[0]


def select(module):
    cells = module['cells']
    drivers = {}
    leaves = {b for p in module['ports'].values() if p['direction'] == 'input' for b in p['bits']}
    for name, c in cells.items():
        if re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dff\w*_\d+', c['type']):
            leaves.update(c['connections']['Q'])
        for p, direction in c['port_directions'].items():
            if direction == 'output':
                for b in c['connections'][p]:
                    if b in drivers:
                        raise ValueError('Multiple drivers')
                    drivers[b] = name
    for capture, c in sorted(cells.items()):
        if c['type'] != 'gf180mcu_fd_sc_mcu7t5v0__dffrnq_1':
            continue
        ordered, roots, visiting = {}, set(), set()
        def visit(bit):
            if bit in leaves:
                roots.add(bit)
                return
            if not isinstance(bit, int) or bit not in drivers or len(visiting) > 8:
                raise ValueError('Unsupported cone')
            name = drivers[bit]
            if name in ordered:
                return
            if name in visiting:
                raise ValueError('Cycle')
            visiting.add(name)
            gate = cells[name]
            _, inputs, _ = primitive(gate)
            for pin in inputs:
                visit(gate['connections'][pin][0])
            ordered[name] = gate
            visiting.remove(name)
        try:
            target = c['connections']['D'][0]
            visit(target)
        except ValueError:
            continue
        if 3 <= len(ordered) <= 6 and 2 <= len(roots) <= 6:
            return capture, target, sorted(roots), ordered
    raise ValueError('No small supported cone; do not expand pilot silently')


def reference(roots, cells, target, vector):
    values = dict(zip(roots, vector))
    for c in cells.values():
        kind, inputs, output = primitive(c)
        v = [values[c['connections'][p][0]] for p in inputs]
        if kind in ('AND', 'NAND'):
            value = all(v)
        elif kind in ('OR', 'NOR'):
            value = any(v)
        elif kind in ('XOR', 'XNOR'):
            value = sum(v) % 2 != 0
        else:
            value = v[0]
        values[c['connections'][output][0]] = int(not value if kind in ('NAND', 'NOR', 'XNOR', 'NOT') else value)
    return values[target]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quaigh', required=True)
    parser.add_argument('--yosys', required=True)
    parser.add_argument('--netlist', required=True, type=Path)
    parser.add_argument('--liberty', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    commands = []
    def run(cmd, name):
        before = time.monotonic()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        (out / (name + '.log')).write_text(p.stdout + p.stderr)
        commands.append(dict(command=cmd, seconds=time.monotonic()-before, returncode=p.returncode))
        if p.returncode:
            raise RuntimeError(name + ' failed; preserve log')
        return p.stdout
    module = json.loads(args.netlist.read_text())['modules']['DeadhorseSoc']
    capture, target, roots, cells = select(module)
    bench = [f'INPUT(n{b})' for b in roots] + [f'OUTPUT(n{target})']
    for cell in cells.values():
        kind, inputs, output = primitive(cell)
        bench.append(f'n{cell["connections"][output][0]} = {kind}(' + ', '.join(f'n{cell["connections"][p][0]}' for p in inputs) + ')')
    net = out / 'cone.bench'
    net.write_text('\n'.join(bench) + '\n')
    patterns = out / 'patterns.test'
    run([args.quaigh, 'atpg', str(net), '-o', str(patterns), '--seed', '37', '--with-redundant-faults'], 'atpg')
    vectors = []
    for line in patterns.read_text().splitlines():
        if not line.strip() or line.startswith('*'):
            continue
        bits = line.partition(':')[2].strip()
        if not re.fullmatch('[01]{'+str(len(roots))+'}', bits):
            raise ValueError('Malformed ATPG vector')
        vectors.append(tuple(map(int, bits)))
    if not vectors:
        raise ValueError('Empty patterns')
    all_vectors = list(itertools.product((0, 1), repeat=len(roots)))
    ports = {f'i{i}': dict(direction='input', bits=[b]) for i, b in enumerate(roots)}
    ports['result'] = dict(direction='output', bits=[target])
    base = dict(attributes={}, ports=ports, cells=cells, netnames={})
    cases = [('gold', base)]
    for name, cell in cells.items():
        _, inputs, output = primitive(cell)
        for pin in inputs + [output]:
            for value in (0, 1):
                m = copy.deepcopy(base)
                if pin == output:
                    bit = cell['connections'][pin][0]
                    m['cells'][name]['connections'][pin] = [max(dr for cc in cells.values() for bs in cc['connections'].values() for dr in bs) + 1]
                    for other in m['cells'].values():
                        for p, direction in other['port_directions'].items():
                            if direction == 'input':
                                other['connections'][p] = [str(value) if b == bit else b for b in other['connections'][p]]
                    m['ports']['result']['bits'] = [str(value) if target == bit else target]
                else:
                    m['cells'][name]['connections'][pin] = [str(value)]
                cases.append((f'{name}/{pin}/SA{value}', m))
    # Independent Liberty functional replay: all truth-table rows, then each
    # physical gate input/output fault. No scan/clock/reset sites are counted.
    script = [f'read_liberty -ignore_miss_func {args.liberty.resolve()}', 'design -save cells']
    for index, (_, m) in enumerate(cases):
        f = out / f'case{index}.json'
        f.write_text(json.dumps(dict(modules=dict(pilot=m))))
        script += ['design -reset', 'design -load cells', f'read_json {f}', 'hierarchy -top pilot', 'proc', 'flatten', 'opt_clean']
        for vector in all_vectors:
            settings = ' '.join(f'-set i{i} {b}' for i, b in enumerate(vector))
            script.append(f'eval {settings} -show result')
    ys = out / 'replay.ys'
    ys.write_text('\n'.join(script)+'\n')
    log = run([args.yosys, '-s', str(ys)], 'replay')
    results = [int(b) for b in re.findall(r"Eval result: \\result = 1'([01])\.", log)]
    if len(results) != len(cases)*len(all_vectors):
        raise ValueError('Missing replay rows')
    gold = [reference(roots, cells, target, v) for v in all_vectors]
    if results[:len(all_vectors)] != gold:
        raise ValueError('BENCH primitive mapping differs from Liberty')
    indices = [all_vectors.index(v) for v in vectors]
    faults = []
    fault_values = []
    for index, (name, _) in enumerate(cases[1:], 1):
        observed = results[index*len(all_vectors):(index+1)*len(all_vectors)]
        detectable = any(a != b for a, b in zip(gold, observed))
        detected = any(gold[i] != observed[i] for i in indices)
        faults.append(dict(site=name, detectable_exhaustively=detectable, detected=detected))
        fault_values.append(observed)
        if detectable and not detected:
            raise ValueError('ATPG missed detectable pilot fault: '+name)
    if not any(f['detected'] for f in faults):
        raise ValueError('Vacuous campaign')
    def require_patterns(selected):
        if not selected or any(f['detectable_exhaustively'] and not any(gold[i] != values[i] for i in selected)
                               for f, values in zip(faults, fault_values)):
            raise ValueError('Missing detecting patterns')
    require_patterns(indices)
    empty_rejected = False
    try:
        require_patterns([])
    except ValueError:
        empty_rejected = True
    # The actual faulted netlists above, not just expected Boolean differences,
    # must detect both polarities stuck at the captured D cone's output.
    final_cell = next(n for n, c in cells.items() if c['connections'][primitive(c)[2]][0] == target)
    final_pin = primitive(cells[final_cell])[2]
    by_site = {f['site']:f for f in faults}
    negatives = dict(empty_patterns_rejected=empty_rejected,
                     forced_output_zero_detected=by_site[f'{final_cell}/{final_pin}/SA0']['detected'],
                     forced_output_one_detected=by_site[f'{final_cell}/{final_pin}/SA1']['detected'])
    if not all(negatives.values()):
        raise ValueError('Vacuous fault controls')
    receipt = dict(result='pass_tool_interface_only', source_sha256=sha(__file__),
                   inputs={str(p):sha(p) for p in (args.netlist,args.liberty,net,patterns)},
                   binaries={p:sha(p) for p in (args.quaigh,args.yosys)},
                   capture_D=capture+'/D', roots=roots, cells=list(cells), patterns=len(vectors),
                   truth_rows=len(all_vectors), faults=faults, negative_controls=negatives,
                   measured_seconds=time.monotonic()-started, commands=commands,
                   exclusions='All other production logic, FF/scan/clock/reset pins and macros; isolated combinational tool pilot only. No whole-chip coverage or scan protocol qualification.')
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('result','capture_D','cells','patterns','truth_rows','negative_controls','measured_seconds')}))


if __name__ == '__main__':
    main()
