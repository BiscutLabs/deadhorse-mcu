"""T35 relevant SRAM/affected SoC campaign. No aggregate CI tier."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from dv.soc.check_io import snapshot
from dv.soc.debug.probe import probe


def main(output,phase):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    begin=time.monotonic()
    receipt=dict(status='running',phase=phase,source_sha256=snapshot(),commands=[],scenarios=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='SRAM/BIST plus affected memory, boot, sleep and JTAG regression only. Formal, macro STA and production flight cycles reported separately. No CI tier.')
    def run(label,command,cap=1200):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try:code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=cap).returncode
            except subprocess.TimeoutExpired:code=124
        receipt['commands'].append(dict(command=command,returncode=code,seconds=time.monotonic()-start,log=label+'.log'))
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if code:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        run('prepare',[sys.executable,'dv/soc/prepare_production.py'])
        run('macro-views',[sys.executable,'hw/vendor/gf180_sram/prepare.py','--source','build/t35/macro-upstream'])
        run('debug-views',[sys.executable,'hw/vendor/riscv_dbg/prepare.py'])
        run('usb-views',[sys.executable,'hw/vendor/usb/prepare.py'])
        if phase in ('all','unit'):
            run('unit',[sys.executable,'tools/sbt.py','hw/testOnly deadhorse.sram.*'])
        if phase in ('all','integration'):
            run('memory-boot-sleep',[sys.executable,'tools/sbt.py',
                'hw/testOnly deadhorse.top.SocMemorySpec deadhorse.top.SocI1SupportSpec deadhorse.top.SocLiteSpec deadhorse.top.SocBootReleaseSpec deadhorse.top.SocClockResetSpec'],cap=3600)
        if phase in ('all','jtag'):
            run('emit',[sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.top.EmitDebugSoc {out.relative_to(ROOT)}/emit correct'])
            run('compile',[sys.executable,'dv/soc/debug/compile.py','--emitted',str(out/'emit'),'--output',str(out/'sim')])
            binary=out/'sim/obj/VSocExternalClockTest'
            for label,script in [('bist','dv/soc/sram/bist.tcl'),('ordinary','dv/soc/debug/basic.tcl'),
                                 ('reset','dv/soc/debug/reset.tcl'),('inflight','dv/soc/debug/inflight_reset.tcl')]:
                row=probe(binary,ROOT/script,out/label)
                receipt['scenarios'].append(dict(name=label,result=row))
                if row['status']!='pass':raise RuntimeError(label+' failed')
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Sources changed during SRAM campaign')
        receipt['status']='pass'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['seconds']=time.monotonic()-begin
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.log','.sv','.v','.tcl') and p!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True)
    p.add_argument('--phase',choices=('all','unit','integration','jtag'),default='all')
    a=p.parse_args();sys.exit(main(a.output,a.phase))
