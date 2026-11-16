"""Compose saved kind/first alignment from independently proved ownership controls."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, property_cell
from jalr_receipts import combine_hashes, verify_hashes
from compose_jalr_ownership import frame, conjunction, implies, MODULE
from check_jalr_request import BINDINGS
from qualify_owner_valid import inject


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ownership',default='build/t13/ownership-composition-confirmed')
    ap.add_argument('--phase',default='build/t13/phase-stability')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();ownership=local(args.ownership);phase=local(args.phase);out=output_dir(args.output)
    receipt=dict(status='running',scope='saved kind/first alignment only; operands/opcode/ISA unresolved',results={})
    protected={}
    try:
        raw=ownership/'result.json';proof=json.loads(raw.read_text())
        if proof['status']!='composition proved with qualified premises; independent review pending':
            raise ValueError('Ownership composition unavailable')
        for role in ('base','step','final'):
            if proof['results'][role]['status']!='proved' or proof['results'][role+'-negative']['status']!='rejected':
                raise ValueError('Ownership composition obligations incomplete')
        protected=dict(proof['input_sha256'])
        for p in (raw,Path(__file__),Path(__file__).with_name('compose_jalr_ownership.py'),
                  Path(__file__).with_name('qualify_owner_valid.py')):
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        sourcepath=phase/'monitor.json'
        if str(sourcepath) not in protected:raise ValueError('Unbound monitor')
        source=json.loads(sourcepath.read_text())['modules']['PhaseStabilityProperty']
        receipt.update(assumptions=proof['assumptions'],timeout_seconds=120,depth=144,
                       antecedents=['ownershipHolds','retentionHolds','retainedKindHolds'])
        for role in ('compose','kind-negative','first-negative'):
            m=dict(attributes={'top':'1'},ports={},cells={},netnames={})
            p,_=frame(m,source,'current_')
            antecedent=conjunction(m,p['ownershipHolds'],p['retentionHolds'],p['retainedKindHolds'])
            kind=gate(m,'$eq',p['requestKind'],['1','0'] if role=='kind-negative' else ['0','0'])
            first=gate(m,'$not',p['requestFirst']) if role=='first-negative' else p['requestFirst']
            holds=implies(m,antecedent,implies(m,p['capture'],conjunction(m,kind,first)))
            m['ports']['holds']=dict(direction='output',bits=holds)
            m['ports']['capture']=dict(direction='output',bits=p['capture'])
            m['netnames']={n:dict(bits=p['bits'],attributes={}) for n,p in m['ports'].items()}
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(dict(modules={MODULE:m})))
            script=job/'check.ys';witness=job/'counterexample.json';negative=role!='compose'
            script.write_text(f'read_json {path}\nhierarchy -top {MODULE}\nopt_clean\ncheck -assert\nsat '+
                ('' if negative else '-verify ')+f'-prove holds 1 -show-inputs -show-outputs -dump_json {witness}\n')
            protected.update({str(p):digest(p) for p in (path,script)})
            result=run(['yosys','-Q','-T','-s',script],job,'check',timeout=120)
            expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
            if expected not in result.stdout or negative and not witness.exists():raise ValueError(role+' failed')
            receipt['results'][role]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
            if negative:protected[str(witness)]=digest(witness)
            print('PASS '+role,flush=True)
        # Active qualifications use the unchanged phase production model. The
        # only positive change is the property; no internal premise is assumed.
        fullpath=phase/'step-prove/model.json'
        if str(fullpath) not in protected:raise ValueError('Unauthenticated production model')
        original=json.loads(fullpath.read_text())
        for role in ('capture-cover','kind-fault','first-fault'):
            design=copy.deepcopy(original);m=design['modules'][TOP]
            def net(n):return m['netnames']['__phase_'+n]['bits']
            if set(n for n,c in m['cells'].items() if c['type']=='$assert')!={'__phase_assert'}:
                raise ValueError('Unexpected production property inventory')
            conclusion=conjunction(m,gate(m,'$eq',net('requestKind'),['0','0']),net('requestFirst'))
            m['cells']['__phase_assert']=property_cell('assert',implies(m,net('capture'),conclusion))
            mode='bmc'
            if role=='capture-cover':
                m['cells']['__phase_assert']=property_cell('cover',conjunction(m,net('capture'),conclusion));mode='cover'
            else:
                field='requestKind' if role=='kind-fault' else 'requestFirst'
                receipt[role+'_driver']=inject(m,m['netnames'][BINDINGS[field]]['bits'][0],net('capture'))
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)})
            verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statusfile=job/'work/status';status=statusfile.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('PASS',0) if role=='capture-cover' else ('FAIL',2)):
                raise RuntimeError(role+': '+status)
            protected[str(statusfile)]=digest(statusfile)
            traces=list((job/'work').glob('engine_*/trace*.vcd'))
            if not traces:raise ValueError('Missing active trace')
            receipt['results'][role]['witnesses']=[dict(path=str(t),sha256=digest(t)) for t in traces]
            protected.update({str(t):digest(t) for t in traces})
            print(role+': '+status,flush=True)
        verify_hashes(protected)
        receipt['status']='composition proved; active witness audit and independent review pending'
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
