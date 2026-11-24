"""PLAN04 actual-clock policy/boundary composition; no clock-ratio assumption."""
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


def main(output,closure=False,abstract_startup=False):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    vendor=ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv'
    paths=[p for parent in ('hw/lib/src/main/scala','hw/ip/osc_ctrl/src/main/scala')
           for p in (ROOT/parent).rglob('*.scala')]
    paths += [vendor,Path(__file__),ROOT/'hw/ip/osc_ctrl/formal/ClockComposition.scala',
              ROOT/'tools/formal.py',ROOT/'tools/env/lock.json',ROOT/'build.sbt']
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        assumptions=['Initial combined reset asserted; afterward reset and all inputs arbitrary',
            'Actual independent unconstrained source and AON clocks; no fairness or frequency assumption',
            'Policy/local hold and idle observations independently arbitrary (over-approximate production CDC delay)',
            'Normal POR and internal AON selection; routing/other static modes proved separately by reset_check',
            'Digital shared gate model; analog metastability, pulse shape and physical CTS outside scope'],
        scope=('Delayed closure acknowledgement with registered local hold and arbitrary live core idle' if closure else
               'New main edges require current oscillator-epoch AON observation of actual source stability'))
    receipt['abstraction']=dict(enabled=abstract_startup,
        cutpoints=['boundary.counter.stable','policy.elapsed','policy.delay','policy.timeout'] if abstract_startup else [],
        scope='Positive proof only: arbitrary startup datapath outputs retain all gate/CDC/hold/control logic. No startup duration/count claim. Covers and faults use the real model.')
    if closure:
        receipt['assumptions'][2]='Local hold modeled as arbitrary main-edge register updates, retained while gated; core idle live/arbitrary; AON hold independent'
    top='ClosureComposition' if closure else 'ClockComposition'
    assertion_count=4 if closure else 2
    cover_count=4 if closure else 3
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            try:code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitClockComposition {out}/emit'+(' closure' if closure else '')],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        # Faults and safety are independent from the reachability witness search.
        # Rung-one portfolio closed all covers after Z3 alone hit its 120s cap.
        faults=[('closure-fault','closure-fault','bmc'),('hold-fault','hold-fault','bmc')] if closure else [('early','early','bmc'),('stale','stale','bmc')]
        for label,variant,mode in faults+[('correct','correct','prove'),('cover','correct','cover')]:
            files=sorted((out/'emit'/variant).glob('*.sv'))+[vendor]
            if len(files)<2:raise RuntimeError('Missing emitted model')
            engines=['abc pdr'] if mode=='prove' else ['btor btormc','smtbmc yices']
            cuts=[]
            if abstract_startup and mode=='prove':
                for signal in receipt['abstraction']['cutpoints']:
                    selector='w:* a:hdlname='+signal.replace('.','?')+' %i'
                    cuts += ['select -assert-count 1 '+selector,'select *','cutpoint '+selector]
                cuts += ['select *','opt_clean']
            job=out/(label+'.sby')
            # 256 global witness steps span bootstrap plus startup, closure,
            # oscillator-off and restart at the shortest programmable counts.
            # Positive and negative safety jobs use unbounded PDR, not this bound.
            job.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 256','timeout 120',
                '[engines]',*engines,'[script]',f'read_slang --top {top} '+' '.join(p.name for p in files),
                f'prep -top {top} -flatten',*cuts,"fminit -seq reset_n 0,'z",'clk2fflogic','chformal -lower',
                f'select -assert-count {assertion_count} t:$assert','select -assert-count 1 t:$assume',f'select -assert-count {cover_count} t:$cover',
                '[files]',*map(str,files),'']))
            row=run(['sby','-d',str(out/label),str(job)],label)
            statusfile=out/label/'status';status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
            row.update(name=label,engines=engines,solver_status=status,
                model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
            receipt['jobs'].append(row)
            if status=='TIMEOUT':
                row['status']='unresolved'
                raise TimeoutError(label+' reached the existing 120-second cap; triage required')
            kind='negative' if variant!='correct' else 'proof' if mode=='prove' else 'cover'
            row['failed_properties']=validate_job(out/label,kind,
                row['returncode'],status,set(assertion_names(assertion_count)) if kind=='negative' else None)
            row['status']=dict(proof='proved',negative='fault_rejected',cover='covered')[kind]
            print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Composition sources changed')
        receipt['status']='pass'
    except TimeoutError as error:receipt.update(status='unresolved',error=str(error))
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--closure',action='store_true',help='Prove delayed closure with registered local demand')
    parser.add_argument('--abstract-startup',action='store_true',help='Sound startup-datapath cutpoints in positive safety only')
    args=parser.parse_args();sys.exit(main(args.output,args.closure,args.abstract_startup))
