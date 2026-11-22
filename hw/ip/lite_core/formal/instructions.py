"""All-cycle RV32E checks against pinned riscv-formal instruction models; no CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import assertion_names,validate_job
RF=ROOT/'hw/vendor/ibex_ref/riscv-formal/insns'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--instructions',nargs='+',required=True,choices=(RF/'isa_rv32i.txt').read_text().split())
    p.add_argument('--portfolio',action='store_true',help='Triage rung1: same proof with ABC PDR and Z3 induction')
    a=p.parse_args();out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[x for name in ('hw/ip/lite_core/src/main','hw/ip/lite_core/formal') for x in (ROOT/name).rglob('*')
           if x.is_file() and x.suffix in ('.scala','.py')]
    paths += [RF/'isa_rv32i.txt',*[RF/f'insn_{name}.v' for name in a.instructions],ROOT/'tools/formal.py',
              ROOT/'tools/sbt.py',ROOT/'build.sbt',ROOT/'tools/env/lock.json',ROOT/'hw/ip/lite_core/provenance.json']
    hashes=lambda:{x.relative_to(ROOT).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in paths}
    receipt=dict(status='running',source_sha256=hashes(),instructions={},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        assumptions=['Initially reset_n=0, then arbitrary; single digital clock; no other input assumptions'],
        scope='All-cycle selected instruction semantics on production core; register consistency and machine CSR/IRQ separate')
    def command(argv,log,timeout=180):
        begin=time.monotonic()
        with (out/log).open('w') as stream:
            try:code=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=argv,returncode=code,seconds=time.monotonic()-begin,log=log)
    try:
        for name in a.instructions:
            folder=out/name;folder.mkdir();row=dict(jobs=[]);receipt['instructions'][name]=row
            row['emission']=command([sys.executable,'tools/sbt.py',
                'set hw / Compile / unmanagedSources += file("/work/hw/ip/lite_core/formal/LiteInstruction.scala")',
                f'hw/runMain deadhorse.lite_core.EmitLiteInstruction {name} {folder}/emit'],name+'/emit.log')
            if row['emission']['returncode']:raise RuntimeError(name+' emission failed')
            for variant in ('cover','corrupt','correct'):
                sv=sorted((folder/'emit'/variant).glob('*.sv'))
                mode='cover' if variant=='cover' else 'bmc' if variant=='corrupt' else 'prove'
                engine=('abc pdr\nsmtbmc z3' if a.portfolio else 'abc pdr') if mode=='prove' else 'btor btormc'
                config=folder/(variant+'.sby');model=RF/f'insn_{name}.v'
                config.write_text('\n'.join(['[options]',f'mode {mode}','depth 32','timeout 120','[engines]',engine,
                    '[script]','read_slang --top LiteInstructionFormal -DRISCV_FORMAL_XLEN=32 -DRISCV_FORMAL_ILEN=32 '
                    '-DRISCV_FORMAL_ALIGNED_MEM '+' '.join(x.name for x in sv)+' '+model.name,
                    'prep -top LiteInstructionFormal -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                    f'select -assert-count {2 if mode=="cover" else 14} t:$'+('cover' if mode=='cover' else 'assert'),
                    'select -assert-count 1 t:$assume','[files]',*map(str,sv),str(model),'']))
                result=command(['sby','-d',str(folder/variant),str(config)],f'{name}/{variant}.log')
                status=folder/variant/'status';solver=status.read_text().split()[0] if status.exists() else 'ERROR'
                result.update(mode=mode,engine=engine,variant=variant,solver_status=solver)
                row['jobs'].append(result)
                if solver=='TIMEOUT':
                    result['status']='unresolved';raise TimeoutError(name+' '+variant+' unresolved; no unchanged rerun')
                result['failed_properties']=validate_job(folder/variant,
                    'cover' if mode=='cover' else 'negative' if variant=='corrupt' else 'proof',
                    result['returncode'],solver,{assertion_names(14)[5]} if variant=='corrupt' else None)
                result['status']='covered' if mode=='cover' else 'fault_rejected' if variant=='corrupt' else 'proved'
                print(name,variant,result['status'],flush=True)
            (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Proof sources changed')
        receipt['status']='pass'
    except TimeoutError as e:receipt.update(status='unresolved',error=str(e))
    except Exception as e:receipt.update(status='failed',error=str(e))
    receipt['artifact_sha256']={x.relative_to(out).as_posix():hashlib.sha256(x.read_bytes()).hexdigest()
        for x in out.rglob('*') if x.is_file() and x!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())
