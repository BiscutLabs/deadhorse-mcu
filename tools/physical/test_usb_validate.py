"""Faults in measurement accounting must not become passing evidence."""
import copy
import unittest
from usb_validate import annotation, corrected, number, require_complete,class_coverage,audit_hashes
from usb_sdc_audit import compare

class ValidationTests(unittest.TestCase):
    def test_stale_manifest_rejected(self):
        with self.assertRaises(ValueError):audit_hashes({'tools/physical/lock.json':'0'*64})
    def test_missing_class_and_changed_constraints(self):
        class_coverage([{'class':'FF'}],{'classes':{'FF':{},'CP':None}})
        with self.assertRaises(ValueError):class_coverage([],{'classes':{'FF':{}}})
        full='set_multicycle_path 3 -setup -from a -to b\n'
        boundary='create_clock -period 20 clk\nset_input_delay 2 p\n'
        effective=full+boundary+'set_propagated_clock clk\n'
        compare(full,boundary,effective)
        for bad in (effective.replace('3 -setup','4 -setup'),effective.replace('delay 2','delay 3'),effective.replace('set_propagated_clock clk','')):
            with self.assertRaises(ValueError):compare(full,boundary,bad)
        continued='set_multicycle_path 3 -setup \\\n  -from a \\\n  -to b\nset_clock_groups -asynchronous \\\n  -group appClock -group usbClock\n'
        effective=continued+boundary+'set_propagated_clock clk\n'
        compare(continued,boundary,effective)
        for bad in (effective.replace('-to b','-to wrong'),effective.replace('-group usbClock','-group wrong')):
            with self.assertRaises(ValueError):compare(continued,boundary,bad)
    def test_clock_insertion_removed_but_clock_to_q_retained(self):
        # Independent arithmetic fixture: launch clock 3, CLK-Q 2, logic 7.
        row=dict(start='a/Q',end='b/D',delay_ns='12',points='unused')
        clocks={'a/CLK':dict(max_rise_ns='3')}
        self.assertEqual(corrected(row,clocks)['delay_ns'],9)
        self.assertEqual(corrected(dict(row,delay_ns='9'),clocks,'launch-relative-data-v2')['delay_ns'],9)
        with self.assertRaises(ValueError):corrected(row,clocks,'unknown')
        self.assertEqual(corrected(dict(row,start='port'),{})['delay_ns'],12)
        with self.assertRaises(KeyError):corrected(row,{})
        with self.assertRaises(ValueError):corrected(dict(row,delay_ns='nan'),clocks)
        with self.assertRaises(ValueError):corrected(dict(row,delay_ns='2'),clocks)

    def test_incomplete_or_error_log_rejected(self):
        require_complete('FINISHED','FINISHED')
        for log in ('','Error: failure\nFINISHED','[ERROR DRT-1]\nFINISHED','not a valid start point\nFINISHED'):
            with self.subTest(log=log),self.assertRaises(ValueError):require_complete(log,'FINISHED')

    def test_only_sinkless_annotation_omissions_allowed(self):
        m=dict(ports={'p':dict(direction='input',bits=[2])},cells={
            'a':dict(type='gf180mcu_fd_sc_mcu7t5v0__buf_1',connections={'I':[3],'Z':[4]},port_directions={'I':'input','Z':'output'}),
            'clkload1':dict(type='gf180mcu_fd_sc_mcu7t5v0__inv_4',connections={'I':[3]},port_directions={'I':'input'})})
        log='Found 3 unannotated drivers.\np\na/Z\nclkload1/ZN\nFound 0 partially unannotated drivers.'
        self.assertEqual(annotation(log,m)['partially_unannotated'],0)
        for pin in ('port','cell','output','missing'):
            bad=copy.deepcopy(m)
            if pin=='port':bad['cells']['a']['connections']['I']=[2]
            if pin=='cell':bad['cells']['a']['connections']['I']=[4]
            if pin=='output':bad['ports']['out']=dict(direction='output',bits=[4])
            if pin=='missing':bad['cells']['clkload1']['type']='unknown'
            with self.subTest(pin=pin),self.assertRaises((ValueError,KeyError)):annotation(log,bad)
        with self.assertRaises(ValueError):annotation(log.replace('Found 0 partially','Found 1 partially'),m)
        with self.assertRaises(ValueError):annotation(log.replace('Found 3','Found 4'),m)

if __name__=='__main__':unittest.main()
