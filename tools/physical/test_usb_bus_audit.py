import copy
import unittest
from tools.physical.usb_bus_audit import audit_rows, MODES


class BusAuditTest(unittest.TestCase):
    def setUp(self):
        self.launches = {'request': ['source/Q'], 'response': ['usb/Q']}
        self.targets = {'request': ['usb/D', 'unused/D'], 'response': ['source/D']}
        self.clocks = {n: 'appClock' for pins in self.targets.values() for n in pins}
        self.queries = [dict(direction=d, mode=m, query=pin, count='1')
                        for d, pins in self.launches.items() for pin in pins for m in MODES]
        self.paths = [dict(q, start=q['query'], end=self.targets[q['direction']][0],
                           slack_ns='1', delay_ns='2') for q in self.queries]

    def audit(self):
        return audit_rows(self.queries, self.paths, self.launches, self.targets, self.clocks)

    def test_absent_capture_is_accounted(self):
        result = self.audit()
        self.assertEqual(result[0]['no_path_bitmap_hex'], '0x2')
        self.assertEqual(result[-1]['no_path_bitmap_hex'], '0x0')

    def test_duplicate_query_cannot_replace_missing_query(self):
        self.queries[0] = copy.deepcopy(self.queries[1])
        with self.assertRaisesRegex(ValueError, 'query'):
            self.audit()

    def test_wrong_launch(self):
        self.paths[0]['start'] = 'wrong/Q'
        with self.assertRaisesRegex(ValueError, 'launch'):
            self.audit()

    def test_wrong_destination(self):
        self.paths[0]['end'] = 'source/D'
        with self.assertRaisesRegex(ValueError, 'capture'):
            self.audit()

    def test_wrong_clock(self):
        self.clocks['usb/D'] = 'usbClock'
        with self.assertRaisesRegex(ValueError, 'domain'):
            self.audit()

    def test_duplicate_endpoint(self):
        self.paths.append(copy.deepcopy(self.paths[0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate capture'):
            self.audit()

    def test_nonfinite(self):
        self.paths[0]['slack_ns'] = 'nan'
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            self.audit()

    def test_budget_and_hold_fail(self):
        self.paths[0]['delay_ns'] = '25.0'
        with self.assertRaisesRegex(ValueError, 'class delay'):
            self.audit()
        self.paths[0]['delay_ns'] = '2.0'
        self.paths[2]['slack_ns'] = '-0.001'
        with self.assertRaisesRegex(ValueError, 'setup/hold'):
            self.audit()

    def test_missing_path_count(self):
        self.paths.pop()
        with self.assertRaisesRegex(ValueError, 'count'):
            self.audit()
