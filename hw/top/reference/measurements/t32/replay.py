"""Fresh T32 physical-boundary measurement using preserved area07 producers.

Only artifact path constants are adapted; mapping, budgets and algorithms are
unchanged. Requires the pinned PDK and a previously qualified USB mapped island.
This measures pre-layout screens, not physical signoff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True)
    ap.add_argument('--usb-map',default='build/plan03/production-measure04/usb-mapping')
    ap.add_argument('--usb-certificate',default='build/plan03/fast02/fast/usb/timing/usb')
    a=ap.parse_args()
    def build_path(name):
        p=(ROOT/name).resolve();p.relative_to(ROOT/'build');return p
    out=build_path(a.output);usb=build_path(a.usb_map);certificate=build_path(a.usb_certificate)
    for p in (usb/'mapped.json',certificate/'mapped.json',certificate/'certificate/result.json'):
        if not p.is_file():raise ValueError('Missing qualified input: '+str(p))
    out.mkdir(parents=True,exist_ok=False);producers=out/'producers';producers.mkdir()
    names=['t32_area07_'+n+'.py' for n in ('hierarchy','sockets','map','partition','budget')]
    names+=['t32_layered_reset.py','t32_packed_reset.py','t32_timing_screen.py',
            't32_reset_timing.py','t32_reset_endpoints.py','t32_pulse_screen.py',
            't32_usb_class_screen.py','t32_usb_class_audit.py']
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    replacements={'build/t32/area07':out.relative_to(ROOT).as_posix(),
        'build/plan03/production-measure04/usb-mapping':usb.relative_to(ROOT).as_posix(),
        'build/plan03/fast02/fast/usb/timing/usb':certificate.relative_to(ROOT).as_posix()}
    receipt=dict(status='running',scope='8 MHz area07 flow; ideal-clock screens; no pad/macro/CTS signoff',
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),*[HERE/n for n in names]]},
        input_sha256={str(p.relative_to(ROOT)):digest(p) for p in (usb/'mapped.json',certificate/'mapped.json',certificate/'certificate/result.json')},
        path_replacements=replacements,commands=[],producer_sha256={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    tracked=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    def snapshot():
        return {n:digest(ROOT/n) for n in sorted(set(tracked)) if n and (ROOT/n).is_file() and not n.endswith('.md')}
    receipt['production_source_sha256']=snapshot()
    start=time.monotonic()
    def save():
        receipt['seconds']=time.monotonic()-start
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def run(command,label):
        begin=time.monotonic()
        with(out/(label+'.log')).open('w') as f:
            code=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=command,returncode=code,seconds=time.monotonic()-begin,log=label+'.log'))
        save()
        if code:raise RuntimeError(label+' failed; retain receipt')
        print('PASS '+label,flush=True)
    try:
        for n in names:
            value=(HERE/n).read_text()
            for old,new in replacements.items():value=value.replace(old,new)
            target=producers/n;target.write_text(value)
            receipt['producer_sha256'][n]=digest(target)
        run([sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.top.EmitSoc {out.relative_to(ROOT).as_posix()}/emit-8 production 8'],'emit')
        for stage in ('hierarchy','sockets','map','partition','budget'):
            run([sys.executable,str(producers/f't32_area07_{stage}.py')],stage)
        for name,extra in [('t32_timing_screen.py',[str(out/'mapped'),'8']),
                           ('t32_reset_timing.py',[str(out/'mapped')]),
                           ('t32_reset_endpoints.py',[str(out/'mapped')]),
                           ('t32_pulse_screen.py',[]),('t32_usb_class_screen.py',[]),('t32_usb_class_audit.py',[])]:
            run([sys.executable,str(producers/name),*extra],name.removesuffix('.py'))
        if snapshot()!=receipt['production_source_sha256']:raise RuntimeError('Source changed during measurement')
        if any(digest(ROOT/p)!=h for p,h in receipt['input_sha256'].items()):raise RuntimeError('USB input changed')
        receipt['status']='measurements complete; negative physical diagnostics are not signoff'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    save();print(receipt['status'],receipt.get('error',''),flush=True)
    return 1 if receipt['status']=='failed' else 0


if __name__=='__main__':sys.exit(main())
