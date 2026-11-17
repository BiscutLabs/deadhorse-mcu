"""Behavioral and runner fail-closed checks for the S3 experiment."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dv.memory.sram import BankedWords, Request
from dv.memory.flash import FlashBus, PROFILES, Profile
from dv.memory.check_sram import run_sram
from dv.memory.check_flash import boundaries_and_boot, interference, logging
from tools.spikes.s3_memory import memory_models


class MemoryTests(unittest.TestCase):
    def test_sram_configurations_and_faults(self):
        result = run_sram()
        self.assertEqual(len(result['configurations']),18)
        self.assertEqual(len(result['negative_controls']),4)

    def test_invalid_sram_configuration_and_payload(self):
        for args in ((0,1,1),(16,0,1),(16,3,1),(16,1,0)):
            with self.assertRaises(ValueError): BankedWords(*args)
        model = BankedWords(16,1,2)
        for req in (Request(0,mask=16),Request(0,data=-1),Request(0,data=2**32)):
            with self.assertRaises(ValueError):model.issue(req)

    def test_flash_boundary_and_boot_scenarios(self):
        for profile in PROFILES:
            boundaries_and_boot(profile)

    def test_flash_arbitration_all_arrival_edges(self):
        for profile in PROFILES:
            result = interference(profile)
            self.assertEqual(result['measured_model_max_response_cycles'],result['estimated_bound_cycles'])

    def test_flash_erase_queue_overflow_is_nonblocking(self):
        for profile in PROFILES:
            self.assertGreater(logging(profile,1,True)['measured_model_dropped_records'],0)

    def test_flash_actual_model_faults_are_rejected(self):
        for fault,check,reason in (
            ('omit_dummy',interference,'interference mismatch'),
            ('held_bus',interference,'blocked by write busy'),
            ('unbounded_burst',boundaries_and_boot,'unbounded burst')):
            with self.subTest(fault=fault), self.assertRaisesRegex(AssertionError,reason):
                check(PROFILES[0],fault)

    def test_flash_invalid_requests(self):
        with self.assertRaises(ValueError):Profile('bad',0)
        model = FlashBus(PROFILES[0])
        for address,size in ((-1,4),(0,0),(0,257),(2**32-2,4)):
            with self.assertRaises(ValueError):model.read(address,size)
        model.read(0,4)
        with self.assertRaises(ValueError):model.read(4,4)
        with self.assertRaises(ValueError):model.advance(-1)

    def test_runner_failure_cannot_pass_or_overwrite(self):
        (memory_models.ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=memory_models.ROOT/'build',prefix='s3-unit-') as tmp:
            with patch.object(memory_models,'run_sram',side_effect=AssertionError('injected mismatch')):
                result = memory_models.run(Path(tmp))
            self.assertEqual(result['status'],'failed')
            self.assertEqual(result['error'],'injected mismatch')
            with self.assertRaisesRegex(ValueError,'fresh'):
                memory_models.run(Path(tmp))


if __name__=='__main__':unittest.main()
