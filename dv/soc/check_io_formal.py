"""Focused T21 proofs with covers, actual faults, source hashes and hard caps. No CI."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from formal import validate_job, assertion_names

CASES = {
    'main8': ('MainTimerFormal', 'prove', 48, 6, 2),
    'main9': ('MainTimerFormal', 'prove', 48, 6, 2),
    'aon': ('AonTimerFormal', 'prove', 32, 4, 1),
    'wake': ('GpioWakeFormal', 'prove', 8, 4, 2),
    'gpio_denied': ('GpioDeniedFormal', 'prove', 16, 7, 1),
    'adc_denied': ('AdcDeniedFormal', 'prove', 16, 7, 1),
    'adc_scale': ('AdcScaleFormal', 'bmc', 16, 2, 1),
}

def run(output, cases):
    output = (ROOT / output).resolve(); output.relative_to(ROOT / 'build')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use fresh output; preserve prior evidence')
    output.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for parent in ('hw/lib', 'hw/ip/gpio', 'hw/ip/timers', 'hw/ip/aon_timer', 'hw/ip/adc')
                     for p in (ROOT / parent).rglob('*') if p.is_file() and p.suffix in ('.scala', '.yaml'))
    sources += [Path(__file__).resolve(), ROOT / 'tools/formal.py', ROOT / 'tools/env/lock.json',
                ROOT/'build.sbt', ROOT/'tools/sbt.py', *sorted((ROOT/'project').glob('*')),
                *(ROOT/f'build/t21/{n}/{n}_regs.json' for n in ('gpio','timers','aon_timer','adc'))]
    sources = [p for p in sources if p.is_file()]
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt = dict(status='running', source_sha256=hashes(), cases={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), assumptions=[
        'reset_n initially low, then arbitrary; one digital clock',
        'Denied jobs map origin0 to1 against owner0, covering every non-owner tag',
        'GPIO denied fixture ties clocks together; does not prove asynchronous FIFO liveness',
        'Scaler captures one arbitrary sample at its scripted start; bounded16, not unbounded',
        'No analog synchronizer, oscillator, physical pad or whole-chip timing claim'])
    def command(argv, log):
        start = time.monotonic()
        with log.open('w') as stream:
            try:
                p = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
                code = p.returncode
            except subprocess.TimeoutExpired:
                code = 124
        return dict(command=argv, returncode=code, seconds=time.monotonic()-start,
                    log=log.relative_to(ROOT).as_posix())
    try:
        for case in cases:
            top, mode, depth, assertions, covers = CASES[case]
            directory = output / case; directory.mkdir()
            entry = dict(jobs=[], status='running'); receipt['cases'][case] = entry
            added = 'set hw / Compile / unmanagedSourceDirectories ++= Seq(' + ','.join(
                f'file("/work/hw/ip/{n}/formal")' for n in ('gpio','adc','timers')) + ')'
            emission = command([sys.executable, 'tools/sbt.py', added,
                                f'hw/runMain deadhorse.timers.EmitIoFormal {case} {directory}/emit'], directory/'emit.log')
            entry['emission'] = emission
            if emission['returncode']: raise RuntimeError(f'{case} emission failed')
            for variant in ('cover','corrupt','correct'):
                sv = sorted((directory/'emit'/variant).glob('*.sv'))
                if not sv: raise RuntimeError('Missing emitted model')
                inventory={p.stem:tuple(re.findall(r'(assert__\w+):',p.read_text())) for p in sv}
                inventory={n:v for n,v in inventory.items() if v}
                module={'main8':'MainTimers','main9':'MainTimers','aon':'AonTimers'}.get(case,top)
                if variant=='corrupt':
                    inventory={module if n==top+'_Anon' else n:v for n,v in inventory.items()}
                if inventory!=({} if variant=='cover' else {module:assertion_names(assertions)}):
                    raise RuntimeError(f'Reviewed assertion inventory changed: {inventory}')
                jobmode = 'cover' if variant=='cover' else 'bmc' if variant=='corrupt' else mode
                engine = 'abc pdr' if jobmode=='prove' else 'btor btormc'
                expected = covers if variant=='cover' else assertions
                script = '\n'.join(['[options]', f'mode {jobmode}', f'depth {depth}', 'timeout 120',
                    '', '[engines]', engine, '', '[script]',
                    f'read_slang --top {top} '+' '.join(p.name for p in sv), f'prep -top {top} -flatten',
                    "fminit -seq reset_n 0,'z", 'async2sync', 'chformal -lower',
                    f'select -assert-count {expected} t:$'+('cover' if variant=='cover' else 'assert'),
                    'select -assert-count 1 t:$assume',
                    '', '[files]', *map(str,sv), ''])
                path=directory/(variant+'.sby');path.write_text(script)
                row=command(['sby','-d',str(directory/variant),str(path)], directory/(variant+'.log'))
                statusfile=directory/variant/'status'
                result=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
                row.update(variant=variant, mode=jobmode, engine=engine, depth=depth, solver_status=result,
                    model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sv})
                entry['jobs'].append(row)
                if result=='TIMEOUT':
                    row['status']='unresolved'
                else:
                    faults={'main8':{'d.assert__chisel3_builtin'},'main9':{'d.assert__chisel3_builtin'},
                            'aon':{'d.'+a for a in assertion_names(4)},
                            'wake':set(assertion_names(4)[1:]),
                            'gpio_denied':set(assertion_names(7)),
                            'adc_denied':set(assertion_names(7)),
                            'adc_scale':{assertion_names(2)[1]}}[case]
                    row['failed_properties']=validate_job(directory/variant, 'cover' if variant=='cover' else 'negative' if variant=='corrupt' else 'proof',row['returncode'],result,faults if variant=='corrupt' else None)
                    row['assertion_inventory']=inventory
                    row['status']='covered' if variant=='cover' else 'fault_rejected' if variant=='corrupt' else 'proved' if mode=='prove' else 'bounded'
                print(case,variant,row['status'],flush=True)
            entry['status']='unresolved' if any(j['status']=='unresolved' for j in entry['jobs']) else 'pass'
            (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if hashes()!=receipt['source_sha256']: raise RuntimeError('Proof sources changed during run')
        receipt['status']='pass' if all(c['status']=='pass' for c in receipt['cases'].values()) else 'unresolved'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
        for entry in receipt['cases'].values():
            if entry['status']=='running': entry['status']='failed'
    receipt['artifact_sha256']={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob('*')) if p.is_file() and p!=output/'result.json'}
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES))
    a=p.parse_args();r=run(a.output,a.cases);print(r['status'].upper(),r.get('error',''))
    sys.exit(0 if r['status']=='pass' else 1)
