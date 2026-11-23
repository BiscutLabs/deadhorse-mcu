import csv,json,re,subprocess,sys
from pathlib import Path
base=Path(sys.argv[1]);out=base/'reset-endpoints-8';out.mkdir(exist_ok=False)
prefix=(base/'reset-screen-8/timing.tcl').read_text().split('puts ELECTRICAL_BEGIN')[0]
m=json.loads((base/'map-8/canonical.json').read_text())['modules']['DeadhorseSoc']
pins=[name+'/'+pin for name,c in m['cells'].items() for pin in ('RN','SETN') if pin in c['connections']]
script=out/'timing.tcl'
script.write_text(prefix+f'''
set capture [get_pins {{{' '.join(pins)}}}]
set f [open {out}/paths.tsv w]
puts $f "mode\\tstart\\tend\\tslack_ns"
foreach mode {{max_rise max_fall min_rise min_fall}} {{
 foreach path [find_timing_paths -to $capture -path_delay $mode -group_path_count [expr {{2*[llength $capture]}}] -endpoint_path_count 1] {{
  puts $f "$mode\\t[get_full_name [get_property $path startpoint]]\\t[get_full_name [get_property $path endpoint]]\\t[get_property $path slack]"
 }}
}}
close $f
puts RESET_ENDPOINTS_COMPLETE
''')
p=subprocess.run(['sta','-no_init','-exit',str(script)],text=True,capture_output=True)
log=p.stdout+p.stderr;(out/'sta.log').write_text(log)
assert p.returncode==0 and 'RESET_ENDPOINTS_COMPLETE' in log and not any(s.startswith('Error') for s in log.splitlines()),log[-1000:]
with(out/'paths.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
assert rows
receipt=dict(status='measured_raw_reset_endpoint_screen',endpoints_requested=len(pins),rows=len(rows),negative_rows=sum(float(r['slack_ns'])<0 for r in rows),minimum_slack_ns=min(float(r['slack_ns']) for r in rows))
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
# Reclassify existing report summaries correctly; preserve original diagnostic.
old=base/'reset-screen-8';report=(old/'sta.log').read_text();fixed=json.loads((old/'result.json').read_text())
for check in ('recovery','removal'):
    part=report.split('CHECK_BEGIN_'+check+'\n')[1].split('CHECK_END_'+check)[0]
    values=[float(x) for x in re.findall(r'^asynchronous\s+(-?\d+\.\d+)\s*$',part,re.M)]
    assert values
    fixed['checks'][check]=dict(minimum_reported_slack_ns=min(values),negative_summary_groups=sum(x<0 for x in values),qualification='Group summary, not endpoint violation count; see reset-endpoints-8')
(old/'result02.json').write_text(json.dumps(fixed,indent=2)+'\n')
