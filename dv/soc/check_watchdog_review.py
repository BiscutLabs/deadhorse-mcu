"""Verify T26 frozen evidence, then check only reviewed test/mapping deltas. No CI."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dv.soc.check_io import snapshot

ALLOWED={
    'hw/top/reference/src/test/scala/deadhorse/top/SocDmaSpec.scala',
    'hw/top/reference/src/test/scala/deadhorse/top/SocWatchdogEpochSpec.scala',
    'tools/timing/check.py','tools/timing/fanout.py','tools/timing/test_fanout.py',
    'hw/ip/watchdog/check_timing.py','dv/soc/check_watchdog_review.py'}

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def guard_review(out):
    """Validate the final fail-closed selector guard without redoing unchanged STA."""
    from tools.timing.fanout import internal_reset_sources, buffer_module
    prior=ROOT/'build/t26/review02';old=json.loads((prior/'result.json').read_text())
    current=snapshot();allowed={'tools/timing/fanout.py','tools/timing/test_fanout.py','dv/soc/check_watchdog_review.py'}
    receipt=dict(status='running',source_sha256=current,prior_receipt_sha256=digest(prior/'result.json'),
        prior_status=old['status'],ci='Neither tier run',
        scope='Tool-only clock-ancestry rejection; exact existing buffer transforms and all prior evidence unchanged')
    try:
        if old['status']!='pass':raise ValueError('Prior focused review did not pass')
        changes={n:dict(before=old['source_sha256'].get(n),after=current.get(n))
            for n in set(current)|set(old['source_sha256']) if current.get(n)!=old['source_sha256'].get(n)}
        if set(changes)!=allowed:raise ValueError('Unexpected guard delta')
        receipt['reviewed_changes']=changes
        for name,row in changes.items():
            source=ROOT/'build/t26/guard-input/prior_sources'/name
            if digest(source)!=row['before']:raise ValueError('Prior tool bytes missing')
            target=out/'prior-sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        for directory in (prior,ROOT/'build/t26/frozen01'):
            r=json.loads((directory/'result.json').read_text())
            for name,sha in r['artifact_sha256'].items():
                if digest(directory/name)!=sha:raise ValueError('Archived artifact changed')
        if digest(ROOT/'build/t26/frozen01/result.json')!=old['prior_receipt_sha256']:
            raise ValueError('Original frozen receipt changed')
        receipt['transforms']={}
        for block,top in (('watchdog','Watchdog'),('pwm','GeneralTimers')):
            directory=prior/'timing'/block/'timing'
            original=json.loads((directory/'reset-unbuffered.json').read_text())['modules'][top]
            expected=json.loads((directory/'reset-buffered.json').read_text())['modules'][top]
            selected=internal_reset_sources(original,'clk')
            actual,inserted=buffer_module(original,'clk',source_bits=selected,prefix='reset_fanout_')
            if actual!=expected:raise ValueError('Measured reset transform changed')
            receipt['transforms'][block]=dict(identical=True,sources=sorted(selected),buffers=len(inserted))
        command=[sys.executable,'-m','unittest','tools.timing.test_fanout','tools.timing.test_timing']
        start=time.monotonic()
        with (out/'tests.log').open('w') as log:
            code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        receipt['tests']=dict(command=command,returncode=code,seconds=time.monotonic()-start)
        if code:raise ValueError('Guard tests failed')
        if current!=snapshot():raise ValueError('Sources changed during guard review')
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={x.relative_to(out).as_posix():digest(x) for x in out.rglob('*')
        if x.is_file() and x!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--guard-only',action='store_true');a=p.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    if a.guard_only:return guard_review(out)
    prior=ROOT/'build/t26/frozen01';old=json.loads((prior/'result.json').read_text())
    current=snapshot()
    receipt=dict(status='running',source_sha256=current,commands=[],ci='Neither tier run',
        prior_receipt_sha256=digest(prior/'result.json'),prior_status=old['status'],prior_error=old.get('error'),
        scope='Reuse unchanged frozen functional/top/output-proof evidence; new epoch fault and reset-buffer mapping checks only',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    def run(argv,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            code=subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=argv,returncode=code,seconds=time.monotonic()-start,log=label+'.log'))
        if code:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    def audit_prior():
        if digest(prior/'result.json')!=receipt['prior_receipt_sha256']:raise ValueError('Prior receipt changed')
        for name,sha in old['artifact_sha256'].items():
            if digest(prior/name)!=sha:raise ValueError('Prior artifact changed: '+name)
    try:
        if old['status']!='failed' or old.get('error')!='timing failed':raise ValueError('Unexpected original outcome')
        if any(c['returncode']!=0 for c in old['commands'] if c['log']!='timing.log'):
            raise ValueError('Original non-timing check did not pass')
        changes={n:dict(before=old['source_sha256'].get(n),after=current.get(n))
            for n in set(current)|set(old['source_sha256']) if current.get(n)!=old['source_sha256'].get(n)}
        if set(changes)!=ALLOWED:raise ValueError('Unreviewed source delta: '+str(set(changes)^ALLOWED))
        receipt['reviewed_changes']=changes
        audit_prior()
        # Preserve exact old edited bytes (verified against the original receipt).
        for name,row in changes.items():
            if row['before'] is None:continue
            source=ROOT/'build/t26/review-input/prior_sources'/name
            if digest(source)!=row['before']:raise ValueError('Missing exact prior source: '+name)
            target=out/'prior-sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        simulation=ROOT/'build/t23/soc-simulation'
        if not simulation.is_dir():raise ValueError('Missing shared simulation evidence')
        shutil.copytree(simulation,out/'prior-simulation')
        run([sys.executable,'-m','unittest','tools.timing.test_fanout','tools.timing.test_timing'],'timing-tool-tests')
        run([sys.executable,'tools/sbt.py','hw/testOnly deadhorse.top.SocWatchdogEpochSpec'],'epoch-simulation')
        run([sys.executable,'hw/ip/watchdog/check_timing.py','--output',str(out.relative_to(ROOT)/'timing'),
            '--blocks','watchdog','pwm'],'reset-buffer-timing')
        for block in ('watchdog','pwm'):
            before=json.loads((prior/'timing'/block/'timing/result.json').read_text())
            after=json.loads((out/'timing'/block/'timing/result.json').read_text())
            if before['assumptions']!=after['assumptions'] or before['class_failure_limits_ns']!=after['class_failure_limits_ns']:
                raise ValueError('Timing contract changed')
            if after['status']!='pass':raise ValueError('New timing did not pass')
        if snapshot()!=current:raise ValueError('Final frozen sources changed')
        audit_prior()
        receipt['status']='pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={x.relative_to(out).as_posix():digest(x) for x in out.rglob('*')
        if x.is_file() and x!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())
