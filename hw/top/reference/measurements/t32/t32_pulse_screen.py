from pathlib import Path
import subprocess,json,hashlib
base=Path('build/t32/area07/mapped')
out=base/'pulse-screen-8';out.mkdir(exist_ok=False)
prefix=(base/'reset-screen-8/timing.tcl').read_text().split('puts ELECTRICAL_BEGIN')[0]
tcl=out/'timing.tcl';tcl.write_text(prefix+'\nreport_check_types -min_pulse_width -min_period -violators -verbose -digits 6\nputs PULSE_SCREEN_COMPLETE\n')
p=subprocess.run(['sta','-no_init','-exit',str(tcl)],capture_output=True,text=True)
(out/'sta.log').write_text(p.stdout+p.stderr)
assert p.returncode==0 and 'PULSE_SCREEN_COMPLETE' in p.stdout and not any(x.startswith('Error') for x in p.stdout.splitlines())
(out/'run.json').write_text(json.dumps(dict(command=['sta','-no_init','-exit',str(tcl)],returncode=p.returncode,tcl_sha256=hashlib.sha256(tcl.read_bytes()).hexdigest(),scope='All reported pulse/period violators; ideal clocks and raw boundary, not physical signoff'),indent=2)+'\n')
print(p.stdout[-10000:])
