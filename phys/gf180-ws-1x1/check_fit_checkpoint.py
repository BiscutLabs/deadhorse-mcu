"""Bind a resumed T43 floorplan to its unchanged synthesis inputs."""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'analog/physical'))
from common import Evidence, sha

p = argparse.ArgumentParser(description=__doc__)
for name in ('before', 'after', 'elaboration', 'output'):
    p.add_argument('--' + name, required=True)
a = p.parse_args()
before, after, elaboration, out = [(ROOT / v).resolve() for v in (a.before, a.after, a.elaboration, a.output)]
for path in (before, after, elaboration, out):
    path.relative_to(ROOT / 'build')
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__)
configs = [directory / 'resolved.json' for directory in (before, after)]
evidence.add_inputs([*configs, elaboration / 'result.json'])
old, new = [json.loads(path.read_text()) for path in configs]
receipt = json.loads((elaboration / 'result.json').read_text())
assert receipt['status'] == 'elaborated_not_physical'
for name, expected in receipt['input_sha256'].items():
    path = ROOT / name
    assert sha(path) == expected, ('Elaboration input changed', name)
    evidence.add_inputs([path])
assert set(old) == set(new)
differences = {key for key in old if old[key] != new[key]}
assert differences <= {'DESIGN_DIR', 'PDN_CFG', 'MACROS', 'VERILOG_FILES'}, differences
assert len(old['VERILOG_FILES']) == len(new['VERILOG_FILES'])
for first, second in zip(old['VERILOG_FILES'], new['VERILOG_FILES']):
    first, second = Path(first), Path(second)
    evidence.add_inputs([first, second])
    assert sha(first) == sha(second), ('Synthesis source changed', first, second)
    if first.name == 'rom_16384x32.sv':
        original = ROOT / 'build/t43/pad-production01/rom_16384x32.sv'
        assert original.read_text().replace('build/t36/rom/rom.hex', str(ROOT / 'build/t36/rom/rom.hex')) == first.read_text()
    else:
        relative = first.relative_to(ROOT).as_posix()
        # Template pad model sources are authenticated by the physical PDK;
        # project and emitted RTL must match the prior elaboration receipt.
        if relative.startswith(('build/t43/pad-production01/', 'build/t43/chip-prod01/src/')):
            assert relative in receipt['input_sha256'], relative
assert set(old['MACROS']) == set(new['MACROS'])
for name in old['MACROS']:
    first, second = copy.deepcopy(old['MACROS'][name]), copy.deepcopy(new['MACROS'][name])
    if name in ('LfRcMacro', 'PorBrownoutMacro'):
        for key in ('gds', 'lef'):
            # Actual physical geometry is intentionally refreshed by floorplan.
            for path in first.pop(key) + second.pop(key):
                evidence.add_inputs([Path(path)])
        v1, v2 = first.pop('vh'), second.pop('vh')
        assert len(v1) == len(v2) == 1
        evidence.add_inputs([Path(v1[0]), Path(v2[0])])
        assert sha(Path(v1[0])) == sha(Path(v2[0])), 'Analog logical boundary changed'
    assert first == second, name
source_state = before / '13-openroad-floorplan/state_in.json'
target_state = after / '01-openroad-floorplan/state_in.json'
evidence.add_inputs([source_state, target_state])
assert json.loads(source_state.read_text()) == json.loads(target_state.read_text())
state = json.loads(source_state.read_text())
evidence.add_inputs([Path(state['nl'])])
metrics = state['metrics']
for key in ('design__instance_unmapped__count', 'synthesis__check_error__count', 'design__inferred_latch__count'):
    assert metrics[key] == 0, key
evidence.data['scope'] = ('Reused completed synthesis/checkpoint, unchanged hashed RTL/logical '
                          'macro boundaries; regenerated floorplan/PDN. Not fresh synthesis.')
evidence.data['configuration_changes'] = sorted(differences)
evidence.finish('pass')
print('PASS synthesis checkpoint, source/config linkage and unchanged logical macro interfaces')
