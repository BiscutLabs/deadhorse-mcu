import unittest
from check_i1_control import checked_faults


class FaultIdentityTests(unittest.TestCase):
    def test_hierarchy_is_preserved(self):
        log = ('Assert failed in SocI1Formal: assert__chisel3_builtin\n'
               'Assert failed in SocI1Formal: credit.assert__chisel3_builtin_0\n')
        names = {'assert__chisel3_builtin', 'credit.assert__chisel3_builtin_0'}
        self.assertEqual(checked_faults(log, names, names), sorted(names))

    def test_wrong_or_missing_property_fails_closed(self):
        for log in ('', 'Assert failed in SocI1Formal: assert__chisel3_builtin_0\n',
                    'Assert failed in SocI1Formal: other.assert__chisel3_builtin_0\n'):
            with self.assertRaises(RuntimeError):
                checked_faults(log, {'credit.assert__chisel3_builtin_0'}, {'credit.assert__chisel3_builtin_0'})


if __name__ == '__main__':
    unittest.main()
