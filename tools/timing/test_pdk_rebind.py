import unittest
from tools.timing.pdk_rebind import equal_content


class RebindControls(unittest.TestCase):
    def test_only_external_comments_and_spacing(self):
        cell = 'cell (x) { pin (D) { direction : input; } area : 1; }'
        original = 'library (x) { time_unit : "1ns"; ' + cell + ' }'
        self.assertEqual(equal_content(original, '/* license */\n' + original), 1)
        for changed in (original.replace('1ns', '1ps'),
                        original.replace('area : 1', 'area : 2'),
                        original.replace('pin (D)', 'pin (Q)'),
                        original.replace(cell, '')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                equal_content(original, changed)


if __name__ == '__main__':
    unittest.main()
