"""Qualify the remaining cheap JALR predicates; preserve destination/trap blockers."""
import argparse
import copy
import json
from pathlib import Path
from common import local, output_dir, run
from jalr_invariant import TOP, PREFIX, digest, gate
from jalr_receipts import verify_hashes
from assertion_partitions import assertions, partition, validate_union
from qualify_owner_valid import inject
from complete_jalr_inventory import checker_witness


def memory_fault_witness(text):
    wanted={'reset':'checker_inst.reset','check':'checker_inst.check','valid':'rvfi_valid',
        'instruction':'rvfi_insn','write':'rvfi_mem_wmask','read':'rvfi_mem_rmask',
        'readData':'rvfi_mem_rdata','writeData':'rvfi_mem_wdata','trap':'rvfi_trap'}
    scope=[];names={};values={};found=[];time=0
    def sample():
        if any(n not in names or names[n] not in values for n in wanted):return
        raw={n:values[names[n]] for n in wanted}
        if any(set(v)-set('01') for v in raw.values()):return
        d={n:int(v,2) for n,v in raw.items()};i=d['instruction']
        if not d['reset'] and d['check'] and d['valid'] and i&127==0x67 and not(i>>12&7) and not d['trap'] and d['write']==1 and (not(d['read']&1) or (d['readData']&255)!=(d['writeData']&255)):
            found.append(dict(time=time,values=d))
    for line in text.splitlines():
        p=line.split()
        if not p:continue
        if p[0]=='$scope':scope.append(p[2])
        elif p[0]=='$upscope':scope.pop()
        elif p[0]=='$var':
            full='.'.join(scope+[p[4]])
            for n,s in wanted.items():
                if full==TOP+'.'+s:names[n]=p[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(p)==2:values[p[1]]=p[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No active original mask assertion fault')
    return found[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--baseline',default='build/t13/jalr-complete-inventory');ap.add_argument('--output',required=True)
    args=ap.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',scope='22 original JALR predicates only; destination/trap and aggregate unresolved',results={});protected={}
    try:
        raw=base/'result.json';prior=json.loads(raw.read_text());protected=dict(prior['input_sha256'])
        for p in (raw,Path(__file__),Path(__file__).with_name('complete_jalr_inventory.py')):protected[str(p)]=digest(p)
        verify_hashes(protected)
        modelpath=base/'remaining/model.json'
        if str(modelpath) not in protected:raise ValueError('Unauthenticated remaining model')
        original=json.loads(modelpath.read_text());inventory=assertions(original)
        deferred=[n for n in inventory if any('rvfi_insn_check.sv:'+str(line)+'$assert' in n for line in (176,198))]
        selected=[n for n in inventory if n not in deferred]
        if len(selected)!=22 or len(deferred)!=2:raise ValueError('Unexpected remaining partition inventory')
        validate_union(inventory,[selected,deferred])
        receipt.update(selected=selected,deferred=deferred,timeout_seconds=120,depth=144,
            original_timeout=prior['results']['remaining'],assumptions=prior['assumptions'])
        model=partition(original,selected)
        for role in ('prove','cover','memory-fault'):
            design=copy.deepcopy(model);m=design['modules'][TOP];mode='prove';engine='abc pdr'
            if role=='cover':mode='cover';engine='btor btormc'
            elif role=='memory-fault':
                enable=gate(m,'$and',m['netnames']['checker_inst.check']['bits'],m['netnames'][PREFIX+'spec_valid']['bits'])
                receipt['fault_driver']=inject(m,m['netnames']['checker_inst.rvfi_mem_wmask']['bits'][0],enable)
                mode='bmc';engine='btor btormc'
            job=output_dir(out/role);path=job/'model.json';path.write_text(json.dumps(design));config=job/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth 144\nmulticlock on\ntimeout 120\n[engines]\n{engine}\n[script]\nread_json {path}\nopt_clean\n')
            protected.update({str(p):digest(p) for p in (path,config)});verify_hashes(protected)
            result=run(['sby','-f','-d',job/'work',config],job,'check',allowed=(0,2,8,16),timeout=150)
            statuspath=job/'work/status';status=statuspath.read_text().split()[0]
            receipt['results'][role]=dict(status=status,returncode=result.returncode,seconds=result.elapsed_seconds)
            if (status,result.returncode)!=(('FAIL',2) if role=='memory-fault' else ('PASS',0)):raise RuntimeError(role+': '+status)
            protected[str(statuspath)]=digest(statuspath)
            if role!='prove':
                witnesses=[]
                for trace in (job/'work').glob('engine_*/trace*.vcd'):
                    try:event=memory_fault_witness(trace.read_text()) if role=='memory-fault' else checker_witness(trace.read_text(),False)
                    except ValueError:continue
                    witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event));protected[str(trace)]=digest(trace)
                if not witnesses:raise ValueError('No concrete original checker witness')
                receipt['results'][role]['witnesses']=witnesses
            print(role+': '+status,flush=True)
        verify_hashes(protected);receipt['status']='pass (22 original JALR predicates; destination/trap unresolved)'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
