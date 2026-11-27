"""Measure and draw an existing placed chip ODB; no routing or DRC run."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def category(name):
    if 'ip_sram__' in name:
        return 'sram'
    if name in ('LfRcMacro', 'PorBrownoutMacro'):
        return 'analog'
    if '_ws_ip__' in name:
        return 'artwork'
    if '_fd_io__' in name:
        return 'pads'
    if name.endswith(('__filltie', '__endcap')):
        return 'taps'
    if '__fill_' in name or '__fillcap_' in name:
        return 'filler'
    return 'logic'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state')
    p.add_argument('--output', required=True)
    p.add_argument('--render', action='store_true', help='Render measured geometry using pinned Python/Pillow')
    a = p.parse_args()
    started = time.monotonic()
    out = (ROOT / a.output).resolve()
    out.relative_to(ROOT / 'build')
    if a.render:
        render(out)
        return
    import odb
    assert a.state
    state_path = (ROOT / a.state).resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = json.loads(state_path.read_text())
    odb_path = Path(state['odb'])
    metrics_path = state_path.parent / 'or_metrics_out.json'
    metrics = json.loads(metrics_path.read_text())
    assert metrics['design__violations'] == 0, 'Placement tool reported violations'
    db = odb.dbDatabase.create()
    odb.read_db(db, str(odb_path))
    block = db.getChip().getBlock()
    units = block.getDbUnitsPerMicron()

    def box(rect):
        return [v / units for v in (rect.xMin(), rect.yMin(), rect.xMax(), rect.yMax())]

    core, die = box(block.getCoreArea()), box(block.getDieArea())
    core_area = (core[2] - core[0]) * (core[3] - core[1])
    assert core_area <= 12.92e6
    counts, areas, clipped = Counter(), Counter(), Counter()
    unplaced, outside = [], []
    geometry = []
    for inst in block.getInsts():
        master = inst.getMaster()
        name, kind = inst.getName(), master.getName()
        group = category(kind)
        rect = box(inst.getBBox())
        counts[group] += 1
        areas[group] += master.getWidth() * master.getHeight() / units ** 2
        clipped[group] += max(0, min(rect[2], core[2]) - max(rect[0], core[0])) * max(0, min(rect[3], core[3]) - max(rect[1], core[1]))
        if str(inst.getPlacementStatus()) not in ('PLACED', 'FIRM', 'LOCKED', 'COVER'):
            unplaced.append(name)
        if group in ('logic', 'taps', 'filler', 'sram', 'analog') and not (
            core[0] <= rect[0] <= rect[2] <= core[2] and core[1] <= rect[1] <= rect[3] <= core[3]):
            outside.append(name)
        geometry.append(dict(name=name, master=kind, group=group, box_um=rect))
    assert not unplaced and not outside, (unplaced[:5], outside[:5])
    assert counts['sram'] == 20 and counts['analog'] == 2
    macros = [g for g in geometry if g['group'] in ('sram', 'analog')]
    for i, left in enumerate(macros):
        for right in macros[i + 1:]:
            x, y = left['box_um'], right['box_um']
            assert min(x[2], y[2]) <= max(x[0], y[0]) or min(x[3], y[3]) <= max(x[1], y[1]), 'Macro overlap'
    occupied = sum(clipped.values())
    assert occupied <= core_area
    usable = core_area - sum(clipped[g] for g in ('sram', 'analog', 'artwork', 'pads'))
    utilization = sum(clipped[g] for g in ('logic', 'taps', 'filler')) / usable

    geometry_path = out / 'geometry.json'
    geometry_path.write_text(json.dumps(geometry) + '\n')
    inputs = [Path(__file__), state_path, odb_path, metrics_path]
    result = dict(status='placed_fit_only', seconds=time.monotonic() - started,
        core_box_um=core, die_box_um=die, core_area_mm2=core_area / 1e6,
        counts=dict(counts), area_mm2={g: v / 1e6 for g, v in areas.items()},
        core_footprint_sum_mm2=occupied / 1e6, core_remainder_after_footprint_sum_mm2=(core_area - occupied) / 1e6,
        available_core_utilization_estimated=utilization,
        utilization_method='Sum of clipped logic/tap/filler footprints divided by core rectangle minus clipped SRAM/analog/artwork/pad footprints; not measured placement-row area.',
        unplaced_count=len(unplaced), outside_core_count=len(outside),
        flow_placement_violations=metrics['design__violations'], macros=macros,
        input_sha256={str(q.relative_to(ROOT)): sha(q) for q in inputs}, geometry_sha256=sha(geometry_path),
        scope='Measured placement geometry and sums of clipped footprints, not a computed geometric union. Ratios/remainder are arithmetic estimates from those measurements. No routing, DRC/LVS, fault-coverage, electrical or timing signoff. Remainder includes necessary routing/keepout space.')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS placed geometry and macro inventory; result.json written')


def render(out):
    from PIL import Image, ImageDraw, ImageFont
    started = time.monotonic()
    result = json.loads((out / 'result.json').read_text())
    assert result['input_sha256'][str(Path(__file__).relative_to(ROOT))] == sha(Path(__file__))
    assert result['geometry_sha256'] == sha(out / 'geometry.json')
    geometry = json.loads((out / 'geometry.json').read_text())
    core, die = result['core_box_um'], result['die_box_um']
    core_area, utilization = result['core_area_mm2'] * 1e6, result['available_core_utilization_estimated']

    width, scale, margin, top = 1800, 1600 / (die[2] - die[0]), 100, 170
    height = int((die[3] - die[1]) * scale) + top + 160
    canvas = Image.new('RGB', (width, height), '#f7f9fc')
    draw = ImageDraw.Draw(canvas)
    title = ImageFont.load_default(size=34)
    font = ImageFont.load_default(size=22)
    small = ImageFont.load_default(size=17)
    draw.text((margin, 28), 'Deadhorse MCU | preliminary placement', font=title, fill='#162438')
    draw.text((margin, 80), 'Placed fit study - routing and DRC deferred', font=font, fill='#536174')

    def pixels(rect):
        return (margin + (rect[0] - die[0]) * scale, top + (die[3] - rect[3]) * scale,
                margin + (rect[2] - die[0]) * scale, top + (die[3] - rect[1]) * scale)

    colors = dict(logic='#3b81c4', taps='#d7e5ee', filler='#d7e5ee', sram='#e8ad48',
                  analog='#db776b', artwork='#ae9dcc', pads='#758495')
    draw.rectangle(pixels(die), fill='#e9edf3', outline='#26384c', width=2)
    draw.rectangle(pixels(core), fill='white', outline='#26384c', width=2)
    order = {'taps': 0, 'filler': 0, 'logic': 1, 'pads': 2, 'artwork': 3, 'sram': 4, 'analog': 5}
    for row in sorted(geometry, key=lambda g: order[g['group']]):
        rect = pixels(row['box_um'])
        draw.rectangle(rect, fill=colors[row['group']])
        if row['group'] in ('sram', 'analog'):
            draw.rectangle(rect, outline='#394655', width=2)
            label = ('1 KiB' if '1024x8' in row['master'] else '512 B') if row['group'] == 'sram' else ('LF RC' if row['master'] == 'LfRcMacro' else 'POR')
            draw.text((rect[0] + 5, rect[1] + 5), label, font=small, fill='#162438')
    draw.rectangle(pixels(core), outline='#26384c', width=2)
    y = height - 125
    for index, (group, label) in enumerate((('logic', 'Logic / buffers'), ('sram', 'SRAM'), ('analog', 'Analog'), ('pads', 'Pads'), ('artwork', 'Markers'))):
        x = margin + index * 315
        draw.rectangle((x, y, x + 20, y + 20), fill=colors[group])
        draw.text((x + 30, y - 2), label, font=font, fill='#26384c')
    draw.text((margin, height - 76), f'Core {core_area / 1e6:.4f} mm2 | geometric available-core use {utilization:.1%} (estimated) | 20 SRAM + 2 analog', font=font, fill='#26384c')
    draw.text((margin, height - 43), 'Whitespace is not a routability or post-scan headroom guarantee.', font=small, fill='#536174')
    image_path = out / 'placement.png'
    canvas.save(image_path)
    result['image_sha256'] = sha(image_path)
    result['render_seconds'] = time.monotonic() - started
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Rendered measured placement.png')


if __name__ == '__main__':
    main()
