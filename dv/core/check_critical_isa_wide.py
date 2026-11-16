"""One fail-fast unchanged critical ISA check with qualified FPU overapproximation.

Safety alone uses the qualified all-port FPU model. Retirement covers and the
original actual RVFI-output mutation use the concrete FPU and original scripts.
Bounds, checker assertions, assumptions and clock sequence remain unchanged.
"""
import argparse
import json
import shlex
from pathlib import Path
from common import ROOT, local, output_dir, run
from jalr_invariant import digest
from jalr_receipts import verify_hashes
from qualify_fpu_protocol_wide import protect
from check_float_integration_wide import graft
from critical_isa_witness import active_witness


def source_paths(script):
    return [local(t) for line in script.splitlines() if line.startswith(('read_slang ','read_verilog '))
            for t in shlex.split(line) if t.endswith(('.sv','.v','.vh'))]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',default='build/t13/rvf-critical')
    ap.add_argument('--integration',default='build/t13/integration-wide')
    ap.add_argument('--binding',default='build/t13/integration-production-binding/result.json')
    ap.add_argument('--qualification',default='build/t13/fpu-protocol-wide-confirmed')
    ap.add_argument('--checks',default='lw,c_add')
    ap.add_argument('--output',required=True)
    ap.add_argument('--prepare-only',action='store_true')
    args=ap.parse_args();base=local(args.baseline);out=output_dir(args.output)
    receipt=dict(status='running',results={},depth=144,check_cycle=64,timeout_seconds=120,
        scope='bounded critical ISA safety with qualified FPU; concrete retirement covers and actual RVFI fault')
    protected={}
    try:
        integration=local(args.integration)/'result.json';prior=json.loads(integration.read_text())
        if prior['status']!='pass (28 integration safety assertions; eight abstract covers); ISA unresolved':
            raise ValueError('Wide integration safety not cleared')
        protected=dict(prior['input_sha256'])
        binding_path=local(args.binding);binding=json.loads(binding_path.read_text())
        if binding['status']!='pass (fresh concrete integration instrumentation-to-production binding; no safety proof rerun)':raise ValueError('Fresh integration production binding unavailable')
        if binding['safety_receipt']!={'path':str(integration),'sha256':digest(integration)}:raise ValueError('Binding targets different integration receipt')
        if {k:v['status'] for k,v in binding['results'].items()}!={'positive':'proved','output':'rejected','reset-value':'rejected','next-state':'rejected','clock':'rejected'}:raise ValueError('Binding negative controls incomplete')
        for name,value in binding['input_sha256'].items():
            if name in protected and protected[name]!=value:raise ValueError('Conflicting binding dependency')
            protected[name]=value
        protect(protected,[binding_path]);verify_hashes(protected)
        receipt['production_binding']={'path':str(binding_path),'sha256':digest(binding_path)}
        qualified=local(args.qualification);qpath=qualified/'result.json';q=json.loads(qpath.read_text())
        if prior['qualification']!={'path':str(qpath),'sha256':digest(qpath)}:
            raise ValueError('Integration used different qualification')
        protect(protected,[integration,Path(__file__),ROOT/'dv/core/check_float_integration_wide.py',
            ROOT/'dv/core/riscv_formal.py',ROOT/'dv/core/critical_isa_witness.py',base/'result.json',base/'candidate-sources.json'])
        for entry in json.loads((base/'candidate-sources.json').read_text()):
            if 'candidate' in entry:
                path=local(entry['candidate'])
                if digest(path)!=entry['sha256']:raise ValueError('Original candidate source changed')
                protect(protected,[path])
        abstract=json.loads((qualified/'abstract.json').read_text())['modules']['Fpu']
        fault=base/'fault-wrapper/rvfi_wrapper.sv';protect(protected,[fault])
        checks=args.checks.split(',')
        if any(c not in ('lw','c_add') for c in checks) or len(set(checks))!=len(checks):raise ValueError('Only critical lw/c_add allowed')
        for name in checks:
            job=output_dir(out/name);config=base/name/'bmc/check.sby';frozen=base/name/'bmc/work/model/design.il'
            protect(protected,[config,frozen]);text=config.read_text();prefix,script=text.split('[script]\n')
            if ('depth 144\n' not in prefix or 'timeout 120\n' not in prefix or
                'multiclock on\n' not in prefix or '-DRISCV_FORMAL_CHECK_CYCLE=64 ' not in script):
                raise ValueError('Original checker configuration changed')
            files=source_paths(script)
            include_dirs=[local(t[2:]) for line in script.splitlines() for t in shlex.split(line) if t.startswith('-I')]
            headers=[p for directory in include_dirs for pattern in ('*.svh','*.vh') for p in directory.rglob(pattern)]
            protect(protected,[*files,*headers])
            if local('build/t13/exponent/candidate/Fpu.sv') not in files:raise ValueError('Different concrete FPU source')
            verify_hashes(protected)
            reproduced=job/'original.il';ys=job/'original.ys'
            ys.write_text(script+f'\nhierarchy -smtcheck\nrename -witness\nwrite_jny -no-connections {job}/original-names.json\nwrite_rtlil {reproduced}\n')
            protect(protected,[ys]);run(['python3','-c','import os,sys;os.chdir(sys.argv[1]);os.execvp(sys.argv[2],sys.argv[2:])',base/name/'bmc/work/src','yosys','-Q','-T','-s',ys],job,'original',timeout=120)
            verify_hashes(protected);protect(protected,[reproduced])
            if reproduced.read_bytes()!=frozen.read_bytes():raise ValueError('Frozen original checker reconstruction differs')
            lines=script.splitlines();slang=lines[0]
            if not slang.startswith('read_slang --top rvfi_wrapper '):raise ValueError('Unexpected original frontend')
            hierarchy=job/'hierarchy.json';hys=job/'hierarchy.ys'
            hys.write_text(slang.replace('read_slang ','read_slang --keep-hierarchy ',1)+f'\nwrite_json {hierarchy}\n')
            protect(protected,[hys]);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',hys],job,'hierarchy',timeout=120)
            verify_hashes(protected);protect(protected,[hierarchy])
            changed,boundary=graft(json.loads(hierarchy.read_text()),abstract)
            grafted=job/'grafted.json';grafted.write_text(json.dumps(changed))
            prepared=job/'prepared.json';pys=job/'prepare.ys'
            pys.write_text(f'read_json {grafted}\n'+'\n'.join(lines[1:])+f'\nwrite_json {prepared}\n')
            protect(protected,[grafted,pys]);verify_hashes(protected)
            run(['yosys','-Q','-T','-s',pys],job,'prepare',timeout=120)
            verify_hashes(protected);protect(protected,[prepared])
            receipt['results'][name]=dict(status='prepared',boundary=boundary,checks={})
            if args.prepare_only:continue
            variants=(('bmc',prefix+'[script]\n'+f'read_json {prepared}\n','PASS',0),
                ('cover',text.replace('mode bmc\n','mode cover\n',1),'PASS',0),
                ('negative',text.replace(str(base/'rvfi_wrapper.sv'),str(fault)),'FAIL',2))
            if text.count(str(base/'rvfi_wrapper.sv'))!=1:raise ValueError('Original fault wrapper not unique')
            for role,body,expected,code in variants:
                folder=output_dir(job/role);cfg=folder/'check.sby';cfg.write_text(body)
                protect(protected,[cfg]);verify_hashes(protected)
                result=run(['sby','-f','-d',folder/'work',cfg],folder,'check',allowed=(0,2,8,16),timeout=150)
                status=folder/'work/status';actual=status.read_text().split()[0]
                protect(protected,[status]);verify_hashes(protected)
                record=dict(status=actual,returncode=result.returncode,seconds=result.elapsed_seconds,
                    concrete=role!='bmc')
                receipt['results'][name]['checks'][role]=record
                if (actual,result.returncode)!=(expected,code):raise ValueError(name+'/'+role+': '+actual+'; no acceptance claim')
                if role!='bmc':
                    traces=list((folder/'work').glob('engine_*/trace*.vcd'))
                    if not traces:raise ValueError('Missing concrete witness')
                    protect(protected,traces);witnesses=[]
                    for trace in traces:
                        try:event=active_witness(trace.read_text(),name,role=='negative')
                        except ValueError:continue
                        witnesses.append(dict(path=str(trace),sha256=digest(trace),event=event))
                    if not witnesses:raise ValueError('Missing active check-cycle concrete witness')
                    record['witnesses']=witnesses
                print(name+'/'+role+': '+actual,flush=True)
            receipt['results'][name]['status']='bounded safety checked; concrete retirement reached; fault rejected'
        verify_hashes(protected)
        receipt['status']='prepared; no ISA solver run' if args.prepare_only else 'pass (bounded critical ISA only); no unbounded ISA proof'
    except BaseException as exc:receipt.update(status='unresolved',error=str(exc));raise
    finally:
        receipt['input_sha256']=protected;(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
