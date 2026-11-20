"""Measure the effective constraints after the two physical diagnostic SDC loads."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from usb_prepare import ROOT,linux,sha
from usb_validate import require_complete

def commands(text,prefixes):
    # write_sdc wraps clock groups and long endpoint collections. Comparing
    # only command headers would silently omit the actual exception scope.
    text=re.sub(r'\\\r?\n\s*',' ',text)
    return {' '.join(line.split()) for line in text.splitlines() if line.startswith(prefixes)}

def compare(full,boundary,effective):
    for prefixes,expected in ((('set_multicycle_path','set_false_path','set_clock_groups'),full),
                              (('create_clock','set_input_delay','set_output_delay','set_input_transition','set_load'),boundary)):
        if commands(expected,prefixes)!=commands(effective,prefixes):raise ValueError('Effective constraints differ: '+str(prefixes))
    if not commands(effective,('set_propagated_clock',)):raise ValueError('Clocks not propagated')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--physical',type=Path,required=True);p.add_argument('--validation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args();out=a.output.resolve();out.relative_to(ROOT/'build')
    if not a.verify:out.mkdir(parents=True,exist_ok=False)
    result=[]
    for target in sorted(a.validation.iterdir()):
        if not target.is_dir():continue
        d=out/target.name
        if a.verify:
            require_complete((d/'run.log').read_text(),'USB_SDC_AUDIT_COMPLETE')
            compare((a.physical/'full.sdc').read_text(),(a.physical/'timing'/target.name/'boundary.sdc').read_text(),(d/'effective.sdc').read_text())
            result.append(dict(corner=target.name,status='pass',effective_sha256=sha(d/'effective.sdc')))
            continue
        d.mkdir()
        text=(target/'run.tcl').read_text().split('source /work/tools/physical/usb_diagnostics.tcl')[0]
        text+='\nread_liberty $liberty\nread_verilog $netlist\nlink_design Usb\nread_spef $spef\nread_sdc $full_sdc\nread_sdc $boundary_sdc\nset_propagated_clock [all_clocks]\n'
        text+=f'write_sdc {{{linux(d/"effective.sdc")}}}\nputs USB_SDC_AUDIT_COMPLETE\n'
        (d/'run.tcl').write_text(text)
        with (d/'run.log').open('w') as log:subprocess.run(['sta','-no_init','-exit',str(d/'run.tcl')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        require_complete((d/'run.log').read_text(),'USB_SDC_AUDIT_COMPLETE')
        compare((a.physical/'full.sdc').read_text(),(a.physical/'timing'/target.name/'boundary.sdc').read_text(),(d/'effective.sdc').read_text())
        result.append(dict(corner=target.name,status='pass',effective_sha256=sha(d/'effective.sdc')))
    if len(result)!=15:raise ValueError('Incomplete SDC audit')
    if a.verify:
        if result!=json.loads((out/'result.json').read_text()):raise ValueError('Stale SDC receipt')
    else:(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS effective clock, boundary and multicycle constraints across 15 corners')
