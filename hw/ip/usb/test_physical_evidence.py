import copy
import unittest
from pathlib import Path
import physical_evidence as evidence


class PhysicalEvidenceTests(unittest.TestCase):
    def test_wrong_async_library_rejected(self):
        lib=evidence.ROOT/'build/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
        text='set liberty {'+str(lib)+'}\n'
        self.assertEqual(evidence.corner_library([str(lib)],text,'ss_125C_3v00-max'),lib)
        for bindings,driver in [([str(lib),str(lib)],text),([str(lib)],text.replace('ss_125C','ff_125C')),
                                ([str(lib)],text+text)]:
            with self.assertRaises(ValueError):evidence.corner_library(bindings,driver,'ss_125C_3v00-max')

    def test_missing_and_duplicate_hold_captures_fail(self):
        rows=[dict(check='hold/min_rise',start='bus_req',end='capture/D',slack_ns='0.5'),
              dict(check='hold/min_fall',start='bus_req',end='capture/D',slack_ns='0.4')]
        measured=dict(rows[1],slack_ns=0.4)
        evidence.hold_inventory(rows,rows,measured)
        for bad in ([],rows[:1],rows+[rows[0]]):
            with self.assertRaises(ValueError):evidence.hold_inventory(bad,rows,measured)
        bad=copy.deepcopy(rows);bad[1]['slack_ns']='nan'
        with self.assertRaises(ValueError):evidence.hold_inventory(bad,rows,measured)
        bad=copy.deepcopy(rows);bad[1]['slack_ns']='0.3'
        with self.assertRaises(ValueError):evidence.hold_inventory(bad,rows,measured)

    def test_swapped_candidate_inputs_fail(self):
        candidate=evidence.ROOT/'build/candidate'
        text=('set netlist {'+str(candidate/'routed.v')+'}\nset spef {'+str(candidate/'extract-min/routed.spef')+'}\n'+
              'read_sdc {'+str(candidate/'validation/ss-min/base.sdc')+'}\n'+
              'read_sdc {'+str(candidate/'timing/ss-min/boundary.sdc')+'}\n')
        evidence.hold_driver_inputs(text,candidate,'ss-min')
        with self.assertRaises(ValueError):evidence.hold_driver_inputs(text,candidate.with_name('other'),'ss-min')
        with self.assertRaises(ValueError):evidence.hold_driver_inputs(text.replace('extract-min','extract-max'),candidate,'ss-min')

    def test_swapped_usb_or_slot_composition_fails(self):
        good={'usb.json':'usb-hash','slot.json':'slot-hash','binding.json':'binding-hash'}
        evidence.exact_input_bindings(good,good)
        for key in ('usb.json','slot.json'):
            bad=dict(good);bad[key]='other-hash'
            with self.assertRaises(ValueError):evidence.exact_input_bindings(bad,good)
        bad=dict(good);bad['extra.json']='binding-hash'
        with self.assertRaises(ValueError):evidence.exact_input_bindings(bad,good)
