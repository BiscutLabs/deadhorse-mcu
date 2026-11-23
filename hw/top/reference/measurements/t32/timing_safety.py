"""Retain all data hold and reset recovery/removal diagnostics for a mapping."""
import argparse
import csv
from pathlib import Path
import re
import subprocess
import time
from timing_iterations import ROOT,sha,write


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();base=args.base.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=(base/'timing.tcl').read_text()
    # Reuse the original netlist; put all newly emitted reports in this folder.
    script=source.replace(str(base/'paths.tsv'),str(out/'paths.tsv')).replace(str(base/'gate_checks.tsv'),str(out/'gate_checks.tsv'))
    script+='''
set reset_targets {}
foreach cell [all_registers] {
    set n [get_full_name $cell]
    foreach p {RN SETN} {lappend reset_targets {*}[get_pins -quiet $n/$p]}
}
set safety [open {OUT/safety.tsv} w]
puts $safety "class\tmode\tstart\tend\tslack_ns"
foreach {kind targets modes} [list hold [all_registers -data_pins] {min_rise min_fall} reset $reset_targets {min_rise min_fall max_rise max_fall}] {
    if {![llength $targets]} {error "Missing safety targets"}
    foreach mode $modes {
        foreach path [find_timing_paths -to $targets -path_delay $mode -group_path_count [expr {2*[llength $targets]}] -endpoint_path_count 1] {
            puts $safety "$kind\t$mode\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"
        }
    }
}
close $safety
puts "SAFETY_COMPLETE"
'''.replace('OUT',str(out))
    (out/'safety.tcl').write_text(script)
    command=['sta','-no_init','-exit',str(out/'safety.tcl')];start=time.monotonic()
    r=subprocess.run(command,capture_output=True,text=True,timeout=120)
    log=r.stdout+r.stderr;(out/'sta.log').write_text(log)
    assert r.returncode==0 and 'SAFETY_COMPLETE' in log and not re.search(r'^Error:',log,re.M)
    rows=list(csv.DictReader((out/'safety.tsv').open(),delimiter='\t'));assert rows
    summary={}
    for kind in ('hold','reset'):
        selected=[r for r in rows if r['class']==kind];assert selected
        summary[kind]=dict(rows=len(selected),negative=sum(float(r['slack_ns'])<0 for r in selected),
                           worst=min(selected,key=lambda r:float(r['slack_ns'])))
    write(out/'result.json',dict(status='measured-diagnostics',summary=summary,command=command,seconds=time.monotonic()-start,
        input_sha256={str(x):sha(x) for x in (base/'timing.tcl',base/'mapped.v',ROOT/'tools/timing/analyze.tcl',Path(__file__))},
        artifacts={p.name:sha(p) for p in out.iterdir() if p.is_file()},
        qualification='Ideal-clock pre-layout diagnostics; negative reset-removal is retained, not physical qualification.'))
    print(summary,flush=True)


if __name__=='__main__':main()
