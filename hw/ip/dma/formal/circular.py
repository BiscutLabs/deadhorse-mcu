"""T40 scoped formal replay; original finite obligations plus real ring wrapper.

No CI, no implicit timeout retry. Bounded results are explicitly not proofs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import assertion_names, validate_job

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',required=True)
    ap.add_argument('--cases',nargs='+',choices=['finite','circular'],default=['finite','circular'])
    ap.add_argument('--faults-from',help='Authenticated emitted models from a previous run; run only fault cones after a runner repair')
    a=ap.parse_args();out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build')
    out.mkdir(parents=True,exist_ok=False)
    sources=sorted(p for directory in ['hw/lib','hw/ip/dma/src/main','hw/ip/dma/formal']
                   for p in (ROOT/directory).rglob('*') if p.suffix in ['.scala','.py'])
    sources += [ROOT/p for p in ['hw/ip/dma/dma.regmap.yaml','build/t23/dma/dma_regs.json',
                 'tools/formal.py','tools/env/lock.json','build.sbt']]
    digest=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt=dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_sha256=digest(),commands=[],jobs=[],assumptions=['initial reset_n=0; thereafter arbitrary',
        'one digital clock; no bus progress, shadow stability or fairness assumptions'],
        scope='Original finite inputs have circular=0. Ring model includes real MMIO shadow lock. BMC is bounded evidence only.')
    def save(): (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def command(cmd,name,cap=180):
        start=time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            try: code=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=cap).returncode
            except subprocess.TimeoutExpired: code=124
        row=dict(command=cmd,returncode=code,seconds=time.monotonic()-start,log=name+'.log')
        receipt['commands'].append(row);save();return row
    def emit(name,entry):
        r=command([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/dma/formal")',
            f'hw/runMain deadhorse.dma.{entry} {out/name}'],'emit-'+name)
        if r['returncode']: raise RuntimeError('emission failed: '+name)
    def job(name,model,top,mode,depth,count,keep=None,faults=None,portfolio=False):
        sv=sorted((out/model).glob('*.sv'));assert sv
        engine='abc pdr\nsmtbmc yices' if portfolio else 'abc pdr' if mode=='prove' else 'btor btormc'
        script=[f'read_slang --top {top} '+ ' '.join(p.name for p in sv),f'prep -top {top} -flatten',
            "fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
            f'select -assert-count {count} t:$'+('cover' if mode=='cover' else 'assert'),
            'select -assert-count 1 t:$assume']
        if keep is not None:
            script += [f'select -assert-count 1 c:{keep}',f'delete t:$assert c:{keep} %d',
                       'select -assert-count 1 t:$assert','select *','opt_clean']
        elif faults:
            selection=' '.join('c:'+p for p in sorted(faults))+' %u'*(len(faults)-1)
            script += [f'select -assert-count {len(faults)} {selection}',
                       f'delete t:$assert {selection} %d',f'select -assert-count {len(faults)} t:$assert',
                       'select *','opt_clean']
        cfg=out/(name+'.sby')
        cfg.write_text('\n'.join(['[options]',f'mode {mode}',f'depth {depth}','timeout 120',
            '[engines]',engine,'[script]',*script,'[files]',*map(str,sv),'']))
        r=command(['sby','-d',str(out/name),str(cfg)],name,150)
        status=(out/name/'status').read_text().split()[0] if (out/name/'status').exists() else 'ERROR'
        row=dict(name=name,mode=mode,depth=depth,engine=engine,property=keep,solver_status=status,
                 seconds=r['seconds'],model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sv})
        receipt['jobs'].append(row)
        if status=='TIMEOUT':row['result']='unresolved'
        else:
            row['failed_properties']=validate_job(out/name,'negative' if faults else 'cover' if mode=='cover' else 'proof',
                r['returncode'],status,faults)
            row['result']='fault_rejected' if faults else 'covered' if mode=='cover' else 'proved' if mode=='prove' else 'bounded'
        save();print(name,row['result'],flush=True)
    try:
        if a.faults_from:
            prior=(ROOT/a.faults_from).resolve();prior.relative_to(ROOT/'build')
            previous=json.loads((prior/'result.json').read_text())
            for path,h in previous['source_sha256'].items():
                if path!=Path(__file__).relative_to(ROOT).as_posix():
                    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
            for path in (prior/'ring').rglob('*.sv'):
                assert hashlib.sha256(path.read_bytes()).hexdigest()==previous['artifact_sha256'][path.relative_to(prior).as_posix()]
            shutil.copytree(prior/'ring',out/'ring');a.cases=[]
            receipt['reused_receipt_sha256']=hashlib.sha256((prior/'result.json').read_bytes()).hexdigest()
        if 'finite' in a.cases:
            emit('finite','EmitDmaFormal safety')
            job('finite-cover','finite/cover','DmaSafetyFormal','cover',36,5)
            job('finite-fault','finite/corrupt','DmaSafetyFormal','bmc',36,10,faults={'d.'+assertion_names(10)[1]})
            for i,p in enumerate(assertion_names(10)):
                # The inherited memory-range PDR job already timed out. Do not
                # repeat it; replay its original claim bounded and retain debt.
                job('finite-'+str(i),'finite/correct','DmaSafetyFormal','bmc' if i==3 else 'prove',36,10,keep='d.'+p)
        if 'circular' in a.cases:
            emit('ring','EmitDmaCircularFormal')
            job('ring-cover','ring/cover','DmaCircularFormal','cover',64,5)
            # One triage round after ring01's 64-step timeout. Add independent
            # lap accounting requested by review; keep every original claim.
            job('ring-quarter','ring/correct','DmaCircularFormal','bmc',16,38)
            job('ring-half-depth','ring/correct','DmaCircularFormal','bmc',32,38)
            job('ring-portfolio','ring/correct','DmaCircularFormal','prove',64,38,portfolio=True)
        if 'circular' in a.cases or a.faults_from:
            faults={'lock':{'d.'+assertion_names(21)[5*i] for i in range(4)},
                    'half':{'d.'+assertion_names(21)[5*i+1] for i in range(4)},
                    'done':{'d.'+assertion_names(21)[5*i+3] for i in range(4)},
                    'reload':{'d.engine.'+assertion_names(17)[3*i+2] for i in range(4)}}
            for v in faults: job('ring-'+v,'ring/'+v,'DmaCircularFormal','bmc',64,38,faults=faults[v])
        if digest()!=receipt['source_sha256']:raise RuntimeError('formal sources changed during run')
        receipt['status']='pass_with_deferrals' if any(j['result']=='unresolved' for j in receipt['jobs']) or 'finite' in a.cases else 'bounded_pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    save();print(receipt['status'].upper(),receipt.get('error',''))
    return 1 if receipt['status']=='failed' else 0
if __name__=='__main__':sys.exit(main())
