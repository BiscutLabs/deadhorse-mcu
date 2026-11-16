"""Audit completed JALR source correspondence; never grants arithmetic acceptance."""
import argparse
import copy
import json
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import TOP, digest
from jalr_receipts import verify_hashes
from check_jalr_capture import capture_witness


def audit(directory):
    out=local(directory);record=out/'source-audit.json';receipt=dict(status='running',scope='source correspondence only; arithmetic and ISA unresolved')
    record.write_text(json.dumps(receipt))
    try:
        raw=out/'result.json';evidence=json.loads(raw.read_text())
        receipt['aggregate_status']=evidence['status']
        receipt['arithmetic_result']=evidence['results'].get('arithmetic-prove',{'status':'not run'})
        protected={**evidence['input_sha256'],str(raw):digest(raw),str(Path(__file__)):digest(Path(__file__))}
        verify_hashes(protected)
        for role,expected in [('source-prove','PASS'),('source-zero','PASS'),
                              ('source-alias','PASS'),('source-fault','FAIL')]:
            result=evidence['results'][role]
            work=local(result['reused_from']) if 'reused_from' in result else out/role
            status_path=work/'work/status'
            if (result['status']!=expected or status_path.read_text().split()[0]!=expected or
                    result['returncode']!=(2 if expected=='FAIL' else 0)):
                raise ValueError('Source status mismatch: '+role)
            protected[str(status_path)]=digest(status_path)
            if role!='source-prove':
                witnesses=result['witnesses']
                if not witnesses: raise ValueError('Missing source witness receipt')
                for w in witnesses:
                    trace=local(w['path'])
                    if digest(trace)!=w['sha256'] or capture_witness(trace.read_text(),role)!=w['retirement']:
                        raise ValueError('Source witness changed')
                    protected[str(trace)]=digest(trace)
        arithmetic=evidence['results'].get('arithmetic-prove')
        if arithmetic:
            status_path=out/'arithmetic-prove/work/status'
            if status_path.read_text().split()[0]!=arithmetic['status']:
                raise ValueError('Arithmetic status mismatch')
            protected[str(status_path)]=digest(status_path)
        bad=copy.deepcopy(json.loads((out/'guard.json').read_text()))
        targets=[(n,c) for n,c in bad['modules'][TOP]['cells'].items()
            if n.startswith('__capture_') and c['type']=='$eq' and
            c['connections'].get('B')==list(reversed(format(0x67,'07b')))]
        if len(targets)!=1: raise ValueError('Unique guard opcode not found')
        name,c=targets[0];c['connections']['B'][0]='0'
        job=output_dir(out/'source-guard-negative');model=job/'model.json';model.write_text(json.dumps(bad))
        ys=job/'check.ys';witness=job/'counterexample.json'
        ys.write_text(f'read_json {model}\ncheck -assert\nsat -prove same 1 '
                      f'-show-inputs -show-outputs -dump_json {witness}\n')
        protected.update({str(p):digest(p) for p in (model,ys)})
        result=run(['yosys','-Q','-T','-s',ys],job,'check',timeout=120)
        if 'SAT proof finished - model found: FAIL!' not in result.stdout or not witness.is_file() or not witness.stat().st_size:
            raise ValueError('Wrong-opcode activation escaped qualification')
        verify_hashes(protected)
        receipt.update(status='pass (source only)',receipt_sha256=digest(raw),input_sha256=protected,
                       qualification_negative=dict(cell=name,change='0x67 -> 0x66',status='rejected',
                           seconds=result.elapsed_seconds,witness_sha256=digest(witness)))
        print('PASS source-only audit: input/witness hashes valid; wrong-opcode guard rejected')
        print('Aggregate remains: '+evidence['status']+'; arithmetic: '+receipt['arithmetic_result']['status'])
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally: record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    audit(parser.parse_args().output)
