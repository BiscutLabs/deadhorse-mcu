"""Run unchanged physical recipes on PLAN05's freshly buffered USB bus fixture.

Run each phase in the pinned digital environment. Between prepare and extract,
run run.tcl in the pinned physical environment; after extract run its three RC
scripts there. No proof solver or whole-chip physical signoff is involved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
OLD=ROOT/'build/plan03/usb-closure'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,d):Path(p).write_text(json.dumps(d,indent=2)+'\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',required=True);parser.add_argument('--phase',choices=('prepare','extract','audit'),required=True)
    parser.add_argument('--evidence',default='build/plan05/usb-evidence-qualified01')
    args=parser.parse_args();out=(ROOT/args.base).resolve();out.relative_to(ROOT/'build');bus=out/'bus-physical01'
    prepared=read(out/'result.json');assert prepared['status']=='prepared'
    for name,h in prepared['source_sha256'].items():assert sha(ROOT/name)==h,name
    for name,h in prepared['artifact_sha256'].items():assert sha(out/name)==h,name
    receipt=dict(status='running',phase=args.phase,commands=[],runner_sha256=sha(__file__),original_scripts={})
    result=out/('physical-'+args.phase+'.json');assert not result.exists()
    def run(command,label):
        then=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            process=subprocess.run(list(map(str,command)),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(command=list(map(str,command)),returncode=process.returncode,seconds=time.monotonic()-then))
        write(result,receipt);assert process.returncode==0,label
    def derive(name,replacements,scratch=False):
        original=ROOT/'scratch'/name;code=original.read_text();receipt['original_scripts'][str(original)]=sha(original)
        for before,after in replacements:
            assert code.count(before)==1,(name,before)
            code=code.replace(before,after)
        target=(ROOT/'scratch'/('plan05_'+out.name+'_'+name)) if scratch else out/name
        assert not target.exists();target.write_text(code);return target
    try:
        if args.phase=='prepare':
            driver=derive('plan03_bus_physical_prepare.py',[
                ("out=root/'build/plan03/usb-closure/bus-physical01'",f"out=Path('{bus}')"),
                ("out.parent/'physical-hold01/replacements.json'",f"Path('{OLD}/physical-hold01/replacements.json')")])
            run([sys.executable,driver],'physical-prepare')
            receipt['next']=[f'python tools/physical/run.py openroad -exit {bus}/run.tcl > {out}/bus-physical01-driver.log']
        elif args.phase=='extract':
            driver=derive('plan03_bus_extract.py',[("Path('/work/build/plan03/usb-closure/bus-physical01')",f"Path('{bus}')")])
            run([sys.executable,driver],'physical-extract-prepare')
            receipt['next']=[f'python tools/physical/run.py openroad -exit {bus}/extract-{rc}/run.tcl' for rc in ('min','nom','max')]
        else:
            driver=derive('plan03_bus_timing.py',[
                ("out=root/'build/plan03/usb-closure/bus-physical01'",f"out=Path('{bus}')"),
                ("out.parent/'physical-hold01/replacements.json'",f"Path('{OLD}/physical-hold01/replacements.json')")])
            run([sys.executable,driver],'physical-boundary-timing')
            assert read(bus/'boundary-result.json')['status']=='boundary-pass'
            hold=derive('plan03_bus_hold.py',[
                ("Path('build/plan03/usb-closure')",f"Path('{out}')"),
                ("physical=root/'physical-hold01-audited'",f"physical=Path('{OLD}/physical-hold01-audited')")],scratch=True)
            run([sys.executable,hold],'physical-conservative-hold')
            manifest=read(ROOT/'build/plan04/usb-boundary02/physical-manifest.json')
            manifest.update(source=str(out/'bus-source-qualified01/result.json'),hold=str(out/'bus-hold01/result.json'),
                hold_driver=str(hold),bus=str(bus),seal=str(out/'derived-internal-seal.json'))
            write(out/'physical-manifest.json',manifest)
            run([sys.executable,'hw/ip/usb/physical_evidence.py','--manifest',out/'physical-manifest.json',
                 '--emission',out/'fresh-usb/usb','--output',out/'physical-audit'],'physical-audit')
            evidence=(ROOT/args.evidence).resolve();assert read(evidence/'result.json')['status']=='pass'
            write(out/'acceptance-manifest.json',dict(schema=1,physical=str(out/'physical-manifest.json'),
                sampling=str(evidence/'sampling-manifest.json'),packet=str(evidence/'packet-manifest.json')))
        receipt['status']='pass'
    except Exception as error:receipt.update(status='failed',error=str(error));raise
    finally:
        receipt['artifact_sha256']={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p!=result}
        write(result,receipt)
if __name__=='__main__':main()
