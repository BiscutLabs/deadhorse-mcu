"""T20 reset-only mapped-netlist repair; preserves every original cell and clock."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.fanout import BUFFER,buffer_module,verify


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mapped',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    source=(ROOT/a.mapped).resolve();source.relative_to(ROOT/'build')
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    assert digest(lib)==cfg['sha256']
    design=json.loads(source.read_text());old=design['modules']['DeadhorseSoc']
    names=('_coreRelease_released','_serviceRelease_released')
    roots={name:old['netnames'][name]['bits'] for name in names}
    assert all(len(bits)==1 and isinstance(bits[0],int) for bits in roots.values())
    assert len({bits[0] for bits in roots.values()})==2
    new,inserted=buffer_module(old,'mainClock',source_bits={b[0] for b in roots.values()},prefix='soc_reset_')
    assert inserted
    verify(old,new,inserted)
    # Exercise the checker on this exact production netlist, not only a fixture.
    fault=copy.deepcopy(new)
    first=inserted[0]
    fault['cells'][first]['connections']['I']=fault['cells'][first]['connections']['Z'][:]
    try:verify(old,fault,inserted)
    except ValueError as e:
        assert 'cycle' in str(e)
    else:raise ValueError('Production reset-buffer cycle fault escaped')
    design['modules']['DeadhorseSoc']=new
    (out/'buffered.json').write_text(json.dumps(design))
    script=out/'export.ys'
    script.write_text(f'read_json {out}/buffered.json\ncheck -assert\nstat -liberty {lib}\nwrite_json {out}/mapped.json\nwrite_verilog -noattr -noexpr {out}/mapped.v\n')
    with (out/'export.log').open('w') as log:
        subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=log,stderr=subprocess.STDOUT,check=True,cwd=ROOT)
    def loads(module,bit):
        return sum(bits.count(bit) for c in module['cells'].values() for p,bits in c['connections'].items() if c['port_directions'][p]=='input')
    receipt=dict(status='verified_mapping_only',buffer_cell=BUFFER,count=len(inserted),limit=8,
        roots={n:dict(bit=b[0],before_loads=loads(old,b[0]),after_loads=loads(new,b[0])) for n,b in roots.items()},
        checks=['Every original cell/pin restored through non-inverting buffers','All clock pins unchanged','Production cycle negative rejected'],
        scope='No RTL/state change; asynchronous assertion retained through combinational buffers. STA including electrical and reset recovery/removal still required.',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),ROOT/'tools/timing/fanout.py',source,lib,ROOT/'tools/env/lock.json')},
        artifacts={str(p.relative_to(out)):digest(p) for p in out.iterdir() if p.is_file()})
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS reset-only mapping: {len(inserted)} buffers; original logic and clocks verified')


if __name__=='__main__':main()
