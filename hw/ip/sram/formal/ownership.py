"""One capped T35 multiclock ownership attempt and reachable fault controls."""
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
from tools.formal import validate_job


def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    files=[ROOT/p for p in ('hw/ip/sram/src/main/scala/deadhorse/sram/Sram.scala',
        'hw/ip/sram/src/main/scala/deadhorse/sram/SramBist.scala','hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',
        'hw/lib/src/main/scala/deadhorse/lib/CdcEpoch.scala',
        'hw/ip/sram/formal/SramOwnershipFormal.scala','tools/env/lock.json','tools/formal.py')]+[Path(__file__)]
    def seal():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    receipt=dict(status='running',source_sha256=seal(),jobs=[],
        assumptions=['Cold asserted initially; pin epoch independently arbitrary, including initially; all later cold/pin resets, requests and memory read data arbitrary.',
                     'Independent unconstrained main/AON/observation clocks; ideal digital CDC sampling.'],
        scope='Full-size owner with production shared reset/FIFO cells, no analog metastability or physical memory proof.',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    def run(command,label,cap=180):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            try:code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=cap).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/sram/formal")',
            f'hw/runMain deadhorse.sram.EmitSramOwnership {out}/emit'],'emit',300)
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for label,variant,kind,engine in (('fault','fault','negative','smtbmc yices'),
                ('cover','correct','cover','smtbmc yices'),('proof','correct','proof','abc pdr')):
            emitted=sorted((out/'emit'/variant).glob('*.sv'));job=out/(label+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {dict(negative="bmc",proof="prove",cover="cover")[kind]}',
                'multiclock on','depth 64','timeout 120','[engines]',engine,'[script]',
                'read_slang --top SramOwnershipFormal '+' '.join(p.name for p in emitted),
                'prep -top SramOwnershipFormal -flatten',"fminit -seq cold_n 0,'z",'clk2fflogic','chformal -lower',
                'select -assert-count 13 t:$assert','select -assert-count 2 t:$cover',
                'select -assert-count 1 t:$assume','[files]',*map(str,emitted),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            status_path=out/label/'status';status=status_path.read_text().split()[0] if status_path.exists() else 'ERROR'
            row.update(name=label,engine=engine,solver_status=status,
                model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in emitted})
            receipt['jobs'].append(row)
            if status=='TIMEOUT':row['status']='unresolved'
            else:
                row['failed_properties']=validate_job(out/label,kind,row['returncode'],status)
                if kind=='negative':
                    # Flattened hierarchical assertion names retain the instance
                    # prefix; the shared legacy parser accepts only root names.
                    failed=set(re.findall(r'Assert failed in SramOwnershipFormal: ([\w.]+)',
                        (out/label/'logfile.txt').read_text()))
                    if not failed or not failed <= {'assert__chisel3_builtin','d.assert__chisel3_builtin_0'}:
                        raise RuntimeError('Unexpected ownership fault identities: '+str(failed))
                    row['failed_properties']=sorted(failed)
                row['status']=dict(negative='fault_rejected',cover='covered',proof='proved')[kind]
            print(label,row['status'],flush=True)
        if seal()!=receipt['source_sha256']:raise RuntimeError('Sources changed during ownership attempt')
        receipt['status']='unresolved' if any(j['status']=='unresolved' for j in receipt['jobs']) else 'pass'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    sys.exit(main(p.parse_args().output))
