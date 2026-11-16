"""One complete original JALR checker plus its independently proved assertion.

Requires the raw lemma receipt AND its companion audit. Original assertions,
assumptions and covers are all retained. Fail fast at the existing short cap.
"""
import argparse
import copy
import json
from pathlib import Path

from common import ROOT, local, output_dir, run
from jalr_receipts import snapshot_baseline_audit
from assertion_partitions import TOP, assertions
from jalr_invariant import attach, digest, next_bit, property_cell


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lemma',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();base=local(args.lemma);out=output_dir(args.output)
    record=out/'result.json';receipt=dict(status='running',scope='complete JALR only; other ISA unchecked',results={})
    record.write_text(json.dumps(receipt))
    try:
        audit_snapshot=snapshot_baseline_audit(base,out)
        evidence=json.loads((base/'result.json').read_text())
        timeout=evidence['timeout_seconds'];depth=evidence['depth']
        if timeout>120: raise ValueError('Focused experiment cap is 120 seconds')
        original=json.loads((base/'original.json').read_text())
        monitor=json.loads((base/'monitor.json').read_text())['modules']['JalrAddressProperty']
        model,signals=attach(original,monitor)
        model['modules'][TOP]['cells']['__jalr_address_assert']=property_cell('assert',signals['holds'])
        inventory=assertions(original)
        if set(assertions(model))!=set(inventory)|{'__jalr_address_assert'}:
            raise ValueError('Original assertion inventory changed')
        protected=dict(evidence['input_sha256'])
        protected.update({str(p):digest(p) for p in (base/'result.json',audit_snapshot,Path(__file__),ROOT/'dv/core/jalr_receipts.py',
            ROOT/'dv/core/audit_jalr_invariant.py')})
        receipt.update(original_assertions=inventory,helper='__jalr_address_assert (assert, never assume)',
                       timeout_seconds=timeout,depth=depth,input_sha256=protected)
        for role in ('prove','cover','fault'):
            job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
            mode='prove';engine='abc pdr'
            if role=='cover': mode='cover';engine='btor btormc'
            if role=='fault':
                # Real reported destination-bit corruption, as in the ordinary
                # acceptance wrapper. All original checker assertions remain.
                bit=m['netnames']['checker_inst.rvfi_rd_wdata']['bits'][0]
                drivers=[(n,p,i) for n,c in m['cells'].items() for p,d in c['port_directions'].items()
                    if d=='output' for i,b in enumerate(c['connections'][p]) if b==bit]
                if len(drivers)!=1: raise ValueError('Destination bit lacks unique driver')
                n,p,i=drivers[0];fresh=next_bit(m);m['cells'][n]['connections'][p][i]=fresh
                m['cells']['__jalr_destination_fault']=dict(type='$not',parameters={'A_WIDTH':'1',
                    'A_SIGNED':'0','Y_WIDTH':'1'},attributes={},port_directions={'A':'input','Y':'output'},
                    connections={'A':[fresh],'Y':[bit]})
                receipt['fault_driver']=[n,p,i];mode='bmc';engine='btor btormc'
            path=job/'model.json';path.write_text(json.dumps(design))
            config=job/'check.sby';config.write_text(f'[options]\nmode {mode}\ndepth {depth}\n'
                f'multiclock on\ntimeout {timeout}\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
            for p,h in protected.items():
                if digest(local(p))!=h: raise ValueError('Changed input: '+p)
            status=(job/'work/status').read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            expected=('FAIL',2) if role=='fault' else ('PASS',0)
            if (status,result.returncode)!=expected: raise RuntimeError(f'Complete JALR {role}: {status}')
            if role in ('cover','fault') and not list((job/'work').glob('engine_*/trace*.vcd')):
                raise ValueError('Missing '+role+' witness')
            print(f'complete JALR {role}: {status}',flush=True)
        receipt['status']='pass (fixed-window JALR only)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally: record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
