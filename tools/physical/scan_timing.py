"""Scoped physical scan timing measurements; not manufacturing acceptance.

Run in the pinned LibreLane environment. Uses placement-estimated RC, actual
pad arcs, explicit trial timing and no functional multicycle exceptions.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import librelane

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.physical.scan_constraints import pairs,envelope
from tools.physical.scan_libraries import authenticate


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def validate_clocks(observed, expected, phases):
    clocks={r['pin']:r for r in observed}
    assert len(clocks)==len(observed), 'Duplicate clock endpoint'
    assert {n:r['clocks'] for n,r in clocks.items()}==expected, 'Clock coverage changed'
    for pin,falling in phases.items():
        assert int(clocks[pin]['falling'])==falling, 'Wrong scan phase '+pin


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('state', 'environment', 'audit', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--mode', choices=('shift', 'capture', 'reset', 'functional-rc', 'functional-external'), required=True)
    p.add_argument('--functional', type=Path)
    p.add_argument('--corner', choices=('ss', 'ff'), default='ss')
    a = p.parse_args(); out = a.output.resolve(); out.relative_to(ROOT / 'build')
    functional=a.mode.startswith('functional-')
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-scan_timing.py').write_bytes(Path(__file__).read_bytes())
    executed_source_sha=sha(out/'executed-scan_timing.py')
    state = json.loads(a.state.read_text())
    audit = json.loads((a.audit / 'result.json').read_text())
    assert audit['status'] == 'pass_preserved_physical_graph'
    assert sha(state['odb']) in audit['input_sha256'].values(), 'Unreviewed physical database'
    insert = ROOT / 'build/t37/insert05'
    receipt = json.loads((insert / 'result.json').read_text())
    assert receipt['status'] == 'pass_unplaced_insertion'
    assert sha(insert / 'after.json') == receipt['artifacts']['after.json']
    assert sha(insert / 'chains.json') == receipt['artifacts']['chains.json']
    graph = json.loads((insert / 'after.json').read_text())
    rows = json.loads((insert / 'chains.json').read_text())
    assert sum(len(r['cells']) for r in rows) == 20380
    control = receipt['controls']
    campaign = ROOT / 'build/t37/campaign01'
    cr = json.loads((campaign / 'result.json').read_text())
    assert cr['status'] == 'measured_physical_SA_campaign'
    vector = campaign / cr['batches'][0]['file']
    assert sha(vector) == cr['batches'][0]['sha256']
    fixture = json.loads(vector.read_text())
    manifest_path = ROOT / 'build/t37/scan-manifest02.json'
    manifest = json.loads(manifest_path.read_text())
    assert sha(manifest_path) in receipt['input_sha256'].values()
    def driver(net):
        found = [n + '/' + pin for n, c in graph.items() for pin, wire in c['pins'].items()
                 if wire == net and pin in control['output_pins'][c['type']]]
        assert len(found) == 1
        return found[0]
    scripts = Path(librelane.__file__).resolve().parent / 'scripts'
    executable=Path(shutil.which('openroad'))
    # Pinned devshell executable is a Nix environment wrapper around this
    # OpenROAD binary; authenticate both rather than confusing their hashes.
    binary=Path('/nix/store/bccb19a0l8q7g83kdgbabr8fh6j2gf74-openroad-2026-02-17/bin/openroad')
    assert sha(executable)=='2acbf144af1ec5d4fd9dffbc46f325b032f809703ec25c465ffdf6ffe48ad4d8'
    assert str(binary).encode() in executable.read_bytes()
    assert sha(binary)=='a58debef32b592a7f2622a42a65434c313f2d332b84dc15af4798b33db24e0b4'
    for name,expected in {
        'io.tcl':'b70a8733a2a26a0909be220d8320d78e22a13cb418a862c1ef08a70da2985fe4',
        'set_rc.tcl':'4d338cf468b644652380158db86b35c1966a0797ed891fb24e4bfc3f9384fece',
    }.items(): assert sha(scripts/'openroad/common'/name)==expected
    corner = 'max_ss_125C_3v00' if a.corner == 'ss' else 'min_ff_n40C_3v60'
    commands = [
        'create_clock -name scan -period 100 [get_ports clk_PAD]',
        'set_clock_uncertainty 0.25 [all_clocks]',
        'set_clock_transition 0.15 [all_clocks]',
        'set_timing_derate -early 0.95', 'set_timing_derate -late 1.05',
        'set_case_analysis 1 [get_pins {' + driver(control['mode']) + '}]',
        'set_input_transition 0.5 [get_ports {input_PAD[*] bidir_PAD[*] rst_n_PAD}]',
        'set_load 0.07291 [get_ports {bidir_PAD[*]}]',
    ]
    for port, value in fixture['fixed_fixture'].items():
        if port == 'clk_PAD' or (port == 'input_PAD[7]' and a.mode == 'reset'): continue
        if port == 'input_PAD[8]': value = int(a.mode != 'capture')
        commands.append(f'set_case_analysis {value} [get_ports {{{port}}}]')
    # Explicit assumed tester window. Existing protocol requires stable reset
    # and SE during load/capture. Reset mode deliberately removes reset's case
    # to expose recovery/removal; its raw phase is diagnostic, not a waiver.
    inputs = sorted(fixture['pads'])
    if a.mode == 'reset': inputs.append('input_PAD[7]')
    for ports in (' '.join(inputs),):
        for limit, value in (('min', 0), ('max', 1)):
            commands.append(f'set_input_delay -{limit} {value} -clock scan [get_ports {{{ports}}}]')
    for limit, value in (('min', 0), ('max', 1)):
        commands.append(f'set_output_delay -{limit} {value} -clock scan [get_ports {{bidir_PAD[9] bidir_PAD[10] bidir_PAD[11] bidir_PAD[25] bidir_PAD[26] bidir_PAD[27] bidir_PAD[28]}}]')
    commands.append('set_propagated_clock [all_clocks]')
    functional_inputs=[]
    if functional:
        assert a.functional is not None
        fr=json.loads((a.functional/'result.json').read_text())
        assert fr['status']=='prepared_functional_only'
        for name,digest in fr['inputs'].items():assert sha(ROOT/name)==digest,name
        for name,digest in fr['artifacts'].items():assert sha(a.functional/name)==digest
        expected_clocks=json.loads((a.functional/'expected.json').read_text())
        sdc=a.functional/(a.mode.removeprefix('functional-')+'.sdc')
        commands=sdc.read_text().splitlines()+['set_case_analysis 0 [get_pins {'+driver(control['mode'])+'}]']
        functional_inputs=[a.functional/'result.json',a.functional/'expected.json',a.functional/'phases.json',sdc]+[ROOT/name for name in fr['inputs']]
    else:
        expected_clocks={n+'/CLK':'scan' for row in rows for n in row['cells']}
        for n in manifest['excluded']:
            pins=[pin for pin in ('CLK','CLKN') if pin in graph[n]['pins']]
            assert len(pins)==1
            expected_clocks[n+'/'+pins[0]]=''
        # Retained SRAM keeps its original AON socket clock, parked by the
        # fixture; only scanned FF loads use that root's inserted bypass.
        # Main SRAM remains on the test-enabled main clock tree. All SRAM
        # enables are isolated separately by the qualified capture protocol.
        macros={n+'/CLK':('' if c['pins']['CLK']=='i_chip_core.soc.digital.subsystem.usb.aonClock' else 'scan')
                for n,c in graph.items() if 'ip_sram__' in c['type']}
        assert len(macros)==20
        assert list(macros.values()).count('')==4
        expected_clocks.update(macros)
    phases=json.loads((a.functional/'phases.json').read_text()) if functional else {n+'/CLK':int(row['edge']=='falling') for row in rows for n in row['cells']}
    commands.append('set_input_transition 0.15 [get_ports clk_PAD]')
    (out / 'mode.sdc').write_text('\n'.join(commands) + '\n')
    queries = []
    for row in ([] if a.mode == 'reset' or functional else rows):
        source = ' '.join(n + '/Q' for n in row['cells'])
        target = ' '.join(n + ('/SI' if a.mode == 'shift' else '/D') for n in row['cells'])
        # Cross-group capture paths are real: query all state launches.
        if a.mode != 'shift':
            source = ' '.join(n + '/Q' for r in rows for n in r['cells'])
        queries.append(f'query lane{row["lane"]} [get_pins {{{source}}}] [get_pins {{{target}}}]')
    if a.mode == 'capture':
        for first in ('rising', 'falling'):
            for last in ('rising', 'falling'):
                source = ' '.join(n+'/Q' for r in rows if r['edge']==first for n in r['cells'])
                target = ' '.join(n+'/D' for r in rows if r['edge']==last for n in r['cells'])
                queries.append(f'query {first}-{last} [get_pins {{{source}}}] [get_pins {{{target}}}]')
    queries += ['query input [all_inputs] [all_registers -data_pins]',
                'query output [all_registers -output_pins] [all_outputs]',
                'query reset [get_ports {input_PAD[7]}] [all_registers -async_pins]']
    if functional:
        queries=[f'query {domain} [get_clocks {domain}] [get_clocks {domain}]' for domain in ('usb','main','aon','tck')]
        queries+=['query raw-reset [all_registers -output_pins] [all_registers -async_pins]']
    script = out / 'timing.tcl'
    script.write_text(f'''set ::env(_TCL_ENV_IN) {{{a.environment.resolve()}}}
set ::env(SCRIPTS_DIR) {{{scripts}}}
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
set ::env(DEFAULT_CORNER) {corner}
set ::env(STA_CORNERS) [list {corner}]
define_corners {corner}
set libs [list]
foreach key {{CELL_LIBS PAD_LIBS}} {{
 dict for {{pattern paths}} $::env($key) {{
  if {{[string match $pattern $::env(DEFAULT_CORNER)]}} {{lappend libs {{*}}$paths}}
 }}
}}
dict for {{name macro}} $::env(MACROS) {{
 dict for {{pattern paths}} [dict get $macro lib] {{
  if {{[string match $pattern $::env(DEFAULT_CORNER)]}} {{lappend libs {{*}}$paths}}
 }}
}}
set f [open {{{out}/libraries.txt}} w]
foreach lib [lsort -unique $libs] {{read_liberty -corner {corner} $lib; puts $f $lib}}
close $f
read_db {{{state['odb']}}}
source {{{out}/mode.sdc}}
set_global_vars
set ::env(SET_RC_VERBOSE) 1
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
estimate_parasitics -placement
set f [open {{{out}/paths.tsv}} w]
puts $f "group\tcheck\tslack_ns\tstart\tend"
proc query {{label from to}} {{
 global f
 foreach delay {{max min}} {{
  set paths [find_timing_paths -from $from -to $to -path_delay $delay -group_path_count 1]
  if {{![llength $paths]}} {{puts $f "$label\t$delay\tNONE\t\t"}}
  foreach path $paths {{
   puts $f "$label\t$delay\t[get_property $path slack]\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]"
  }}
  puts "QUERY $label $delay"
  report_checks -from $from -to $to -path_delay $delay -group_path_count 1 -format full_clock_expanded -fields {{slew cap fanout}} -digits 6
 }}
}}
{chr(10).join(queries)}
close $f
set f [open {{{out}/clocks.tsv}} w]
puts $f "pin\tclocks\tfalling"
set negative [all_registers -fall_clock {'tck' if functional else 'scan'} -clock_pins]
foreach pin [all_registers -clock_pins] {{
 set names [list]
 foreach c [get_property $pin clocks] {{lappend names [get_full_name $c]}}
 puts $f "[get_full_name $pin]\t$names\t[expr {{$pin in $negative}}]"
}}
close $f
report_check_types -max_slew -max_capacitance -max_fanout -violators -digits 6 > {{{out}/electrical.rpt}}
report_check_types -recovery -removal -min_pulse_width -min_period -clock_gating_setup -clock_gating_hold -violators -digits 6 > {{{out}/controls.rpt}}
check_setup -verbose > {{{out}/coverage.rpt}}
write_sdc {{{out}/applied.sdc}}
set f [open {{{out}/periods.tsv}} w]
puts $f "clock\tperiod\twaveform"
foreach c [all_clocks] {{
 # Pinned Clock.waveform returns SI seconds; get_property has no waveform.
 set waveform [list]
 foreach edge [$c waveform] {{lappend waveform [expr {{$edge*1e9}}]}}
 puts $f "[get_full_name $c]\t[get_property $c period]\t$waveform"
}}
close $f
puts T37_TIMING_MEASURED
''')
    command = ['openroad', '-exit', '-threads', '8', str(script)]
    start = time.monotonic()
    preflight=out/'preflight.tcl'
    preflight.write_text(script.read_text().split('read_db {',1)[0]+'puts T37_LIBRARY_PREFLIGHT_COMPLETE\n')
    with (out/'preflight.log').open('w') as log:
        pre=subprocess.run(['openroad','-exit',str(preflight)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    assert pre.returncode==0 and 'T37_LIBRARY_PREFLIGHT_COMPLETE' in (out/'preflight.log').read_text()
    libraries=[Path(q) for q in (out/'libraries.txt').read_text().splitlines()]
    inputs = [Path(__file__), script, out/'mode.sdc', a.state, a.environment, Path(state['odb']), a.audit/'result.json',
              insert / 'result.json', insert / 'after.json', insert / 'chains.json',manifest_path,
              campaign/'result.json',vector,executable,binary,scripts/'openroad/common/io.tcl',scripts/'openroad/common/set_rc.tcl',
              ROOT/'tools/physical/scan_constraints.py',ROOT/'tools/timing/usb_qualification.py',
              ROOT/'tools/physical/scan_libraries.py']+functional_inputs+libraries+authenticate(libraries)
    frozen={str(q):sha(q) for q in inputs}
    with (out / 'timing.log').open('w') as log:
        run = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    log = (out / 'timing.log').read_text()
    success = run.returncode == 0 and 'T37_TIMING_MEASURED' in log and not any(l.startswith(('[ERROR', 'Error:')) for l in log.splitlines())
    if success:
        applied=(out/'applied.sdc').read_text()
        envelope((out/'mode.sdc').read_text(),applied)
        if functional:
            assert pairs(applied)==pairs(sdc.read_text()), 'Changed functional exceptions'
            wanted=[s for s in commands if s.startswith('create_generated_clock ')]
            actual=[s for s in applied.splitlines() if s.startswith('create_generated_clock ')]
            assert actual==[s.replace('[get_ports clk_PAD]','[get_ports {clk_PAD}]') for s in wanted]
        else:
            assert pairs(applied)=={}, 'Unexpected scan exception'
        expected_periods=dict(usb=1000/48,main=125,aon=31250,tck=10000) if functional else dict(scan=100)
        with (out/'periods.tsv').open() as f: periods=list(csv.DictReader(f,delimiter='\t'))
        assert {r['clock'] for r in periods}==set(expected_periods) and len(periods)==len(expected_periods)
        for row in periods:
            period=expected_periods[row['clock']];actual=float(row['period'])
            # Binary32 STA seconds plus text serialization, never slack tolerance.
            assert math.isfinite(actual) and abs(actual-period)<=period*2**-23+0.0000005
            waveform=[float(v) for v in row['waveform'].split()]
            assert len(waveform)==2 and abs(waveform[0])<0.0000005 and abs(waveform[1]-period/2)<=period*2**-23+0.0000005
        with (out/'clocks.tsv').open() as f:
            clock_rows = list(csv.DictReader(f,delimiter='\t'))
        validate_clocks(clock_rows,expected_clocks,phases)
        faults=[('missing-clock-endpoint',clock_rows[1:]),
                ('wrong-clock', [dict(clock_rows[0],clocks='wrong'),*clock_rows[1:]])]
        if phases:
            pin=next(iter(phases))
            faults.append(('wrong-scan-phase',[dict(r,falling=str(1-int(r['falling']))) if r['pin']==pin else r for r in clock_rows]))
        rejected=[]
        for label,fault in faults:
            try:validate_clocks(fault,expected_clocks,phases)
            except AssertionError:rejected.append(label)
            else:raise AssertionError('Clock fault accepted: '+label)
    assert [str(q) for q in libraries]==(out/'libraries.txt').read_text().splitlines(), 'Selected libraries changed'
    assert {str(q):sha(q) for q in inputs}==frozen, 'Timing inputs changed during run'
    result = dict(status='measured_not_qualified' if success else 'failed', mode=a.mode, corner=corner,
                  clock_fault_controls=rejected if success else [],
                  command=command, seconds=time.monotonic()-start, returncode=run.returncode,
                  input_sha256=frozen,
                  artifact_sha256={q.name:sha(q) for q in out.iterdir() if q.is_file()},
                  assumptions=(['Existing functional clocks and certified USB MCPs; complete executed clock identity check',
                    'No IO boundary contract in this functional screen; raw CDC/reset and timing-class qualification remain open'] if functional else ['Trial100ns scan period, not approved manufacturing speed',
                    'Tester input0..1ns, output setup1ns/hold0ns; inherited0.5ns slew/72.91fF load',
                    'Placement-estimated RC, not extracted routed parasitics',
                    'Entered fixture from qualified capture vectors; TCK parked low and12access bits intentionally unclocked',
                    'Static mode/SE; reset case omitted only in diagnostic reset mode; no entry/exit qualification',
                    'No functional MCP or false paths; raw reset phase is diagnostic, not tester procedure acceptance']))
    assert sha(Path(__file__))==executed_source_sha, 'Timing source changed during run'
    (out / 'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'], result['seconds'])
    if not success: raise SystemExit(log[-2000:])


if __name__ == '__main__':
    main()
