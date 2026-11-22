"""Isolate the production shared MAC for matched, synthesis-only experiments.

Run after fresh EmitSocTiming and t20_timing_prepare. No RTL is rewritten.
The sole replaced cell is identified by exact ports, signed widths and aliases.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
TOP = 'DeadhorseSoc'
MAC = 'T20Mac'
ALIAS = 'core.u_ibex_core.ex_block_i.gen_multdiv_fast_multdiv_i.'
LIB = ROOT / 'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def run(path, lines):
    path.write_text('\n'.join(lines) + '\n')
    with path.with_suffix('.log').open('w') as stream:
        subprocess.run(['yosys', '-Q', '-T', '-s', str(path)], check=True,
                       stdout=stream, stderr=subprocess.STDOUT)


def verify(root, hashes):
    for name, expected in hashes.items():
        path = (root / name).resolve()
        path.relative_to(ROOT)
        if digest(path) != expected:
            raise ValueError(f'Stale input: {name}')


def namespace_private(design):
    # JSON omits Yosys's global autoidx. Avoid collisions when optimization
    # resumes in a fresh process; no signal, parameter or attribute changes.
    renamed = copy.deepcopy(design)
    reverse = copy.deepcopy(design)
    for module_name, module in renamed['modules'].items():
        for field in ('cells', 'netnames'):
            items = module.get(field, {})
            mapping = {n: '$t20_snapshot$' + n if n.startswith('$') else n for n in items}
            assert len(set(mapping.values())) == len(mapping)
            module[field] = {mapping[n]: value for n, value in items.items()}
            reverse['modules'][module_name][field] = {
                n: module[field][mapping[n]] for n in items}
    assert reverse == design
    return renamed


def restore(design, name, cell, isolated):
    """Inline the exact extracted graph through its actual instance pins."""
    result = copy.deepcopy(design)
    instance = result['modules'][TOP]['cells'].pop(name)
    child = isolated['modules'][MAC]
    mapping = {}
    for port, desc in child['ports'].items():
        assert len(desc['bits']) == len(instance['connections'][port])
        mapping.update(zip(desc['bits'], instance['connections'][port]))
    rebuilt = copy.deepcopy(child['cells']['mac'])
    rebuilt['connections'] = {
        p: [mapping[b] if isinstance(b, int) else b for b in bits]
        for p, bits in rebuilt['connections'].items()}
    result['modules'][TOP]['cells'][name] = rebuilt
    result['modules'].pop(MAC)
    assert rebuilt == cell
    return result


def mapping_script(dest):
    return '\n'.join([
        f'read_json {dest}/integrated.json', f'hierarchy -check -top {TOP}',
        'flatten', 'check -assert',
        f'synth -top {TOP} -flatten -noabc -run fine:',
        f'dfflibmap -liberty {LIB}',
        f'abc -liberty {LIB} -constr {dest}/mapping.constr -script {dest}/mapping.abc',
        'clean -purge', 'check -assert', f'stat -liberty {LIB}',
        f'write_json {dest}/mapped.json', f'write_verilog -noattr -noexpr {dest}/mapped.v']) + '\n'


def audit(out, receipt):
    assert receipt['status'] == 'pass_isolated_mac_variants'
    verify(ROOT, receipt['sources']); verify(out, receipt['artifacts'])
    coarse = json.loads((out / 'coarse.json').read_text())
    isolated = json.loads((out / 'isolated.json').read_text())
    before = json.loads((out / 'before.json').read_text())
    name = receipt['original_cell']
    assert restore(isolated, name, coarse['modules'][TOP]['cells'][name], before) == coarse
    for strategy in receipt['variants']:
        dest = out / strategy
        child = json.loads((dest / 'arith.json').read_text())
        assert set(child['modules']) == {MAC}
        assert child['modules'][MAC]['ports'] == before['modules'][MAC]['ports']
        if strategy == 'control':
            assert child == before
        expected = copy.deepcopy(isolated)
        expected['modules'][MAC] = child['modules'][MAC]
        assert json.loads((dest / 'integrated.json').read_text()) == namespace_private(expected)
        assert (dest / 'synth.ys').read_text() == mapping_script(dest)
        for file in ('mapping.abc', 'mapping.constr'):
            assert (dest / file).read_bytes() == (ROOT / 'build/t20/core-map-balanced-xor' / file).read_bytes()


def prepare(out):
    prep = json.loads((out / 'prep/result.json').read_text())
    assert prep['status'] == 'pass_boundary_projection'
    verify(ROOT, prep['production_source_sha256'])
    verify(out / 'prep', prep['artifact_sha256'])
    assert digest(LIB) == prep['library_sha256']
    assert digest(out / 'prep/cut.v') == prep['cut_sha256']
    # End label is exclusive in this pinned Yosys: include coarse, stop at fine.
    coarse_lines = [f'read_liberty -lib {LIB}',
        f'read_slang --keep-hierarchy --top {TOP} -DSYNTHESIS {out}/prep/cut.v',
        f'hierarchy -check -top {TOP}', 'check -assert',
        f'synth -top {TOP} -flatten -noabc -run begin:fine',
        f'write_json {out}/coarse.json']
    if (out / 'coarse.json').exists():
        # Reuse only the exact fresh command already run in this experiment.
        actual = (out / 'coarse.ys').read_text().replace('"', '').strip().splitlines()
        assert [' '.join(x.split()) for x in actual] == coarse_lines
    else:
        run(out / 'coarse.ys', coarse_lines)
    coarse = json.loads((out / 'coarse.json').read_text())
    module = coarse['modules'][TOP]
    nets = module['netnames']
    target = nets[ALIAS + 'mac_res']['bits']
    matches = [(n, c) for n, c in module['cells'].items()
               if c['port_directions'].get('Y') == 'output'
               and c['connections'].get('Y') == target]
    assert len(matches) == 1
    name, cell = matches[0]
    assert cell['type'] == '$macc_v2'
    expected = dict(ADDEND_NEGATED=0, A_SIGNED=1, A_WIDTHS=17,
                    B_SIGNED=1, B_WIDTHS=17, C_SIGNED=1, C_WIDTHS=34,
                    NADDENDS=1, NPRODUCTS=1, PRODUCT_NEGATED=0, Y_WIDTH=34)
    assert {k: int(v, 2) for k, v in cell['parameters'].items()} == expected
    assert cell['connections'] == dict(
        A=nets[ALIAS + 'mult_op_a']['bits'] + nets[ALIAS + 'sign_a']['bits'],
        B=nets[ALIAS + 'mult_op_b']['bits'] + nets[ALIAS + 'sign_b']['bits'],
        C=nets[ALIAS + 'accum']['bits'], Y=target)
    assert cell['port_directions'] == dict(A='input', B='input', C='input', Y='output')
    ports = {}; mapping = {}; nextbit = 2
    for p, bits in cell['connections'].items():
        assert all(isinstance(b, int) and b not in mapping for b in bits)
        new = list(range(nextbit, nextbit + len(bits))); nextbit += len(bits)
        mapping.update(zip(bits, new))
        ports[p] = dict(direction=cell['port_directions'][p], bits=new)
    inner = copy.deepcopy(cell)
    inner['connections'] = {p: [mapping[b] for b in bits]
                            for p, bits in cell['connections'].items()}
    before = dict(modules={MAC: dict(attributes={}, ports=ports,
        cells={'mac': inner}, netnames={p: dict(hide_name=0, bits=d['bits'], attributes={})
                                      for p, d in ports.items()})})
    save(out / 'before.json', before)
    isolated = copy.deepcopy(coarse)
    isolated['modules'][MAC] = before['modules'][MAC]
    inst = copy.deepcopy(cell); inst.update(type=MAC, parameters={}, attributes={})
    isolated['modules'][TOP]['cells'][name] = inst
    assert restore(isolated, name, cell, before) == coarse
    fault = copy.deepcopy(isolated)
    fault['modules'][TOP]['cells'][name]['connections']['A'][0] = cell['connections']['B'][0]
    try:
        restore(fault, name, cell, before)
    except AssertionError:
        pass
    else:
        raise ValueError('Wrong-port graph fault escaped')
    save(out / 'isolated.json', isolated)
    for strategy in ('control', 'fa', '42'):
        dest = out / strategy; dest.mkdir(exist_ok=False)
        if strategy == 'control':
            transformed = copy.deepcopy(before)
            save(dest / 'arith.json', transformed)
        else:
            run(dest / 'arith.ys', [f'read_json {out}/before.json',
                f'hierarchy -check -top {MAC}', 'check -assert',
                f'arith_tree -strategy {strategy} -final prefix',
                'check -assert', f'write_json {dest}/arith.json'])
            transformed = json.loads((dest / 'arith.json').read_text())
        assert set(transformed['modules']) == {MAC}
        assert transformed['modules'][MAC]['ports'] == ports
        candidate = copy.deepcopy(isolated)
        candidate['modules'][MAC] = transformed['modules'][MAC]
        outside = copy.deepcopy(candidate); outside['modules'][MAC] = before['modules'][MAC]
        assert outside == isolated
        save(dest / 'integrated.json', namespace_private(candidate))
        for file in ('mapping.constr', 'mapping.abc'):
            source = ROOT / 'build/t20/core-map-balanced-xor' / file
            (dest / file).write_bytes(source.read_bytes())
        (dest / 'synth.ys').write_text(mapping_script(dest))
    sources = dict(prep['production_source_sha256'])
    sources[str(Path(__file__).relative_to(ROOT))] = digest(Path(__file__))
    sources[str(LIB.relative_to(ROOT))] = digest(LIB)
    for name0 in ('mapping.constr', 'mapping.abc'):
        p = ROOT / 'build/t20/core-map-balanced-xor' / name0
        sources[str(p.relative_to(ROOT))] = digest(p)
    receipt = dict(status='pass_isolated_mac_variants', sources=sources,
        artifacts={str(p.relative_to(out)): digest(p) for p in out.rglob('*')
                   if p.is_file() and p.name != 'producer.json'},
        original_cell=name, cell=cell, scope='single signed17x17 plus signed34 accumulator, modulo 2^34',
        isolation='Exact original graph restored through extracted instance ports; outside modules unchanged',
        negative_control='swapped actual operand pin rejected',
        variants=['control', 'fa', '42'], rtl_changed=False, ci='not run',
        private_name_namespace='Reversible $t20_snapshot$ prefix on private cell/net keys; no graph change')
    save(out / 'producer.json', receipt)
    audit(out, receipt)
    print('PASS isolated MAC variants, exact restoration and wrong-port control')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--map', choices=['control', 'fa', '42'])
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    out = (ROOT / args.output).resolve(); out.relative_to(ROOT / 'build')
    if args.map or args.verify:
        receipt = json.loads((out / 'producer.json').read_text())
        audit(out, receipt)
        if args.verify:
            print('PASS source/artifact hashes, exact graph restoration and identical mapping recipes')
            return
        script = out / args.map / 'synth.ys'
        with script.with_suffix('.log').open('w') as stream:
            subprocess.run(['yosys', '-Q', '-T', '-s', str(script)], check=True,
                           stdout=stream, stderr=subprocess.STDOUT)
        print(f'PASS mapped integrated {args.map} variant')
    else:
        prepare(out)


if __name__ == '__main__':
    main()
