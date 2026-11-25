"""Bind the existing mapped USB snapshot and prepare a standalone physical run."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT))
from tools.pdk import root as pdk_root,liberty as pdk_liberty
from pdk_views import manifest as pdk_manifest,require_manifest,view as physical_view

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def linux(p):return '/work/'+Path(p).resolve().relative_to(ROOT).as_posix()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();src=a.snapshot.resolve();out=a.output.resolve()
    src.relative_to(ROOT/'build');out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    root=json.loads((src/'result.json').read_text());block=src/'timing/usb';timing=json.loads((block/'result.json').read_text())
    bound={n:h for n,h in root['source_sha256'].items() if n.startswith(('hw/ip/usb/src/main/','hw/lib/src/main/','hw/top/stubs/','hw/vendor/usb/','tools/timing/')) or n in ('build.sbt','tools/env/lock.json','tools/sbt.py')}
    if not bound or any(sha(ROOT/n)!=h for n,h in bound.items()):raise ValueError('Changed production/timing source')
    for n,h in timing['flow_sha256'].items():
        if sha(ROOT/n)!=h:raise ValueError('Changed baseline flow')
    for n,h in timing['source_sha256'].items():
        p=ROOT/n.removeprefix('/work/')
        if sha(p)!=h:raise ValueError('Changed baseline emission')
    pdk=pdk_root();sc=pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0'
    lib=sc/'lib/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    if lib!=pdk_liberty():raise ValueError('Changed mapping corner')
    physical_view('libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef')
    physical_view('libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef')
    ties=out/'ties.ys'
    ties.write_text(f'read_liberty -lib {linux(lib)}\nread_verilog {linux(block/"mapped.v")}\nhierarchy -top Usb\nhilomap -hicell gf180mcu_fd_sc_mcu7t5v0__tieh Z -locell gf180mcu_fd_sc_mcu7t5v0__tiel ZN -singleton\nwrite_verilog -noattr -noexpr {linux(out/"mapped-ties.v")}\n')
    with (out/'ties.log').open('w') as log:subprocess.run(['yosys','-Q','-T','-s',str(ties)],stdout=log,stderr=subprocess.STDOUT,check=True)
    baseline=(block/'timing.tcl').read_text().replace(linux(block/'paths.tsv'),linux(out/'prelayout/paths.tsv')).replace(linux(block/'gate_checks.tsv'),linux(out/'prelayout/gate_checks.tsv'))
    baseline=baseline.replace(linux(block/'mapped.v'),linux(out/'mapped-ties.v'))
    (out/'prelayout').mkdir();(out/'load.tcl').write_text(baseline)
    config=f'set out {{{linux(out)}}}\nset techlef {{{linux(sc/"techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef")}}}\nset celllef {{{linux(sc/"lef/gf180mcu_fd_sc_mcu7t5v0.lef")}}}\nsource /work/tools/physical/usb_place.tcl\n'
    (out/'run.tcl').write_text(config)
    inputs=[block/n for n in ('result.json','mapped.v','mapped.json','protocol.tcl','timing.tcl')]
    inputs += list((ROOT/'tools/physical').glob('*'))
    (out/'flow').mkdir()
    for p in (ROOT/'tools/physical').glob('*'):
        if p.is_file():(out/'flow'/p.name).write_bytes(p.read_bytes())
    inputs += [physical_view('libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef'),physical_view('libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef')]
    inputs += [pdk_liberty(p.stem.split('__')[1]) for p in sorted((sc/'lib').glob('*.lib'))]
    inputs += [physical_view(p.relative_to(pdk).as_posix()) for p in (pdk/'libs.tech/librelane').glob('rules.openrcx.gf180mcuD.*')]
    inputs += [ROOT/n for n in pdk_manifest()['input_sha256']]
    receipt=dict(status='prepared',pdk=pdk_manifest(),commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_sha256=bound,
        input_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in inputs if p.is_file()},
        scope='Standalone USB; estimated pad/reset contract retained; no whole-chip signoff',
        assumptions=dict(core_utilization_percent=55,placement_density=0.60,core_margin_um=10),ci='not run')
    (out/'inputs.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PREPARED '+str(out))
