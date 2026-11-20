"""Independent graph fixtures and deliberately broken physical/reset connections."""
import copy
import unittest
from usb_graph import equivalent,reset_chains

SC='gf180mcu_fd_sc_mcu7t5v0__'
def cell(kind,**connections):
    return dict(type=SC+kind,connections=connections,
                port_directions={p:'output' if p in ('Q','Z','ZN') else 'input' for p in connections})
def model():
    ports={n:dict(direction='input',bits=[i]) for i,n in enumerate(('appClock','usbClock','aonClock','appReset_n','usbReset_n','aonReset_n'),2)}
    ports['out']=dict(direction='output',bits=[21])
    cells={'common':cell('and2_1',A1=[5],A2=[6],Z=[10])}
    for i,(clock,rn) in enumerate(((2,10),(3,10),(4,7))):
        cells[f'f{i}']=cell('dffrnq_1',CLK=[clock],RN=[rn],D=['1'],Q=[20+i*2])
        cells[f's{i}']=cell('dffrnq_1',CLK=[clock],RN=[rn],D=[20+i*2],Q=[21+i*2])
    return dict(ports=ports,cells=cells)

class GraphTests(unittest.TestCase):
    def test_parameters_and_unknown_directions_rejected(self):
        for fault in ('parameter','direction'):
            a=model();b=copy.deepcopy(a)
            if fault=='parameter':b['cells']['f0']['parameters']={'changed':'1'}
            else:
                a['cells']['f0']['port_directions']['D']='unknown'
                b['cells']['f0']['port_directions']['D']='unknown'
            with self.assertRaises(ValueError):equivalent(a,b)
    def test_valid_reset_structure(self):
        self.assertEqual(len(reset_chains(model())['chains']),3)

    def test_reset_faults(self):
        for fault in ('first_leaks','early_release','wrong_clock','wrong_assertion','bypass','exposed'):
            m=model()
            if fault=='first_leaks':m['cells']['s1']['connections']['D']=[20]
            if fault=='early_release':m['cells']['s0']['connections']['D']=['1']
            if fault=='wrong_clock':m['cells']['s0']['connections']['CLK']=[3]
            if fault=='wrong_assertion':m['cells']['common']['type']=SC+'nand2_1'
            if fault=='bypass':m['cells']['extra']=cell('dffrnq_1',D=['0'],RN=[5],CLK=[3],Q=[99])
            if fault=='exposed':m['ports']['out']['bits']=[20]
            with self.subTest(fault=fault),self.assertRaises(ValueError):reset_chains(m)

    def test_physical_buffer_and_tie_preserve_connections(self):
        a=model();b=copy.deepcopy(a)
        b['cells']['clockbuf']=cell('clkbuf_4',I=[2],Z=[30])
        b['cells']['tie']=cell('tieh',Z=[31])
        b['cells']['f0']['connections'].update(CLK=[30],D=[31])
        b['cells']['s0']['connections']['CLK']=[30]
        self.assertEqual(equivalent(a,b)['inserted_cells'],2)

    def test_physical_faults(self):
        for fault in ('clock_phase','data_pin','new_state','removed','output','tie_value'):
            a=model();b=copy.deepcopy(a)
            if fault=='clock_phase':
                b['cells']['buf']=cell('inv_1',I=[2],ZN=[30]);b['cells']['f0']['connections']['CLK']=[30]
            if fault=='data_pin':b['cells']['s0']['connections']['D']=[22]
            if fault=='new_state':b['cells']['extra']=cell('dffrnq_1',CLK=[2],D=['0'],RN=[5],Q=[30])
            if fault=='removed':del b['cells']['f0']
            if fault=='output':b['ports']['out']['bits']=[23]
            if fault=='tie_value':
                b['cells']['tie']=cell('tiel',ZN=[30]);b['cells']['f0']['connections']['D']=[30]
            with self.subTest(fault=fault),self.assertRaises(ValueError):equivalent(a,b)

if __name__=='__main__':unittest.main()
