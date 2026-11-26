"""Extract a generated analog macro; RC output is diagnostic, not accepted.

Explicitly flatten before capacitance extraction. Preserve the original RC
output and warnings for the conservation/coverage audit rather than silently
repairing or discarding them.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from common import Evidence

root = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
for name in ('source', 'top', 'tech', 'output'):
    p.add_argument('--' + name, required=True)
p.add_argument('--pdk', default='build/t43/pdk-candidate/gf180mcuD')
a = p.parse_args()
assert a.top in ('LfRcMacro', 'PorBrownoutMacro')
source, out, pdk, tech = [(root / x).resolve()
                          for x in (a.source, a.output, a.pdk, a.tech)]
for path in (source, out, pdk, tech):
    path.relative_to(root / 'build')
lock_path = root / 'analog/physical/inputs.lock.json'
lock = json.loads(lock_path.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(tech) == lock['patched_tech_sha256']
magic = Path(lock['magic_store_path']) / 'bin/magic'
assert sha(magic) == lock['magic_executable_sha256']
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__, pdk)
evidence.add_inputs([tech, source / (a.top + '.gds'), *source.glob('*.mag')])
for path in source.glob('*.mag'):
    shutil.copyfile(path, out / path.name)
script = out / 'extract.tcl'
script.write_text(f'''tech load {tech}
drc off
gds readonly true
gds read {source / (a.top + '.gds')}
load {a.top}
flatten -dotoplabels {a.top}Flat
load {a.top}Flat
save {a.top}Flat
gds write {a.top}Flat.gds
extract no resistance
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice cthresh 0
ext2spice extresist off
ext2spice -o capacitance.spice
extresist threshold 0
extresist mindelay 0
extresist minresist 0
extresist simplify off
extract do resistance
extract all
ext2spice extresist on
ext2spice -o original_rc.spice
quit -noprompt
''')
command = [str(magic), '-dnull', '-noconsole', '-rcfile',
           str(pdk / 'libs.tech/magic/gf180mcuD.magicrc'), str(script)]
result = dict(status='running', scope='Extraction only; RC validation open',
              inputs={str(q): sha(q) for q in
                      [Path(__file__), lock_path, tech,
                       source / (a.top + '.gds'), *source.glob('*.mag')]},
              command=command, magic_sha256=sha(magic))
start = time.monotonic()
try:
    with (out / 'extract.log').open('w') as log:
        run = subprocess.run(command, cwd=out,
                             env={**os.environ, 'PDK_ROOT': str(pdk.parent)},
                             stdout=log, stderr=subprocess.STDOUT, timeout=120)
    result['exit'] = run.returncode
    assert run.returncode == 0
    for name in ('capacitance.spice', 'original_rc.spice'):
        assert (out / name).stat().st_size > 0
    result['status'] = 'extracted_not_electrically_qualified'
    evidence.finish(result['status'])
except BaseException as error:
    result.update(status='failed', error=repr(error))
    raise
finally:
    result['seconds'] = time.monotonic() - start
    result['artifacts'] = {q.name: sha(q) for q in out.iterdir() if q.is_file()}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'], result['seconds'])
