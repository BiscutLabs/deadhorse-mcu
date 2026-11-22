"""Focused lite_core proofs, covers and actual RTL faults; never invokes CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import assertion_names, validate_job

CASES={'baseline':('LiteBaselineEquivalence',5,4,16),'adapter':('LiteAdapterFormal',10,5,16),
       'control':('LiteControlFormal',9,6,32)}

def prepare_reference():
    pin='4671317186003740ceb61360ba08c59bbdf10136'
    out=ROOT/'build/t25/reference';out.mkdir(parents=True,exist_ok=True)
    for source in ('shared/src/main/scala/riscay/Architecture.scala',
                   'designs/clocked/src/main/scala/riscay/clocked/ClockedCore.scala'):
        raw=subprocess.check_output(['git','-C',str(ROOT/'build/riscay-mcu'),'show',pin+':'+source]).decode()
        raw=raw.replace('package riscay.clocked','package lite_reference').replace('package riscay','package lite_reference').replace('import riscay._','')
        (out/Path(source).name).write_text(raw)

def run(output,cases):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    prepare_reference()
    paths=[p for root in ('hw/lib','hw/ip/lite_core/src/main','hw/ip/lite_core/formal','build/t25/reference')
           for p in (ROOT/root).rglob('*') if p.is_file() and p.suffix in ('.scala','.py')]
    paths += [ROOT/'hw/ip/lite_core/provenance.json',
              ROOT/'build.sbt',ROOT/'tools/formal.py',ROOT/'tools/sbt.py',ROOT/'tools/env/lock.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),cases={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        assumptions=['Initially reset_n=0, then arbitrary; one digital AON clock; no input restrictions'],
        scope='Full production widths; unbounded safety, finite cover/fault witnesses; no pad/CDC timing claim')
    def command(argv,log):
        start=time.monotonic()
        with log.open('w') as stream:
            try: code=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired: code=124
        return dict(command=argv,returncode=code,seconds=time.monotonic()-start,log=str(log.relative_to(out)))
    try:
        for case in cases:
            top,asserts,covers,depth=CASES[case];directory=out/case;directory.mkdir()
            entry=dict(jobs=[]);receipt['cases'][case]=entry
            row=command([sys.executable,'tools/sbt.py',
                'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/lite_core/formal")',
                'set hw / Compile / unmanagedSourceDirectories += file("/work/build/t25/reference")',
                f'hw/runMain deadhorse.lite_core.EmitLiteFormal {case} {directory}/emit'],directory/'emit.log')
            entry['emission']=row
            if row['returncode']:raise RuntimeError(case+' emission failed')
            for variant in ('cover','corrupt','correct'):
                sv=sorted((directory/'emit'/variant).glob('*.sv'))
                if not sv:raise RuntimeError('Missing model')
                mode='cover' if variant=='cover' else 'bmc' if variant=='corrupt' else 'prove'
                engine='abc pdr' if mode=='prove' else 'btor btormc'
                sby=directory/(variant+'.sby')
                sby.write_text('\n'.join(['[options]',f'mode {mode}',f'depth {depth}','timeout 120',
                    '[engines]',engine,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in sv),
                    f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                    f'select -assert-count {covers if mode=="cover" else asserts} t:$'+('cover' if mode=='cover' else 'assert'),
                    'select -assert-count 1 t:$assume','[files]',*map(str,sv),'']))
                row=command(['sby','-d',str(directory/variant),str(sby)],directory/(variant+'.log'))
                status=directory/variant/'status'
                result=status.read_text().split()[0] if status.exists() else 'ERROR'
                row.update(variant=variant,mode=mode,engine=engine,depth=depth,solver_status=result,
                    model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sv})
                entry['jobs'].append(row)
                if result=='TIMEOUT':
                    row['status']='unresolved'
                else:
                    faults={'baseline':{assertion_names(5)[4]},
                            'adapter':{assertion_names(10)[9]},
                            'control':{assertion_names(9)[8]}}[case]
                    row['failed_properties']=validate_job(directory/variant,
                        'cover' if mode=='cover' else 'negative' if variant=='corrupt' else 'proof',
                        row['returncode'],result,faults if variant=='corrupt' else None)
                    row['status']='covered' if mode=='cover' else 'fault_rejected' if variant=='corrupt' else 'proved'
                print(case,variant,row['status'],flush=True)
                (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Proof sources changed during run')
        receipt['status']='unresolved' if any(j['status']=='unresolved' for c in receipt['cases'].values() for j in c['jobs']) else 'pass'
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--cases',nargs='+',choices=CASES,default=list(CASES));a=p.parse_args()
    sys.exit(0 if run(a.output,a.cases)['status']=='pass' else 1)
