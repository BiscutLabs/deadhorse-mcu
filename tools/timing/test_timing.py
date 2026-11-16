"""Boundary-contract tests on netlist data, never RTL source text."""
import copy
import unittest

from tools.timing.check import validate_boundary, electrical_checks, result_status, output_aliases


class ElectricalTests(unittest.TestCase):
    def test_port_aliases_add_load_but_constants_and_inputs_do_not(self):
        module = {'ports': {
            'a': {'direction':'input','bits':[2]},
            'first': {'direction':'output','bits':[2,3,'0','0']},
            'second': {'direction':'output','bits':[3,4,'1','0']},
            'third': {'direction':'output','bits':[3]}}}
        self.assertEqual(output_aliases(module),(3,[['first[1]','second[0]','third[0]']]))

    def test_incomplete_or_duplicate_report_is_rejected(self):
        for log in ('', 'ELECTRICAL_BEGIN\n', 'ELECTRICAL_END',
                    'ELECTRICAL_BEGIN\nELECTRICAL_END\nELECTRICAL_BEGIN\nELECTRICAL_END'):
            with self.assertRaisesRegex(ValueError, 'electrical report'):
                electrical_checks(log)

    def test_electrical_failure_cannot_pass_with_positive_timing_margin(self):
        clean = electrical_checks('unrelated (VIOLATED)\nELECTRICAL_BEGIN\nELECTRICAL_END\n')
        failed = electrical_checks('ELECTRICAL_BEGIN\nnet 1.0 2.0 -1.0 (VIOLATED)\nELECTRICAL_END\n')
        self.assertEqual(result_status(10, 24.96, clean), 'pass')
        self.assertEqual(result_status(10, 24.96, failed), 'fail')
        self.assertEqual(result_status(30, 24.96, clean), 'fail')
        self.assertEqual(result_status(30, 24.96, failed), 'fail')


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.design = {
            'ports': {'clk': {'direction': 'input', 'bits': [2]},
                      'data': {'direction': 'input', 'bits': [3]},
                      'out': {'direction': 'output', 'bits': [4]}},
            'cells': {'register': {'type': 'known_ff', 'connections': {'CLK': [2], 'D': [3], 'Q': [4]}}}}

    def test_direct_clock_is_supported(self):
        validate_boundary(self.design, 'clk', {'known_ff'})

    def test_combinational_mode_rejects_registers(self):
        with self.assertRaisesRegex(ValueError, 'Sequential cell'):
            validate_boundary(self.design, None, {'known_ff'}, combinational=True)

    def test_combinational_mode_accepts_stateless_logic(self):
        self.design['cells'] = {'invert': {'type': 'known_inv', 'connections': {'I': [3], 'ZN': [4]}}}
        validate_boundary(self.design, None, {'known_inv'}, combinational=True)

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

    def test_only_characterized_root_driven_gate_is_supported(self):
        gate='gf180mcu_fd_sc_mcu7t5v0__icgtp_1'
        library={'known_ff',gate}
        self.design['cells']['gate']={'type':gate,'connections':{'CLK':[2],'E':[3],'TE':[6],'Q':[7]}}
        self.design['cells']['register']['connections']['CLK']=[7]
        validate_boundary(self.design,'clk',library)
        for bad_clock in ([7],[8],[2,8]):
            self.design['cells']['gate']['connections']['CLK']=bad_clock
            with self.assertRaisesRegex(ValueError,'clock-gate binding'):
                validate_boundary(self.design,'clk',library)
        self.design['cells']['gate']['connections']['CLK']=[2]
        self.design['cells']['gate']['connections']['Q']=[7,8]
        with self.assertRaisesRegex(ValueError,'clock-gate binding'):
            validate_boundary(self.design,'clk',library)

    def test_bidirectional_boundary_requires_constraints(self):
        self.design['ports']['data']['direction'] = 'inout'
        with self.assertRaisesRegex(ValueError, 'bidirectional'):
            validate_boundary(self.design, 'clk', {'known_ff'})


if __name__ == '__main__':
    unittest.main()
