"""Close the exact original JALR assertion inventory using authenticated proofs."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate, flavor
from jalr_receipts import combine_hashes, verify_hashes
from assertion_partitions import assertions, partition, validate_partition, validate_union
from check_jalr_link import link_witness
from qualify_owner_valid import inject


def relocate(directory,raw,evidence):
    hashes=dict(evidence['input_sha256']);manifest=directory/'input-relocations.json'
    if manifest.exists():
        relocation=json.loads(manifest.read_text())
        if relocation['receipt_sha256']!=digest(raw):raise ValueError('Historical relocation receipt mismatch')
        for original,item in relocation['relocations'].items():
            archive=local(item['snapshot']);expected=item['expected_sha256']
            if hashes.get(original)!=expected or digest(archive)!=expected:raise ValueError('Historical input missing')
            del hashes[original];hashes[str(archive)]=expected
        hashes[str(manifest)]=digest(manifest)
    verify_hashes(hashes);hashes[str(raw)]=digest(raw)
    return hashes


def validate_helper(original,model,selected):
    inventory=set(assertions(original));m=model['modules'][TOP];o=original['modules'][TOP]
    if selected not in assertions(model) or set(assertions(model))&inventory!={selected}:
        raise ValueError('Original helper partition assertion inventory changed')
    for n,c in o['cells'].items():
        if n not in inventory or n==selected:
            if m['cells'].get(n)!=c:raise ValueError('Original partition semantic cell changed: '+n)
    for n,c in m['cells'].items():
        if n not in o['cells'] and flavor(c)=='assume':raise ValueError('Unchecked helper assumption')
    if m['ports']!=o['ports'] or any(m['netnames'].get(n)!=v for n,v in o['netnames'].items()):
        raise ValueError('Original helper partition interface changed')


def normalize_wrapper_metadata(model,old,new):
    result=copy.deepcopy(model);changes=[]
    for section in ('cells','netnames'):
        for name,item in result['modules'][TOP][section].items():
            for key,value in item.get('attributes',{}).items():
                if key in ('src','module_src') and isinstance(value,str) and old in value:
                    item['attributes'][key]=value.replace(old,new);changes.append((section,name,key))
    return result,changes


def checker_witness(text,fault):
    wanted={'reset':'checker_inst.reset','check':'checker_inst.check','valid':'rvfi_valid',
        'instruction':'rvfi_insn','trap':'rvfi_trap','pc':'rvfi_pc_rdata','next':'rvfi_pc_wdata',
        'source':'rvfi_rs1_rdata'}
    names={};values={};scope=[];found=[];time=0
    def sample():
        if any(n not in names or names[n] not in values for n in wanted):return
        raw={n:values[names[n]] for n in wanted}
        if any(set(v)-set('01') for v in raw.values()):return
        d={n:int(v,2) for n,v in raw.items()};insn=d['instruction']
        if d['reset'] or not d['check'] or not d['valid'] or insn&127!=0x67 or insn>>12&7:return
        imm=insn>>20;imm=imm-4096 if imm&2048 else imm
        expected=((d['source'] if insn>>15&31 else 0)+imm)&0xfffffffe
        if d['next']!=(expected^2 if fault else expected):return
        if d['trap']:return
        found.append(dict(time=time,values=d,expected_target=expected))
    for line in text.splitlines():
        p=line.split()
        if not p:continue
        if p[0]=='$scope':scope.append(p[2])
        elif p[0]=='$upscope':scope.pop()
        elif p[0]=='$var':
            full='.'.join(scope+[p[4]])
            for name,suffix in wanted.items():
                if full==TOP+'.'+suffix:names[name]=p[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(p)==2:values[p[1]]=p[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No concrete checked JALR '+('fault' if fault else 'cover'))
    return found[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--address',default='build/t13/jalr-address-strengthened')
    ap.add_argument('--link',default='build/t13/jalr-link-v2')
    ap.add_argument('--target',default='build/t13/jalr-target-composition-confirmed')
    ap.add_argument('--split',default='build/t13/rvf-jalr-split/jalr/bmc')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();address,link,target,split=[local(getattr(args,n)) for n in ('address','link','target','split')]
    out=output_dir(args.output);receipt=dict(status='running',scope='complete original JALR checker inventory only; other ISA instructions unresolved',results={});protected={}
    try:
        docs=[];inventories=[]
        for directory in (address,link,target):
            raw=directory/'result.json';evidence=json.loads(raw.read_text());docs.append(evidence)
            inventories.append(relocate(directory,raw,evidence))
        adr,lnk,tgt=docs
        if adr['status']!='pass (lemma and original address partition only)' or lnk['status']!='pass (link lemma and original value assertion only)' or tgt['status']!='pass (JALR target composition and original PC assertion; aggregate ISA unresolved)':
            raise ValueError('Preproved JALR obligation incomplete')
        protected=combine_hashes(*inventories)
        for p in (Path(__file__),Path(__file__).with_name('assertion_partitions.py'),Path(__file__).with_name('check_jalr_link.py'),Path(__file__).with_name('qualify_owner_valid.py')):protected[str(p)]=digest(p)
        original_path=address/'original.json';original=json.loads(original_path.read_text());inventory=assertions(original)
        if str(original_path) not in protected or len(inventory)!=33:raise ValueError('Unexpected original JALR inventory')
        # Existing partition proofs have identical semantics; only the verified
        # byte-identical wrapper emission's source-location path differs.
        split_raw=split/'partitions.json';prior=json.loads(split_raw.read_text());complete=split/'complete.json'
        for path,key in ((complete,'model_sha256'),(split/'raw.json','raw_sha256'),(split/'prepare.ys','preparation_sha256')):
            if digest(path)!=prior[key]:raise ValueError('Old partition preparation changed')
            protected[str(path)]=digest(path)
        protected[str(split_raw)]=digest(split_raw)
        old_wrapper=split.parents[1]/'rvfi_wrapper.sv';new_wrapper=address/'rvfi_wrapper.sv'
        if old_wrapper.read_bytes()!=new_wrapper.read_bytes():raise ValueError('Partition wrapper bytes changed')
        protected.update({str(p):digest(p) for p in (old_wrapper,new_wrapper)})
        split_model=json.loads(complete.read_text());normalized,changes=normalize_wrapper_metadata(split_model,
            str(old_wrapper.relative_to(local('.'))),str(new_wrapper.relative_to(local('.'))))
        if normalized!=original:raise ValueError('Partition model changed beyond verified wrapper source metadata')
        receipt['wrapper_metadata_relocations']=changes
        if prior['timeout_seconds']!=120 or prior['depth']!=144:raise ValueError('Old partition limits changed')
        reused=[]
        for index,item in enumerate(prior['results']):
            if item['status']!='PASS':continue
            job=split/f'part-{index:02d}';model=job/'model.json';config=job/'check.sby';status=job/'work/status'
            if digest(model)!=item['model_sha256'] or digest(config)!=item['config_sha256'] or status.read_text().split()[0]!='PASS':
                raise ValueError('Old partition proof bytes/status mismatch')
            expected=f'[options]\nmode prove\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nabc pdr\n[script]\nread_json {model}\nopt_clean\n'
            if config.read_text()!=expected:raise ValueError('Old partition was not the claimed unbounded proof')
            validate_partition(split_model,json.loads(model.read_text()),item['assertions'])
            protected.update({str(p):digest(p) for p in (model,config,status)})
            reused.append(dict(assertions=item['assertions'],kind='unbounded ABC PDR',status='PASS',seconds=item['seconds'],receipt=str(split_raw)))
        if len(reused)!=6:raise ValueError('Unexpected reused partition inventory')
        groups=[r['assertions'] for r in reused]
        for directory,evidence,role in ((address,adr,'original-source-address'),(link,lnk,'original-link-value')):
            selected=evidence['target_assertion'];model=directory/role/'model.json';status=directory/role/'work/status'
            if selected not in inventory or evidence['results'][role]['status']!='PASS' or status.read_text().split()[0]!='PASS':
                raise ValueError('Original address/link proof missing')
            validate_helper(original,json.loads(model.read_text()),selected)
            protected[str(status)]=digest(status);groups.append([selected])
        groups.append([tgt['original_target_assertion']])
        done={n for group in groups for n in group};remaining=[n for n in inventory if n not in done]
        validate_union(inventory,groups+[remaining])
        receipt.update(assertions={n:original['modules'][TOP]['cells'][n] for n in inventory},
                       reused_partitions=reused,preproved_groups=groups,remaining=remaining,depth=144,timeout_seconds=120,
                       assumptions='every original checker/environment assumption retained byte-for-byte; no peer assumptions')
        job=output_dir(out/'remaining');path=job/'model.json';path.write_text(json.dumps(partition(original,remaining)))
        config=job/'check.sby';config.write_text(f'[options]\nmode prove\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nabc pdr\n[script]\nread_json {path}\nopt_clean\n')
        protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
        result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
        statuspath=job/'work/status';status=statuspath.read_text().split()[0]
        receipt['results']['remaining']=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds,assertions=remaining)
        protected[str(statuspath)]=digest(statuspath)
        if (status,result.returncode)!=('PASS',0):raise RuntimeError('Remaining original JALR assertions: '+status)
        print('PASS remaining original JALR assertions',flush=True)
        for role in ('original-cover','original-fault'):
            design=copy.deepcopy(original);m=design['modules'][TOP];mode='cover'
            if role=='original-fault':
                enable=gate(m,'$and',m['netnames']['checker_inst.check']['bits'],m['netnames'][PREFIX+'spec_valid']['bits'])
                receipt['fault_driver']=inject(m,m['netnames']['checker_inst.rvfi_pc_wdata']['bits'][1],enable);mode='bmc'
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\nbtor btormc\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statuspath=job/'work/status';status=statuspath.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('PASS',0) if mode=='cover' else ('FAIL',2)):raise RuntimeError(role+': '+status)
            protected[str(statuspath)]=digest(statuspath);witnesses=[]
            for trace in (job/'work').glob('engine_*/trace*.vcd'):
                try:event=checker_witness(trace.read_text(),mode=='bmc')
                except ValueError:continue
                witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
            if not witnesses:raise ValueError('No concrete original checker witness: '+role)
            receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        validate_union(inventory,groups+[remaining]);verify_hashes(protected)
        receipt['status']='pass (all 33 original JALR assertions; other ISA instructions unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
