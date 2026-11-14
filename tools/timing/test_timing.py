"""Boundary-contract tests on netlist data, never RTL source text."""
import copy
import unittest

from tools.timing.check import validate_boundary


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.design = {
            'ports': {'clk': {'direction': 'input', 'bits': [2]},
                      'data': {'direction': 'input', 'bits': [3]},
                      'out': {'direction': 'output', 'bits': [4]}},
            'cells': {'register': {'type': 'known_ff', 'connections': {'CLK': [2], 'D': [3], 'Q': [4]}}}}

    def test_direct_clock_is_supported(self):
        validate_boundary(self.design, 'clk', {'known_ff'})

    def test_missing_clock(self):
        with self.assertRaisesRegex(ValueError, 'Missing scalar clock'):
            validate_boundary(self.design, 'absent', {'known_ff'})

    def test_vector_clock(self):
        self.design['ports']['clk']['bits'].append(5)
        with self.assertRaisesRegex(ValueError, 'Missing scalar clock'):
            validate_boundary(self.design, 'clk', {'known_ff'})

    def test_unconstrained_second_clock_or_generated_clock(self):
        self.design['cells']['other'] = copy.deepcopy(self.design['cells']['register'])
        self.design['cells']['other']['connections']['CLK'] = [5]
        with self.assertRaisesRegex(ValueError, 'non-root CLK net'):
            validate_boundary(self.design, 'clk', {'known_ff'})

    def test_macro_cannot_pass_as_logic(self):
        self.design['cells']['register']['type'] = 'uncharacterized_sram'
        with self.assertRaisesRegex(ValueError, 'Unsupported macro/cell timing view'):
            validate_boundary(self.design, 'clk', {'known_ff'})

    def test_bidirectional_boundary_requires_constraints(self):
        self.design['ports']['data']['direction'] = 'inout'
        with self.assertRaisesRegex(ValueError, 'bidirectional'):
            validate_boundary(self.design, 'clk', {'known_ff'})


if __name__ == '__main__':
    unittest.main()
