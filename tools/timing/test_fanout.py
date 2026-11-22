import copy
import unittest
from tools.timing.fanout import buffer_module, verify, internal_reset_sources

class FanoutTests(unittest.TestCase):
    def test_internal_reset_selection_and_faults(self):
        m=self.fixture()
        self.assertEqual(internal_reset_sources(m,'clk'),set())
        for c in m['cells'].values():c['connections']['RN']=[1001]
        with self.assertRaisesRegex(ValueError,'driver'):internal_reset_sources(m,'clk')
        m['cells']['combine']=dict(type='and2',hide_name=0,parameters={},attributes={},
            port_directions={'A':'input','B':'input','Z':'output'},connections={'A':[3],'B':[4],'Z':[1001]})
        self.assertEqual(internal_reset_sources(m,'clk'),{1001})
        buffered,inserted=buffer_module(m,'clk',source_bits=internal_reset_sources(m,'clk'),prefix='reset_fanout_')
        verify(m,buffered,inserted);self.assertTrue(inserted)
        bad=copy.deepcopy(buffered);bad['cells']['ff0']['connections']['RN']=[3]
        with self.assertRaisesRegex(ValueError,'logic/pin'):verify(m,bad,inserted)
        bad=copy.deepcopy(buffered);del bad['cells']['ff0']['connections']['RN']
        with self.assertRaisesRegex(ValueError,'logic/pin'):verify(m,bad,inserted)
        bad=copy.deepcopy(m);bad['cells']['duplicate']=copy.deepcopy(m['cells']['combine'])
        with self.assertRaisesRegex(ValueError,'ambiguous'):internal_reset_sources(bad,'clk')
        bad=copy.deepcopy(m);bad['cells']['ff0']['connections']['CLK']=[1001]
        with self.assertRaisesRegex(ValueError,'clock'):internal_reset_sources(bad,'clk')
        bad=copy.deepcopy(m)
        bad['cells']['clock_buffer']=dict(type='buf',hide_name=0,parameters={},attributes={},
            port_directions={'I':'input','Z':'output'},connections={'I':[1001],'Z':[1100]})
        bad['cells']['ff0']['connections']['CLK']=[1100]
        with self.assertRaisesRegex(ValueError,'clock'):internal_reset_sources(bad,'clk')

    def test_selected_reset_sources_leave_other_data_nets_unchanged(self):
        original=self.fixture()
        for cell in original['cells'].values():cell['connections']['D']=[1001]
        buffered,inserted=buffer_module(original,'clk',source_bits={3},prefix='soc_reset_')
        verify(original,buffered,inserted)
        self.assertTrue(inserted)
        self.assertTrue(all(n.startswith('soc_reset_') for n in inserted))
        for name in original['cells']:
            self.assertEqual(buffered['cells'][name]['connections']['D'],[1001])
        for bits in ({2},{9999},set(),{'0'}):
            with self.assertRaises(ValueError):buffer_module(original,'clk',source_bits=bits)

    def fixture(self):
        return dict(ports={'clk':{'direction':'input','bits':[2]},'reset_n':{'direction':'input','bits':[3]}},
            netnames={'unused':{'bits':[1000]}},cells={f'ff{i}':dict(type='ff',hide_name=0,
                parameters={},attributes={},port_directions={'CLK':'input','D':'input','RN':'input','Q':'output'},
                connections={'CLK':[2],'D':[4+i],'RN':[3],'Q':[200+i]}) for i in range(80)})
    def test_balanced_reset_tree_preserves_every_pin_and_never_buffers_clocks(self):
        original=self.fixture(); buffered, inserted=buffer_module(original,'clk')
        self.assertTrue(inserted);verify(original,buffered,inserted)
        for name in original['cells']:
            self.assertEqual(buffered['cells'][name]['connections']['CLK'],[2])
        self.assertTrue(all(buffered['cells'][n]['connections']['Z'][0]>1000 for n in inserted))
        fanout={}
        for cell in buffered['cells'].values():
            for port,direction in cell['port_directions'].items():
                if direction=='input':
                    for bit in cell['connections'][port]:fanout[bit]=fanout.get(bit,0)+1
        self.assertTrue(all(count<=8 for bit,count in fanout.items() if bit!=2))
    def test_wrong_pin_and_clock_negative_controls_are_rejected(self):
        original=self.fixture();buffered,inserted=buffer_module(original,'clk')
        bad=copy.deepcopy(buffered);bad['cells']['ff0']['connections']['D']=[5]
        with self.assertRaisesRegex(ValueError,'logic/pin'):verify(original,bad,inserted)
        bad=copy.deepcopy(buffered);bad['cells']['ff0']['connections']['CLK']=[3]
        with self.assertRaisesRegex(ValueError,'clock'):verify(original,bad,inserted)
    def test_cycle_and_original_net_collision_are_rejected(self):
        original=self.fixture();buffered,inserted=buffer_module(original,'clk')
        bad=copy.deepcopy(buffered);cell=bad['cells'][inserted[0]];cell['connections']['I']=cell['connections']['Z'][:]
        with self.assertRaisesRegex(ValueError,'cycle'):verify(original,bad,inserted)
        bad=copy.deepcopy(buffered);bad['cells'][inserted[0]]['connections']['Z']=[3]
        with self.assertRaisesRegex(ValueError,'overlaps'):verify(original,bad,inserted)
    def test_original_output_pin_cannot_be_moved_onto_a_buffer_output(self):
        original=self.fixture();buffered,inserted=buffer_module(original,'clk')
        bad=copy.deepcopy(buffered);name=inserted[0]
        old=original['cells']['ff0']['connections']['Q'][0]
        fresh=bad['cells'][name]['connections']['Z'][0]
        bad['cells'][name]['connections']['I']=[old]
        bad['cells']['ff0']['connections']['Q']=[fresh]
        with self.assertRaisesRegex(ValueError,'logic/pin'):verify(original,bad,inserted)
