"""Run pinned OpenOCD against an actual TAP simulator and preserve both exits."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]


def probe(binary, script, output, sleep=False, aon=1000000):
    binary=Path(binary).resolve();binary.relative_to(ROOT/'build')
    script=Path(script).resolve();script.relative_to(ROOT)
    output=Path(output).resolve();output.relative_to(ROOT/'build')
    output.mkdir(parents=True,exist_ok=False)
    ready=output/'port.txt'
    control=output/'control.txt'
    if aon not in (32000,1000000):raise ValueError('Unsupported clock fixture')
    command=[str(binary),str(ready),'sleep' if sleep else 'run',str(control),str(aon)]
    receipt=dict(status='running',simulator_command=command,
                 binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                 script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                 config_sha256=hashlib.sha256((ROOT/'dv/soc/debug/openocd.cfg').read_bytes()).hexdigest(),
                 pin_helpers_sha256=hashlib.sha256((ROOT/'dv/soc/debug/pins.tcl').read_bytes()).hexdigest(),
                 start_from_sleep=sleep, aon_hz=aon)
    start=time.monotonic()
    with (output/'sim.log').open('w') as log:
        sim=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        try:
            while not ready.exists():
                if sim.poll() is not None:raise RuntimeError('Simulator exited before listening')
                if time.monotonic()-start>10:raise TimeoutError('Simulator startup')
                time.sleep(.02)
            port=int(ready.read_text().strip())
            receipt['command']=['openocd','-d2','-c',f'set sim_port {port}', '-c',f'set sim_control {{{control}}}',
                                '-f','dv/soc/debug/openocd.cfg','-f',str(script)]
            with (output/'openocd.log').open('w') as f:
                result=subprocess.run(receipt['command'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=120)
            receipt['openocd_exit']=result.returncode
            # Normal OpenOCD shutdown sends Q. A killed simulator is not a pass.
            receipt['simulator_exit']=sim.wait(timeout=10)
            if result.returncode or sim.returncode:raise RuntimeError('OpenOCD or simulator failed')
            if hashlib.sha256(binary.read_bytes()).hexdigest()!=receipt['binary_sha256']:
                raise RuntimeError('Simulator binary changed during probe')
            host=(output/'openocd.log').read_text();rtl=(output/'sim.log').read_text()
            if 'PASS T32' not in host:raise RuntimeError('No completed test marker')
            counts=dict(re.findall(r'(?<![a-z_])(application_addi|stopped_ns|wakes|reset_pulses|main_edges_during_reset|loader_starts|loader_busy_stops|aon_stopped_ns|service_reset_pulses)=(\d+)',rtl))
            receipt['observations']={k:int(v) for k,v in counts.items()}
            if 'PASS T32 BASIC' in host and counts.get('application_addi')!='1':
                raise RuntimeError('Expected exactly one application ADDI retirement')
            if sleep and (int(counts.get('stopped_ns','0'))<=0 or counts.get('wakes')!='1'):
                raise RuntimeError('Missing real stopped-clock wake')
            if 'PASS T32 INDEPENDENT RESET' in host and (counts.get('reset_pulses')!='1' or counts.get('main_edges_during_reset')!='0'):
                raise RuntimeError('Did not test short reset with main stopped')
            if 'PASS T32 LOADER OWNERSHIP' in host and (counts.get('loader_starts')!='1' or counts.get('loader_busy_stops')!='1' or int(counts.get('aon_stopped_ns','0'))<=0):
                raise RuntimeError('Missing loader busy/ownership/explicit START race')
            if 'PASS T32 INFLIGHT RESET' in host and (counts.get('service_reset_pulses')!='2' or int(counts.get('aon_stopped_ns','0'))<=0):
                raise RuntimeError('Missing stopped-destination service resets')
            receipt['status']='pass'
        except Exception as exc:
            receipt.update(status='failed',error=str(exc))
        finally:
            if sim.poll() is None:sim.terminate()
            receipt['simulator_final_exit']=sim.wait(timeout=10)
    receipt['seconds']=time.monotonic()-start
    receipt['logs_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.log')}
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),output,flush=True)
    return receipt


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary',required=True);ap.add_argument('--script',required=True)
    ap.add_argument('--output',required=True);ap.add_argument('--sleep',action='store_true')
    ap.add_argument('--aon',type=int,choices=(32000,1000000),default=1000000)
    a=ap.parse_args()
    raise SystemExit(0 if probe(a.binary,a.script,a.output,a.sleep,a.aon)['status']=='pass' else 1)
