"""Matched before/after boundary diagnostic; not async-boundary qualification."""
import json,re,subprocess,sys
from pathlib import Path
base=Path(sys.argv[1]);out=base/'reset-screen-8';out.mkdir(exist_ok=False)
prefix=(base/'sta-screen-8/timing.tcl').read_text().split('set f [open')[0]
m=json.loads((base/'map-8/canonical.json').read_text())['modules']['DeadhorseSoc']
gates=[n+'/E' for n,c in m['cells'].items() if '__icgtp_' in c['type']]
assert gates
script=out/'timing.tcl'
script.write_text(prefix+f'''
foreach domain {{main aon usb tck}} {{
 set_input_delay 0 -clock $domain -add_delay $inputs
 set_output_delay 0 -clock $domain -add_delay [get_ports -filter "direction == output" *]
}}
puts ELECTRICAL_BEGIN
report_check_types -max_slew -max_capacitance -violators -digits 6
puts ELECTRICAL_END
foreach check {{recovery removal min_pulse_width min_period}} {{
 puts CHECK_BEGIN_$check
 report_check_types -$check -digits 6
 puts CHECK_END_$check
}}
set f [open {out}/gates.tsv w]
puts $f "pin\\tmode\\tslack_ns"
foreach pin {{ {' '.join(gates)} }} {{
 foreach mode {{max_rise max_fall min_rise min_fall}} {{
  set paths [find_timing_paths -to [get_pins $pin] -path_delay $mode -group_path_count 1]
  if {{[llength $paths]!=1}} {{error "Missing ICG check $pin $mode"}}
  puts $f "$pin\\t$mode\\t[get_property [lindex $paths 0] slack]"
 }}
}}
close $f
puts RESET_SCREEN_COMPLETE
''')
p=subprocess.run(['sta','-no_init','-exit',str(script)],text=True,capture_output=True)
log=p.stdout+p.stderr;(out/'sta.log').write_text(log)
assert p.returncode==0 and 'RESET_SCREEN_COMPLETE' in log and not any(s.startswith('Error') for s in log.splitlines()),log[-1600:]
sections={}
for check in ('recovery','removal','min_pulse_width','min_period'):
    section=log.split('CHECK_BEGIN_'+check+'\n',1)[1].split('CHECK_END_'+check,1)[0]
    numbers=[float(x) for x in re.findall(r'(-?\d+\.\d+)\s+\((?:VIOLATED|MET)\)',section)]
    sections[check]=dict(violations=section.count('(VIOLATED)'),minimum_reported_slack_ns=min(numbers) if numbers else None)
electrical=log.split('ELECTRICAL_BEGIN\n')[1].split('ELECTRICAL_END')[0]
result=dict(status='raw_matched_boundary_diagnostic',checks=sections,electrical_violations=electrical.count('(VIOLATED)'),
  assumptions='Zero input/output delay in all four domains, ideal clocks, same slew/load as register screen; intentionally raw asynchronous reset/CDC boundaries, not signoff or exception qualification')
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
