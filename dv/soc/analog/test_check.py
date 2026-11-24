"""Receipt fault controls: never convert a real formal failure into deferral."""
import unittest
from dv.soc.analog.check import formal_disposition


class FormalReceiptTest(unittest.TestCase):
    def timeout(self):
        return dict(status='failed', emission={'returncode': 0}, error='por-initial: TIMEOUT',
                    jobs=[dict(name='por-initial', mode='prove', solver_status='TIMEOUT', returncode=8)])

    def test_actual_timeout_can_be_deferred(self):
        self.assertEqual(formal_disposition(self.timeout(), 1), 'deferred_timeout')

    def test_real_failure_is_not_deferred(self):
        for status in ('FAIL', 'ERROR', 'UNKNOWN', 'PASS'):
            row = self.timeout(); row['jobs'][0]['solver_status'] = status
            with self.assertRaises(ValueError): formal_disposition(row, 1)

    def test_wrong_order_or_hidden_failure_is_rejected(self):
        row = self.timeout(); row['jobs'].insert(0, dict(name='wrong', mode='prove',
                solver_status='FAIL', returncode=2))
        with self.assertRaises(ValueError): formal_disposition(row, 1)

    def test_changed_source_failure_is_not_deferred(self):
        row = self.timeout(); row['error'] = 'Reset sources changed during checks'
        with self.assertRaises(ValueError): formal_disposition(row, 1)

    def test_empty_or_incomplete_pass_is_rejected(self):
        row = self.timeout(); row['jobs'] = []
        with self.assertRaises(ValueError): formal_disposition(row, 0)
        row = self.timeout(); row['status'] = 'pass'
        row['jobs'][0].update(solver_status='PASS', returncode=0, status='proved')
        with self.assertRaises(ValueError): formal_disposition(row, 0)


if __name__ == '__main__': unittest.main()
