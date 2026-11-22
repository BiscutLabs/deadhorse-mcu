"""Focused watchdog proofs, covers and actual RTL faults; never invokes CI."""
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

CASES={'channel':('WatchdogFormal',12,5,20),'break':('PwmBreakFormal',3,2,8),'pad':('PadDisableFormal',2,3,8)}

def run(output,cases):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for root in ('hw/lib','hw/ip/watchdog/src/main','hw/ip/watchdog/formal','hw/ip/pwm/src/main','hw/ip/pinmux/src/main')
           for p in (ROOT/root).rglob('*') if p.is_file() and p.suffix in ('.scala','.py')]
    paths += [ROOT/'hw/ip/watchdog/watchdog.regmap.yaml',ROOT/'build/t26/watchdog/watchdog_regs.json',
              ROOT/'build.sbt',ROOT/'tools/formal.py',ROOT/'tools/sbt.py',ROOT/'tools/env/lock.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),cases={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        assumptions=['Initially por_n=0 and reset_n=0; thereafter both reset inputs and all commands/settings arbitrary; one AON sample clock'],
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
            emitter='EmitWatchdogFormal' if case=='channel' else f'EmitOutputDisableFormal {case}'
            row=command([sys.executable,'tools/sbt.py',
                'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/watchdog/formal")',
                f'hw/runMain deadhorse.watchdog.{emitter} {directory}/emit'],directory/'emit.log')
            entry['emission']=row
            if row['returncode']:raise RuntimeError(case+' emission failed')
            variants=('cover','early','hold','retention','correct') if case=='channel' else ('cover','corrupt','correct')
            for variant in variants:
                sv=sorted((directory/'emit'/variant).glob('*.sv'))
                if not sv:raise RuntimeError('Missing model')
                mode='cover' if variant=='cover' else 'bmc' if variant not in ('correct','cover') else 'prove'
                engine=('abc pdr\nsmtbmc yices\naiger suprove' if case=='channel' else 'abc pdr') if mode=='prove' else 'btor btormc'
                sby=directory/(variant+'.sby')
                sby.write_text('\n'.join(['[options]',f'mode {mode}',f'depth {depth}','timeout 120',
                    '[engines]',engine,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in sv),
                    f'prep -top {top} -flatten',("fminit -seq por_n 0,'z -seq reset_n 0,'z" if case=='channel' else "fminit -seq reset_n 0,'z"),'async2sync','chformal -lower',
                    f'select -assert-count {covers if mode=="cover" else asserts} t:$'+('cover' if mode=='cover' else 'assert'),
                    f'select -assert-count {2 if case=="channel" else 1} t:$assume','[files]',*map(str,sv),'']))
                row=command(['sby','-d',str(directory/variant),str(sby)],directory/(variant+'.log'))
                status=directory/variant/'status'
                result=status.read_text().split()[0] if status.exists() else 'ERROR'
                row.update(variant=variant,mode=mode,engine=engine,depth=depth,solver_status=result,
                    model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sv})
                entry['jobs'].append(row)
                if result=='TIMEOUT':
                    row['status']='unresolved'
                else:
                    faults={
                        'early':{assertion_names(12)[1],assertion_names(12)[7]},
                        'hold':{assertion_names(12)[3]},
                        'retention':{assertion_names(12)[0],assertion_names(12)[1],assertion_names(12)[3]}
                    }.get(variant,set()) if case=='channel' else ({assertion_names(3)[2]} if case=='break' else set(assertion_names(2)))
                    row['failed_properties']=validate_job(directory/variant,
                        'cover' if mode=='cover' else 'negative' if variant not in ('correct','cover') else 'proof',
                        row['returncode'],result,faults if variant not in ('correct','cover') else None)
                    row['status']='covered' if mode=='cover' else 'fault_rejected' if variant not in ('correct','cover') else 'proved'
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
