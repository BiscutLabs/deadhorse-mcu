"""Budgeted triage of existing instruction jobs, without new instruction properties.

User-approved order: Step0 diagnostics, concrete engine portfolio, data-only
cutpoints, then cover-minimum+8 check cycles. One invocation per rung/property.
No induction, assertion partitioning or protocol replacement is performed.
"""
import argparse
import hashlib
import json
import re
import shlex
import shutil
import sys
import time
from pathlib import Path

from common import ROOT, local, output_dir, run
from critical_isa_witness import active_witness

ENGINES=['btor btormc','smtbmc yices','smtbmc z3','abc bmc3']
STAGES=('portfolio','cutpoints','window')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_archive(folder,source,value):
    stems={str(Path(__file__).resolve()):'executed-runner',str(ROOT/'dv/core/critical_isa_witness.py'):'executed-witness'}
    if source not in stems:raise ValueError('Non-tool input changed: '+source)
    for suffix in ('','-'+value):
        path=folder/(stems[source]+suffix+'.py')
        if path.exists() and sha(path)==value:return path
    raise ValueError('No exact executed source archive: '+source)


def last_step(text):
    return max([int(v) for v in re.findall(r'(?:at bound k = |in step |at step )(\d+)',text)],default=None)


def configured(original,mode='bmc',depth=144,cycle=64,timeout=600,engines=None,cutpoints=(),clock_depth=None):
    _,source=original.split('[script]\n')
    source,count=re.subn(r'RISCV_FORMAL_CHECK_CYCLE=\d+',f'RISCV_FORMAL_CHECK_CYCLE={cycle}',source)
    if count!=1:raise ValueError('Expected one checker cycle')
    source,count=re.subn(r'fminit -seq clock [01,]+',
        'fminit -seq clock '+','.join(str(i%2) for i in range(clock_depth or depth)),source)
    if count!=1:raise ValueError('Expected original alternating clock initialization')
    if cutpoints:
        for name in cutpoints:
            if not re.fullmatch(r'[a-zA-Z0-9_.$]+',name):raise ValueError('Invalid data cutpoint')
            source+=f'\nselect -assert-count 1 rvfi_testbench/w:{name}\ncutpoint rvfi_testbench/w:{name}\n'
        source+='select *\nopt_clean\n'
    selected=engines or ENGINES
    if mode=='cover':selected=[e for e in selected if not e.startswith('abc ')]
    return (f'[options]\nmode {mode}\ndepth {depth}\nmulticlock on\ntimeout {timeout}\n'
            '[engines]\n'+'\n'.join(selected)+'\n[script]\n'+source)


def outcome(folder,process):
    work=folder/'work';status=(work/'status').read_text().split()[0]
    if (status,process.returncode) not in [('PASS',0),('FAIL',2),('TIMEOUT',8),('ERROR',16)]:
        raise ValueError('Inconsistent solver result')
    text=(work/'logfile.txt').read_text()
    return dict(status=status,returncode=process.returncode,seconds=process.elapsed_seconds,
        winner=re.findall(r'summary: engine_\d+ \(([^)]+)\) returned (?:pass|PASS|FAIL|fail)',text),
        last_step=last_step(text),
        traces=[str(p) for p in work.glob('engine_*/trace*.vcd')])


def job(folder,body,timeout,protected):
    folder=output_dir(folder)
    if (folder/'check.sby').exists():
        # Resume parsing/remaining roles only. A completed job is never rerun,
        # including a timeout; exact configuration and its command receipt bind it.
        if (folder/'check.sby').read_text()!=body:raise ValueError('Existing job configuration differs')
        records=[json.loads(line) for line in (folder/'commands.jsonl').read_text().splitlines()]
        expected=['sby','-f','-d',str(folder/'work'),str(folder/'check.sby')]
        matches=[r for r in records if r.get('command')==expected and 'returncode' in r]
        if len(matches)!=1:raise ValueError('No unique completed job to resume; no retry authorized')
        from types import SimpleNamespace
        process=SimpleNamespace(returncode=matches[0]['returncode'],elapsed_seconds=matches[0]['elapsed_seconds'])
        for p in [folder/'check.sby',folder/'commands.jsonl',folder/'work/status',folder/'work/logfile.txt']:
            protected[str(p)]=sha(p)
        result=outcome(folder,process);result['reused_completed_job']=True
        for p in result['traces']:protected[p]=sha(p)
        return result
    cfg=folder/'check.sby';cfg.write_text(body);protected[str(cfg)]=sha(cfg)
    process=run(['sby','-f','-d',folder/'work',cfg],folder,'run',allowed=(0,2,8,16),timeout=timeout+30)
    result=outcome(folder,process)
    for p in [folder/'work/status',folder/'work/logfile.txt',*[Path(p) for p in result['traces']]]:
        protected[str(p)]=sha(p)
    return result


