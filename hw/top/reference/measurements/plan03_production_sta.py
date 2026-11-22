"""First production register-path screen; no false paths or USB class claims."""
import csv,json,math,subprocess,sys
from pathlib import Path
root=Path.cwd();base=root/(sys.argv[1] if len(sys.argv)>1 else 'build/plan03/production-measure01')
cfg=json.loads((root/'phys/gf180-ws-1x1/block-timing.json').read_text())
lib=root/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
for mhz in ([int(sys.argv[2])] if len(sys.argv)>2 else (8,9)):
    out=base/f'sta-{mhz}';out.mkdir(exist_ok=False)
    mapped=base/f'map-{mhz}'
    script=out/'timing.tcl'
    script.write_text(f'''read_liberty {lib}
read_verilog {mapped}/mapped.v
link_design DeadhorseSoc
set_units -time ns -capacitance pF
create_clock -name main -period {1000/mhz} [get_ports mainClock]
create_clock -name aon -period 1000 [get_ports i1_aonClock]
create_clock -name usb -period [expr {{1000.0/48}}] [get_ports i1_usbClock]
set inputs [get_ports -filter "direction == input" *]
foreach n {{mainClock i1_aonClock i1_usbClock}} {{set inputs [lsearch -all -inline -not -exact $inputs [get_ports $n]]}}
set_input_transition {cfg['input_transition_ns']} $inputs
set_load {cfg['output_load_pf']} [get_ports -filter "direction == output" *]
foreach pin [all_registers -clock_pins] {{
 if {{[llength [get_property $pin clocks]]!=1}} {{error "Unclocked/ambiguous register [get_full_name $pin]"}}
}}
set f [open {out}/paths.tsv w]
puts $f "domain\tpolarity\tdelay_ns\tstart\tend\tslack_ns"
foreach domain {{main aon usb}} {{
 set from [all_registers -clock $domain -clock_pins]
 set to [all_registers -clock $domain -data_pins]
 if {{![llength $from] || ![llength $to]}} {{error "Empty clock domain $domain"}}
 foreach mode {{max_rise max_fall min_rise min_fall}} {{
  foreach path [find_timing_paths -from $from -to $to -path_delay $mode -group_path_count [expr {{2*[llength $to]}}] -endpoint_path_count 1] {{
   set last [lindex [get_property $path points] end]
   puts $f "$domain\t$mode\t[get_property $last arrival]\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"
  }}
 }}
}}
close $f
puts ELECTRICAL_BEGIN
report_check_types -max_slew -max_capacitance -violators -digits 6
puts ELECTRICAL_END
report_checks -path_delay max -group_path_count 5 -format full_clock_expanded -digits 6
puts PRODUCTION_SCREEN_COMPLETE
''')
    run=subprocess.run(['sta','-no_init','-exit',str(script)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'sta.log').write_text(run.stdout)
    assert run.returncode==0 and 'PRODUCTION_SCREEN_COMPLETE' in run.stdout and not any(s.startswith('Error') for s in run.stdout.splitlines()),run.stdout[-2000:]
    with (out/'paths.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
    result={}
    for domain in ('main','aon','usb'):
        group=[dict(r,delay_ns=float(r['delay_ns']),slack_ns=float(r['slack_ns'])) for r in rows if r['domain']==domain]
        assert group and all(math.isfinite(r['delay_ns']) and math.isfinite(r['slack_ns']) for r in group)
        worst=max((r for r in group if r['polarity'].startswith('max')),key=lambda r:r['delay_ns'])
        result[domain]=dict(worst=worst,min_slack=min(r['slack_ns'] for r in group if r['polarity'].startswith('min')),
          budget_ns=.6*(1000/mhz if domain=='main' else 1000 if domain=='aon' else 1000/48),
          scope='same-domain register screening; USB certificates not yet applied')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(mhz,json.dumps(result),flush=True)
