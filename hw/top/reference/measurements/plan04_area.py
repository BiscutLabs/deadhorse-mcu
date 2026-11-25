"""Area-only characterization of PLAN04 digital blocks from production hierarchy."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.usb_boundary import groups

def main(base):
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    out=base/'new-digital-area';out.mkdir(exist_ok=False)
    hierarchy=base/'map/hier.json';design=json.loads(hierarchy.read_text())
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest(lib)==cfg['sha256']
    initial={str(p.relative_to(ROOT)):digest(p) for p in (hierarchy,lib,Path(__file__))}
    areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
    rows=[]
    blocks=[('OscClockReset',12500),('OscCtrl',18750000),('OscSleepTransfer',75000),('ResetCauses',18750000)]
    if any(n.split('$')[0]=='PowerReset' for n in design['modules']):blocks.append(('PowerReset',18750000))
    if any(n.split('$')[0]=='SocResetDomains' for n in design['modules']):blocks.append(('SocResetDomains',12500))
    for top,target in blocks:
        names=[n for n in design['modules'] if n.split('$')[0]==top];assert len(names)==1
        dest=out/top;dest.mkdir()
        constraints=dest/'mapping.constr';constraints.write_text(f'set_driving_cell {cfg["library"]}__buf_1\nset_load 50\n')
        script=dest/'area.ys';script.write_text('\n'.join([f'read_json {hierarchy}',f'hierarchy -top {names[0]}',
            f'rename {names[0]} {top}',f'synth -top {top} -flatten -nofsm -noabc',f'dfflibmap -liberty {lib}',
            f'abc -liberty {lib} -constr {constraints} -D {target}','clean -purge','check -assert',
            f'write_json {dest}/mapped.json',f'tee -o {dest}/area.txt stat -liberty {lib}','']))
        with (dest/'run.log').open('w') as stream:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        cells=json.loads((dest/'mapped.json').read_text())['modules'][top]['cells']
        assert all(c['type'] in areas for c in cells.values())
        total=sum(areas[c['type']] for c in cells.values())
        flops=[c for c in cells.values() if '__dff' in c['type']]
        uplift=sum(areas[c['type'].replace('__dff','__sdff')]-areas[c['type']] for c in flops)
        rows.append(dict(block=top,mapped_area_um2_measured=total,flops_measured=len(flops),
            scan_uplift_um2_estimated=uplift,mapped_sha256=digest(dest/'mapped.json'),
            scope='Isolated combinational/FF mapping with assumed50fF loads; no timing or physical acceptance'))
    assert initial=={str(p.relative_to(ROOT)):digest(p) for p in (hierarchy,lib,Path(__file__))}
    receipt=dict(status='measured_area_only',blocks=rows,input_sha256=initial,
        digital_area_um2_measured=sum(r['mapped_area_um2_measured'] for r in rows),
        scan_uplift_um2_estimated=sum(r['scan_uplift_um2_estimated'] for r in rows),
        scope='Nonoverlapping oscillator/reset/controller/FIFO/cause blocks and T33 PowerReset when present; existing peripheral holds and newly connected SoC glue measured in whole-top mapping. No macro/placement/CTS signoff.')
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',required=True)
    main(parser.parse_args().base)
