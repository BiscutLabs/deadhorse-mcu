"""Seal B4's transitive source and measurement evidence; no acceptance waiver."""
import hashlib,json,subprocess,time
from pathlib import Path
root=Path.cwd();out=root/'build/plan03/b4-seal01.json';assert not out.exists()
files=set()
for args in (['git','ls-files','-z'],['git','ls-files','--others','--exclude-standard','-z']):
    files.update(root/p for p in subprocess.check_output(args,text=True).split('\0') if p and (root/p).is_file())
for pattern in ('scratch/plan03_*','scratch/production_benchmark*.cpp','scratch/EmitProductionBenchmark.scala'):
    files.update(p for p in root.glob(pattern) if p.is_file())
roots=['build/plan03/production-measure04/usb-mapping','build/plan03/production-measure06',
       'build/plan03/production-performance04','build/plan03/production-measure03/context02-8',
       'build/plan03/production-measure03/context02-9']
for path in roots:files.update(p for p in (root/path).rglob('*') if p.is_file())
for mhz in (8,9):
    files.update(p for p in (root/f'build/plan03/production-measure01/emit-{mhz}').rglob('*') if p.is_file())
    files.add(root/f'build/plan03/production-measure01/map-{mhz}/hier.json')
    files.add(root/f'build/plan03/production-measure01/map-{mhz}/macro-sockets.json')
for p in ['build/plan03/fast02/fast/usb/formal/result.json','build/plan03/fast02/fast/usb/preenable-equivalence/result.json',
          'build/plan03/fast02/fast/usb/timing/usb/mapped.v','build/t28/firmware/lite.hex',
          'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib',
          'build/riscay-mcu/.tools/gf180-sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.lef']:
    files.add(root/p)
files.update(p for p in (root/'build/plan03/fast02/fast/usb/emit/usb').rglob('*') if p.is_file())
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
started=time.monotonic();hashes={}
for i,p in enumerate(sorted(files)):
    hashes[p.relative_to(root).as_posix()]=digest(p)
    if i and i%500==0:print('sealed',i,'files',flush=True)
out.write_text(json.dumps(dict(status='sealed_measurement_evidence',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    scope='B4 mapped digital measurements and planning estimates; not CI, complete task acceptance or physical signoff',
    files=hashes,wall_seconds=time.monotonic()-started),indent=2)+'\n')
print('PASS B4 source/evidence seal',len(hashes),'files',flush=True)
