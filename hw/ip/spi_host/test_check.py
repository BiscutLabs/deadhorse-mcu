import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('spi_host_check',Path(__file__).with_name('check.py'))
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)


class ReceiptTests(unittest.TestCase):
    def test_failure_or_timeout_cannot_report_plain_pass(self):
        for code,status in ((1,'pass'),(0,'failed'),(0,'unresolved')):
            with self.subTest(code=code,status=status), self.assertRaises(RuntimeError):
                check.accept_child(code,dict(status=status))

    def test_deferral_is_explicit_and_not_a_proof(self):
        item=dict(id='T16-FRAME0-CORRECT',status='deferred_unproved')
        self.assertEqual(check.accept_child(0,dict(status='pass_with_deferrals',deferred=[item])),[item])
        for detail in (dict(status='pass_with_deferrals'),dict(status='pass',deferred=[item]),
                       dict(status='pass_with_deferrals',deferred=[dict(id='a',status='proved')])):
            with self.subTest(detail=detail),self.assertRaises(ValueError):check.accept_child(0,detail)


if __name__=='__main__':unittest.main()
