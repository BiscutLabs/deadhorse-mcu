"""T32 actual OpenOCD/production TAP regression. Formal and CI run separately."""
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


def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    receipt=dict(status='running',source_sha256=snapshot(),commands=[],scenarios=[],
                 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 clocks={'main_hz':8000000,'aon_hz':1000000,'usb_hz':48000000,'tck_max_hz':100000},
                 clock_basis='simulator schedule, digital models; not analog clock qualification',
                 assumptions=['Shared clock-gate simulation model; fixture boot ROM explicitly prepared',
                              'Remote-bitbang drives only TAP pins; fault scenario changes public reset/clock pins'],
                 scope_limits=['Stopped-AON SBA test is before destination acceptance; late accepted-beat data integrity requires the separate composition proof'])

    def run(label,cmd,timeout=600):
        begin=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        receipt['commands'].append(dict(command=cmd,returncode=p.returncode,seconds=time.monotonic()-begin,log=label+'.log'))
        if p.returncode:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)

    try:
        run('prepare',[sys.executable,'dv/soc/prepare_production.py'])
        run('prepare-debug',[sys.executable,'dv/soc/debug/prepare.py'])
        run('vendor-debug',[sys.executable,'hw/vendor/riscv_dbg/prepare.py'])
        run('vendor-usb',[sys.executable,'hw/vendor/usb/prepare.py'])
        for variant in ('correct','missing-halt'):
            folder=out/variant;folder.mkdir()
            emit=folder/'emit'
            run('emit-'+variant,[sys.executable,'tools/sbt.py',
                f'hw/runMain deadhorse.top.EmitDebugSoc {emit.relative_to(ROOT)} {variant}'])
            run('compile-'+variant,[sys.executable,'dv/soc/debug/compile.py','--emitted',str(emit),'--output',str(folder/'sim')])
            binary=folder/'sim/obj/VSocExternalClockTest'
            cases=[('basic',False,1000000),('basic',True,1000000),('basic',False,32000),('reset',False,1000000),('errors',False,1000000),('independent_reset',False,1000000),('counters',False,1000000),('inflight_reset',False,1000000)] if variant=='correct' else [('basic',False,1000000)]
            for script,sleep,aon in cases:
                label=script+('-sleep' if sleep else '')+('-aon32k' if aon==32000 else '')
                row=probe(binary,ROOT/'dv/soc/debug'/(script+'.tcl'),folder/label,sleep,aon)
                receipt['scenarios'].append(dict(variant=variant,scenario=label,result=row))
                if variant=='correct':
                    if row['status']!='pass':raise RuntimeError(label+' failed')
                else:
                    log=(folder/label/'openocd.log').read_text()
                    if row['status']!='failed' or row.get('openocd_exit',0)==0 or 'PASS T32 BASIC' in log:
                        raise RuntimeError('Missing-halt binding fault escaped')
                    if not any(x in log.lower() for x in ('failed to halt','not halted','unable to halt','timed out while waiting for target halted')):
                        raise RuntimeError('Missing-halt fault failed for unrelated reason')
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Frozen sources changed')
        receipt['status']='pass'
    except Exception as exc:
        receipt.update(status='failed',error=str(exc))
    receipt['seconds']=time.monotonic()-start
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in out.rglob('*') if p.is_file() and p.suffix in ('.json','.log','.sv','.v','.tcl')}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True)
    sys.exit(main(ap.parse_args().output))
