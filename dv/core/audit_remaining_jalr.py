"""Recover only witness parsing after the qualified22 proof run; preserve raw receipts."""
import argparse
import json
from pathlib import Path
from common import local
from jalr_invariant import digest
from jalr_receipts import verify_hashes
from complete_jalr_inventory import checker_witness
from split_remaining_jalr import memory_fault_witness


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True)
    args=ap.parse_args();out=local(args.output);raw=out/'result.json';evidence=json.loads(raw.read_text())
    receipt=dict(status='running',scope='22 original JALR predicates only; destination/trap aggregation required');protected={}
    try:
        oldscript=local('dv/core/split_remaining_jalr.py');archive=out/'split_remaining_jalr.executed.py'
        hashes=dict(evidence['input_sha256']);expected=hashes[str(oldscript)]
        if digest(archive)!=expected:raise ValueError('Exact executed runner archive missing')
        verify_hashes(hashes,{str(oldscript):str(archive)})
        del hashes[str(oldscript)];hashes[str(archive)]=expected;protected=hashes
        for p in (raw,oldscript,Path(__file__),Path(__file__).with_name('complete_jalr_inventory.py')):protected[str(p)]=digest(p)
        if len(evidence['selected'])!=22 or len(evidence['deferred'])!=2:raise ValueError('Inventory changed')
        events={}
        for role,status,code in (('prove','PASS',0),('cover','PASS',0),('memory-fault','FAIL',2)):
            item=evidence['results'][role];statuspath=out/role/'work/status'
            if (item['status'],item['returncode'],statuspath.read_text().split()[0])!=(status,code,status):raise ValueError('Role mismatch')
            protected[str(statuspath)]=digest(statuspath)
            if role!='prove':
                events[role]=[]
                for trace in (out/role/'work').glob('engine_*/trace*.vcd'):
                    try:event=memory_fault_witness(trace.read_text()) if role=='memory-fault' else checker_witness(trace.read_text(),False)
                    except ValueError:continue
                    events[role].append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
                if not events[role]:raise ValueError('Missing concrete checked witness')
        verify_hashes(protected)
        receipt.update(status='pass (22 original JALR predicates and qualification; aggregation required)',
            raw_receipt_sha256=digest(raw),raw_status=evidence['status'],events=events,
            selected=evidence['selected'],deferred=evidence['deferred'],input_sha256=protected,
            parser_fix='scalar VCD value indexed by identifier string, exact prior runner archived; no proof/model/status changed')
        print('PASS22 original JALR predicates: exact proof inputs, concrete cover and actual mask fault')
    except BaseException as exc:receipt.update(status='failed',error=str(exc));raise
    finally:(out/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
