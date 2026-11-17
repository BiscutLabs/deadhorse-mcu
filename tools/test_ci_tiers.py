import unittest
from unittest.mock import patch
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import ci_tiers
from ci_tiers import ROOT, plan


class TierTest(unittest.TestCase):
    def test_bus_checks_are_required_by_both_tiers_without_replacing_existing_jobs(self):
        output=ROOT/'build/tier-test'
        fast=plan('fast',output,[])
        full=plan('full',output,[['python3','retained-legacy.py']])
        self.assertEqual(full[:len(fast)],fast)
        names=[name for name,_ in fast]
        self.assertEqual(len(names),len(set(names)))
        jobs=dict(fast)
        self.assertEqual(jobs['bus-block-tests'][2:],[
            'hw/testOnly deadhorse.lib.CdcSpec deadhorse.bus.* deadhorse.bus_bridge.* deadhorse.mailbox.*'])
        self.assertEqual(jobs['bus-formal'][1:],[
            'tools/formal.py','--blocks','cdc,bus,bus_bridge,mailbox',
            '--output','build/tier-test/fast/bus-formal'])
        self.assertEqual(jobs['bus-timing'][1:],[
            'hw/ip/bus/formal/timing.py','--output','build/tier-test/fast/bus-timing'])
        self.assertIn('register-formal',jobs)
        self.assertIn('clock-gate-formal',jobs)
        self.assertIn('local-no-f-formal',jobs)
        self.assertIn('faithful-local-no-f-formal',jobs)
        self.assertEqual(jobs['uart'][1:],['hw/ip/uart/check.py','--output','build/tier-test/fast/uart'])
        self.assertIn(('full-legacy-00',['python3','retained-legacy.py']),full)

    def test_faithful_float_checks_are_separate_and_preserve_registered_checks(self):
        jobs=dict(plan('full',ROOT/'build/tier-test',[]))
        self.assertNotIn('--registered',jobs['package-faithful-floating'])
        self.assertIn('--float',jobs['package-faithful-floating'])
        self.assertIn('main-9mhz',jobs['faithful-floating-timing'])
        self.assertNotIn('--operating-point',jobs['integrated-timing'])
        self.assertIn('--registered',jobs['package-floating'])
        self.assertNotIn('--checks',jobs['full-faithful-f-isa'])
        self.assertNotIn('--triage-policy',jobs['full-faithful-f-isa'])

    def test_fast_is_fixed_and_excludes_sweep(self):
        jobs=plan('fast',ROOT/'build/tier-test',[])
        names={name for name,_ in jobs}
        self.assertTrue({'structure','core-units','block-smoke','integrated-timing','lockstep-smoke',
                         'register-formal','clock-gate-formal','local-no-f-formal'}<=names)
        self.assertFalse(any('dv/core/riscv_formal.py' in argv for _,argv in jobs))

    def test_local_no_f_pairs_registered_production_profiles(self):
        jobs=dict(plan('fast',ROOT/'build/tier-test',[]))
        self.assertIn('deadhorse.perf_core.EmitRegisteredCore',jobs['emit-baseline'][-1])
        self.assertIn('--registered',jobs['package-baseline'])
        self.assertNotIn('--float',jobs['package-baseline'])
        self.assertIn('--registered',jobs['package-floating'])
        self.assertIn('--float',jobs['package-floating'])

    def test_full_retains_every_legacy_check_and_full_f_isa(self):
        old=[['python3','one.py','build/t11/ci/a'],['python3','two.py']]
        jobs=plan('full',ROOT/'build/tier-test',old)
        legacy=[argv for name,argv in jobs if name.startswith('full-legacy')]
        self.assertEqual(legacy,[['python3','one.py','build/tier-test/legacy-t11/a'],old[1]])
        full=dict(jobs)['full-f-isa']
        self.assertIn('dv/core/riscv_formal.py',full)
        self.assertNotIn('--checks',full)

    def test_full_uses_successful_triage_policy_without_omitting_checks(self):
        full=dict(plan('full',ROOT/'build/tier-test',[],'build/triage/result.json'))['full-f-isa']
        self.assertIn('--triage-policy',full)
        self.assertNotIn('--checks',full)

    def run_receipt_case(self,child,fail_after=False,tier='fast',job_name='formal'):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ci-receipt-test-',dir=ROOT/'build') as temporary:
            output=Path(temporary)/'run'
            child_output=output/'formal'
            jobs=[(job_name,['python3','formal.py','--output',str(child_output)])]
            if fail_after:jobs.append(('later',['python3','later.py']))
            def run(command,**kwargs):
                if '--output' in command:
                    child_output.mkdir(parents=True)
                    if child is not None:(child_output/'result.json').write_text(json.dumps(child))
                    return SimpleNamespace(returncode=0)
                return SimpleNamespace(returncode=1)
            capture=io.StringIO()
            with patch.object(ci_tiers,'plan',return_value=jobs),patch.object(ci_tiers,'snapshot',return_value={}), \
                 patch.object(ci_tiers.subprocess,'check_output',return_value='test-commit'), \
                 patch.object(ci_tiers.subprocess,'run',side_effect=run),contextlib.redirect_stdout(capture):
                code=ci_tiers.main(['--tier',tier,'--output',str(output)],[])
            return code,json.loads((output/'result.json').read_text()),capture.getvalue()

    def test_nested_deferrals_remain_visible_in_successful_fast_and_full_receipts(self):
        ids=['T14-BUS-FAIR-M0','T14-BUS-FAIR-M1','T14-BUS-FAIR-M2','T14-BRIDGE-RETURN-DATA']
        deferred=[dict(id=i,status='deferred_unproved',authorization='User decision 2026-11-17') for i in ids]
        limits=['Bridge watchdog 32 proof does not qualify production 131072']
        for tier in ('fast','full'):
            with self.subTest(tier=tier):
                code,receipt,output=self.run_receipt_case(dict(status='pass_with_deferrals',deferred=deferred,qualification_limits=limits),tier=tier,job_name='bus-formal')
                self.assertEqual(code,0)
                self.assertEqual(receipt['status'],'pass_with_deferrals')
                self.assertEqual([d['id'] for d in receipt['deferred']],ids)
                self.assertTrue(all(d['status']=='deferred_unproved' for d in receipt['deferred']))
                self.assertEqual(receipt['commands'][0]['deferred'],deferred)
                self.assertEqual(receipt['commands'][0]['qualification_limits'],limits)
                self.assertEqual(receipt['qualification_limits'][0]['limit'],limits[0])
                self.assertEqual(len(receipt['commands'][0]['child_receipt']['sha256']),64)
                self.assertIn('4 deferred, unproved',output)
                if tier=='full':self.assertEqual(receipt['full_tier'],'pass_with_deferrals')

    def test_later_failure_is_not_masked_by_earlier_authorized_deferrals(self):
        code,receipt,_=self.run_receipt_case(dict(status='pass_with_deferrals',deferred=[dict(id='deferred',status='deferred_unproved')]),fail_after=True)
        self.assertEqual(code,1)
        self.assertEqual(receipt['status'],'failed (partial tier run)')
        self.assertEqual(receipt['deferred'][0]['id'],'deferred')
        self.assertEqual(len(receipt['commands']),2)

    def test_child_without_deferrals_retains_plain_pass(self):
        code,receipt,_=self.run_receipt_case(dict(status='pass'))
        self.assertEqual(code,0)
        self.assertEqual(receipt['status'],'pass')
        self.assertEqual(receipt['deferred'],[])

    def test_missing_deferral_inventory_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing child deferral inventory'):
            self.run_receipt_case(dict(status='pass_with_deferrals'))

    def test_bus_formal_zero_exit_requires_success_receipt(self):
        with self.assertRaisesRegex(ValueError,'Missing bus-formal success receipt'):
            self.run_receipt_case(None,job_name='bus-formal')

    def test_uart_success_requires_explicit_valid_receipt(self):
        with self.assertRaisesRegex(ValueError,'Missing uart success receipt'):
            self.run_receipt_case(None,job_name='uart')
        for detail in (dict(status='pass'),dict(task='T15',status='failed'),
                       dict(task='T15',status='pass_with_deferrals',deferred=[dict(id='unknown',status='deferred_unproved')])):
            with self.subTest(detail=detail),self.assertRaisesRegex(ValueError,'Invalid UART success receipt'):
                self.run_receipt_case(detail,job_name='uart')
        item=dict(id='T15-FRAME-CORRECT',status='deferred_unproved')
        code,receipt,_=self.run_receipt_case(dict(task='T15',status='pass_with_deferrals',deferred=[item]),job_name='uart')
        self.assertEqual(code,0)
        self.assertEqual(receipt['deferred'][0]['id'],item['id'])

    def test_bus_formal_zero_exit_rejects_inconsistent_status_or_deferrals(self):
        ids=['T14-BUS-FAIR-M0','T14-BUS-FAIR-M1','T14-BUS-FAIR-M2','T14-BRIDGE-RETURN-DATA']
        deferred=[dict(id=i,status='deferred_unproved') for i in ids]
        cases=[dict(status=status,deferred=deferred) for status in ('failed','unresolved','unknown','pass')]
        cases.extend([
            dict(status='pass',deferred=[]),
            dict(status='pass_with_deferrals',deferred=deferred[:-1]),
            dict(status='pass_with_deferrals',deferred=deferred+[dict(id='unknown',status='deferred_unproved')]),
            dict(status='pass_with_deferrals',deferred=deferred[:-1]+[deferred[0]]),
            dict(status='pass_with_deferrals',deferred=[dict(d,status='proved') for d in deferred]),
        ])
        for child in cases:
            with self.subTest(child=child),self.assertRaisesRegex(ValueError,'Invalid bus-formal success receipt'):
                self.run_receipt_case(child,job_name='bus-formal')


if __name__=='__main__':unittest.main()
