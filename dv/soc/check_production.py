"""Frozen PLAN03 production composition regression; CI is a separate step."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from dv.soc.check_io import snapshot

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    out=(ROOT/args.output).resolve();out.relative_to(ROOT/'build')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    receipt=dict(status='running',commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 source_sha256=snapshot(),commands=[],ci='Neither CI tier invoked by this focused runner')
    def run(label,command):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(command=command,returncode=result.returncode,
                                       seconds=time.monotonic()-start,log=label+'.log'))
        if result.returncode:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        run('prepare',[sys.executable,'dv/soc/prepare_production.py'])
        run('map-tests',[sys.executable,'hw/top/reference/test_soc_map.py'])
        run('fixture-tests',[sys.executable,'-m','unittest','discover','-s','dv/soc','-p','test_fixture.py','-v'])
        run('control-tool-tests',[sys.executable,'-m','unittest','discover','-s','hw/top/reference/formal','-p','test_i1_control.py','-v'])
        run('structure',[sys.executable,'tools/check_structure.py','--include-untracked'])
        run('simulation',[sys.executable,'tools/sbt.py','hw/testOnly deadhorse.top.*'])
        command=[sys.executable,'tools/sbt.py']
        for variant in ('production','usb-stub-test'):
            command.append(f'hw/runMain deadhorse.top.EmitSoc {out.relative_to(ROOT)}/chip-8-{variant} {variant} 8')
        for mhz in (8,9):
            for variant in ('production','usb-stub-test'):
                command.append(f'hw/runMain deadhorse.top.EmitSocExternalClockTest {out.relative_to(ROOT)}/soc-{mhz}-{variant} {variant} {mhz}')
        run('whole-soc',command)
        from dv.soc import fixture
        fixture.prepare(out/'minimal-i0-inputs')
        fixture.compile_sim(out/'minimal-i0',out/'minimal-i0-inputs')
        print('PASS minimal-i0 emission and simulator compilation',flush=True)
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Frozen implementation changed during checks')
        receipt['status']='pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['seconds']=time.monotonic()-started
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':sys.exit(main())
