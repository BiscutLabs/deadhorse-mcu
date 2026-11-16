"""Retry the original owner-JALR predicate with independently proved phase assertions."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, digest, gate, property_cell
from jalr_receipts import verify_hashes, combine_hashes
from state_equiv import prepare


def project_monitor(old,new):
    old=copy.deepcopy(old);new=copy.deepcopy(new)
    extra={'instructionWrite','holding','noWriteHolds','noClearHolds','stabilityActive',
           'stabilityHolds','currentTag','previousTag'}
    if set(new['ports'])-set(old['ports'])!=extra or not set(old['ports'])<=set(new['ports']):
        raise ValueError('Unexpected monitor projection interface')
    for n,p in old['ports'].items():
        q=new['ports'][n]
        if p['direction']!=q['direction'] or len(p['bits'])!=len(q['bits']):
            raise ValueError('Inherited monitor port changed')
    for n in extra: del new['ports'][n]
    return [dict(modules={'OwnershipProjection':m}) for m in (old,new)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',required=True);parser.add_argument('--owner',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();base=local(args.phase);owner=local(args.owner);out=output_dir(args.output)
    receipt=dict(status='running',scope='owner-JALR with asserted phase invariants only; ISA unresolved',results={})
    record=out/'result.json';protected={}
    try:
        raw=base/'result.json';audit=base/'audit.json';oldraw=owner/'result.json'
        evidence=json.loads(raw.read_text());audited=json.loads(audit.read_text());old=json.loads(oldraw.read_text())
        if evidence['status']!='pass (phase stability only; composition unresolved)' or audited['status']!='pass':
            raise ValueError('Phase prerequisites incomplete')
        if audited['receipt_sha256']!=digest(raw): raise ValueError('Phase audit receipt mismatch')
        protected=combine_hashes(evidence['input_sha256'],audited['input_sha256'],old['input_sha256'])
        for p in (raw,audit,oldraw,Path(__file__),Path(__file__).with_name('state_equiv.py')):
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        timeout=evidence['timeout_seconds'];depth=evidence['depth']
        if timeout!=120 or depth!=144: raise ValueError('Unexpected proof limits')
        receipt.update(timeout_seconds=timeout,depth=depth,assumptions=evidence['assumptions'])
        old_sv=[local(p) for p in old['input_sha256'] if p.endswith('/JalrOwnershipProperty.sv')]
        if len(old_sv)!=1: raise ValueError('Original monitor emission not unique')
        old_mp=old_sv[0].parent/'monitor.json'
        if str(old_mp) not in old['input_sha256']: raise ValueError('Unauthenticated original monitor')
        old_m=json.loads(old_mp.read_text())['modules']['JalrOwnershipProperty']
        new_m=json.loads((base/'monitor.json').read_text())['modules']['PhaseStabilityProperty']
        paths=[]
        for name,design in zip(('old','new'),project_monitor(old_m,new_m)):
            path=out/(name+'-raw.json');path.write_text(json.dumps(design));canonical=out/(name+'.json')
            ys=out/(name+'.ys');ys.write_text(f'read_json {path}\nprep -top OwnershipProjection -flatten\nopt_clean\ncheck -assert\nwrite_json {canonical}\n')
            run(['yosys','-Q','-T','-s',ys],out,name,timeout=120)
            protected.update({str(p):digest(p) for p in (path,ys,canonical)});paths.append(canonical)
        binding=output_dir(out/'monitor-binding')
        gold,candidate,state=prepare(*paths,'OwnershipProjection',binding,{})
        ys=binding/'check.ys';ys.write_text(f'read_json {gold}\nrename OwnershipProjection gold\nread_json {candidate}\n'
            'rename OwnershipProjection gate\nmiter -equiv -flatten gold gate miter\nhierarchy -top miter\n'
            'opt_expr\nopt_merge\nopt_clean\nsat -verify -prove trigger 0\n')
        protected.update({str(p):digest(p) for p in (gold,candidate,ys)})
        result=run(['yosys','-Q','-T','-s',ys],binding,'check',timeout=120)
        if 'SAT proof finished - no model found: SUCCESS!' not in result.stdout: raise ValueError('Inherited monitor binding failed')
        receipt['monitor_binding']=dict(status='proved',kind='named-state induction',correspondence=state,seconds=result.elapsed_seconds)
        # Invert the inherited tag output in the cut-state comparison. This is
        # a binding negative, not a replacement for a production fault below.
        bad=json.loads(candidate.read_text());m=bad['modules']['OwnershipProjection']
        bit=m['ports']['ownerJalr']['bits'];flipped=gate(m,'$not',bit)
        m['ports']['ownerJalr']['bits']=flipped;m['netnames']['ownerJalr']['bits']=flipped
        badpath=binding/'negative.json';badpath.write_text(json.dumps(bad))
        negys=binding/'negative.ys';negys.write_text(ys.read_text().replace(str(candidate),str(badpath)).replace('sat -verify -prove trigger 0','sat -prove trigger 0 -dump_json '+str(binding/'negative-witness.json')))
        protected.update({str(p):digest(p) for p in (badpath,negys)})
        result=run(['yosys','-Q','-T','-s',negys],binding,'negative',timeout=120)
        if 'SAT proof finished - model found: FAIL!' not in result.stdout: raise ValueError('Monitor tag binding fault escaped')
        receipt['monitor_binding']['negative']='rejected'
        model=json.loads((base/'step-prove/model.json').read_text());m=model['modules'][TOP]
        def net(n): return m['netnames']['__phase_'+n]['bits']
        if m['cells']['__phase_assert']!=property_cell('assert',net('stabilityHolds')):
            raise ValueError('Unexpected original phase assertion')
        m['cells']['__no_write_assert']=property_cell('assert',net('noWriteHolds'))
        m['cells']['__no_clear_assert']=property_cell('assert',net('noClearHolds'))
        target=gate(m,'$or',gate(m,'$not',net('capture')),net('ownerJalr'))
        m['cells']['__owner_jalr_assert']=property_cell('assert',target)
        # All four are assertions, including all three previously proved helpers.
        job=output_dir(out/'prove');path=job/'model.json';path.write_text(json.dumps(model))
        config=job/'check.sby';config.write_text(f'[options]\nmode prove\ndepth {depth}\nmulticlock on\ntimeout {timeout}\n'
            f'[engines]\nabc pdr\n[script]\nread_json {path}\nopt_clean\n')
        protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
        result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=timeout+30)
        status=(job/'work/status').read_text().split()[0]
        receipt['results']['prove']=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
        verify_hashes(protected)
        if (status,result.returncode)!=('PASS',0): raise RuntimeError('Strengthened owner-JALR: '+status)
        receipt['status']='positive proof pass; active cover/fault and composition pending'
        print('PASS owner-JALR with three asserted phase invariants; cover/fault still required')
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;record.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
