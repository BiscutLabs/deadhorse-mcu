"""Required negative qualification and receipt audit for JALR transport."""
import argparse
import copy
import json
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, digest
from jalr_receipts import verify_hashes
from check_jalr_transport import transport_witness


def audit(directory):
    out=local(directory);record=out/'audit.json';receipt=dict(status='running',scope='transport only; arithmetic unresolved')
    record.write_text(json.dumps(receipt))
    try:
        raw=out/'result.json';evidence=json.loads(raw.read_text())
        if evidence['status']!='pass (transport only; architectural arithmetic unresolved)': raise ValueError('Transport proof incomplete')
        protected={**evidence['input_sha256'],str(raw):digest(raw),str(Path(__file__)):digest(Path(__file__))}
        verify_hashes(protected)
        for role,expected in [('prove','PASS'),('cover','PASS'),('fault','FAIL')]:
            if evidence['results'][role]['status']!=expected or (out/role/'work/status').read_text().split()[0]!=expected:
                raise ValueError('Transport status mismatch')
            if role!='prove':
                witnesses=evidence['results'][role]['witnesses']
                if not witnesses: raise ValueError('Missing transport witness receipt')
                for w in witnesses:
                    trace=local(w['path'])
                    if digest(trace)!=w['sha256'] or transport_witness(trace.read_text(),role=='fault')!=w['retirement']:
                        raise ValueError('Transport witness changed')
        bad=copy.deepcopy(json.loads((out/'guard.json').read_text()))
        targets=[(n,c) for n,c in bad['modules'][TOP]['cells'].items()
            if n.startswith('__transport_') and c['type']=='$eq' and
            c['connections'].get('B')==list(reversed(format(0x67,'07b')))]
        if len(targets)!=1: raise ValueError('Unique guard opcode not found')
        name,c=targets[0];c['connections']['B'][0]='0'
        job=output_dir(out/'guard-negative');model=job/'model.json';model.write_text(json.dumps(bad))
        ys=job/'check.ys';witness=job/'counterexample.json'
        ys.write_text(f'read_json {model}\ncheck -assert\nsat -prove same 1 '
                      f'-show-inputs -show-outputs -dump_json {witness}\n')
        protected.update({str(p):digest(p) for p in (model,ys)})
        result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
        if 'SAT proof finished - model found: FAIL!' not in result.stdout or not witness.is_file() or not witness.stat().st_size:
            raise ValueError('Wrong-opcode activation escaped qualification')
        verify_hashes(protected)
        receipt.update(status='pass',receipt_sha256=digest(raw),input_sha256=protected,
                       qualification_negative=dict(cell=name,change='0x67 -> 0x66',status='rejected',
                           seconds=result.elapsed_seconds,witness_sha256=digest(witness)))
        print('PASS transport audit: input/witness hashes valid; wrong-opcode guard rejected')
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally: record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    audit(parser.parse_args().output)
