import copy
import unittest
from tools.timing.fanout import buffer_module, verify

class FanoutTests(unittest.TestCase):
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
