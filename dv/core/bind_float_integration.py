"""Fresh exact concrete integration instrumentation to production binding.

Consumes the protected pre-graft normal model from the wide integration run.
No old unrecorded canonical netlist is trusted, and no safety proof is rerun.
"""
import argparse
import copy
import json
from pathlib import Path
from common import ROOT, VENDOR, local, output_dir, run, inputs
from jalr_invariant import digest, gate
from jalr_receipts import verify_hashes
from state_equiv import prepare, Mismatch
from candidate import sources as candidate_sources

TOP='FloatIntegrationFormal'
MODULE='ibex_core'


def projection(design):
    if set(design['modules'])!={TOP}:raise ValueError('Expected flattened concrete normal monitor')
    result=copy.deepcopy(design);m=result['modules'].pop(TOP);result['modules'][MODULE]=m
    if m['ports']['checking']!={'direction':'input','bits':m['ports']['checking']['bits']} or len(m['ports']['checking']['bits'])!=1:
        raise ValueError('Unexpected checking interface')
    del m['ports']['checking']
    removed={n:c for n,c in m['cells'].items() if c['type'] in ('$check','$assert','$assume','$cover')}
    if len(removed)!=28 or any(c['type']!='$check' or c['parameters']['FLAVOR']!='assert' for c in removed.values()):
        raise ValueError('Original28 assertion inventory changed')
    for n in removed:del m['cells'][n]
    return result,removed


