"""Prepare the T43 pre-global-placement smoke with actual analog views.

This flow uses the template clock solely for physical preparation. The matched
multidomain production STA remains a separate required measurement.
"""
import argparse
import json
from pathlib import Path
import shlex
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'analog/physical'))
from common import Evidence, sha

p = argparse.ArgumentParser(description=__doc__)
for name in ('chip', 'sram', 'rtl-script', 'abstracts', 'output'):
    p.add_argument('--' + name, required=True)
p.add_argument('--pdk', default='build/t43/pdk-candidate/gf180mcuD')
a = p.parse_args()
paths = {name: (ROOT / getattr(a, name.replace('-', '_'))).resolve()
         for name in ('chip', 'sram', 'rtl-script', 'abstracts', 'output', 'pdk')}
for path in paths.values():
    path.relative_to(ROOT / 'build')
out = paths['output']
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__)
lock = json.loads((HERE / 'template.lock.json').read_text())
evidence.add_inputs([HERE / 'template.lock.json', HERE / 'analog_pdn.tcl',
                     paths['rtl-script'], paths['chip'] / 'chip-receipt.json',
                     paths['sram'] / 'result.json'])


def read(path, template=False):
    evidence.add_inputs([path])
    if template:
        relative = path.relative_to(paths['chip']).as_posix()
        assert sha(path) == lock['files'][relative], relative

    def resolve(value):
        if isinstance(value, str) and value.startswith('dir::'):
            return str((path.parent / value[5:]).resolve())
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        return value
    return resolve(yaml.safe_load(path.read_text()))


src = paths['chip'] / 'librelane'
config = read(src / 'config.yaml', True)
config.update(read(src / 'slots/slot_1x1.yaml', True))
config.update(read(paths['sram'] / 'macros_3v3.yaml'))
corners = ('tt_025C_3v30', 'ss_125C_3v00', 'ff_n40C_3v60')
library = paths['pdk'] / 'libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib'
config.update(CELL_LIBS={'*_' + c: [str(library / ('gf180mcu_fd_sc_mcu7t5v0__' + c + '.lib'))] for c in corners},
              STA_CORNERS=[rc + '_' + c for rc in ('nom', 'min', 'max') for c in corners],
              DEFAULT_CORNER='max_ss_125C_3v00', VDD_PIN_VOLTAGE=3.3)
lines = [s for s in paths['rtl-script'].read_text().splitlines() if s.startswith('read_slang ')]
assert len(lines) == 1
config['VERILOG_FILES'] = [v for v in shlex.split(lines[0]) if v.endswith(('.v', '.sv'))]
roms = [Path(v) for v in config['VERILOG_FILES'] if Path(v).name == 'rom_16384x32.sv']
assert len(roms) == 1
rom = roms[0]
image = ROOT / 'build/t36/rom/rom.hex'
evidence.add_inputs([rom, image])
text = rom.read_text()
assert text.count('build/t36/rom/rom.hex') == 1
(out / rom.name).write_text(text.replace('build/t36/rom/rom.hex', str(image)))
config['VERILOG_FILES'] = [str(out / rom.name) if v == str(rom) else v for v in config['VERILOG_FILES']]
config.update(VERILOG_INCLUDE_DIRS=[str(paths['chip'] / 'src')],
              VERILOG_DEFINES=['SYNTHESIS', 'ENABLE_INITIAL_MEM_'],
              USE_SLANG=True, SLANG_ARGUMENTS=['--keep-hierarchy'], CLOCK_PERIOD=1000 / 48)
for top, instance, location in [('LfRcMacro', 'i_chip_core.soc.lf', [2300, 500]),
                                 ('PorBrownoutMacro', 'i_chip_core.soc.por', [2300, 700])]:
    config['MACROS'][top] = {key: [str(paths['abstracts'] / (top + suffix))]
                            for key, suffix in [('gds', '.gds'), ('lef', '.lef'), ('vh', '.v')]}
    config['MACROS'][top]['instances'] = {instance: dict(location=location, orientation='N')}
    config['PDN_MACRO_CONNECTIONS'].append(instance + ' VDD VSS vdd vss')
pdn = out / 'pdn'
pdn.mkdir()
original = src / 'pdn/pdn_cfg.tcl'
assert sha(original) == lock['files']['librelane/pdn/pdn_cfg.tcl']
evidence.add_inputs([original, paths['sram'] / 'pdn_3v3_sram.tcl'])
(pdn / 'pdn_cfg.tcl').write_text('set ::env(SRAM_DEFINE) SRAM_gf180mcu_ocd_ip_sram\n' +
    original.read_text() + '\n' + (HERE / 'analog_pdn.tcl').read_text())
(pdn / 'pdn_3v3_sram.tcl').write_bytes((paths['sram'] / 'pdn_3v3_sram.tcl').read_bytes())
config['PDN_CFG'] = str(pdn / 'pdn_cfg.tcl')
config['meta']['flow'] = 'Chip'
for path in config['VERILOG_FILES']:
    evidence.add_inputs([Path(path)])
for macro in config['MACROS'].values():
    for key in ('gds', 'lef', 'vh'):
        evidence.add_inputs([Path(v) for v in macro[key]])
for paths_for_corner in config['CELL_LIBS'].values():
    evidence.add_inputs([Path(v) for v in paths_for_corner])
(out / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
evidence.data['scope'] = ('Pre-placement fit/padring/PDN only; template48MHz physical '
                          'clock is not production multidomain timing acceptance')
evidence.finish('prepared')
print(out / 'config.json')
