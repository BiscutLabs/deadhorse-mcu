"""Explicit fast/full local CI plans; no timeout-dependent check selection."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BUS_FORMAL_DEFERRALS=frozenset(('T14-BUS-FAIR-M0','T14-BUS-FAIR-M1',
    'T14-BUS-FAIR-M2','T14-BRIDGE-RETURN-DATA'))


def fast_commands(output):
    py=sys.executable;root=output.relative_to(ROOT).as_posix()
    def emit(name,path):return [py,'tools/sbt.py',f'hw/runMain {name} {root}/{path}']
    def package(floating):
        return [py,'hw/ip/perf_core/formal/package_candidate.py',
            '--registered',*(['--float'] if floating else []),
            '--top',f'{root}/'+('float-emit' if floating else 'baseline-emit')+'/model',
            '--leaves',f'{root}/leaves','--core',f'{root}/core',
            '--output',f'{root}/'+('floating' if floating else 'baseline')]
    return [
        ('environment',[py,'tools/env/check.py']),
        ('structure',[py,'tools/check_structure.py','--include-untracked']),
        ('vendor-lock',[py,'hw/vendor/ibex_ref/verify_lock.py']),
        ('tool-units',[py,'-m','unittest','discover','-s','tools','-p','test_*.py']),
        ('core-units',[py,'-m','unittest','discover','-s','dv/core','-p','test_*.py']),
        ('formal-harness-units',[py,'-m','unittest','discover','-s','hw/lib/formal','-p','test_*.py']),
        ('fpu-receipt-units',[py,'-m','unittest','discover','-s','hw/ip/fpu/formal','-p','test_*.py']),
        ('regmap-units',[py,'-m','unittest','hw/regmap/test_regmap.py']),
        ('block-smoke',[py,'tools/sbt.py','hw/testOnly deadhorse.perf_core.ClockedExecuteSpec deadhorse.perf_core.FloatCoreSpec deadhorse.perf_core.FaithfulFloatCoreSpec']),
        ('bus-block-tests',[py,'tools/sbt.py','hw/testOnly deadhorse.lib.CdcSpec deadhorse.bus.* deadhorse.bus_bridge.* deadhorse.mailbox.*']),
        ('bus-formal',[py,'tools/formal.py','--blocks','cdc,bus,bus_bridge,mailbox','--output',f'{root}/bus-formal']),
        ('bus-timing',[py,'hw/ip/bus/formal/timing.py','--output',f'{root}/bus-timing']),
        ('emit-leaves',emit('deadhorse.perf_core.EmitLeaves','leaves')),
        ('emit-core',emit('deadhorse.perf_core.EmitCore','core')),
        ('emit-baseline',emit('deadhorse.perf_core.EmitRegisteredCore','baseline-emit')),
        ('emit-floating',emit('deadhorse.perf_core.EmitFloatCore','float-emit')),
        ('package-baseline',package(False)),('package-floating',package(True)),
        ('integrated-timing',[py,'hw/ip/perf_core/check_top_timing.py','--emitted',f'{root}/float-emit/asic','--output',f'{root}/timing']),
        ('lockstep-smoke',[py,'dv/core/lockstep.py','--candidate',f'{root}/floating','--isa','rv32imfc','--suite','random','--output',f'{root}/lockstep']),
        ('register-formal',[py,'hw/lib/formal/regblock_proof.py']),
        ('emit-clock-gate',emit('deadhorse.lib.EmitClockGate','clock-gate')),
        ('clock-gate-formal',[py,'hw/lib/formal/clock_gate_proof.py','--emitted',f'{root}/clock-gate','--output',f'{root}/clock-gate-formal']),
        ('local-no-f-formal',[py,'hw/ip/perf_core/formal/check_no_f.py','--baseline',f'{root}/baseline','--candidate',f'{root}/floating','--output',f'{root}/no-f-formal']),
        ('emit-faithful-floating',emit('deadhorse.perf_core.EmitFaithfulFloatCore','faithful-float-emit')),
        ('package-faithful-floating',[py,'hw/ip/perf_core/formal/package_candidate.py','--float',
            '--top',f'{root}/faithful-float-emit/model','--leaves',f'{root}/leaves','--core',f'{root}/core',
            '--output',f'{root}/faithful-floating']),
        ('faithful-floating-timing',[py,'hw/ip/perf_core/check_top_timing.py','--emitted',f'{root}/faithful-float-emit/asic',
            '--operating-point','main-9mhz','--output',f'{root}/faithful-floating-timing']),
        ('faithful-floating-smoke',[py,'dv/core/lockstep.py','--candidate',f'{root}/faithful-floating',
            '--isa','rv32imfc','--suite','random','--output',f'{root}/faithful-floating-smoke']),
        ('faithful-local-no-f-formal',[py,'hw/ip/perf_core/formal/check_no_f.py','--baseline',f'{root}/baseline',
            '--candidate',f'{root}/faithful-floating','--output',f'{root}/faithful-no-f-formal'])]


def plan(tier,output,legacy,triage_result=None):
    commands=fast_commands(output/'fast')
    if tier=='full':
        # Full retains every pre-tier gate command. Relocate its explicit T10/T11
        # output paths to avoid overwriting historical comparison candidates.
        prefix=output.relative_to(ROOT).as_posix()
        for index,command in enumerate(legacy):
            relocated=[str(x).replace('build/t11/ci',prefix+'/legacy-t11').replace('build/t10/ci',prefix+'/legacy-t10') for x in command]
            commands.append((f'full-legacy-{index:02d}',relocated))
        commands.append(('full-f-isa',[sys.executable,'dv/core/riscv_formal.py','--target','candidate',
            '--candidate',f'{prefix}/fast/floating','--output',f'{prefix}/floating-isa',
            *(['--triage-policy',str(triage_result)] if triage_result else [])]))
        commands.append(('full-f-lockstep',[sys.executable,'dv/core/lockstep.py','--candidate',f'{prefix}/fast/floating',
            '--isa','rv32imfc','--suite','arch,random,flight-float','--output',f'{prefix}/floating-lockstep']))
        commands.append(('full-faithful-f-isa',[sys.executable,'dv/core/riscv_formal.py','--target','candidate',
            '--candidate',f'{prefix}/fast/faithful-floating','--output',f'{prefix}/faithful-floating-isa']))
        commands.append(('full-faithful-f-lockstep',[sys.executable,'dv/core/lockstep.py',
            '--candidate',f'{prefix}/fast/faithful-floating','--isa','rv32imfc',
            '--suite','arch,random,flight-float','--output',f'{prefix}/faithful-floating-lockstep']))
    return commands


def snapshot():
    names=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(set(names))
            if name and (ROOT/name).is_file()}


def main(argv,legacy):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tier',choices=('fast','full'),default='fast')
    ap.add_argument('--output')
    ap.add_argument('--list',action='store_true',help='Describe plan; does not execute or claim a pass')
    ap.add_argument('--triage-result',help='Known critical triage result; unresolved budget blocks full instead of retrying it')
    args=ap.parse_args(argv)
    default_output='build/ci-tiers/'+args.tier+'/'+str(time.time_ns())
    output=(ROOT/(args.output or default_output)).resolve()
    output.relative_to(ROOT/'build');commands=plan(args.tier,output,legacy,args.triage_result)
    if args.list:
        print(json.dumps(dict(tier=args.tier,commands=commands),indent=2));return 0
    if (output/'result.json').exists():raise ValueError('Use a fresh output directory; retain previous CI evidence')
    output.mkdir(parents=True,exist_ok=True);started=time.monotonic();sources=snapshot()
    receipt=dict(status='running',tier=args.tier,commands=[],source_sha256=sources,
        deferred=[],qualification_limits=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        full_tier='running' if args.tier=='full' else 'not run by this invocation',
        scope='fixed fast checks; complete ISA sweep excluded' if args.tier=='fast' else 'fast plus complete legacy checks and F-integrated ISA/lockstep')
    path=output/'result.json'
    def save():
        receipt['elapsed_seconds']=time.monotonic()-started
        path.write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    try:
        if args.tier=='full' and args.triage_result:
            triage_path=(ROOT/args.triage_result).resolve();triage_path.relative_to(ROOT)
            triage=json.loads(triage_path.read_text())
            receipt['triage_result']=dict(path=str(triage_path),sha256=hashlib.sha256(triage_path.read_bytes()).hexdigest())
            if triage.get('status')!='pass' or set(triage.get('checks',{}))!={'lw','c_add'} or any(v.get('status')!='accepted' for v in triage.get('checks',{}).values()):
                receipt.update(status='unresolved (triage budget stop)',full_tier='not completed; critical ISA unresolved; no unchanged retry')
                print('UNRESOLVED full tier: critical triage did not pass; no proof retry',flush=True);return 1
        for index,(name,command) in enumerate(commands):
            if snapshot()!=sources:raise RuntimeError('Source changed during CI; result not accepted')
            if name.startswith('full-legacy') and 'dv/fpu/check.py' in command and (ROOT/'build/t12').exists():
                # Existing FPU tools use fixed build/t12 paths internally. Retain
                # the prior generated evidence before their explicit full rerun.
                shutil.copytree(ROOT/'build/t12',output/'previous-t12')
            log=output/f'{index:02d}-{name}.log';step=time.monotonic()
            print('RUN '+name+': '+' '.join(command),flush=True)
            with log.open('w') as stream:
                result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            receipt['commands'].append(dict(name=name,command=command,returncode=result.returncode,
                seconds=time.monotonic()-step,log=str(log.relative_to(ROOT))))
            step_receipt=receipt['commands'][-1]
            bus_formal_success=name=='bus-formal' and result.returncode==0
            if bus_formal_success and '--output' not in command:
                raise ValueError('Missing bus-formal output receipt path')
            if '--output' in command:
                child=(ROOT/command[command.index('--output')+1]/'result.json').resolve()
                child.relative_to(ROOT)
                if bus_formal_success and not child.is_file():
                    raise ValueError('Missing bus-formal success receipt')
                if child.exists():
                    detail=json.loads(child.read_text())
                    step_receipt['child_status']=detail.get('status','')
                    step_receipt['child_receipt']=dict(path=str(child.relative_to(ROOT)),
                        sha256=hashlib.sha256(child.read_bytes()).hexdigest())
                    deferred=detail.get('deferred',[])
                    if not isinstance(deferred,list) or any(not isinstance(d,dict) or not d.get('id') for d in deferred):
                        raise ValueError('Invalid child deferral inventory: '+name)
                    if detail.get('status')=='pass_with_deferrals' and not deferred:
                        raise ValueError('Missing child deferral inventory: '+name)
                    if bus_formal_success and (detail.get('status')!='pass_with_deferrals' or
                            len(deferred)!=len(BUS_FORMAL_DEFERRALS) or
                            {d['id'] for d in deferred}!=BUS_FORMAL_DEFERRALS or
                            any(d.get('status')!='deferred_unproved' for d in deferred)):
                        raise ValueError('Invalid bus-formal success receipt: expected exactly four approved, unproved deferrals')
                    step_receipt['deferred']=deferred
                    receipt['deferred'].extend(dict(d,command=name,receipt=str(child.relative_to(ROOT))) for d in deferred)
                    limits=detail.get('qualification_limits',[])
                    if not isinstance(limits,list):raise ValueError('Invalid child qualification limits: '+name)
                    step_receipt['qualification_limits']=limits
                    receipt['qualification_limits'].extend(dict(command=name,receipt=str(child.relative_to(ROOT)),limit=limit) for limit in limits)
            save()
            if result.returncode:
                receipt['status']='failed (partial tier run)'
                if args.tier=='full':receipt['full_tier']='failed; later commands not run'
                if step_receipt.get('child_status','').startswith('unresolved'):
                    receipt['status']='unresolved (partial tier run)'
                    if args.tier=='full':receipt['full_tier']='unresolved; later commands not run'
                print(log.read_text()[-5000:],flush=True);return result.returncode
            print('PASS '+name+(' active checks; '+str(len(step_receipt.get('deferred',[])))+' deferred, unproved' if step_receipt.get('deferred') else ''),flush=True)
        if snapshot()!=sources:raise RuntimeError('Source changed during CI; result not accepted')
        receipt['status']='pass_with_deferrals' if receipt['deferred'] else 'pass'
        if args.tier=='full':receipt['full_tier']=receipt['status']
        suffix=(' active checks; '+str(len(receipt['deferred']))+' deferred, unproved (see receipt)' if receipt['deferred'] else '')
        print('PASS '+args.tier+' tier'+suffix,flush=True);return 0
    except BaseException as exc:
        receipt.update(status='unresolved',error=str(exc));raise
    finally:save()
