from pathlib import Path
import sys,json,subprocess,time
sys.path.append('hw/ip/usb');from evidence import simulation_sources,digest
out=Path('build/t32/usb-fullsize01');out.mkdir()
before=simulation_sources();command=['python3','tools/sbt.py','testOnly deadhorse.usb.UsbThroughputSpec'];start=time.monotonic()
with (out/'simulation.log').open('w') as log:r=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
text=(out/'simulation.log').read_text();ok=r.returncode==0 and 'Tests: succeeded 2, failed 0' in text and 'All tests passed.' in text and simulation_sources()==before
receipt=dict(status='pass' if ok else 'failed',command=command,returncode=r.returncode,seconds=time.monotonic()-start,source_sha256=before,log_sha256=digest(out/'simulation.log'),qualification='Full16byte seeded production-wrapper simulation, including unchanged slow-service negative control; no proof claim',commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt['seconds'],flush=True)
raise SystemExit(0 if ok else 1)
