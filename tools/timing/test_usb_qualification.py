import copy
import unittest
from tools.timing.usb_qualification import audit_exceptions,delay_fault


class QualificationTests(unittest.TestCase):
    def test_exact_exception_pairs_and_faults(self):
        cert=dict(status='pass',reset_aware=dict(groups={'r':['a'],'s':['b']},allowed_pairs=[['r','r'],['s','s']]),
                  pre_enable=dict(status='pass',allowed_launch_groups=['r'],capture_pins={'p':'p/D'}))
        text='\n'.join(f'set_multicycle_path -{mode} -from [get_pins {{{a}/CLK}}] -to [get_pins {{{b}/D}}] {value}'
            for a,b,setup,hold in [('a','a',4,3),('b','b',4,3),('a','p',3,2)]
            for mode,value in [('setup',setup),('hold',hold)])+'\n'
        self.assertEqual(audit_exceptions(text,cert),{'setup4':2,'hold3':2,'setup3':1,'hold2':1})
        for bad in (text.replace(' 4\n',' 5\n',1),text.replace('a/D','a/CLK',1),
                    text.replace(' 3\n',' 2\n',1),text+'  set_false_path -from [all_registers]\n',
                    text+'set_clock_groups -asynchronous -group [get_clocks {block_clock}]\n',
                    '\n'.join(text.splitlines()[1:]),text+'set_multicycle_path -setup -from [get_pins {b/CLK}] -to [get_pins {p/D}] 3\n'):
            with self.assertRaises(ValueError):audit_exceptions(bad,cert)
        self.assertEqual(audit_exceptions('  '+text,cert),audit_exceptions(text,cert))
        groups='set_clock_groups -name group1 -asynchronous -group [get_clocks {usbClock}] -group [get_clocks {appClock}] -group [get_clocks {aonClock}]\n'
        audit_exceptions(text+groups,cert,'Usb')
        for bad in (groups.replace('aonClock','appClock'),groups.replace('-asynchronous','-logically_exclusive')):
            with self.assertRaises(ValueError):audit_exceptions(text+bad,cert,'Usb')

    def test_delay_fault_preserves_original_logic_and_drives_all_loads(self):
        model={'modules':{'Top':{'ports':{'i':dict(direction='input',bits=[2]),'o':dict(direction='output',bits=[3])},
            'netnames':{'o':dict(bits=[3])},
            'cells':{'a':dict(type='inv',port_directions={'I':'input','ZN':'output'},connections={'I':[2],'ZN':[3]})}}}}
        bad,meta=delay_fault(model,'Top','i',3)
        self.assertEqual(model['modules']['Top']['cells']['a']['connections']['I'],[2])
        self.assertEqual(meta['loads'],1)
        self.assertEqual(bad['modules']['Top']['cells']['a']['connections']['I'],[6])
        output,_=delay_fault(model,'Top','a/ZN',3)
        self.assertEqual(output['modules']['Top']['ports']['o']['bits'],[6])
        self.assertEqual(output['modules']['Top']['netnames']['o']['bits'],[6])
        self.assertEqual(output['modules']['Top']['cells']['a']['connections']['ZN'],[3])
        for source in ('a/I','o'):
            with self.assertRaises(ValueError):delay_fault(model,'Top',source)


if __name__=='__main__':unittest.main()
