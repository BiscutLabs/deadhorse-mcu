"""T35 bounded-cost wrapper/March jobs; unresolved proofs remain explicit."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.formal import assertion_names,validate_job


def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    sources=[p for folder in ('hw/ip/sram/src/main','hw/ip/sram/formal','hw/lib/src/main')
             for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.scala','.py')]
    sources += [ROOT/p for p in ('tools/env/lock.json','tools/formal.py','build.sbt','hw/vendor/gf180_sram/gf180_sram.lock.json')]
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        assumptions=['Initial reset asserted; later reset and functional inputs arbitrary.',
                     'Data witness address constant within each reset epoch; it never drives DUT inputs.'],
        scope='Macro pin wiring, full-depth independent digital memory model, 8-word March control. Not physical SRAM correctness, full-SoC ownership or CDC composition.')
    def run(command,label,cap=180):
        begin=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            try:code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=cap).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-begin)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/sram/formal")',
            f'hw/runMain deadhorse.sram.EmitSramFormal {out}/emit'],'emit',300)
        if receipt['emission']['returncode']:raise RuntimeError('Formal emission failed')
        macro='gf180mcu_ocd_ip_sram__sram1024x8m8wm1'
        lib=ROOT/f'build/vendor/gf180_sram/cells/{macro}/{macro}__tt_025C_3v30.lib'
        for model,top,count,assumptions,kind,engine in (
            ('pins','SramPinsFormal',20,1,'proof','abc pdr'),
            ('wrong-lane','SramPinsFormal',20,1,'negative','btor btormc'),
            ('pins','SramPinsFormal',20,1,'cover','btor btormc'),
            ('data','SramDataFormal',4,2,'proof','smtbmc yices'),
            ('data','SramDataFormal',4,2,'cover','btor btormc'),
            ('march','SramMarchFormal',6,1,'proof','abc pdr'),
            ('early','SramMarchFormal',6,1,'negative','btor btormc'),
            ('march','SramMarchFormal',6,1,'cover','btor btormc')):
            label=model+'-'+kind;mode=dict(proof='prove',negative='bmc',cover='cover')[kind]
            files=sorted((out/'emit'/model).glob('*.sv'))
            if not files:raise RuntimeError('Missing model '+model)
            job=out/(label+'.sby')
            commands=[f'read_liberty -lib {lib}'] if 'Pins' in top else []
            commands += [f'read_slang --top {top} '+' '.join(p.name for p in files),
                f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'async2sync','chformal -lower',
                f'select -assert-count {count} t:$assert',f'select -assert-count {assumptions} t:$assume',
                'select -assert-count 2 t:$cover']
            job.write_text('\n'.join(['[options]',f'mode {mode}',f'depth {128 if "March" in top else 24}',
                'timeout 120','[engines]',engine,'[script]',*commands,'[files]',*map(str,files),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            status_file=out/label/'status';status=status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
            row.update(name=label,solver_status=status,engine=engine,kind=kind,
                model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            receipt['jobs'].append(row)
            if status=='TIMEOUT':row['status']='unresolved'
            else:
                # Stateless BTOR faults have @0 inputs but no #0 state section;
                # retain strict identity/witness validation for that format too.
                row['failed_properties']=validate_job(out/label,kind,row['returncode'],status)
                if kind=='negative':
                    names=re.findall(r'^\d+ bad \d+ (\S+)',(out/label/'model/design_btor.btor').read_text(),re.M)
                    failed=set()
                    for witness in (out/label).glob('engine_*/trace*.wit'):
                        text=witness.read_text()
                        if not text.startswith('sat\n'):continue
                        prefix=re.split(r'(?m)^[#@]0\s*$',text,maxsplit=1)[0]
                        for number in re.findall(r'\bb(\d+)\b',prefix):
                            if int(number)>=len(names):raise RuntimeError('Invalid fault property number')
                            failed.add(names[int(number)])
                    expected=set(assertion_names(count))
                    if model=='wrong-lane':expected={assertion_names(count)[i] for i in (2,4,7,9,12,14,17,19)}
                    if not failed or not failed<=expected:raise RuntimeError('Unexpected fault identities: '+str(failed))
                    row['failed_properties']=sorted(failed)
                row['status']=dict(proof='proved',negative='fault_rejected',cover='covered')[kind]
            print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Formal sources changed during run')
        receipt['status']='unresolved' if any(r['status']=='unresolved' for r in receipt['jobs']) else 'pass'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    sys.exit(main(p.parse_args().output))
