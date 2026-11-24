"""First PLAN04 reset-cause proof: real clocks/reset, no assumed helpers."""
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
    paths=[Path(__file__),*[ROOT/p for p in (
        'hw/ip/osc_ctrl/formal/ResetCausesFormal.scala',
        'hw/ip/osc_ctrl/src/main/scala/deadhorse/osc_ctrl/ResetCauses.scala',
        'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala','tools/formal.py',
        'tools/env/lock.json','tools/sbt.py','build.sbt')]]
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',source_sha256=hashes(),jobs=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        assumptions=['Static D84 bypass choice, both cases exhaust legal choices',
            'Initial raw cold reset asserted; all later reset/brownout inputs arbitrary',
            'checkerInit_n initializes only cover history, then stays released',
            'Independent arbitrary AON, observer and pin-edge clocks; no fairness or frequency assumption'],
        scope='Cause encoding, raw cold clear, sub-AON pin pulse capture, held brownout capture, sticky causes and no source-free pin/brownout causes; no analog qualification',
        cover_note='24 global steps cannot wrap the six-bit AON epoch used solely to witness a sub-AON pin pulse')
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as stream:
            try:code=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:code=124
        return dict(command=command,returncode=code,seconds=time.monotonic()-start)
    try:
        receipt['emission']=run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitResetCausesFormal {out}/emit'],'emit')
        if receipt['emission']['returncode']:raise RuntimeError('Emission failed')
        for case in ('normal','bypass'):
            faults=('cold','pin','brown','invent-pin','invent-brown') if case=='normal' else ('bypass',)
            count=8 if case=='normal' else 2;covers=5 if case=='normal' else 2
            reset='supplyReset_n' if case=='normal' else 'externalReset_n'
            for variant in ('correct',*faults,'cover'):
                mode='prove' if variant=='correct' else 'cover' if variant=='cover' else 'bmc'
                label=case+'-'+variant;model=case+'-'+('correct' if variant=='cover' else variant)
                sources=sorted((out/'emit'/model).glob('*.sv'))
                if not sources:raise RuntimeError('Missing model '+model)
                engine='abc pdr' if mode=='prove' else 'btor btormc'
                job=out/(label+'.sby')
                job.write_text('\n'.join(['[options]',f'mode {mode}','multiclock on','depth 24','timeout 120',
                    '[engines]',engine,'[script]','read_slang --top ResetCausesFormal '+' '.join(p.name for p in sources),
                    'prep -top ResetCausesFormal -flatten',f"fminit -seq {reset} 0,'z",
                    'fminit -seq checkerInit_n 0,1','clk2fflogic','chformal -lower',
                    f'select -assert-count {count} t:$assert','select -assert-count 3 t:$assume',
                    f'select -assert-count {covers} t:$cover','[files]',*map(str,sources),'']))
                row=run(['sby','-d',str(out/label),str(job)],label)
                statusfile=out/label/'status';status=statusfile.read_text().split()[0] if statusfile.exists() else 'ERROR'
                row.update(name=label,engine=engine,solver_status=status,
                    model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
                receipt['jobs'].append(row)
                if status=='TIMEOUT':raise TimeoutError(label+' reached the existing 120-second cap')
                intended={'cold':{assertion_names(count)[0]},'pin':{assertion_names(count)[2]},
                    'brown':{assertion_names(count)[3]},'invent-pin':{assertion_names(count)[4]},
                    'invent-brown':{assertion_names(count)[5]}} if case=='normal' else {'bypass':set(assertion_names(count))}
                kind='proof' if mode=='prove' else 'cover' if mode=='cover' else 'negative'
                row['failed_properties']=validate_job(out/label,kind,row['returncode'],status,intended.get(variant))
                row['status']={'proof':'proved','cover':'covered','negative':'fault_rejected'}[kind]
                print(label,row['status'],flush=True)
        if hashes()!=receipt['source_sha256']:raise RuntimeError('Sources changed during proof')
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
    sys.exit(main(parser.parse_args().output))
