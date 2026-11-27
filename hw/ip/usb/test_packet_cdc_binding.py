"""Fault controls for exact packet-proof model reuse; no RTL text matching."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).parent / 'formal/packet_cdc_binding.py'
SPEC = importlib.util.spec_from_file_location('packet_cdc_binding_tested', SOURCE)
binding = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(binding)


class PacketModelIdentityTests(unittest.TestCase):
    def setUp(self):
        self.old = binding.ROOT / 'build/old'
        self.new = binding.ROOT / 'build/new'
        self.model = {'modules': {'subject': {'attributes': {'src': 'build/old/a.sv:2'},
            'cells': {'state': {'type': '$adff', 'parameters': {'ARST_VALUE': '0'},
                'connections': {'D': [2], 'Q': [3], 'ARST': [4]},
                'attributes': {'src': str(self.old) + '/a.sv:7'}},
                'integrity': {'type': '$assert', 'connections': {'A': [3], 'EN': [5]}}},
            'netnames': {'payload': {'bits': [3], 'attributes': {'init': '0'}}}}}}
        self.fresh = copy.deepcopy(self.model)
        binding.relocate(self.fresh, self.old, self.new)
        binding.relocate(self.fresh, 'build/old', 'build/new')

    def test_only_exact_source_prefix_relocation_is_allowed(self):
        binding.same_model(self.fresh, self.model, self.new, self.old)

    def test_changed_reset_value_rejected(self):
        self.fresh['modules']['subject']['cells']['state']['parameters']['ARST_VALUE'] = '1'
        with self.assertRaisesRegex(ValueError, 'transition system'):
            binding.same_model(self.fresh, self.model, self.new, self.old)

    def test_changed_assertion_rejected(self):
        self.fresh['modules']['subject']['cells']['integrity']['connections']['A'] = ['1']
        with self.assertRaisesRegex(ValueError, 'transition system'):
            binding.same_model(self.fresh, self.model, self.new, self.old)

    def test_changed_initial_state_rejected(self):
        self.fresh['modules']['subject']['netnames']['payload']['attributes']['init'] = '1'
        with self.assertRaisesRegex(ValueError, 'transition system'):
            binding.same_model(self.fresh, self.model, self.new, self.old)

    def test_changed_source_line_not_erased(self):
        self.fresh['modules']['subject']['attributes']['src'] = 'build/new/a.sv:3'
        with self.assertRaisesRegex(ValueError, 'transition system'):
            binding.same_model(self.fresh, self.model, self.new, self.old)


if __name__ == '__main__':
    unittest.main()
