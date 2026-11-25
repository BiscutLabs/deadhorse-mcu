"""Synthetic netlist checks; no RTL-source inspection."""
import copy,unittest
from hw.top.reference.measurements.plan05_usb_boundary import isolate,audit
from tools.timing.fanout import verify

class UsbBoundaryTests(unittest.TestCase):
    def fixture(self):
        ref={'ports':{'bus_bits_addr':dict(direction='input',bits=[2,3]),
            'bus_bits_origin':dict(direction='input',bits=[4]),'clk':dict(direction='input',bits=[5])}}
        m=dict(ports={'clock':dict(direction='input',bits=[5])},netnames={},cells={})
        for n,p in ref['ports'].items():m['netnames']['digital.subsystem.usb.'+n]=dict(hide_name=0,bits=p['bits'][:],attributes={})
        m['cells']['digital.subsystem.usb.input']=dict(type='example',hide_name=0,attributes={},parameters={},
            port_directions=dict(A='input',B='input',C='input',CLK='input',Q='output'),connections=dict(A=[2],B=[3],C=[4],CLK=[5],Q=[6]))
        return m,ref
    def test_keeps_values_and_audits_buffer_identity(self):
        old,ref=self.fixture();new,rows=isolate(old,ref)
        self.assertEqual(len(rows),3);audit(new,rows)
        verify(old,new,[r['cell'] for r in rows])
        for pin,value in [('I',[0]),('Z',[107])]:
            bad=copy.deepcopy(new);bad['cells'][rows[0]['cell']]['connections'][pin]=value
            with self.assertRaises(AssertionError):audit(bad,rows)
    def test_rejects_clock_or_other_input_alias(self):
        old,ref=self.fixture();old['netnames']['digital.subsystem.usb.bus_bits_addr']['bits'][0]=5
        with self.assertRaisesRegex(AssertionError,'another input class'):isolate(old,ref)
    def test_existing_same_data_source_uses_one_buffer(self):
        old,ref=self.fixture();old['netnames']['digital.subsystem.usb.bus_bits_addr']['bits'][1]=2
        old['cells']['digital.subsystem.usb.input']['connections']['B']=[2]
        new,rows=isolate(old,ref);self.assertEqual(len(rows),2);audit(new,rows)
        self.assertEqual(new['cells']['digital.subsystem.usb.input']['connections']['A'],new['cells']['digital.subsystem.usb.input']['connections']['B'])
if __name__=='__main__':unittest.main()
