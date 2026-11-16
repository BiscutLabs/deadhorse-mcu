"""Focused formal selection fails closed and preserves the default inventory."""
import unittest
from riscv_formal import selected_checks

class SelectionTest(unittest.TestCase):
    def test_default_is_complete(self):
        self.assertEqual(selected_checks(['addi','c_add','jalr'],None),['addi','c_add','jalr'])
    def test_selection_is_explicit(self):
        self.assertEqual(selected_checks(['addi','c_add','jalr'],'jalr,addi'),['jalr','addi'])
    def test_bad_selection_rejected(self):
        for selection in ('','addi,addi','missing','addi,'):
            with self.subTest(selection=selection),self.assertRaises(ValueError):
                selected_checks(['addi','c_add'],selection)
