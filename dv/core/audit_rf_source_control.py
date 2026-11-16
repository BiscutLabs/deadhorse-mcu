"""Audit RF controls and bind inherited monitor to authenticated operand RTL."""
import argparse
import copy
import json
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import digest, gate
from jalr_receipts import combine_hashes, verify_hashes
from state_equiv import prepare
from check_rf_source_control import witness


def project(old, new):
    old = copy.deepcopy(old); new = copy.deepcopy(new)
    extra = {'rfReadAddress','rfWriteAddress','rfWriteEnable','rfAddressHolds','rfNoConflictHolds','rfPriorAddress'}
    if set(new['ports']) - set(old['ports']) != extra or not set(old['ports']) <= set(new['ports']):
        raise ValueError('Unexpected inherited interface')
    for name, port in old['ports'].items():
        other = new['ports'][name]
        if port['direction'] != other['direction'] or len(port['bits']) != len(other['bits']):
            raise ValueError('Inherited port changed: ' + name)
    for name in extra: del new['ports'][name]
    return [dict(modules={'RfProjection': m}) for m in (old, new)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', default='build/t13/rf-source-control')
    parser.add_argument('--operands', default='build/t13/jalr-operands')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(); base = local(args.controls); phase = local(args.operands); out = output_dir(args.output)
    receipt = dict(status='running', scope='RF controls and inherited operand binding; source composition unresolved', results={})
    protected = {}
    try:
        paths = [base/'result.json', phase/'result.json', phase.parent/'jalr-operands-audit/audit.json']
        evidence, old, audit = [json.loads(p.read_text()) for p in paths]
        if audit['status'] != 'pass (issue and retention only; source unresolved)' or audit['input_sha256'].get(str(paths[1])) != digest(paths[1]):
            raise ValueError('Phase audit mismatch')
        protected = combine_hashes(evidence['input_sha256'], old['input_sha256'], audit['input_sha256'])
        for p in paths: protected[str(p)] = digest(p)
        # Existing phase evidence authenticates the inherited hierarchy. This
        # companion additionally records all direct proof/binding dependencies.
        dependencies = [ROOT/'hw/ip/perf_core/formal'/name for name in
            ('RfSourceControlProperty.scala','OperandOwnershipProperty.scala','PhaseStabilityProperty.scala','JalrOwnershipProperty.scala',
             'JalrRequestProperty.scala','JalrCaptureProperty.scala','JalrTransportProperty.scala')]
        dependencies += [ROOT/'dv/core'/name for name in ('audit_rf_source_control.py','check_rf_source_control.py','audit_jalr_operands.py','check_jalr_operands.py',
            'check_phase_stability.py','check_jalr_ownership.py','check_jalr_request.py','check_jalr_capture.py',
            'check_jalr_transport.py','check_jalr_target.py','jalr_receipts.py','jalr_invariant.py',
            'qualify_owner_valid.py','state_equiv.py','common.py')]
        for p in dependencies:
            expected = protected.get(str(p))
            if expected is not None and expected != digest(p): raise ValueError('Changed dependency: ' + str(p))
            protected[str(p)] = digest(p)
        verify_hashes(protected)
        for family in ('address','conflict'):
            for kind in ('prove','cover','fault'):
                role = family+'-'+kind; item = evidence['results'][role]
                expected = ('FAIL',2) if kind == 'fault' else ('PASS',0)
                status = base/role/'work/status'
                if (item['status'],item['returncode']) != expected or status.read_text().split()[0] != expected[0]:
                    raise ValueError('Unexpected role status: ' + role)
                protected[str(status)] = digest(status)
                if kind != 'prove':
                    if not item.get('witnesses'): raise ValueError('Missing active witness')
                    for w in item['witnesses']:
                        path = local(w['path'])
                        if digest(path) != w['sha256'] or witness(path.read_text(),role) != w['event']:
                            raise ValueError('Changed active witness')
                        protected[str(path)] = digest(path)
        old_m = json.loads((phase/'monitor.json').read_text())['modules']['OperandOwnershipProperty']
        new_m = json.loads((base/'monitor.json').read_text())['modules']['RfSourceControlProperty']
        models=[]
        for name, model in zip(('old','new'), project(old_m,new_m)):
            raw=out/(name+'-raw.json');raw.write_text(json.dumps(model));canonical=out/(name+'.json');ys=out/(name+'.ys')
            ys.write_text(f'read_json {raw}\nprep -top RfProjection -flatten\nopt_clean\ncheck -assert\nwrite_json {canonical}\n')
            run(['yosys','-Q','-T','-s',ys],out,name,timeout=120)
            protected.update({str(p):digest(p) for p in (raw,canonical,ys)});models.append(canonical)
        binding=output_dir(out/'binding');gold,candidate,state=prepare(*models,'RfProjection',binding,{})
        for negative in (False,True):
            name='negative' if negative else 'positive';selected=candidate
            if negative:
                model=json.loads(candidate.read_text());m=model['modules']['RfProjection']
                bits=gate(m,'$not',m['ports']['sourceStabilityHolds']['bits'])
                m['ports']['sourceStabilityHolds']['bits']=bits;m['netnames']['sourceStabilityHolds']['bits']=bits
                selected=binding/'negative.json';selected.write_text(json.dumps(model))
            ys=binding/(name+'.ys');trace=binding/(name+'-witness.json')
            ys.write_text(f'read_json {gold}\nrename RfProjection gold\nread_json {selected}\nrename RfProjection gate\n'
                'miter -equiv -flatten gold gate miter\nhierarchy -top miter\nopt_expr\nopt_merge\nopt_clean\n'
                + 'sat '+('' if negative else '-verify ')+f'-prove trigger 0 -dump_json {trace}\n')
            protected.update({str(p):digest(p) for p in (gold,selected,ys)})
            result=run(['yosys','-Q','-T','-s',ys],binding,name,timeout=120)
            expected='SAT proof finished - model found: FAIL!' if negative else 'SAT proof finished - no model found: SUCCESS!'
            if expected not in result.stdout or negative and not trace.is_file(): raise ValueError('Monitor binding failed')
            receipt['results'][name]=dict(status='rejected' if negative else 'proved',seconds=result.elapsed_seconds)
            if negative: protected[str(trace)]=digest(trace)
        receipt['state_correspondence']=state
        verify_hashes(protected);receipt['status']='pass (RF controls and inherited operand binding; source composition unresolved)'
        print('PASS RF controls audit and exact inherited operand monitor binding')
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
