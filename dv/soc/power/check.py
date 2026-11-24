"""T33 simulation regression. Formal, physical qualification and CI are separate."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.ci_tiers import snapshot

WATCHDOG_CASES=(
    'performance watchdog preserves shared state and disables all PWM routes while main is stopped',
    'wrongly widening performance watchdog reset is rejected',
    'lite watchdog resets all ordinary services but retains causes and SRAM')


def completed_evidence(directory):
    """Reuse completed cases, never the interrupted aggregate or stale XML."""
    directory=(ROOT/directory).resolve();directory.relative_to(ROOT/'build')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=json.loads((directory/'result.json').read_text())
    if manifest['status']!='completed_cases_from_interrupted_run':raise ValueError('Wrong carryover status')
    previous=(ROOT/manifest['previous']).resolve();previous.relative_to(ROOT/'build')
    if digest(previous/'result.json')!=manifest['previous_receipt_sha256']:raise ValueError('Changed prior receipt')
    prior=json.loads((previous/'result.json').read_text())
    if prior['status']!='failed' or prior.get('decision')!='D86':raise ValueError('Wrong prior result')
    if set(snapshot())!=set(prior['source_sha256']):raise ValueError('Added or removed carryover source')
    deltas={}
    for field,base in (('source_sha256',ROOT),('prepared_sha256',ROOT),('artifact_sha256',previous)):
        for name,expected in prior[field].items():
            path=(base/name).resolve();path.relative_to(base)
            actual=digest(path)
            if actual!=expected:
                if field=='source_sha256' and path==Path(__file__).resolve():
                    deltas[name]=dict(before=expected,after=actual,reason='Reviewed test-selection and receipt repair only')
                else:raise ValueError('Changed carryover input '+name)
    allowed={f'deadhorse.top.{n}' for n in ('SocClockResetSpec','SocPowerThresholdSpec','SocResetPhaseSpec',
        'SocClientPhaseSpec','SocWatchdogPhaseSpec','SocWatchdogOfferedSpec','SocWatchdogCoreSpec','SocWatchdogSpec')}
    if set(manifest['suites'])!=allowed:raise ValueError('Incomplete or unexpected completed suite')
    log=(previous/'simulation.log').read_text()
    for name,row in manifest['suites'].items():
        path=(directory/row['xml']).resolve();path.relative_to(directory)
        if digest(path)!=row['sha256']:raise ValueError('Changed completed XML')
        xml=ET.parse(path).getroot();cases=[c.attrib['name'] for c in xml.findall('testcase')]
        if (xml.attrib['name']!=name or any(xml.attrib[k]!='0' for k in ('failures','errors','skipped'))
            or len(cases)!=int(xml.attrib['tests']) or any(list(c) for c in xml.findall('testcase'))
            or any('[info] - '+c not in log for c in cases)):
            raise ValueError('Incomplete or unsuccessful completed suite')
        expected=list(WATCHDOG_CASES) if name.endswith('.SocWatchdogSpec') else cases
        if row['cases']!=expected or not set(expected)<=set(cases):raise ValueError('Wrong credited cases')
        if row['observed_not_credited']!=[c for c in cases if c not in expected]:raise ValueError('Hidden extra cases')
    if manifest['credited_cases']!=sum(len(r['cases']) for r in manifest['suites'].values()):
        raise ValueError('Wrong credited case count')
    return dict(manifest=manifest,manifest_path=str(directory/'result.json'),
        manifest_sha256=digest(directory/'result.json'),driver_delta=deltas,
        prepared_sha256=prior['prepared_sha256'])


def main(output,focused=False,t33_closeout=False,completed=None):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    receipt=dict(status='running',source_sha256=snapshot(),commands=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='T33 simulation only; no proof, analog, physical or CI acceptance',
        focused=focused, t33_closeout=t33_closeout, assumptions=[
            'Analog macros replaced by their documented digital behavioral models',
            'Supply thresholds, reference period and release delay are assumed pending T34',
            'Board startup and nominal AON/source ratios follow each named test scenario'],
        qualification_limits=[
            'Local MMIO reset-phase tests are not a proof of every composed SoC reset phase',
            'External-clock containment fixtures supplement production clock-wrapper tests',
            'Unbounded count/shutdown and CDC/RDC/physical qualification are separate obligations'])
    def save():
        receipt['seconds']=time.monotonic()-started
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    def run(label,command):
        save();start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(name=label,command=command,returncode=result.returncode,
            seconds=time.monotonic()-start,log=label+'.log'))
        save()
        if result.returncode:raise RuntimeError(label+' failed')
        print('PASS',label,flush=True)
    try:
        reuse=completed_evidence(completed) if completed else None
        if reuse and not t33_closeout:raise ValueError('Carryover is only valid for D86 closeout')
        reused=set(reuse['manifest']['suites']) if reuse else set()
        if reuse:receipt['completed_evidence']=reuse
        if reuse:
            receipt['preparation']='Reused verified prepared inputs; no regeneration'
        else:
            run('prepare',[sys.executable,'dv/soc/prepare_production.py'])
            run('sleep-firmware',[sys.executable,'dv/soc/prepare_osc_sleep.py'])
        run('map',[sys.executable,'hw/top/reference/check_soc_map.py'])
        run('map-faults',[sys.executable,'hw/top/reference/test_soc_map.py'])
        run('socket-tests',[sys.executable,'-m','unittest',
            'hw.top.reference.measurements.test_t33_analog_socket','hw.top.reference.measurements.test_t33_crossings',
            'hw.top.reference.measurements.test_t33_binding',
            'hw.top.reference.measurements.test_plan04_screen','-v'])
        firmware_dirs=('build/t20/i0-firmware','build/t20/map','build/t30/firmware','build/t30/qspi',
                       'build/plan04/sleep-firmware','build/t33/threshold-firmware',
                       'build/t33/client-firmware','build/t33/watchdog-phase-firmware')
        receipt['prepared_sha256']={}
        for directory in firmware_dirs:
            for source in sorted((ROOT/directory).rglob('*')):
                if not source.is_file():continue
                relative=source.relative_to(ROOT)
                receipt['prepared_sha256'][relative.as_posix()]=hashlib.sha256(source.read_bytes()).hexdigest()
                archived=out/'prepared'/relative
                archived.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,archived)
        if reuse and receipt['prepared_sha256']!=reuse['prepared_sha256']:
            raise RuntimeError('Prepared input set differs from reused evidence')
        suites=('deadhorse.top.SocClockResetSpec deadhorse.top.SocPowerThresholdSpec deadhorse.top.SocResetPhaseSpec deadhorse.top.SocClientPhaseSpec deadhorse.top.SocWatchdogPhaseSpec deadhorse.top.SocWatchdogOfferedSpec '
                'deadhorse.top.SocWatchdogCoreSpec deadhorse.top.SocWatchdogSpec '
                'deadhorse.top.SocPwmCoreResetSpec deadhorse.top.SocI1ResetSpec '
                'deadhorse.top.SocI1CoreResetSpec' if focused or t33_closeout else 'deadhorse.top.*')
        if focused:suites+=' deadhorse.top.SocI1Spec'
        suites+=' deadhorse.osc_ctrl.* deadhorse.power_reset.*'
        if t33_closeout:
            # SocWatchdogSpec inherits broader SocIoSpec tests: select its
            # three task-related cases explicitly, never the complete suite.
            suites=' '.join(s for s in suites.split() if s not in reused and s!='deadhorse.top.SocWatchdogSpec')
            receipt.update(decision='D86',ci=dict(fast='not_run',full='not_run'),
                excluded_scope=['Unrelated IP unit suites and top-level peripheral functionality suites',
                    'SocI1Spec serial/decode/IRQ, generic traffic and SPI/I2C chip-ID tests'],
                deferred=[dict(id=name,status='deferred_unproved',decision='D86') for name in
                    ('T33-STARTUP-MINIMUM-COUNT','T33-SHUTDOWN-OWNERSHIP',
                     'T33-STALE-RESPONSE-COMPOSITION','T33-CDC-RDC-COMPOSITION')])
        receipt['simulation_suites']=suites.split()
        run('simulation',[sys.executable,'tools/sbt.py','hw/testOnly '+suites])
        log=re.sub(r'\x1b\[[0-9;]*m','',(out/'simulation.log').read_text())
        counts=re.findall(r'Total number of tests run:\s*(\d+)',log)
        suite_counts=re.findall(r'Suites:\s*completed\s*(\d+),\s*aborted\s*(\d+)',log)
        if len(counts)!=1 or int(counts[0])<=0 or len(suite_counts)!=1 or int(suite_counts[0][1]):
            raise RuntimeError('Missing, empty or aborted Scala test summary')
        if 'All tests passed.' not in log:raise RuntimeError('Missing successful test summary')
        for name in ('PowerResetSpec','OscCtrlSpec','SocClockResetSpec','SocPowerThresholdSpec','SocResetPhaseSpec','SocClientPhaseSpec','SocWatchdogPhaseSpec','SocWatchdogOfferedSpec'):
            if 'deadhorse.top.'+name not in reused and not re.search(r'(?m)^\[info\]\s*'+name+r':\s*$',log):
                raise RuntimeError('Required suite absent: '+name)
        receipt['simulation_summary']=dict(tests=int(counts[0]),suites=int(suite_counts[0][0]),aborted=0)
        if t33_closeout:
            if 'deadhorse.top.SocWatchdogSpec' not in reused:
                command='hw/testOnly deadhorse.top.SocWatchdogSpec -- '+' '.join('-t '+json.dumps(t) for t in WATCHDOG_CASES)
                run('watchdog-containment',[sys.executable,'tools/sbt.py',command])
                containment=(out/'watchdog-containment.log').read_text()
                if ('All tests passed.' not in containment or
                        re.findall(r'Total number of tests run:\s*(\d+)',containment)!=['3'] or
                        any('[info] - '+name not in containment for name in WATCHDOG_CASES)):
                    raise RuntimeError('Missing selected watchdog containment result')
                receipt['watchdog_containment_summary']=dict(tests=3,suites=1)
            selected=(
                'mailbox round trip, retained byte lanes, denied program writes and independent service reset',
                'real USB recovers after an outer timeout while its service reset blocks admission',
                'recovery I2C wire loads actual retained SRAM, rejects bad CRC and preserves lock across warm reset')
            receipt['selected_service_reset_tests']=selected
            command='hw/testOnly deadhorse.top.SocI1Spec -- '+' '.join('-t '+json.dumps(t) for t in selected)
            run('service-reset',[sys.executable,'tools/sbt.py',command])
            service=re.sub(r'\x1b\[[0-9;]*m','',(out/'service-reset.log').read_text())
            if ('All tests passed.' not in service or
                    re.findall(r'Total number of tests run:\s*(\d+)',service)!=[str(len(selected))] or
                    any('[info] - '+name not in service for name in selected)):
                raise RuntimeError('Missing selected service-reset result')
            receipt['service_reset_summary']=dict(tests=len(selected),suites=1)
        for name,expected in receipt['prepared_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
                raise RuntimeError('Prepared firmware changed during regression: '+name)
        if snapshot()!=receipt['source_sha256']:raise RuntimeError('Sources changed during regression')
        receipt['status']='pass_with_deferrals' if t33_closeout else 'pass'
    except Exception as error:
        receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
    save();print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status'] in ('pass','pass_with_deferrals') else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--focused',action='store_true',help='Partial diagnostic; complete SoC suite omitted explicitly')
    scope.add_argument('--t33-closeout',action='store_true',help='D86 task-specific acceptance; explicit proof deferrals, no CI or unrelated IP tests')
    parser.add_argument('--completed-evidence',help='Reviewed archived completed cases from an interrupted D86 run; never treats that aggregate as passing')
    args=parser.parse_args();sys.exit(main(args.output,args.focused,args.t33_closeout,args.completed_evidence))
