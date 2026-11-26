"""Check layout reproduction and exercise generator rejection controls."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pya
from common import Evidence, ROOT, lf_port_bindings, spice_ports

p = argparse.ArgumentParser(description=__doc__)
for name in ('access', 'interfaces', 'lf-baseline', 'por-baseline', 'abstracts', 'abstract-baseline', 'output'):
    p.add_argument('--' + name, required=True)
a = p.parse_args()
paths = {name: (ROOT / getattr(a, name.replace('-', '_'))).resolve()
         for name in ('access', 'interfaces', 'lf-baseline', 'por-baseline', 'abstracts', 'abstract-baseline', 'output')}
for path in paths.values():
    path.relative_to(ROOT / 'build')
out = paths['output']
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__)
evidence.add_inputs([ROOT / 'analog/physical/write_abstracts.py', paths['interfaces']])

# Compare the physical layers of the candidate against the electrically
# characterized baseline. GDS timestamps and cell names are immaterial.
for top, baseline in [('LfRcMacro', paths['lf-baseline']),
                      ('PorBrownoutMacro', paths['por-baseline'])]:
    inputs = [paths['access'] / top / (top + '.gds'), baseline / (top + '.gds')]
    evidence.add_inputs(inputs)
    layouts = []
    for path in inputs:
        layout = pya.Layout()
        layout.read(str(path))
        layouts.append(layout)
    left, right = layouts
    assert left.dbu == right.dbu
    layers = {str(l.get_info(i)): l.get_info(i) for l in layouts for i in l.layer_indexes()}
    for info in layers.values():
        if info.datatype == 10 or (info.layer, info.datatype) == (63, 63):
            continue
        regions = [pya.Region(l.cell(top).begin_shapes_rec(l.layer(info))) for l in layouts]
        assert (regions[0] ^ regions[1]).is_empty(), (top, str(info), 'geometry changed')

    # Reusing a physical-flow checkpoint requires identical abstracts and
    # geometry, even when a later generator adds fail-closed guards.
    current = paths['abstracts'] / (top + '.gds')
    prior = paths['abstract-baseline'] / (top + '.gds')
    evidence.add_inputs([current, prior])
    a_layout, b_layout = pya.Layout(), pya.Layout()
    a_layout.read(str(current))
    b_layout.read(str(prior))
    assert a_layout.dbu == b_layout.dbu
    infos = {str(l.get_info(i)): l.get_info(i) for l in (a_layout, b_layout) for i in l.layer_indexes()}
    for info in infos.values():
        regions = [pya.Region(l.cell(top).begin_shapes_rec(l.layer(info))) for l in (a_layout, b_layout)]
        assert (regions[0] ^ regions[1]).is_empty(), (top, info, 'abstract geometry changed')
    for suffix in ('.lef', '.v'):
        pair = [paths[key] / (top + suffix) for key in ('abstracts', 'abstract-baseline')]
        evidence.add_inputs(pair)
        assert pair[0].read_bytes() == pair[1].read_bytes(), (top, suffix)

# Arbitrary mapped bit numbering must not change the interface binding.
module = {'ports': {name: {'direction': direction, 'bits': [bit]}
                   for name, direction, bit in [('source', 'input', 97),
                       ('power_n', 'input', 4), ('enable', 'input', 210),
                       ('ready', 'output', 11)]}}
assert lf_port_bindings(module) == {'0': 'vss', '1': 'vdd', 97: 'clock',
                                   4: 'init_n', 210: 'enable', 11: 'ready'}


def rejects(function, name):
    try:
        function()
    except AssertionError:
        return
    raise AssertionError(name + ' was not rejected')


duplicate = copy.deepcopy(module)
duplicate['ports']['ready']['bits'] = [97]
rejects(lambda: lf_port_bindings(duplicate), 'ambiguous mapped identity')
missing = copy.deepcopy(module)
del missing['ports']['source']
rejects(lambda: lf_port_bindings(missing), 'missing mapped port')
wrong = copy.deepcopy(module)
wrong['ports']['ready']['direction'] = 'input'
rejects(lambda: lf_port_bindings(wrong), 'wrong mapped direction')
assert spice_ports('.subckt example a b\n+ c\n.ends', 'example', ['a', 'b', 'c']) == ['a', 'b', 'c']
rejects(lambda: spice_ports('.subckt example a a c', 'example', ['a', 'b', 'c']),
        'duplicated SPICE pin')

# Inject an actual foreign-metal polygon into the lower supply band. The
# abstract writer must refuse to advertise this area as free routing space.
bad = out / 'foreign-metal'
shutil.copytree(paths['access'], bad)
top = 'LfRcMacro'
gds = bad / top / (top + '.gds')
layout = pya.Layout()
layout.read(str(gds))
ports = json.loads((bad / top / 'ports.json').read_text())
x0, y0, x1, y1 = ports['rails']['vss']
layout.cell(top).shapes(layout.layer(46, 0)).insert(
    pya.DBox(x0 + 20, y0 + .5, x0 + 21, y0 + 1.5).to_itype(layout.dbu))
layout.write(str(gds))
command = [sys.executable, str(ROOT / 'analog/physical/write_abstracts.py'),
           '--access', str(bad), '--interfaces', str(paths['interfaces']),
           '--output', str(out / 'rejected-abstract')]
with (out / 'negative.log').open('w') as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
assert result.returncode != 0
assert 'foreign Metal4 in lower power-access band' in (out / 'negative.log').read_text()
evidence.data['scope'] = 'Geometry reproduction, mapped identity and power-band rejection controls'
evidence.finish('pass')
print('PASS geometry XOR, renumbered mapped ports, and all rejection controls')
