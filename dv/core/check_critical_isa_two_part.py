"""One exact two-part critical ISA refinement; unchanged non-assertion model.

The two complementary groups remove only peer assertions, never assume them.
A fail-fast run stops after any unresolved group or qualification role.

Boolector's --checkall checks the disjunction of bad properties (UNSAT means
every assertion holds), instead of separate SAT calls for each assertion.
Primary implementation: https://github.com/Boolector/boolector/blob/master/src/btormcmain.c
Pinned executable help and SBY's actual solver command are retained in output.
This changes scheduling only; it is neither an abstraction nor an assumption.
"""
import argparse
import json
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import digest
from jalr_receipts import verify_hashes, combine_hashes
from qualify_fpu_protocol_wide import protect
from assertion_partitions import assertions, partition, validate_union
from critical_isa_witness import active_witness


def checkall_config(text):
    sections=text.split('[engines]\n')
    if len(sections)!=2 or not sections[1].startswith('btor btormc\n[script]\n'):
        raise ValueError('Unexpected engine configuration')
    options=sections[0]
    if options!='[options]\nmode bmc\ndepth 144\nmulticlock on\ntimeout 120\n':
        raise ValueError('Original bounded limits changed')
    return options+'[engines]\nbtor btormc --checkall\n'+sections[1][len('btor btormc\n'):]


def model_inventory(model):
    inventory=assertions(model)
    if len(inventory)!=33:raise ValueError('Original instruction assertion count changed')
    cells=model['modules']['rvfi_testbench']['cells']
    return {kind:{name:cell for name,cell in cells.items() if
            (name in inventory if kind=='assertions' else cell['type'] in ('$assume','$cover') or
             cell['type']=='$check' and cell['parameters'].get('FLAVOR') in ('assume','cover'))}
            for kind in ('assertions','assumptions_and_covers')}


def run_check(name,prior_name,out,protected,receipt):
    item=dict(status='running',checks={});receipt['results'][name]=item
    out=output_dir(out/name)
    prior_path=local(prior_name);prior=json.loads(prior_path.read_text())
    if prior.get('error')!=name+'/bmc: TIMEOUT; no acceptance claim' or prior['results'][name]['checks']['bmc']['status']!='TIMEOUT':
        raise ValueError('Expected immutable original instruction timeout receipt')
    merged=combine_hashes(protected,prior['input_sha256']);protected.update(merged);verify_hashes(protected)
    protect(protected,[prior_path,Path(__file__),ROOT/'dv/core/assertion_partitions.py',
        ROOT/'dv/core/critical_isa_witness.py',ROOT/'dv/core/common.py',ROOT/'dv/core/jalr_receipts.py'])
    old=prior_path.parent/name/'bmc/check.sby';model=prior_path.parent/name/'prepared.json'
    if str(old) not in protected or str(model) not in protected:raise ValueError('Old model/config not authenticated')
    old_text=old.read_text()
    if old_text.split('[script]\n')[1]!=f'read_json {model}\n':raise ValueError('Unexpected old model reference')
    item['inventory']=model_inventory(json.loads(model.read_text()))
    item['original_model']={'path':str(model),'sha256':digest(model)}
    item['historical_timeout']={'path':str(prior_path),'sha256':digest(prior_path)}
    receipt['production_binding']=prior['production_binding']
    help_result=run(['btormc','--help'],out,'btormc-help',timeout=10)
    if '--checkall' not in help_result.stdout or 'disjunction of given' not in help_result.stdout:
        raise ValueError('Pinned btormc lacks native disjunction option')
    protect(protected,[out/'btormc-help.log'])
    base=local('build/t13/rvf-critical');concrete=base/name/'bmc/check.sby'
    if str(concrete) not in protected:raise ValueError('Concrete checker config not authenticated')
    concrete_text=concrete.read_text()
    checkall_config(concrete_text)
    if '-DRISCV_FORMAL_CHECK_CYCLE=64 ' not in concrete_text:raise ValueError('Concrete checker cycle changed')
    normal=str(base/'rvfi_wrapper.sv');fault=str(base/'fault-wrapper/rvfi_wrapper.sv')
    if concrete_text.count(normal)!=1 or fault not in protected:raise ValueError('Original concrete fault missing')
    original=json.loads(model.read_text());inventory=assertions(original)
    groups=[inventory[:11],inventory[11:]];validate_union(inventory,groups)
    try:validate_union(inventory,[groups[0][:-1],groups[1]])
    except ValueError:item['omitted_property_negative']='rejected'
    else:raise ValueError('Missing-property union escaped')
    item['groups']=groups;configs=[]
    for index,group in enumerate(groups):
        folder=output_dir(out/f'bmc-{index}');selected=folder/'partition.json'
        selected.write_text(json.dumps(partition(original,group)))
        protect(protected,[selected])
        configs.append((f'bmc-{index}',checkall_config(old_text).replace(str(model),str(selected)),'PASS',0))
    configs.extend([('cover',concrete_text.replace('mode bmc\n','mode cover\n',1),'PASS',0),
        ('negative',checkall_config(concrete_text.replace(normal,fault)),'FAIL',2)])
    for role,body,expected,code in configs:
        folder=output_dir(out/role);cfg=folder/'check.sby';cfg.write_text(body)
        protect(protected,[cfg]);verify_hashes(protected)
        result=run(['sby','-f','-d',folder/'work',cfg],folder,'check',allowed=(0,2,8,16),timeout=150)
        status=folder/'work/status';actual=status.read_text().split()[0]
        protect(protected,[status,folder/'work/logfile.txt']);verify_hashes(protected)
        record=dict(status=actual,returncode=result.returncode,seconds=result.elapsed_seconds,concrete=not role.startswith('bmc-'))
        item['checks'][role]=record
        if (actual,result.returncode)!=(expected,code):raise ValueError(name+'/'+role+': '+actual+'; no acceptance claim')
        if role!='cover':
            log=(folder/'work/logfile.txt').read_text()
            if 'btormc --stop-first 1 -v 1 -kmax 143 --checkall' not in log:
                raise ValueError('Pinned engine did not execute requested native scheduling')
        if not role.startswith('bmc-'):
            traces=list((folder/'work').glob('engine_*/trace*.vcd'));protect(protected,traces)
            witnesses=[]
            for trace in traces:
                try:event=active_witness(trace.read_text(),name,role=='negative')
                except ValueError:continue
                witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event))
            if not witnesses:raise ValueError('No active concrete '+name+' '+role+' witness')
            record['witnesses']=witnesses
        print(name+'/'+role+': '+actual,flush=True)
    verify_hashes(protected)
    item['status']='two complementary bounded partitions checked; concrete retirement reached; fault rejected'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lw-prior',default='build/t13/critical-wide/result.json')
    ap.add_argument('--c-add-prior',default='build/t13/critical-c-add-wide/result.json')
    ap.add_argument('--output',required=True)
    args=ap.parse_args();out=output_dir(args.output);protected={}
    receipt=dict(status='running',depth=144,check_cycle=64,timeout_seconds=120,results={},
        scope='exact 11/22 complementary partitions of all 33 originals; no peer assumptions; bounded only')
    try:
        # Fail fast: do not start C.ADD if any LW role remains unresolved.
        for name,prior in [('lw',args.lw_prior),('c_add',args.c_add_prior)]:
            run_check(name,prior,out,protected,receipt)
        verify_hashes(protected)
        receipt['status']='pass (bounded critical ISA two-part proof only); no unbounded ISA proof'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
