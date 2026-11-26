"""Export real PDN shapes and validate placed macro inventory/clearance."""
import argparse
import json
from pathlib import Path
import odb
from common import Evidence, ROOT

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--state', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
state_path, out = [(ROOT / s).resolve() for s in (a.state, a.output)]
for path in (state_path, out):
    path.relative_to(ROOT / 'build')
out.mkdir(parents=True, exist_ok=False)
state = json.loads(state_path.read_text())
odb_path = Path(state['odb'])
evidence = Evidence(out, __file__)
evidence.add_inputs([state_path, odb_path])
db = odb.dbDatabase.create()
odb.read_db(db, str(odb_path))
block = db.getChip().getBlock()
unit = block.getDbUnitsPerMicron()
core = block.getCoreArea()
core_box = [v / unit for v in (core.xMin(), core.yMin(), core.xMax(), core.yMax())]
instances = []
for inst in block.getInsts():
    master = inst.getMaster().getName()
    if master not in ('LfRcMacro', 'PorBrownoutMacro') and not master.startswith('gf180mcu_ocd_ip_sram__'):
        continue
    assert str(inst.getOrient()) == 'R0'
    box = inst.getBBox()
    bounds = [v / unit for v in (box.xMin(), box.yMin(), box.xMax(), box.yMax())]
    # Assumed twenty-micrometre clearance includes the local analog ring.
    halo = 20
    expanded = [bounds[0] - halo, bounds[1] - halo, bounds[2] + halo, bounds[3] + halo]
    assert expanded[0] >= core_box[0] and expanded[1] >= core_box[1]
    assert expanded[2] <= core_box[2] and expanded[3] <= core_box[3]
    for pin, net in [('vdd' if master in ('LfRcMacro', 'PorBrownoutMacro') else 'VDD', 'VDD'),
                     ('vss' if master in ('LfRcMacro', 'PorBrownoutMacro') else 'VSS', 'VSS')]:
        terminal = inst.findITerm(pin)
        assert terminal and terminal.getNet() and terminal.getNet().getName() == net, (inst.getName(), pin)
    instances.append(dict(name=inst.getName(), macro=master, bounds_um=bounds,
                          halo_bounds_um=expanded, xy_um=[v / unit for v in inst.getLocation()],
                          orient=str(inst.getOrient())))
assert len(instances) == 22
assert sum(i['macro'].endswith('sram1024x8m8wm1') for i in instances) == 16
assert sum(i['macro'].endswith('sram512x8m8wm1') for i in instances) == 4
for n, first in enumerate(instances):
    for second in instances[n + 1:]:
        a, b = first['halo_bounds_um'], second['halo_bounds_um']
        assert a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], (first['name'], second['name'])
analog = [i for i in instances if i['macro'] in ('LfRcMacro', 'PorBrownoutMacro')]
assert len(analog) == 2
assert {(i['name'], i['macro']) for i in analog} == {
    ('i_chip_core.soc.lf', 'LfRcMacro'), ('i_chip_core.soc.por', 'PorBrownoutMacro')}
window = [min(i['bounds_um'][j] for i in analog) - 30 for j in (0, 1)] + [
          max(i['bounds_um'][j] for i in analog) + 30 for j in (2, 3)]
shapes = []
for name in ('VDD', 'VSS'):
    for wire in block.findNet(name).getSWires():
        for shape in wire.getWires():
            if shape.xMax() / unit < window[0] or shape.xMin() / unit > window[2] or shape.yMax() / unit < window[1] or shape.yMin() / unit > window[3]:
                continue
            if shape.isVia():
                via = shape.getBlockVia() or shape.getTechVia()
                x, y = shape.getViaXY()
                for part in via.getBoxes():
                    shapes.append(dict(net=name, layer=part.getTechLayer().getName(), via=True,
                        box=[(part.xMin() + x) / unit, (part.yMin() + y) / unit,
                             (part.xMax() + x) / unit, (part.yMax() + y) / unit]))
            else:
                shapes.append(dict(net=name, layer=shape.getTechLayer().getName(), via=False,
                    box=[v / unit for v in (shape.xMin(), shape.yMin(), shape.xMax(), shape.yMax())]))
(out / 'shapes.json').write_text(json.dumps(dict(instances=analog, shapes=shapes), indent=2) + '\n')
(out / 'fit.json').write_text(json.dumps(dict(core_um=core_box, instances=instances,
    halo_um_assumed=20, scope='Macro fit and logical supply binding; PDN network check is separate'), indent=2) + '\n')
evidence.finish('fit_and_export_pass')
print('PASS 16 main SRAM, 4 retained SRAM, 2 analog; fit with20um halos and PG bindings;', len(shapes), 'PDN shapes')
