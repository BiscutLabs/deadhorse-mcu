"""Negative controls on clock/constraint data, never RTL source text."""
import copy
import unittest
from hw.top.reference.measurements.plan04_screen import class_limit,clock_manifest,audit_clock_envelope,physical_diagnostics


class Plan04TimingTests(unittest.TestCase):
    def test_physical_violations_cannot_disappear_into_screen_pass(self):
        line='core/CLK (high) 1.712000 -700.110168 -701.822205 (VIOLATED)'
        result=physical_diagnostics('HOLD_RESET_BEGIN\n'+line+'\nHOLD_RESET_END')
        self.assertEqual(result['status'],'unqualified')
        self.assertEqual(result['violations'],[line])
        self.assertEqual(result['reported_violation_count'],1)
        self.assertEqual(physical_diagnostics('HOLD_RESET_BEGIN\nHOLD_RESET_END')['status'],'unqualified')
        with self.assertRaises(ValueError):physical_diagnostics('No paths found.')

    def test_pre_enable_and_clock_control_remain_strict(self):
        for kind in ('FP','RR'):
            self.assertGreater(13.0,class_limit('usb',kind,12.5))
        self.assertLess(13.0,class_limit('usb','FF',12.5))
        self.assertEqual(class_limit('main','FF',75),75)

    def test_clock_envelope_rejects_divider_case_and_extra_overrides(self):
        correct=('create_generated_clock -name main -source [get_ports {oscIn}] -divide_by 6 [get_pins {div/Q}]\n'
            'set_case_analysis 1 [get_pins {frozen/Q}]\n'
            'set_case_analysis 0 [get_pins {strap/Q}]\ncreate_clock -name usb -period 20.8333 [get_ports {oscIn}]')
        self.assertTrue(audit_clock_envelope(correct,'div/Q','strap/Q','frozen/Q',0).startswith('create_clock'))
        for bad in (correct.replace('-divide_by 6','-divide_by 5'),
                    correct.replace('set_case_analysis 0','set_case_analysis 1'),
                    correct+'\nset_case_analysis 1 [get_pins {gate/E}]'):
            with self.assertRaises(ValueError):audit_clock_envelope(bad,'div/Q','strap/Q','frozen/Q',0)

    def test_known_clock_is_not_enough_if_core_is_on_wrong_domain(self):
        m={'ports':{'oscIn':{'bits':[2]},'pins_inactive_jtagTck':{'bits':[3]}},
            'netnames':{'clocks._divider_divided':{'bits':[4]},'digital.subsystem.usb.aonClock':{'bits':[5]}},'cells':{}}
        for index,(name,clk,source) in enumerate([('core',4,'ibex_core'),('aon',5,'OscCtrl'),
                ('source',2,'OscStability'),('tap',3,'dmi_jtag')]):
            m['cells'][name]={'type':'gf180mcu_fd_sc_mcu7t5v0__dffq_1',
                'attributes':{'src':f'build/emit/{source}.sv:10'},
                'connections':{'CLK':[clk],'D':[20+index],'Q':[30+index]},
                'port_directions':{'CLK':'input','D':'input','Q':'output'}}
        self.assertEqual(clock_manifest(m),{'core/CLK':'main','aon/CLK':'aon','source/CLK':'usb','tap/CLK':'tck'})
        for source in ('PowerReset','BrownoutSelect'):
            candidate=copy.deepcopy(m)
            candidate['cells']['aon']['attributes']['src']=f'build/emit/{source}.sv:10'
            self.assertEqual(clock_manifest(candidate)['aon/CLK'],'aon')
            candidate['cells']['aon']['connections']['CLK']=[4]
            with self.assertRaisesRegex(ValueError,'Wrong functional clock'):
                clock_manifest(candidate)
        falling=copy.deepcopy(m)
        falling['cells']['tap']['connections']['CLKN']=falling['cells']['tap']['connections'].pop('CLK')
        falling['cells']['tap']['port_directions']['CLKN']=falling['cells']['tap']['port_directions'].pop('CLK')
        self.assertEqual(clock_manifest(falling)['tap/CLKN'],'tck')
        bad=copy.deepcopy(m);bad['cells']['core']['connections']['CLK']=[5]
        with self.assertRaisesRegex(ValueError,'Wrong functional clock'):clock_manifest(bad)
        bad=copy.deepcopy(m);bad['cells']['core']['connections']['CLK']=[999]
        with self.assertRaisesRegex(ValueError,'Unknown/cyclic'):clock_manifest(bad)


if __name__=='__main__':unittest.main()
