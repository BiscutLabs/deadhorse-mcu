import unittest
from qualify_owner_valid import valid_witness, inject


class OwnerValidQualificationTest(unittest.TestCase):
    def trace(self, capture, valid):
        return ("$scope module rvfi_testbench $end\n"
                "$var wire 1 a __ownership_capture $end\n"
                "$var wire 1 b __ownership_ownerValid $end\n"
                "$upscope $end\n#10\n" + capture + "a\n" + valid + "b\n#20\n")

    def test_active_cover_and_fault(self):
        self.assertEqual(valid_witness(self.trace('1', '1'))['values'], {'capture': 1, 'ownerValid': 1})
        self.assertEqual(valid_witness(self.trace('1', '0'), True)['values']['ownerValid'], 0)

    def test_inactive_unknown_and_wrong_polarity_rejected(self):
        for capture, valid, fault in [('0', '1', False), ('1', 'x', False), ('1', '0', False), ('1', '1', True)]:
            with self.assertRaises(ValueError): valid_witness(self.trace(capture, valid), fault)

    def test_fault_changes_unique_driver_only(self):
        module = {'cells': {'state': {'type': '$dff', 'connections': {'Q': [2], 'D': [3], 'CLK': [4]},
                                     'port_directions': {'Q': 'output', 'D': 'input', 'CLK': 'input'}}},
                  'ports': {}, 'netnames': {}}
        self.assertEqual(inject(module, 2, [5]), ['state', 'Q', 0])
        fault = module['cells']['__qualified_fault']['connections']
        self.assertEqual(fault['Y'], [2]); self.assertEqual(fault['B'], [5])
        self.assertEqual(fault['A'], module['cells']['state']['connections']['Q'])
        self.assertEqual(module['cells']['state']['connections']['D'], [3])

    def test_missing_driver_rejected(self):
        with self.assertRaises(ValueError): inject({'cells': {}}, 2, [3])


if __name__ == '__main__': unittest.main()
