import unittest
from pathlib import Path
from ci_tiers import ROOT, plan


class TierTest(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
