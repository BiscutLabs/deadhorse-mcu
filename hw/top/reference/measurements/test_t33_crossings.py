import unittest
from hw.top.reference.measurements.t33_crossings import inventory,reset_event_contract


class CrossingInventoryTests(unittest.TestCase):
    def fixture(self):
        def flop(d,q,clk,rn):
            return dict(type='gf180mcu_fd_sc_mcu7t5v0__dffrnq_1',
                connections=dict(D=[d],Q=[q],CLK=[clk],RN=[rn]),
                port_directions=dict(D='input',Q='output',CLK='input',RN='input'))
        return dict(ports={str(b):dict(direction='input',bits=[b]) for b in (2,3,4,5,6)},
            cells=dict(a=flop(6,10,2,4),b=flop(10,11,3,5),c=flop(10,12,2,5)))

    def test_no_implicit_cdc_or_reset_waivers(self):
        counts,rows,_=inventory(self.fixture(),{'a/CLK':'main','b/CLK':'aon','c/CLK':'main'})
        self.assertEqual(counts,dict(registers=3,cdc_candidates=1,rdc_candidates=1,external_data=1,reset_origins=3))
        self.assertIn(('cdc','a/Q','b/D'),[(r['kind'],r['source'],r['destination']) for r in rows])
        self.assertIn(('rdc','a/Q','c/D'),[(r['kind'],r['source'],r['destination']) for r in rows])

    def test_missing_driver_is_rejected(self):
        m=self.fixture();m['cells']['b']['connections']['D']=[99]
        with self.assertRaisesRegex(ValueError,'Undriven'):
            inventory(m,{'a/CLK':'main','b/CLK':'aon','c/CLK':'main'})

    def test_clear_and_preset_share_only_the_same_active_low_reset_event(self):
        m=self.fixture();c=m['cells']['c']
        c['type']='gf180mcu_fd_sc_mcu7t5v0__dffsnq_1'
        del c['connections']['RN'];del c['port_directions']['RN']
        c['connections']['SETN']=[4];c['port_directions']['SETN']='input'
        clocks={'a/CLK':'main','b/CLK':'aon','c/CLK':'main'}
        counts,rows,regs=inventory(m,clocks)
        self.assertEqual(counts['rdc_candidates'],0)
        self.assertNotEqual(regs['a']['resets'],regs['c']['resets'])
        self.assertEqual(regs['a']['reset_events'],regs['c']['reset_events'])
        # A different actual reset net must still be reported, irrespective
        # of the opposite reset value of the two flip-flops.
        c['connections']['SETN']=[5]
        counts,rows,_=inventory(m,clocks)
        self.assertEqual(counts['rdc_candidates'],1)
        self.assertIn(('rdc','a/Q','c/D'),[(r['kind'],r['source'],r['destination']) for r in rows])

    def test_reset_event_sets_preserve_unreset_multiple_and_async_boundaries(self):
        clocks={'a/CLK':'main','b/CLK':'aon','c/CLK':'main'}
        m=self.fixture();c=m['cells']['c']
        del c['connections']['RN'];del c['port_directions']['RN']
        self.assertEqual(inventory(m,clocks)[0]['rdc_candidates'],1)
        c['connections']['RN']=[4];c['port_directions']['RN']='input'
        c['connections']['SETN']=[5];c['port_directions']['SETN']='input'
        self.assertEqual(inventory(m,clocks)[0]['rdc_candidates'],1)
        c['connections']['SETN']=[4]
        counts,_,regs=inventory(m,clocks)
        self.assertEqual(counts['rdc_candidates'],0)
        self.assertEqual(regs['c']['reset_events'],[4])
        self.assertEqual(len(regs['c']['resets']),2)
        m['cells']['b']['connections']['RN']=[4]
        self.assertEqual(inventory(m,clocks)[0]['cdc_candidates'],1)
        c['connections']['SETN']=['x']
        with self.assertRaisesRegex(ValueError,'Unknown reset constant'):
            inventory(m,clocks)

    def test_polarity_is_checked_from_liberty_without_assuming_pin_names(self):
        m=self.fixture();clocks={'a/CLK':'main','b/CLK':'aon','c/CLK':'main'}
        typ=m['cells']['a']['type']
        def lib(expr):return f'cell ({typ}) {{ ff (Q, QN) {{ clear : "{expr}"; }} }}'
        self.assertEqual(reset_event_contract(m,clocks,lib('(!RN)')),{typ:{'RN':'active_low'}})
        for expr in ('RN','!OTHER','!RN & !SETN'):
            with self.assertRaisesRegex(ValueError,'Unsupported reset polarity'):
                reset_event_contract(m,clocks,lib(expr))
        with self.assertRaisesRegex(ValueError,'Reset pin inventory'):
            reset_event_contract(m,clocks,f'cell ({typ}) {{ ff (Q, QN) {{ }} }}')


if __name__=='__main__':unittest.main()
