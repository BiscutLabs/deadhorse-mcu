"""Accept every original JALR assertion only after exact partition and witness audits."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate
from jalr_receipts import combine_hashes, verify_hashes
from assertion_partitions import assertions, validate_union
from qualify_owner_valid import inject
from complete_jalr_inventory import checker_witness
from check_jalr_metadata import witness as metadata_witness


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inventory',default='build/t13/jalr-complete-inventory')
    ap.add_argument('--simple',default='build/t13/jalr-remaining-simple')
    ap.add_argument('--metadata',default='build/t13/jalr-metadata')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();base,simple,metadata=[local(getattr(args,n)) for n in ('inventory','simple','metadata')];out=output_dir(args.output)
    receipt=dict(status='running',scope='all original JALR assertions under original startup-window checker; other ISA unresolved',results={});protected={}
    try:
        paths=[base/'result.json',simple/'audit.json',metadata/'result.json']
        prior,small,meta=[json.loads(p.read_text()) for p in paths]
        if small['status']!='pass (22 original JALR predicates and qualification; aggregation required)':raise ValueError('22-predicate audit incomplete')
        if meta['status']!='pass (JALR destination/trap metadata and original predicates; aggregate ISA unresolved)':raise ValueError('Metadata proofs incomplete')
        protected=combine_hashes(prior['input_sha256'],small['input_sha256'],meta['input_sha256'])
        for p in (*paths,Path(__file__),Path(__file__).with_name('check_jalr_metadata.py'),Path(__file__).with_name('assertion_partitions.py'),Path(__file__).with_name('qualify_owner_valid.py')):protected[str(p)]=digest(p)
        verify_hashes(protected)
        originalpath=local('build/t13/jalr-address-strengthened/original.json')
        if str(originalpath) not in protected:raise ValueError('Original model lineage missing')
        original=json.loads(originalpath.read_text());inventory=assertions(original)
        if {n:original['modules'][TOP]['cells'][n] for n in inventory}!=prior['assertions']:raise ValueError('Original assertion inventory changed')
        groups=prior['preproved_groups']+[small['selected'],[meta['address_original']],[meta['trap_original']]]
        validate_union(inventory,groups)
        if set(small['deferred'])!={meta['address_original'],meta['trap_original']}:raise ValueError('Deferred proof inventory mismatch')
        for family in ('address','trap'):
            q=meta[family+'_qualification']
            if q['positive']['status']!='proved' or q['negative']['status']!='rejected':raise ValueError('Original metadata qualification incomplete')
            for kind in ('prove','cover','fault'):
                role=family+'-'+kind;item=meta['results'][role];status=metadata/role/'work/status';expected='FAIL' if kind=='fault' else 'PASS'
                if item['status']!=expected or status.read_text().split()[0]!=expected:raise ValueError('Metadata role mismatch')
                protected[str(status)]=digest(status)
                if kind!='prove':
                    if not item.get('witnesses'):raise ValueError('Missing metadata witness')
                    for w in item['witnesses']:
                        trace=local(w['path'])
                        if digest(trace)!=w['sha256'] or metadata_witness(trace.read_text(),role)!=w['event']:raise ValueError('Metadata witness changed')
                        protected[str(trace)]=digest(trace)
        receipt.update(assertions=prior['assertions'],groups=groups,depth=144,timeout_seconds=120,
            semantics='all33 original assertions, every original assumption preserved; no peer assertions assumed',
            evidence=dict(preproved=str(paths[0]),remaining22=str(paths[1]),destination_and_trap=str(paths[2])),
            historical_timeout_preserved=prior['results']['remaining'])
        for role in ('original-cover','original-fault'):
            design=copy.deepcopy(original);m=design['modules'][TOP];mode='cover'
            if role=='original-fault':
                enable=gate(m,'$and',m['netnames']['checker_inst.check']['bits'],m['netnames'][PREFIX+'spec_valid']['bits'])
                receipt['fault_driver']=inject(m,m['netnames']['checker_inst.rvfi_pc_wdata']['bits'][1],enable);mode='bmc'
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statusfile=job/'work/status';status=statusfile.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('PASS',0) if mode=='cover' else ('FAIL',2)):raise RuntimeError(role+': '+status)
            protected[str(statusfile)]=digest(statusfile);witnesses=[]
            for trace in (job/'work').glob('engine_*/trace*.vcd'):
                try:event=checker_witness(trace.read_text(),mode=='bmc')
                except ValueError:continue
                witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
            if not witnesses:raise ValueError('No concrete checked JALR witness')
            receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        verify_hashes(protected);receipt['status']='pass (all33 original JALR assertions with qualification; other ISA unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
