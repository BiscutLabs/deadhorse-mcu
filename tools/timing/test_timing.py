"""Boundary-contract tests on netlist data, never RTL source text."""
import copy
import json
import unittest

from tools.timing.check import CONFIG, timing_config, mapping_target_ps, validate_boundary, electrical_checks, result_status, output_aliases


class OperatingPointTests(unittest.TestCase):
    def test_usb_sample_clock_keeps_stricter_budget_and_electrical_checks(self):
        original = timing_config()
        usb = timing_config('usb-48mhz')
        self.assertAlmostEqual(usb['period_ns'], 1000 / 48)
        budget = usb['period_ns'] * usb['budget_fraction']
        self.assertAlmostEqual(budget, 12.5)
        self.assertAlmostEqual(mapping_target_ps(usb, 'usb-48mhz'), 12500)
        for key in original.keys() - {'period_ns', 'provenance'}:
            self.assertEqual(usb[key], original[key])
        self.assertEqual(result_status(12.49, budget, {'max_capacitance_and_slew_violations': 0}), 'pass')
        self.assertEqual(result_status(12.51, budget, {'max_capacitance_and_slew_violations': 0}), 'fail')
        self.assertEqual(result_status(12.49, budget, {'max_capacitance_and_slew_violations': 1}), 'fail')

    def test_mapping_target_is_separate_from_unchanged_sta_acceptance(self):
        for point, expected in (('default', 24960), ('main-12mhz', 50000),
                                ('main-9p6mhz', 62500), ('main-9mhz', 62500)):
            with self.subTest(point=point):
                cfg = timing_config(point)
                target = mapping_target_ps(cfg, point)
                allowance = cfg['period_ns'] * cfg['budget_fraction']
                self.assertAlmostEqual(target, expected)
                self.assertLessEqual(target, allowance * 1000)
                if point == 'main-9mhz':
                    self.assertAlmostEqual(allowance, 200 / 3)
                    self.assertEqual(result_status(67, allowance,
                        {'max_capacitance_and_slew_violations': 0}), 'fail')

    def test_trial_changes_only_period_and_provenance_without_mutating_default(self):
        original = json.loads(CONFIG.read_text())
        self.assertEqual(timing_config(), original)
        for point, period, budget in (('main-12mhz', 1000 / 12, 50),
                                      ('main-9p6mhz', 1000 / 9.6, 62.5),
                                      ('main-9mhz', 1000 / 9, 200 / 3)):
            with self.subTest(point=point):
                trial = timing_config(point)
                self.assertAlmostEqual(trial['period_ns'], period)
                self.assertAlmostEqual(trial['period_ns'] * trial['budget_fraction'], budget)
                for key in original.keys() - {'period_ns', 'provenance'}:
                    self.assertEqual(trial[key], original[key])
        self.assertEqual(timing_config(), original)

    def test_unknown_operating_point_is_rejected(self):
        for name in ('waiver', '6mhz', '', None):
            with self.assertRaisesRegex(ValueError, 'operating point'):
                timing_config(name)

    def test_trial_still_rejects_over_budget_and_electrical_failures(self):
        clean = {'max_capacitance_and_slew_violations': 0}
        bad = {'max_capacitance_and_slew_violations': 1}
        for point, budget in (('main-12mhz', 50), ('main-9p6mhz', 62.5),
                              ('main-9mhz', 200 / 3)):
            with self.subTest(point=point):
                cfg = timing_config(point)
                self.assertAlmostEqual(cfg['period_ns'] * cfg['budget_fraction'], budget)
                self.assertEqual(result_status(25.335854, budget, clean), 'pass')
                self.assertEqual(result_status(budget + 0.001, budget, clean), 'fail')
                self.assertEqual(result_status(25.335854, budget, bad), 'fail')


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
