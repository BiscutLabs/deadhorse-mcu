"""Aggregate receipt policy; independent synthetic child outcomes."""
import unittest
import copy
from unittest.mock import patch
import subprocess
import tempfile
from pathlib import Path
from check import ROOT, accept_child, execute_command, validate_allocation


class ReceiptTests(unittest.TestCase):
    def test_success_requires_exit_and_receipt(self):
        self.assertEqual(accept_child(0, {'status':'pass'}), 'pass')
        for code, status in ((1,'pass'), (0,'failed'), (0,'unresolved'), (0,None), (0,'running')):
            with self.subTest(code=code, status=status), self.assertRaises(RuntimeError):
                accept_child(code, {'status':status})

    def test_capacity_review_is_not_pass(self):
        for code in (0,1):
            self.assertEqual(accept_child(code, {'status':'review_required'}), 'review_required')
        for code in (-9, 2, 127):
            with self.assertRaises(RuntimeError):
                accept_child(code, {'status':'review_required'})

    def test_logging_capacity_and_threshold_receipts_must_agree(self):
        memory={'flash':{'profiles':[{'flight':{'queue_bytes':2048,'staging_bytes':256}}]}}
        firmware={'status':'pass','review_required_profiles':[], 'profiles':{}}
        for name in ('size','speed','lite-size','lite-speed'):
            firmware['profiles'][name]={'measurement':dict(baseline_capacity_bytes=3072 if name.startswith('lite') else 16384,
                symbols=[dict(name='log_buffers',bytes=2048,kind='B'),dict(name='log_staging',bytes=256,kind='B')],
                hot_code_bytes=1000,hot_constants_conservative_bytes=100,
                candidate_state_and_buffers_bytes=500 if name.startswith('lite') else 2500,stack_reserved_single_trap_bytes=400,
                candidate_sram_working_set_bytes=2000 if name.startswith('lite') else 4000)}
        self.assertEqual(validate_allocation(memory,firmware)['logging_queue_bytes'],2048)
        missing=copy.deepcopy(firmware)
        missing['profiles']['speed']['measurement']['symbols'][0]['bytes']=512
        with self.assertRaisesRegex(ValueError,'logging-buffer'):
            validate_allocation(memory,missing)
        readonly=copy.deepcopy(firmware)
        readonly['profiles']['speed']['measurement']['symbols'][0]['kind']='R'
        with self.assertRaisesRegex(ValueError,'logging-buffer'):
            validate_allocation(memory,readonly)
        oversized=copy.deepcopy(firmware)
        measured=oversized['profiles']['speed']['measurement']
        measured.update(hot_code_bytes=10000,candidate_sram_working_set_bytes=13000)
        with self.assertRaisesRegex(ValueError,'review inventory'):
            validate_allocation(memory,oversized)
        oversized['review_required_profiles']=['speed']
        with self.assertRaisesRegex(ValueError,'cannot report pass'):
            validate_allocation(memory,oversized)
        oversized['status']='review_required'
        self.assertEqual(validate_allocation(memory,oversized)['review_required_profiles'],['speed'])

    def test_timeout_preserves_attempt_and_log(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            rows=[]
            with patch('check.subprocess.run', side_effect=subprocess.TimeoutExpired(['child'],600)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    execute_command('child',['child'],Path(folder),rows)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['status'],'timeout')
            self.assertEqual(rows[0]['timeout_seconds'],600)
            self.assertEqual(rows[0]['command'],['child'])
            self.assertTrue((ROOT/rows[0]['log']).is_file())
            self.assertGreaterEqual(rows[0]['seconds'],0)


if __name__=='__main__':
    unittest.main()
