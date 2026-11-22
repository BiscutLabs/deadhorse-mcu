"""Whole-SoC raw IO, gate and reset screen under existing zero-delay block assumptions."""
import csv,json,math,subprocess,sys
from pathlib import Path
root=Path.cwd();base=root/'build/plan03/production-measure06';mhz=int(sys.argv[1])
out=base/f'boundary-{mhz}';out.mkdir(exist_ok=False)
original=(base/f'classes-{mhz}/classes.tcl').read_text()
prefix=original.split('set f [open')[0]
script=out/'timing.tcl'
script.write_text(prefix+f'''
foreach domain {{main aon usb}} {{
 set_input_delay 0 -clock $domain -add_delay $inputs
 set_output_delay 0 -clock $domain -add_delay [get_ports -filter "direction == output" *]
}}
set outputs [get_ports -filter "direction == output" *]
set f [open {out}/paths.tsv w]
puts $f "domain\tclass\tpolarity\tdelay_ns\tstart\tend\tslack_ns"
foreach domain {{main aon usb}} {{
 set from [all_registers -clock $domain -clock_pins]
 set to [all_registers -clock $domain -data_pins]
 foreach {{class launch capture}} [list IR $inputs $to RO $from $outputs IO $inputs $outputs] {{
  foreach mode {{max_rise max_fall min_rise min_fall}} {{
   foreach path [find_timing_paths -from $launch -to $capture -path_delay $mode -group_path_count [expr {{2*[llength $capture]}}] -endpoint_path_count 1] {{
    set last [lindex [get_property $path points] end]
    puts $f "$domain\t$class\t$mode\t[get_property $last arrival]\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"
   }}
  }}
 }}
}}
close $f
set f [open {out}/gates.tsv w]
puts $f "pin\tcheck\tslack_ns"
foreach mode {{max_rise max_fall min_rise min_fall}} {{
 set paths [find_timing_paths -to [get_pins core.core_clock_gate_i.cell_0/E] -path_delay $mode -group_path_count 1]
 if {{[llength $paths]!=1}} {{error "Missing actual ICG enable path"}}
 puts $f "core.core_clock_gate_i.cell_0/E\t$mode\t[get_property [lindex $paths 0] slack]"
}}
close $f
report_check_types -recovery -removal -min_pulse_width -min_period -violators -digits 6
write_sdc {out}/applied.sdc
puts BOUNDARY_SCREEN_COMPLETE
''')
r=subprocess.run(['sta','-no_init','-exit',str(script)],text=True,capture_output=True)
(out/'sta.log').write_text(r.stdout+r.stderr)
assert r.returncode==0 and 'BOUNDARY_SCREEN_COMPLETE' in r.stdout and not any(l.startswith('Error') for l in (r.stdout+r.stderr).splitlines()),(r.stdout+r.stderr)[-1000:]
with (out/'paths.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
result={}
for domain in ('main','aon','usb'):
 for kind in ('IR','RO','IO'):
  group=[dict(v,delay_ns=float(v['delay_ns']),slack_ns=float(v['slack_ns'])) for v in rows if v['domain']==domain and v['class']==kind]
  if not group:result[domain+'.'+kind]=None;continue
  assert all(math.isfinite(v['delay_ns']) and math.isfinite(v['slack_ns']) for v in group)
  result[domain+'.'+kind]=dict(worst=max((v for v in group if v['polarity'].startswith('max')),key=lambda v:v['delay_ns']),
    minimum_hold_slack_ns=min(v['slack_ns'] for v in group if v['polarity'].startswith('min')))
with (out/'gates.tsv').open() as f:gates=list(csv.DictReader(f,delimiter='\t'))
receipt=dict(status='measured_raw_diagnostic',classes=result,gates=gates,
  assumptions='Existing block screen: zero IO arrival/required delay in every domain, 0.5 ns slew, 0.05 pF load, ideal clocks. No asynchronous boundary exception. Six synchronous memory interfaces exposed.',
  limitations='Raw async sampler/reset and CDC diagnostics are not qualified failures; no chip pad/analog/CTS signoff or SRAM timing claim. IO is duplicated by domain and is not assigned to a receiving clock.')
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(mhz,json.dumps(receipt),flush=True)
