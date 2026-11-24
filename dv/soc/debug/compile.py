"""Compile one emitted production TAP fixture with runtime assertions enabled."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,shutil

ROOT=Path(__file__).resolve().parents[3]

def compile_sim(emitted,output):
    emitted=Path(emitted).resolve();emitted.relative_to(ROOT/'build')
    output=Path(output).resolve();output.relative_to(ROOT/'build');output.mkdir(parents=True,exist_ok=False)
    sources=sorted(emitted.glob('*.sv'))+sorted(emitted.glob('*.v'))
    package=emitted/'dm_pkg.sv';sources.remove(package)
    sources=[package,*sources,ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv',
             ROOT/'dv/soc/debug/remote_bitbang.cpp']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt=dict(status='running',source_sha256=hashes())
    archive=output/'driver-sources';archive.mkdir()
    for name in ('remote_bitbang.cpp','compile.py'):
        shutil.copyfile(ROOT/'dv/soc/debug'/name,archive/name)
    cmd=['verilator','--cc','--exe','--build','--assert','-DENABLE_INITIAL_MEM_','-DENABLE_INITIAL_REG_',
         '-j','4','-Wno-fatal','--top-module','SocExternalClockTest','--Mdir',str(output/'obj'),*map(str,sources)]
    start=time.monotonic()
    with (output/'compile.log').open('w') as log:
        p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    receipt.update(command=cmd,returncode=p.returncode,seconds=time.monotonic()-start)
    if p.returncode==0 and hashes()==receipt['source_sha256']:
        receipt['status']='compiled'
        receipt['binary_sha256']=hashlib.sha256((output/'obj/VSocExternalClockTest').read_bytes()).hexdigest()
    else:receipt['status']='failed'
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if receipt['status']=='compiled' else 1

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--emitted',required=True);ap.add_argument('--output',required=True)
    a=ap.parse_args();raise SystemExit(compile_sim(a.emitted,a.output))
