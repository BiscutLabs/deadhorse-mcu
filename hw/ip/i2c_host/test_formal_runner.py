"""Exercise fresh solver-result handling through the production formal runner."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
FORMAL=Path(__file__).parent/'formal'
sys.path.insert(0,str(FORMAL))
try:
    spec=importlib.util.spec_from_file_location('i2c_formal_runner',FORMAL/'check.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
finally:
    sys.path.remove(str(FORMAL))


class FreshTimeoutTest(unittest.TestCase):
    def exercise(self, returncode):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
            output=Path(temporary)/'result'
            def process(argv, **kwargs):
                if argv[0]=='sby':
                    target=Path(argv[2]);target.mkdir()
                    (target/'status').write_text('TIMEOUT 120\n')
                    return SimpleNamespace(returncode=returncode)
                # Fake only the external emitter/solver; run the actual receipt
                # classification and policy integration. This fixture is hashed,
                # never synthesized and makes no claim about RTL correctness.
                emit=Path(kwargs['stdout'].name).parent/'emit'
                for variant in ('cover','corrupt','correct'):
                    target=emit/variant;target.mkdir(parents=True)
                    (target/'Model.sv').write_text('unit-test model identity\n')
                return SimpleNamespace(returncode=0)
            with patch.object(runner.subprocess,'run',side_effect=process), \
                 patch.object(runner,'load_policy',return_value={}), \
                 patch.object(runner,'CASES',{'write':runner.CASES['write']}):
                return runner.run(output,Path(temporary)/'registers.json')

    def test_real_timeout_remains_unproved_for_cover_fault_and_correct(self):
        result=self.exercise(8)
        self.assertEqual(result['status'],'pass_with_deferrals')
        self.assertEqual(len(result['deferred']),3)
        for job in result['cases']['write']['jobs']:
            self.assertEqual(job['status'],'deferred_unproved')
            self.assertEqual(job['returncode'],8)
            self.assertFalse(job['retained'])
            self.assertTrue(job['solver_rerun'])

    def test_timeout_text_with_wrong_exit_status_fails_closed(self):
        for code in (0,1,2,7,124,-9):
            with self.subTest(returncode=code):
                result=self.exercise(code)
                self.assertEqual(result['status'],'failed')
                self.assertEqual(result['deferred'],[])
                self.assertEqual(result['cases']['write']['jobs'][0]['returncode'],code)


if __name__=='__main__': unittest.main()
