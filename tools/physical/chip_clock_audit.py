"""Check executed chip clock coverage and exact USB exceptions in both AON modes."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import librelane

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.timing.usb_qualification import applied_pairs


def sha(q):
    return hashlib.sha256(q.read_bytes()).hexdigest()


def audit_envelope(commands, source, mode):
    def statements(lines, prefix):
        return [s for s in lines if s.startswith(prefix + ' ')]
    def canonical(s):
        return s.replace('chip_pins', 'get_pins').replace('[get_ports clk_PAD]', '[get_ports {clk_PAD}]')
    for kind in ('create_generated_clock', 'set_case_analysis'):
        wanted = [canonical(s) for s in statements(source.splitlines(), kind)]
        assert len(wanted) == 1 and statements(commands, kind) == wanted, kind
    roots = statements(commands, 'create_clock')
    # Exact source pins, default 50% waveform, and only one clock on clk_PAD
    # establish main's unique USB master together with the exact /6 statement.
    pins = dict(usb=('ports', 'clk_PAD'), tck=('ports', 'input_PAD[3]'),
                aon=('pins', 'i_chip_core.soc.lf/clock') if mode == 'rc' else ('ports', 'input_PAD[0]'))
    assert len(roots) == len(pins)
    for name, (kind, pin) in pins.items():
        pattern = re.escape(f'create_clock -name {name} -period ') + r'\S+' + re.escape(f' [get_{kind} {{{pin}}}]')
        assert sum(bool(re.fullmatch(pattern, s)) for s in roots) == 1, name
    propagated = statements(commands, 'set_propagated_clock')
    assert len(propagated) == 4 and set(propagated) == {
        f'set_propagated_clock [get_clocks {{{name}}}]' for name in ('usb', 'main', 'aon', 'tck')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('state', 'environment', 'constraints', 'output'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    state_path, env, constraints, out = [(ROOT / getattr(a, n)).resolve()
                                       for n in ('state', 'environment', 'constraints', 'output')]
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    state = json.loads(state_path.read_text())
    prior = json.loads((constraints / 'result.json').read_text())
    for name, digest in prior['artifact_sha256'].items():
        assert sha(constraints / name) == digest, name
    expected = json.loads((constraints / 'expected-clocks.json').read_text())
    scripts = Path(librelane.__file__).resolve().parent / 'scripts'
    inputs = [Path(__file__), ROOT / 'tools/timing/usb_qualification.py', state_path,
              Path(state['odb']), env, constraints / 'result.json']
    results = {}
    for mode in ('rc', 'external'):
        target = out / mode
        target.mkdir()
        sdc = constraints / (mode + '.sdc')
        inputs.append(sdc)
        # The hash-bound generated SDC contains only translated certified MCPs.
        wanted_text = '\n'.join(l.replace('chip_pins', 'get_pins') for l in sdc.read_text().splitlines()
                                if l.startswith('set_multicycle_path '))
        wanted_pairs = applied_pairs(wanted_text)
        assert wanted_pairs
        tcl = target / 'audit.tcl'
        tcl.write_text(f'''set ::env(_TCL_ENV_IN) {{{env}}}
set ::env(SCRIPTS_DIR) {{{scripts}}}
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
set ::env(STEP_ID) T38.ClockAudit
set ::env(OPENLANE_SDC_IDEAL_CLOCKS) 0
set ::env(CURRENT_ODB) {{{state['odb']}}}
set ::env(_SDC_IN) {{{sdc}}}
define_corners $::env(DEFAULT_CORNER)
set libraries [list]
foreach key {{CELL_LIBS PAD_LIBS}} {{
 dict for {{pattern paths}} $::env($key) {{
  if {{[string match $pattern $::env(DEFAULT_CORNER)]}} {{lappend libraries {{*}}$paths}}
 }}
}}
dict for {{name macro}} $::env(MACROS) {{
 dict for {{pattern paths}} [dict get $macro lib] {{
  if {{[string match $pattern $::env(DEFAULT_CORNER)]}} {{lappend libraries {{*}}$paths}}
 }}
}}
set f [open {{{target}/libraries.txt}} w]
foreach lib [lsort -unique $libraries] {{
 read_liberty -corner $::env(DEFAULT_CORNER) $lib
 puts $f $lib
}}
close $f
read_db $::env(CURRENT_ODB)
read_current_sdc
set f [open {{{target}/clocks.tsv}} w]
puts $f "pin\tclock"
foreach pin [all_registers -clock_pins] {{
 set clocks [get_property $pin clocks]
 if {{[llength $clocks] != 1}} {{error "Unclocked or ambiguous register: [get_full_name $pin]"}}
 puts $f "[get_full_name $pin]\t[get_full_name [lindex $clocks 0]]"
}}
close $f
set f [open {{{target}/periods.tsv}} w]
puts $f "clock\tperiod"
foreach clock [all_clocks] {{puts $f "[get_full_name $clock]\t[get_property $clock period]"}}
close $f
write_sdc {{{target}/applied.sdc}}
puts T38_CLOCK_AUDIT_COMPLETE
''')
        start = time.monotonic()
        run = subprocess.run(['openroad', '-exit', str(tcl)], cwd=ROOT,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (target / 'audit.log').write_text(run.stdout)
        assert run.returncode == 0 and 'T38_CLOCK_AUDIT_COMPLETE' in run.stdout, run.stdout[-2000:]
        assert not any(l.startswith(('[ERROR', 'Error:')) for l in run.stdout.splitlines())
        inputs.extend(Path(q) for q in (target / 'libraries.txt').read_text().splitlines())
        with (target / 'clocks.tsv').open() as f:
            rows = list(csv.DictReader(f, delimiter='\t'))
        actual = {r['pin']: r['clock'] for r in rows}
        assert len(rows) == len(actual) and actual == expected, 'Clock sink/domain inventory changed'
        with (target / 'periods.tsv').open() as f:
            period_rows = list(csv.DictReader(f, delimiter='\t'))
        periods = {r['clock']: float(r['period']) for r in period_rows}
        assert len(period_rows) == len(periods) and set(periods) == {'usb', 'main', 'aon', 'tck'}
        assert all(math.isfinite(v) for v in periods.values())
        # OpenSTA stores time as single-precision SI seconds and prints ns.
        # Allow binary32 conversion plus six-decimal text quantization;
        # this is a serialization check, not a change to any timing limit.
        assert all(abs(periods[k] - v) <= v * 2 ** -23 + 0.0000005 for k, v in
                   dict(usb=1000 / 48, main=125, aon=31250, tck=10000).items())
        applied = re.sub(r'\\\r?\n\s*', ' ', (target / 'applied.sdc').read_text())
        commands = [l.strip() for l in applied.splitlines() if l.strip() and not l.strip().startswith('#')]
        allowed = {'current_design', 'create_clock', 'create_generated_clock', 'set_case_analysis',
                   'set_clock_uncertainty', 'set_clock_transition', 'set_propagated_clock',
                   'set_timing_derate', 'set_max_transition', 'set_max_fanout', 'set_load',
                   'set_input_transition', 'set_input_delay', 'set_output_delay', 'set_multicycle_path'}
        assert all(l.split()[0] in allowed for l in commands), 'Unexpected timing override'
        audit_envelope(commands, sdc.read_text(), mode)
        for fault in ([s.replace('-divide_by 6', '-divide_by 5') for s in commands],
                      commands + ['set_case_analysis 0 [get_ports {rst_n_PAD}]'],
                      [s for s in commands if s != 'set_propagated_clock [get_clocks {main}]']):
            try:
                audit_envelope(fault, sdc.read_text(), mode)
            except AssertionError:
                pass
            else:
                raise AssertionError('Clock-envelope fault accepted')
        pairs = applied_pairs('\n'.join(l for l in commands if l.startswith('set_multicycle_path ')))
        assert pairs == wanted_pairs, 'Executed multicycle pairs differ from certificate'
        # Collector controls, distinct from the inherited real RTL/STA faults.
        missing = dict(actual)
        missing.pop(next(iter(missing)))
        wrong = dict(actual)
        name = next(iter(wrong))
        wrong[name] = 'invalid-clock'
        assert missing != expected and wrong != expected
        changed = dict(pairs)
        key = next(iter(changed))
        changed[key] += 1
        assert changed != wanted_pairs
        results[mode] = dict(status='pass', clock_pins=len(actual), periods_ns=periods,
                             exception_pairs=len(pairs), seconds=time.monotonic() - start,
                             collector_controls=['missing-sink', 'wrong-clock', 'wrong-multiplier',
                                                 'wrong-divider', 'extra-case-analysis', 'missing-propagated-clock'])
    result = dict(status='pass', modes=results,
        input_sha256={str(q.relative_to(ROOT)): sha(q) for q in inputs},
        artifact_sha256={str(q.relative_to(out)): sha(q) for q in out.rglob('*') if q.is_file()},
        scope='Executed clock/sink coverage and USB exception correspondence; not timing, CDC/RDC or analog signoff')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS both AON modes: exact register clocks and executed USB exception pairs')


if __name__ == '__main__':
    main()
