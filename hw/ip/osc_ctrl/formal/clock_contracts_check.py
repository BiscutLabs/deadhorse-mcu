"""PLAN04 count-transfer/elapsed-edge and physical-gate closure digital contracts."""
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


def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    vendor=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
    inputs=[p for parent in ('hw/lib/src/main/scala','hw/ip/osc_ctrl/src/main/scala')
            for p in (ROOT/parent).rglob('*.scala')]
    inputs += [vendor,Path(__file__),ROOT/'hw/ip/osc_ctrl/formal/ClockContracts.scala',
               ROOT/'tools/formal.py',ROOT/'tools/env/lock.json',ROOT/'build.sbt']
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        assumptions=['Initially reset asserted, thereafter arbitrary',
            'Actual independent unconstrained clocks; digital sampling only; no data/clock fairness assumptions',
            'Count boundary uses normal reset/internal AON mode; other static routing cases proved separately'],
        scope='Actual shared-FIFO count delivery/hold, no premature stable, and gate-closed acknowledgement truth')
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            try:code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitClockContracts {out}/emit'],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        jobs=[('gate-positive','gate-correct','prove',None),('gate-fault','gate-fault','prove',None),
              ('gate-cover','gate-correct','cover',None),
              ('count-delivery','count-correct','prove',[0,1]),('count-data-fault','count-data','prove',[0,1]),
              ('count-edges','count-correct','prove',[2]),('count-early-fault','count-early','prove',[2]),
              ('count-cover','count-correct','cover',None)]
        for label,variant,mode,keep in jobs:
            top='GateClosureContract' if variant.startswith('gate') else 'CountContract'
            size=1 if variant.startswith('gate') else 3
            files=sorted((out/'emit'/variant).glob('*.sv'))+[vendor]
            if len(files)<2:raise RuntimeError('Missing emitted model')
            engines=['abc pdr'] if mode=='prove' else ['btor btormc','smtbmc yices']
            selection=[]
            if keep is not None:
                names=assertion_names(size)
                for index,name in enumerate(names):
                    if index not in keep:selection.append('delete c:'+name)
                selection += [f'select -assert-count {len(keep)} t:$assert','select *','opt_clean']
            job=out/(label+'.sby')
            job.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 128','timeout 120',
                '[engines]',*engines,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in files),
                f'prep -top {top} -flatten',"fminit -seq reset_n 0,'z",'clk2fflogic','chformal -lower',
                f'select -assert-count {size} t:$assert','select -assert-count 1 t:$assume',
                'select -assert-count 2 t:$cover',*selection,'[files]',*map(str,files),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            statusfile=out/label/'status';status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
            row.update(name=label,engines=engines,solver_status=status,
                model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            receipt['jobs'].append(row)
            if status=='TIMEOUT':row['status']='unresolved'
            else:
                kind='negative' if 'fault' in label else 'proof' if mode=='prove' else 'cover'
                allowed={assertion_names(size)[i] for i in (keep if keep is not None else range(size))}
                row['failed_properties']=validate_job(out/label,kind,row['returncode'],status,allowed if kind=='negative' else None)
                row['status']=dict(proof='proved',negative='fault_rejected',cover='covered')[kind]
            print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Contract sources changed during run')
        receipt['status']='unresolved' if any(j['status']=='unresolved' for j in receipt['jobs']) else 'pass'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    sys.exit(main(parser.parse_args().output))