def mutate(design,kind):
    result=copy.deepcopy(design);m=result['modules'][MODULE]
    if kind=='output':
        name=next(n for n,p in m['ports'].items() if p['direction']=='output' and len(p['bits']))
        prior=m['ports'][name]['bits'][:];bits=gate(m,'$not',prior[:1])+prior[1:]
        m['ports'][name]['bits']=bits;m['netnames'][name]['bits']=bits
        detail=dict(port=name,bit=0)
    else:
        choices=[(n,c) for n,c in m['cells'].items() if c['type'] in ('$aldff','$adff')]
        if not choices:raise ValueError('No concrete resettable state')
        name,c=choices[0];con=c['connections']
        if kind=='reset-value':
            if c['type']=='$adff':
                value=c['parameters']['ARST_VALUE']
                if set(value)-set('01'):raise ValueError('Reset value not constant')
                c['parameters']['ARST_VALUE']=value[:-1]+('1' if value[-1]=='0' else '0')
                detail=dict(cell=name,parameter='ARST_VALUE',bit=0)
            else:
                if con['AD'][0] not in ('0','1'):raise ValueError('Reset value not constant')
                con['AD'][0]='1' if con['AD'][0]=='0' else '0';detail=dict(cell=name,port='AD',bit=0)
        elif kind=='next-state':
            con['D'][0]=gate(m,'$not',con['D'][:1])[0];detail=dict(cell=name,port='D',bit=0)
        elif kind=='clock':
            con['CLK'][0]=gate(m,'$not',con['CLK'][:1])[0];detail=dict(cell=name,port='CLK',bit=0)
        else:raise ValueError('Unknown binding negative')
    return result,detail


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--integration',default='build/t13/integration-wide')
    ap.add_argument('--candidate',default='build/t13/exponent/candidate')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.integration);candidate=local(args.candidate);out=output_dir(args.output)
    receipt=dict(status='running',scope='concrete normal integration monitor projection equals exact production; consumes unchanged wide28 proof',results={});protected={}
    try:
        raw=base/'result.json';evidence=json.loads(raw.read_text())
        if evidence['status']!='pass (28 integration safety assertions; eight abstract covers); ISA unresolved' or evidence['results']['normal']['status']!='PASS' or evidence['results']['normal']['kind']!='unbounded safety proof':
            raise ValueError('Wide integration proof unavailable')
        protected=dict(evidence['input_sha256'])
        normal=base/'normal/original.json';status=base/'normal/work/status'
        if str(normal) not in protected or status.read_text().split()[0]!='PASS':raise ValueError('Protected concrete normal model/safety status missing')
        for p in (raw,status,Path(__file__),ROOT/'dv/core/state_equiv.py',ROOT/'dv/core/module_map.json',ROOT/'dv/core/common.py',ROOT/'dv/core/jalr_receipts.py',ROOT/'dv/core/jalr_invariant.py'):
            previous=protected.get(str(p))
            if previous is not None and previous!=digest(p):raise ValueError('Binding dependency changed')
            protected[str(p)]=digest(p)
        # The production candidate uses rtl/ plus manifest-pinned extra files.
        # Select that complete authenticated configuration before elaboration.
        manifest=candidate/'candidate.json'
        protected[str(manifest)]=digest(manifest)
        for p in (ROOT/'dv/core/candidate.py',ROOT/'dv/core/config.json',ROOT/'dv/core/adaptations.json',
                  VENDOR/'verify_lock.py',VENDOR/'ibex_ref.lock.json'):
            previous=protected.get(str(p))
            if previous is not None and previous!=digest(p):raise ValueError('Candidate selection dependency changed')
            protected[str(p)]=digest(p)
        verify_hashes(protected)
        lock=inputs()
        sources=[local(p) for p in candidate_sources(candidate,lock,out,module=MODULE)]
        for p in sources:
            previous=protected.get(str(p))
            if previous is not None and previous!=digest(p):raise ValueError('Current candidate source differs from protected input')
            protected[str(p)]=digest(p)
        for p in (out/'candidate-sources.json',out/'candidate-configuration.json'):protected[str(p)]=digest(p)
        production_read='read_slang --top ibex_core '+' '.join('-D'+d for d in lock['defines'])+' '+\
            ' '.join('-I'+str(VENDOR/p) for p in lock['include_dirs'])+' '+' '.join(map(str,sources))
        verify_hashes(protected)
        projected,removed=projection(json.loads(normal.read_text()))
        projected_path=out/'projected-raw.json';projected_path.write_text(json.dumps(projected));protected[str(projected_path)]=digest(projected_path)
        # The task's production candidate carries RVFI observation ports,
        # while the original integration monitor explicitly has WithRVFI=false.
        # Project only those additional outputs. Their dead observer registers
        # may prune; every remaining state/output/reset/clock is still compared.
        production_raw=out/'production-raw.json';production_prepare=out/'production-prepare.ys'
        production_prepare.write_text(production_read+f'\nprep -top {MODULE} -flatten\nwrite_json {production_raw}\n')
        protected[str(production_prepare)]=digest(production_prepare);verify_hashes(protected)
        run(['yosys','-Q','-T','-s',production_prepare],out,'production-prepare',timeout=120)
        verify_hashes(protected);protected[str(production_raw)]=digest(production_raw)
        production_design=json.loads(production_raw.read_text());pm=production_design['modules'][MODULE]
        expected_ports=projected['modules'][MODULE]['ports']
        extra=set(pm['ports'])-set(expected_ports)
        if not set(expected_ports)<=set(pm['ports']) or not extra or any(not n.startswith('rvfi_') or pm['ports'][n]['direction']!='output' for n in extra):
            raise ValueError('Candidate differs beyond RVFI observation outputs')
        removed_rvfi={n:pm['ports'].pop(n) for n in sorted(extra)}
        production_projection=out/'production-projected.json';production_projection.write_text(json.dumps(production_design))
        protected[str(production_projection)]=digest(production_projection)
        receipt['observation_projection']=dict(reason='normal integration monitor WithRVFI=false; ISA separately verifies RVFI',ports=removed_rvfi)
        canon=[]
        for role,path0 in [('projected',projected_path),('production',production_projection)]:
            ys=out/(role+'.ys');path=out/(role+'-canonical.json')
            ys.write_text(f'read_json {path0}\nprep -top {MODULE} -flatten\nopt -full -nodffe -nosdff\ncheck -assert\nwrite_json {path}\n')
            protected[str(ys)]=digest(ys);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',ys],out,role,timeout=120)
            verify_hashes(protected);protected[str(path)]=digest(path);canon.append(path)
        receipt.update(safety_receipt=dict(path=str(raw),sha256=digest(raw)),normal_prepared=dict(path=str(normal),sha256=digest(normal)),
            removed_properties=removed,canonical_sha256={str(p):digest(p) for p in canon},
            production_sha256={str(p):digest(p) for p in sources},candidate_manifest_sha256=digest(manifest),assumptions=[],timeout_seconds=120,
            elaboration='fresh canonical netlists from pre-use authenticated concrete normal model and current production SV; exact source/config/netlist hashes recorded')
        mapping=json.loads((ROOT/'dv/core/module_map.json').read_text())['modules'].get(MODULE,{})
        for role in ('positive','output','reset-value','next-state','clock'):
            job=output_dir(out/role);selected=canon[1]
            if role!='positive':
                mutant,change=mutate(json.loads(selected.read_text()),role)
                selected=job/'mutant.json';selected.write_text(json.dumps(mutant));protected[str(selected)]=digest(selected)
            verify_hashes(protected)
            try:
                gold,gatepath,state=prepare(canon[0],selected,MODULE,job,mapping)
            except Mismatch as exc:
                if role!='reset-value' or not str(exc).startswith('State kind/reset/width/polarity differs:'):
                    raise
                receipt['results'][role]=dict(status='rejected',detector='exact state reset parameter comparison',reason=str(exc),mutation=change)
                print(role+': rejected (reset parameter)',flush=True)
                continue
            script=job/'check.ys';witness=job/'counterexample.json'
            script.write_text(f'read_json {gold}\nrename {MODULE} gold\nread_json {gatepath}\nrename {MODULE} gate\n'
                'miter -equiv -flatten gold gate miter\nhierarchy -top miter\nopt_expr\nopt_merge\nopt_clean\nsat '+
                ('-verify ' if role=='positive' else '')+f'-prove trigger 0 -show-inputs -show-outputs -dump_json {witness}\n')
            protected.update({str(p):digest(p) for p in (gold,gatepath,script)});verify_hashes(protected)
            result=run(['yosys','-Q','-T','-s',script],job,'check',timeout=120)
            expected='SAT proof finished - no model found: SUCCESS!' if role=='positive' else 'SAT proof finished - model found: FAIL!'
            if expected not in result.stdout or role!='positive' and not witness.exists():raise ValueError('Integration production binding failed: '+role)
            receipt['results'][role]=dict(status='proved' if role=='positive' else 'rejected',seconds=result.elapsed_seconds,correspondence=state)
            if role!='positive':
                protected[str(witness)]=digest(witness);receipt['results'][role]['mutation']=change
            print(role+': '+receipt['results'][role]['status'],flush=True)
        verify_hashes(protected);receipt['status']='pass (fresh concrete integration instrumentation-to-production binding; no safety proof rerun)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
