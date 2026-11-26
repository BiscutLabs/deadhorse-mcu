"""Check actual analog-macro/PDN overlay, including cut/enclosure geometry."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import pya
from common import Evidence, ROOT, sha

p = argparse.ArgumentParser(description=__doc__)
for name in ('shapes', 'abstracts', 'access', 'output'):
    p.add_argument('--' + name, required=True)
p.add_argument('--pdk', default='build/t43/pdk-candidate/gf180mcuD')
a = p.parse_args()
shapes, abstracts, out, pdk = [(ROOT / v).resolve() for v in (a.shapes, a.abstracts, a.output, a.pdk)]
access = (ROOT / a.access).resolve()
for path in (shapes, abstracts, access, out, pdk):
    path.relative_to(ROOT / 'build')
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__)
evidence.add_inputs([shapes])
data = json.loads(shapes.read_text())
layout = pya.Layout()
layout.dbu = .001
top = layout.create_cell('AnalogPdnOverlay')
for instance in data['instances']:
    assert instance['orient'] == 'R0'
    path = abstracts / (instance['macro'] + '.gds')
    evidence.add_inputs([path])
    layout.read(str(path))
    top.insert(pya.CellInstArray(layout.cell(instance['macro']).cell_index(),
        pya.Trans(*[round(v / layout.dbu) for v in instance['xy_um']])))
layers = {'Metal1': 34, 'Metal2': 36, 'Metal3': 42, 'Metal4': 46, 'Metal5': 81,
          'Via1': 35, 'Via2': 38, 'Via3': 40, 'Via4': 41}
conductors = {net: {name: pya.Region() for name in layers} for net in ('VDD', 'VSS')}
for shape in data['shapes']:
    assert shape['net'] in conductors and shape['layer'] in layers
    box = pya.DBox(*shape['box']).to_itype(layout.dbu)
    top.shapes(layout.layer(layers[shape['layer']], 0)).insert(box)
    conductors[shape['net']][shape['layer']].insert(box)
for name in layers:
    assert (conductors['VDD'][name] & conductors['VSS'][name]).is_empty(), (name, 'PG short')
evidence.add_inputs([abstracts / 'result.json'])
translations = {r['top']: r['translation_dbu'] for r in json.loads((abstracts / 'result.json').read_text())}
for instance in data['instances']:
    macro = instance['macro']
    ports_file = access / macro / 'ports.json'
    evidence.add_inputs([ports_file])
    info = json.loads(ports_file.read_text())
    cell = layout.cell(macro)
    x, y = instance['xy_um']
    dx, dy = [v * layout.dbu for v in translations[macro]]
    transform = pya.Trans(round(x / layout.dbu), round(y / layout.dbu))

    def moved_region(box):
        return pya.Region(pya.DBox(box[0] + dx + x, box[1] + dy + y,
            box[2] + dx + x, box[3] + dy + y).to_itype(layout.dbu))

    for j, (net, pin) in enumerate([('VDD', 'vdd'), ('VSS', 'vss')]):
        rail = info['rails'][pin]
        ry = (rail[1] + rail[3]) / 2
        rx = 5 + 3 * j
        allowed = {'Metal5': moved_region(rail),
                   'Metal4': moved_region([rx - .22, ry - .22, rx + .22, ry + .22])}
        for layer in ('Metal1', 'Metal2', 'Metal3', 'Metal4', 'Metal5'):
            metal = pya.Region(cell.begin_shapes_rec(layout.layer(layers[layer], 0))).transformed(transform)
            landing = allowed.get(layer, pya.Region())

            def validate(candidate):
                assert ((candidate & metal) - landing).is_empty(), (macro, net, layer, 'PG-to-macro short')
                if layer == 'Metal5':
                    assert (landing - candidate).is_empty(), (macro, net, 'uncovered PG rail')

            validate(conductors[net][layer])
            # Semantic checks must reject shorts even when a polygon union
            # could look DRC-clean, and reject a missing supply-rail connection.
            if layer == 'Metal4':
                foreign = metal - landing
                assert not foreign.is_empty()
                try:
                    validate(conductors[net][layer] + foreign)
                except AssertionError:
                    pass
                else:
                    raise AssertionError('PG-to-macro negative escaped')
            if layer == 'Metal5':
                try:
                    validate(conductors[net][layer] - landing)
                except AssertionError:
                    pass
                else:
                    raise AssertionError('Missing PG rail negative escaped')
layout.write(str(out / 'overlay.gds'))
deck = pdk / 'libs.tech/klayout/tech/drc/gf180mcu.drc'
evidence.add_inputs([f for f in deck.parent.rglob('*') if f.is_file()])
tool = Path(shutil.which('klayout')).resolve()
evidence.data['tools']['klayout'] = dict(path=str(tool), sha256=sha(tool))
command = [str(tool), '-b', '-r', str(deck), '-rd', 'input=' + str(out / 'overlay.gds'),
           '-rd', 'report=' + str(out / 'drc.lyrdb'), '-rd', 'topcell=AnalogPdnOverlay',
           '-rd', 'variant=gf180mcuD', '-rd', 'decks=all,-density,-antenna,-cup',
           '-rd', 'workers=1', '-rd', 'threads=4']
evidence.data['command_drc'] = command
with (out / 'drc.log').open('w') as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
assert result.returncode == 0
assert 'DRC RESULT: SUCCESS (0 violations)' in (out / 'drc.log').read_text()
evidence.data['scope'] = ('Analog-area PDN conductor/cut overlay geometry only; '
                          'not whole-chip DRC, IR/EM, density or antenna signoff')
evidence.finish('selected_overlay_geometry_pass')
print('PASS analog PDN overlay: matching rail coverage only, no PG-to-signal/supply shorts, faults rejected; selected DRC0')
