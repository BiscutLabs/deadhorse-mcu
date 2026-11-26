"""Check generated GDS geometry and flat extracted connectivity.

This is not electrical, density, antenna, or chip-level signoff. The rule
selection is the existing isolated-macro geometry check; exclusions remain
explicit in the receipt. All generated files stay below build/.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from common import Evidence, ROOT, sha

p = argparse.ArgumentParser(description=__doc__)
for name in ('source', 'reference', 'top', 'tech', 'output'):
    p.add_argument('--' + name, required=True)
p.add_argument('--pdk', default='build/t43/pdk-candidate/gf180mcuD')
a = p.parse_args()
assert a.top in ('LfRcMacro', 'PorBrownoutMacro')
source, reference, tech, out, pdk = [(ROOT / value).resolve() for value in
                                  (a.source, a.reference, a.tech, a.output, a.pdk)]
for path in (source, reference, tech, out, pdk):
    path.relative_to(ROOT / 'build')
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__, pdk)
lock = json.loads((ROOT / 'analog/physical/inputs.lock.json').read_text())
assert sha(tech) == lock['patched_tech_sha256'], 'Unapproved extraction deck'
gds = source / (a.top + '.gds')
drc = pdk / 'libs.tech/klayout/tech/drc/gf180mcu.drc'
setup = pdk / 'libs.tech/netgen/gf180mcuD_setup.tcl'
evidence.add_inputs([gds, reference, tech, setup,
                     *[q for q in drc.parent.rglob('*') if q.is_file()]])
commands = []


def run(command, name):
    executable = Path(shutil.which(command[0]) or command[0]).resolve()
    evidence.data['tools'][name] = dict(path=str(executable), sha256=sha(executable))
    commands.append(command)
    evidence.data['commands'] = commands
    with (out / (name + '.log')).open('w') as log:
        process = subprocess.run(command, cwd=out,
                                 env={**os.environ, 'PDK_ROOT': str(pdk.parent)},
                                 stdout=log, stderr=subprocess.STDOUT, timeout=120)
    assert process.returncode == 0, (name, process.returncode)
    return (out / (name + '.log')).read_text()


text = run(['klayout', '-b', '-r', str(drc), '-rd', 'input=' + str(gds),
            '-rd', 'report=' + str(out / 'drc.lyrdb'), '-rd', 'topcell=' + a.top,
            '-rd', 'variant=gf180mcuD', '-rd', 'decks=all,-density,-antenna,-cup',
            '-rd', 'workers=1', '-rd', 'threads=4'], 'drc')
assert 'DRC RESULT: SUCCESS (0 violations)' in text
script = out / 'extract.tcl'
script.write_text(f'''tech load {tech}
drc off
gds readonly true
gds read {gds}
load {a.top}
flatten -dotoplabels {a.top}Flat
load {a.top}Flat
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice -o extracted.spice
quit -noprompt
''')
run([str(evidence.magic), '-dnull', '-noconsole', '-rcfile',
     str(pdk / 'libs.tech/magic/gf180mcuD.magicrc'), str(script)], 'extract')
assert (out / 'extracted.spice').stat().st_size
text = run(['netgen', '-batch', 'lvs', 'extracted.spice ' + a.top + 'Flat',
            str(reference) + ' ' + a.top, str(setup), 'comparison.log', '-json'], 'lvs')
comparison = (out / 'comparison.log').read_text()
assert 'Circuits match uniquely.' in comparison
assert 'wrong number of pins' not in text.lower()
evidence.data['scope'] = ('Isolated macro geometry all,-density,-antenna,-cup and '
                          'flat LVS only; no extracted electrical qualification')
evidence.finish('selected_geometry_and_lvs_pass')
print(a.top, 'DRC 0 violations; flat LVS circuits match uniquely')
