"""Matched old/new STA of an immutable certified USB map; no proof relabelling."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.pdk import liberty
from tools.timing.pdk_rebind import reference_library
from tools.timing.check import electrical_checks
from tools.timing.usb_qualification import audit_exceptions


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--reference', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    reference, out = [(ROOT / n).resolve() for n in (a.reference, a.output)]
    for path in (reference, out):
        path.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    prior = json.loads((reference / 'result.json').read_text())
    assert prior['status'] in ('pass', 'warning')
    assert sha(reference / 'mapped.v') == prior['mapped_verilog_sha256']
    assert sha(reference / 'mapped.json') == prior['mapped_sha256']
    assert sha(ROOT / 'tools/timing/analyze.tcl') == prior['flow_sha256']['tools/timing/analyze.tcl']
    rebind = reference_library(reference, liberty())
    original = (reference / 'timing.tcl').read_text()
    assert sha(reference / 'timing.tcl') == prior['async_boundary_qualification']['source_sha256'][str(reference / 'timing.tcl')]
    certificate = json.loads((reference / 'certificate/result.json').read_text())
    old = Path(re.findall(r'^set liberty \{([^{}]+)\}$', original, re.M)[0])
    assert re.findall(r'^source \{([^{}]+)\}$', original, re.M) == [str(reference / 'protocol.tcl'), str(ROOT / 'tools/timing/analyze.tcl')]
    inputs = [reference / name for name in ('result.json', 'mapped.v', 'protocol.tcl', 'timing.tcl')]
    inputs += [Path(__file__), ROOT / 'tools/timing/analyze.tcl', ROOT / 'tools/timing/check.py', ROOT / 'tools/timing/usb_qualification.py']
    inputs += [ROOT / n for n in rebind['input_sha256']]
    inputs += [reference/name for name in ('paths.tsv','short_reset_checks.tsv','output_checks.tsv','gate_checks.tsv') if (reference/name).exists()]
    inputs += [ROOT/'tools/env/lock.json',ROOT/'build/env/image.json']
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    sta_tool=Path(shutil.which('sta'));sta_hash=sha(sta_tool)
    receipt = dict(status='running', rebind=rebind, input_sha256=hashes, commands=[],tool_sha256={'sta':sta_hash})
    for label, lib in (('old', old), ('new', liberty())):
        target = out / label
        target.mkdir()
        script = original.replace(f'set liberty {{{old}}}', f'set liberty {{{lib}}}')
        for name in ('paths.tsv', 'gate_checks.tsv'):
            script = script.replace(str(reference / name), str(target / name))
        script += '\nwrite_sdc {' + str(target / 'applied.sdc') + '}\n'
        (target / 'timing.tcl').write_text(script)
        command = ['sta', '-no_init', '-exit', str(target / 'timing.tcl')]
        start = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True)
        log = result.stdout + result.stderr
        (target / 'sta.log').write_text(log)
        receipt['commands'].append(dict(command=command, returncode=result.returncode, seconds=time.monotonic()-start))
        if result.returncode or 'TIMING_COMPLETE' not in log or re.search(r'^Error:', log, re.M):
            raise ValueError('Incomplete STA: ' + label)
        receipt[label] = dict(electrical=electrical_checks(log), liberty_sha256=sha(lib),
                             exception_audit=audit_exceptions((target/'applied.sdc').read_text(),certificate,'Usb'))
    compared = []
    for name in ('paths.tsv', 'short_reset_checks.tsv', 'output_checks.tsv', 'gate_checks.tsv'):
        left, right = out / 'old' / name, out / 'new' / name
        if not left.exists() and not right.exists():
            continue
        if left.read_bytes() != right.read_bytes():
            raise ValueError('Old/new STA rows differ: ' + name)
        if (reference/name).exists() and left.read_bytes() != (reference/name).read_bytes():
            raise ValueError('Historical/replayed STA rows differ: ' + name)
        compared.append(name)
    assert {'paths.tsv', 'short_reset_checks.tsv', 'output_checks.tsv'} <= set(compared)
    assert receipt['old']['electrical'] == receipt['new']['electrical'] == prior['electrical']
    with (out / 'new/paths.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    classes = {}
    for kind, limit in prior['class_failure_limits_ns'].items():
        found = [row for row in rows if row['class'] == kind]
        worst = max(found, key=lambda row: float(row['delay_ns']), default=None)
        if worst and float(worst['delay_ns']) > limit:
            raise ValueError('Existing failure limit missed: ' + kind)
        if bool(worst) != bool(prior['classes'][kind]):
            raise ValueError('Historical class coverage changed: ' + kind)
        classes[kind] = dict(worst=worst, budget_ns=prior['class_budgets_ns'][kind], failure_limit_ns=limit)
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    assert sha(sta_tool)==sta_hash
    receipt.update(status='matched_sta_no_regression', compared_reports=compared,
                   classes=classes, area_um2=prior['area_um2'],
                   scope='Exact existing map and constraints, authenticated format-only PDK change. Area inherited for this identical map; no fresh synthesis or new proof claim. Current SoC binding is separately required.')
    receipt['artifact_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    (out / 'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print('PASS identical old/new USB path, output, hold/reset and electrical reports')


if __name__ == '__main__':
    main()
