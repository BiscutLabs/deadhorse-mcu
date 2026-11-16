"""Run untouched local ADD obligations without rerunning request alignment."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, property_cell
from jalr_receipts import verify_hashes
from check_jalr_request import BINDINGS, request_witness
from qualify_owner_valid import inject


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',default='build/t13/jalr-request')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='local saved-request ADD only; alignment/arithmetic composition/ISA unresolved',results={})
    protected={}
    try:
        raw=base/'result.json';prior=json.loads(raw.read_text())
        protected=dict(prior['input_sha256'])
        for p in (raw,Path(__file__),Path(__file__).with_name('check_jalr_request.py'),
                  Path(__file__).with_name('qualify_owner_valid.py'),Path(__file__).with_name('jalr_invariant.py'),
                  Path(__file__).with_name('jalr_receipts.py')):
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        if (prior['timeout_seconds'],prior['depth'])!=(120,144): raise ValueError('Unexpected limits')
        source=base/'alignment-prove/model.json'
        if str(source) not in protected: raise ValueError('Unauthenticated production model')
        model=json.loads(source.read_text());m=model['modules'][TOP]
        def net(n):return m['netnames']['__request_'+n]['bits']
        original=property_cell('assert',net('alignmentHolds'))
        if m['cells']['__request_assert']!=original: raise ValueError('Unexpected alignment assertion')
        receipt.update(timeout_seconds=120,depth=144,assumptions=prior['assumptions'],
                       preserved_alignment_result=prior['results']['alignment-prove'])
        for role in ('execute-prove','execute-cover','execute-fault'):
            job=output_dir(out/role);design=copy.deepcopy(model);m=design['modules'][TOP]
            obligation=net('executeAddHolds');m['cells']['__request_assert']=property_cell('assert',obligation)
            mode='prove';engine='abc pdr'
            if role=='execute-cover':
                m['cells']['__request_assert']=property_cell('cover',gate(m,'$and',net('executeCorner'),obligation))
                mode='cover';engine='btor btormc'
            elif role=='execute-fault':
                receipt['fault_driver']=inject(m,m['netnames'][BINDINGS['executeTarget']]['bits'][1],net('executeActive'))
                mode='bmc';engine='btor btormc'
            else:
                restored=copy.deepcopy(design);restored['modules'][TOP]['cells']['__request_assert']=original
                if restored!=model: raise ValueError('Changed production model beyond proposition')
            path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n'
                f'[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statusfile=job/'work/status';status=statusfile.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            expected=('FAIL',2) if role.endswith('fault') else ('PASS',0)
            if (status,result.returncode)!=expected: raise RuntimeError(role+': '+status)
            protected[str(statusfile)]=digest(statusfile)
            if role!='execute-prove':
                witnesses=[]
                for trace in (job/'work').glob('engine_*/trace*.vcd'):
                    try:
                        event=request_witness(trace.read_text(),role)
                        witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event))
                        protected[str(trace)]=digest(trace)
                    except ValueError:continue
                if not witnesses:raise ValueError('Missing active '+role+' witness')
                receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        verify_hashes(protected)
        receipt['status']='pass (local ADD only; alignment and ISA unresolved)'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
