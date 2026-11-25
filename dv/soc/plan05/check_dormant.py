"""Focused PLAN05 dormant firmware/hold tests with a sealed source receipt; no CI."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
def main(output,hold_kind=None):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for folder in ('hw','sw/lite/watcher','dv/soc/plan05') for p in (ROOT/folder).rglob('*') if p.suffix in ('.scala','.yaml','.c','.S','.py')]
    paths += [ROOT/'tools/env/lock.json',ROOT/'build/plan05/dormant-firmware/result.json',ROOT/'build/plan05/hold-firmware/result.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    command=[sys.executable,'tools/sbt.py',f'hw/testOnly deadhorse.top.SocDormantHoldSpec -- -z \"kind={hold_kind}\"' if hold_kind is not None else 'hw/testOnly deadhorse.top.SocDormantSpec deadhorse.top.SocDormantHoldSpec']
    receipt=dict(status='running',command=command,source_sha256=hashes(),scope='Production clock wrapper; watcher radio rejection/acceptance and retained WFI resume; bounded timer/DMA/real-USB sleep inhibition. No full CI or whole-program proof.')
    begin=time.monotonic()
    try:
        with (out/'simulation.log').open('w') as log: code=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600).returncode
        receipt['returncode']=code;assert code==0,'Focused simulation failed'
        log=(out/'simulation.log').read_text();assert 'All tests passed.' in log and f'Total number of tests run: {1 if hold_kind is not None else 6}' in log
        receipt['hold_kind']=hold_kind
        if hold_kind is None:
            receipt['measured_aon_ticks']={key:int(re.search(pattern,log)[1]) for key,pattern in {
                'lite_boot_copy':r'DORMANT_LITE_COPY aon_ticks=(\d+)',
                'valid_irq_to_osc_en':r'DORMANT_IRQ_TO_OSC_EN aon_ticks=(\d+)',
                'osc_en_to_resume':r'DORMANT_OSC_EN_TO_RESUME aon_ticks=(\d+)'}.items()}
            receipt['nominal_aon_hz_assumed']=32000
            receipt['estimated_ms']={k:v*1000/32000 for k,v in receipt['measured_aon_ticks'].items()}
        assert hashes()==receipt['source_sha256'],'Sources changed during simulation'
        receipt['status']='pass_scoped_simulation'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['wall_seconds_measured']=time.monotonic()-begin
    receipt['log_sha256']=hashlib.sha256((out/'simulation.log').read_bytes()).hexdigest()
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass_scoped_simulation' else 1
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--hold-kind',type=int,choices=range(4));a=p.parse_args();sys.exit(main(a.output,a.hold_kind))
