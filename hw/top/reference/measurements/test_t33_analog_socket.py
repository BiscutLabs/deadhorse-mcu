"""Malformed netlist controls for the threshold socket audit."""
import copy
import unittest
from hw.top.reference.measurements.t33_analog_socket import threshold_driver


class ThresholdSocketTests(unittest.TestCase):
    def fixture(self):
        return {'netnames':{'digital.subsystem.powerReset.threshold':{'bits':[12,'0']},
                            'digital.subsystem.powerReset.clk':{'bits':[3]}},
                'cells':{'select':{'type':'$adff',
                                  'connections':{'D':[11],'Q':[12],'CLK':[3]},
                                  'port_directions':{'D':'input','Q':'output','CLK':'input'}}}}

    def test_registered_socket_and_mapped_identity(self):
        m=self.fixture()
        self.assertEqual(threshold_driver(m,[12,'0'])['register'],'select')
        m['cells']['select']['type']='gf180mcu_fd_sc_mcu7t5v0__dffrnq_1'
        self.assertEqual(threshold_driver(m,[12,'0'],True)['clock_bits'],[3])

    def test_wrong_pin_constant_ambiguous_driver_and_wrong_domain_fail(self):
        for bits in ([12,'1'],['0','0'],[12,13],[99,'0']):
            with self.assertRaises(ValueError):threshold_driver(self.fixture(),bits)
        m=self.fixture();m['cells']['select']['connections']['CLK']=[5]
        with self.assertRaisesRegex(ValueError,'wrong clock'):threshold_driver(m,[12,'0'])
        m=self.fixture();m['cells']['select']['type']='$mux'
        with self.assertRaisesRegex(ValueError,'storage'):threshold_driver(m,[12,'0'])
        m=self.fixture();m['cells']['duplicate']=copy.deepcopy(m['cells']['select'])
        with self.assertRaisesRegex(ValueError,'ambiguous'):threshold_driver(m,[12,'0'])


class SocketForms(unittest.TestCase):
    def fixture(self):
        return {'netnames':{'digital.subsystem.powerReset.threshold':{'bits':[12,'0']},
                'digital.subsystem.powerReset.clk':{'bits':[3]}},
            'cells':{'select':{'type':'$aldff',
                'parameters':{p:'0'*31+'1' for p in ('WIDTH','CLK_POLARITY','ALOAD_POLARITY')},
                'connections':{'D':[11],'Q':[12],'CLK':[3],'ALOAD':[4],'AD':['0']},
                'port_directions':{'D':'input','Q':'output','CLK':'input','ALOAD':'input','AD':'input'}}}}

    def test_async_load_zero_frontend_form(self):
        self.assertEqual(threshold_driver(self.fixture(),[12,'0'])['register'],'select')

    def test_async_load_malformed_data_and_parameters_rejected(self):
        for value in (['1'],[13],['x'],['z'],[],['0','0']):
            with self.subTest(data=value):
                m=self.fixture();m['cells']['select']['connections']['AD']=value
                with self.assertRaises(ValueError):threshold_driver(m,[12,'0'])
        for pin in ('CLK','D','Q','ALOAD'):
            for value in ([],[3,4]):
                with self.subTest(pin=pin,value=value):
                    m=self.fixture();m['cells']['select']['connections'][pin]=value
                    with self.assertRaises(ValueError):threshold_driver(m,[12,'0'])
        for parameter in ('WIDTH','CLK_POLARITY','ALOAD_POLARITY'):
            for value in ('0'*32,'0'*30+'10','x',''):
                with self.subTest(parameter=parameter,value=value):
                    m=self.fixture();m['cells']['select']['parameters'][parameter]=value
                    with self.assertRaises(ValueError):threshold_driver(m,[12,'0'])
        for value in ('0','1','x','z'):
            m=self.fixture();m['cells']['select']['connections']['ALOAD']=[value]
            with self.assertRaises(ValueError):threshold_driver(m,[12,'0'])

if __name__=='__main__':unittest.main()
