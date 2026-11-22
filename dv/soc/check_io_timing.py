"""T21 pinned GF180 conservative block screens, not whole-chip/CDC signoff."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.timing.check import measure

def main():
    output=ROOT/'build/t21/timing-first'
    if output.exists() and any(output.iterdir()): raise ValueError('Use fresh output')
    output.mkdir(parents=True,exist_ok=True)
    sources=[p for n in ('gpio','timers','aon_timer','adc') for p in (ROOT/'hw/ip'/n).rglob('*')
             if p.is_file() and p.suffix in ('.scala','.yaml')]
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt=dict(status='running',source_sha256=hashes(),blocks={},limits=[
        'All blocks screened at existing main-9mhz limits: 60% of 1000/9 ns; no new exception',
        'This is conservative for 8MHz main and AON profiles; not physical oscillator/pad qualification',
        'GpioTiming ties both clocks/reset for all-cone logic screen; not asynchronous CDC/RDC timing signoff',
        'Mapped pre-layout cell delay, no placed wire delays; hold/reset rows retain the existing ideal boundary'])
    commands=[sys.executable,'tools/sbt.py',
        'set hw / Compile / unmanagedSources += file("/work/hw/ip/gpio/timing/GpioTiming.scala")',
        f'hw/runMain deadhorse.gpio.EmitGpioTiming build/t21/gpio/gpio_regs.json {output}/gpio/emit',
        f'hw/runMain deadhorse.timers.EmitTimers main build/t21/timers/timers_regs.json {output}/main8/emit 8',
        f'hw/runMain deadhorse.timers.EmitTimers main build/t21/timers/timers_regs.json {output}/main9/emit 9',
        f'hw/runMain deadhorse.timers.EmitTimers aon build/t21/aon_timer/aon_timer_regs.json {output}/aon/emit 8',
        f'hw/runMain deadhorse.adc.EmitAdc build/t21/adc/adc_regs.json {output}/adc/emit']
    receipt['emission_command']=commands
    try:
        with (output/'emit.log').open('w') as log:
            subprocess.run(commands,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        for name,top in [('gpio','GpioTiming'),('main8','MainTimers'),('main9','MainTimers'),('aon','AonTimers'),('adc','Adc')]:
            sv=[str(p) for p in sorted((output/name/'emit').glob('*.sv'))]
            result=measure(top,sv,'clk',output/name/'timing',operating_point='main-9mhz')
            receipt['blocks'][name]=result
            (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(name,result['status'],flush=True)
        if hashes()!=receipt['source_sha256']: raise ValueError('Source changed during timing')
        receipt['status']='pass' if all(r['status']=='pass' for r in receipt['blocks'].values()) else 'failed'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''))
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':sys.exit(main())