def source_inventory(configs):
    files={Path(__file__),ROOT/'dv/core/common.py',ROOT/'dv/core/critical_isa_witness.py'}
    for cfg in configs:
        files.add(cfg)
        for line in cfg.read_text().splitlines():
            if not line.startswith(('read_slang ','read_verilog ')):continue
            for token in shlex.split(line):
                if token.endswith(('.sv','.v','.vh')):files.add(local(token))
                if token.startswith('-I'):
                    for pattern in ('*.vh','*.svh'):files.update(local(token[2:]).rglob(pattern))
    return {str(p):sha(p) for p in files}


def qualify(name,original,out,cycle,depth,protected,base):
    result={}
    for role in ('cover','negative','nonzero-negative'):
        source=original
        if role!='cover':
            fault=base/('fault-wrapper' if role=='negative' else 'nonzero-fault-wrapper')/'rvfi_wrapper.sv'
            protected[str(fault)]=sha(fault)
            source=source.replace(str(base/'rvfi_wrapper.sv'),str(fault))
        r=job(out/role,configured(source,mode='cover' if role=='cover' else 'bmc',
                cycle=cycle,depth=depth),600,protected)
        result[role]=r
        wanted='PASS' if role=='cover' else 'FAIL'
        if r['status']!=wanted:return result
        witnesses=[]
        for trace in r['traces']:
            try:witnesses.append(active_witness(Path(trace).read_text(),name,role!='cover',nonzero=role=='nonzero-negative'))
            except ValueError:pass
        if not witnesses:raise ValueError('No actual checked concrete witness for '+role)
        r['active_witnesses']=witnesses
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',default='build/t13/rvf-critical')
    ap.add_argument('--output',default='build/t13/feedback/triage')
    ap.add_argument('--stage',choices=('step0',*STAGES),required=True)
    ap.add_argument('--checks',default='lw,c_add')
    ap.add_argument('--cutpoints',help='JSON array of exact DATA net names; no control cutpoints')
    ap.add_argument('--resume',action='store_true',help='Parse completed identical jobs and run only never-started roles; never retry a job')
    args=ap.parse_args();base=local(args.baseline);root=output_dir(args.output)
    out=root/args.stage
    if out.exists() and not args.resume:raise ValueError('One attempt per stage; output already exists')
    resumed=None
    if args.resume:
        resumed=json.loads((out/'result.json').read_text())
        if resumed['status']!='error' or not resumed.get('error','').startswith('No actual checked concrete witness'):
            raise ValueError('Resume only a witness-parser interruption, not a proof retry')
        for p,value in resumed['input_sha256'].items():
            if sha(p)==value:continue
            source_archive(out,p,value)
        resume_record=out/('interrupted-'+sha(out/'result.json')+'.json')
        if not resume_record.exists():resume_record.write_bytes((out/'result.json').read_bytes())
    out=output_dir(out);started=time.monotonic();names=args.checks.split(',')
    if not names or len(names)!=len(set(names)) or any(not re.fullmatch('[a-z0-9_]+',n) for n in names):
        raise ValueError('Invalid property list')
    configs=[base/n/'bmc/check.sby' for n in names];protected=source_inventory(configs)
    receipt=dict(status='running',stage=args.stage,checks={},input_sha256=protected,
        budget='one attempt per rung; three rungs per property; stop on counterexample',engines=ENGINES)
    if resumed:
        receipt['resumed_from']=dict(path=str(resume_record),sha256=sha(resume_record),
            reason='native VCD channel scope parser repair; existing solver jobs reused without retry')
        for p in (out/'initial-result.json',out/'executed-runner.py',out/'executed-witness.py'):protected[str(p)]=sha(p)
        protected[str(resume_record)]=sha(resume_record)
        for source,value in resumed['input_sha256'].items():
            if sha(source)!=value:
                archive=source_archive(out,source,value);protected[str(archive)]=value
    def save():
        receipt['elapsed_seconds']=time.monotonic()-started
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    try:
        if args.stage!='step0':
            previous='step0' if args.stage=='portfolio' else STAGES[STAGES.index(args.stage)-1]
            prior_path=root/previous/'result.json';prior=json.loads(prior_path.read_text())
            if prior['status'] in ('counterexample','error'):raise ValueError('Previous stage requires investigation; stop')
            for path,value in prior['input_sha256'].items():
                if sha(path)==value:continue
                archive=source_archive(prior_path.parent,path,value)
                receipt.setdefault('prior_source_archives',{})[path]=dict(path=str(archive),sha256=value)
                protected[str(archive)]=value
            protected[str(prior_path)]=sha(prior_path)
            step0=json.loads((root/'step0/result.json').read_text())
            cuts=json.loads(local(args.cutpoints).read_text()) if args.cutpoints else []
            if args.stage in ('cutpoints','window') and not cuts:raise ValueError('Data cutpoint inventory required')
            if args.cutpoints:protected[str(local(args.cutpoints))]=sha(local(args.cutpoints))
            # Existing Chisel wrapper already supports a nonzero-destination fault.
            fault=output_dir(base/'nonzero-fault-wrapper')
            if not (fault/'rvfi_wrapper.sv').exists():
                for f in ('ports.tsv','parameters.tsv'):shutil.copyfile(base/f,fault/f)
                run([sys.executable,'tools/sbt.py','set hw / Compile / unmanagedSourceDirectories += file("/work/dv/core")',
                    f'hw/runMain deadhorse.reference.EmitReferenceFormal {fault} fault-nonzero'],out,'emit-nonzero-fault')
        for name,cfg in zip(names,configs):
            item={};receipt['checks'][name]=item;original=cfg.read_text();folder=output_dir(out/name)
            if args.stage=='step0':
                if time.monotonic()-started>900:raise RuntimeError('Step0 15-minute budget exhausted')
                model=base/name/'bmc/work/model/design.il';protected[str(model)]=sha(model)
                ys=folder/'stat.ys';ys.write_text(f'read_rtlil {model}\ntee -o {folder}/stat.json stat -json\nwrite_json {folder}/model.json\n')
                run(['yosys','-Q','-T','-s',ys],folder,'stat',timeout=120)
                data=json.loads((folder/'model.json').read_text());cells=data['modules']['rvfi_testbench']['cells']
                item['model_size']=dict(cells=len(cells),flip_flop_bits=sum(int(c['parameters']['WIDTH'],2) for c in cells.values()
                    if ('dff' in c['type'].lower() or c['type']=='$ff') and 'WIDTH' in c['parameters']),
                    memories=sum(c['type'].startswith('$mem') for c in cells.values()))
                old=(base/name/'bmc/work/logfile.txt').read_text()
                item.update(original_depth=144,original_check_cycle=64,
                    original_last_step=last_step(old),growth={})
                for depth in (36,72):
                    r=job(folder/f'depth-{depth}',configured(original,depth=depth,clock_depth=144,timeout=120,engines=['btor btormc']),120,protected)
                    item['growth'][str(depth)]=r;save()
                    if r['status']=='FAIL':receipt['status']='counterexample';save();return 2
                    if r['status']!='PASS':raise RuntimeError('Step0 growth diagnostic unresolved; stop before more attempts')
                item['growth_scope']='Before check-cycle activation: vacuous ISA diagnostics only'
                item['cover_search']=[]
                for cycle in range(1,65):
                    if time.monotonic()-started>900:raise RuntimeError('Step0 15-minute budget exhausted')
                    depth=2*(cycle+8)
                    r=job(folder/f'cover-cycle-{cycle}',configured(original,mode='cover',cycle=cycle,depth=depth,
                        timeout=120,engines=['btor btormc']),120,protected)
                    item['cover_search'].append(dict(check_cycle=cycle,depth=depth,**r));save()
                    if r['status']=='PASS':item['minimum_cover_cycle']=cycle;break
                    if r['status']!='FAIL':raise RuntimeError('Cover minimum unresolved; stop search')
                if 'minimum_cover_cycle' not in item:raise RuntimeError('No reachable original cover in search range')
            else:
                resolved=prior['checks'].get(name,{}).get('status')=='accepted'
                if resolved:item.update(prior['checks'][name]);item['reused_from']=str(prior_path);continue
                cycle=64 if args.stage!='window' else step0['checks'][name]['minimum_cover_cycle']+8
                depth=2*(cycle+8)
                item.update(check_cycle=cycle,depth=depth,cutpoints=cuts,
                    classification='bounded, abstracted' if cuts else 'bounded',
                    histories='shorter startup window covers fewer preceding histories' if args.stage=='window' else 'original startup window')
                item['positive']=job(folder/'bmc',configured(original,cycle=cycle,depth=depth,cutpoints=cuts),600,protected);save()
                if item['positive']['status']=='FAIL':receipt['status']='counterexample';save();return 2
                if item['positive']['status']=='ERROR':raise RuntimeError('Portfolio tooling error; preserve and report')
                if item['positive']['status']=='PASS':
                    item['qualification']=qualify(name,original,folder,cycle,depth,protected,base)
                    expected={'cover':'PASS','negative':'FAIL','nonzero-negative':'FAIL'}
                    item['status']='accepted' if {k:r['status'] for k,r in item['qualification'].items()}==expected else 'unresolved'
                else:item['status']='unresolved'
            save()
        for p,value in protected.items():
            if sha(p)!=value:raise ValueError('Input changed during triage: '+p)
        receipt['status']='measured' if args.stage=='step0' else 'pass' if all(r.get('status')=='accepted' for r in receipt['checks'].values()) else 'unresolved'
    except BaseException as exc:receipt.update(status='error',error=str(exc));raise
    finally:save()
    print(receipt['status']+': '+args.stage,flush=True)
    return 0 if receipt['status'] in ('measured','pass','unresolved') else 1


if __name__=='__main__':sys.exit(main())
