"""Bind a fresh pinned-Yosys parse to the routed netlist used by STA."""
import argparse
import json
from pathlib import Path
import subprocess
from usb_prepare import ROOT,linux,sha
from usb_graph import equivalent

import sys
sys.path.insert(0,str(ROOT))
from tools.pdk import root as pdk_root,liberty as pdk_liberty
from pdk_views import manifest as pdk_manifest,require_manifest,view as physical_view

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--physical',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    physical=a.physical.resolve();physical.relative_to(ROOT/'build')
    require_manifest(json.loads((physical/'inputs.json').read_text()))
    lib=pdk_liberty()
    script=f'read_liberty -lib {linux(lib)}\nread_verilog {linux(physical/"routed.v")}\nhierarchy -top Usb\nwrite_json {linux(out/"routed.json")}\n'
    (out/'parse.ys').write_text(script)
    with (out/'parse.log').open('w') as log:subprocess.run(['yosys','-Q','-T','-s',str(out/'parse.ys')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    a=json.loads((physical/'routed.json').read_text())['modules']['Usb'];b=json.loads((out/'routed.json').read_text())['modules']['Usb']
    result=equivalent(a,b)
    if result['inserted_cells']:raise ValueError('Unexpected parsed cells')
    result['sha256']={f.relative_to(ROOT).as_posix():sha(f) for f in (lib,physical/'routed.v',physical/'routed.json',out/'routed.json',out/'parse.ys',Path(__file__))}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS routed netlist and graph binding')
