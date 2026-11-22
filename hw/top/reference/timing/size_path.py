"""Size explicitly measured combinational cells with actual-Liberty proofs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tools.timing.usb_buffer_sizing import size


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--netlist',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--cell',action='append',required=True,help='Mapped instance=qualified replacement cell')
    a=ap.parse_args()
    source=(ROOT/a.netlist).resolve();source.relative_to(ROOT/'build')
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(lib)==cfg['sha256']
    replacements=dict(v.split('=',1) for v in a.cell);assert len(replacements)==len(a.cell)
    def yosys(name,lines):
        script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n')
        with (out/(name+'.log')).open('w') as log:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    # Resolve the actual STA instance names without guessing Yosys auto-renaming.
    yosys('read',[f'read_liberty -lib {lib}',f'read_verilog {source}',
        'hierarchy -check -top DeadhorseSoc','check -assert',f'write_json {out}/original.json'])
    design=json.loads((out/'original.json').read_text())
    module,proof=size(design['modules']['DeadhorseSoc'],lib,out/'proof',replacements=replacements)
    assert set(proof['cells'])==set(replacements)
    design['modules']['DeadhorseSoc']=module
    (out/'sized.json').write_text(json.dumps(design))
    yosys('export',[f'read_json {out}/sized.json','check -assert',f'stat -liberty {lib}',
        f'write_json {out}/mapped.json',f'write_verilog -noattr -noexpr {out}/mapped.v'])
    receipt=dict(status='proved_mapping_only',proof=proof,
        sources={str(p.relative_to(ROOT)):digest(p) for p in (source,lib,Path(__file__),ROOT/'tools/timing/usb_buffer_sizing.py')},
        artifacts={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()})
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS {len(replacements)} cell sizes; actual Liberty functions proved, polarity faults rejected')


if __name__=='__main__':main()
