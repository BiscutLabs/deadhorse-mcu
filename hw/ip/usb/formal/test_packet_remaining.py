"""Structural guard tests for the source-emitted observation-only monitor."""
import copy
import unittest

from packet_remaining import bind_position_monitor


class PositionMonitorTests(unittest.TestCase):
    def setUp(self):
        ports={'clock':[1], 'reset_n':[2], 'watching':[3], 'inPacket':[4],
               'position':list(range(5,10)), 'queued':list(range(10,15))}
        def cell(kind,connections,parameters=None):
            return dict(type=kind,connections=connections,parameters=parameters or {},
                        port_directions={p:'output' if p=='Y' else 'input' for p in connections},attributes={})
        self.monitor={'modules':{'UsbOutPositionLemma':dict(
            ports={n:dict(direction='input',bits=b) for n,b in ports.items()},cells={
                'ge':cell('$ge',{'A':ports['position'],'B':ports['queued'],'Y':[15]},
                          dict(A_SIGNED='0',B_SIGNED='0',A_WIDTH='101',B_WIDTH='101')),
                'a':cell('$and',{'A':[2],'B':[3],'Y':[16]}),
                'b':cell('$and',{'A':[16],'B':[4],'Y':[17]}),
                'assert__chisel3_builtin':cell('$assert',{'A':[15],'EN':[17]})})}}
        self.base={'modules':{'M':dict(cells={'original':cell('$assert',{'A':[99],'EN':[98]})},
            netnames={n:dict(bits=[b+100 for b in bits]) for n,bits in ports.items()})}}

    def test_monitor_does_not_change_original_transition_system(self):
        before=copy.deepcopy(self.base)
        bound=bind_position_monitor(self.base,'M',self.monitor)
        self.assertEqual(before,self.base)
        self.assertEqual(bound['modules']['M']['cells']['original'],before['modules']['M']['cells']['original'])
        self.assertEqual(bound['modules']['M']['netnames'],before['modules']['M']['netnames'])
        self.assertEqual(bound['modules']['M']['cells']['position_monitor.ge']['connections']['A'],list(range(105,110)))

    def test_wrong_predicate_guard_and_width_are_rejected(self):
        for mode in ('compare','signed','reset','width'):
            monitor=copy.deepcopy(self.monitor);base=copy.deepcopy(self.base)
            cells=monitor['modules']['UsbOutPositionLemma']['cells']
            if mode=='compare':cells['ge']['connections']['B']=cells['ge']['connections']['A']
            if mode=='signed':cells['ge']['parameters']['A_SIGNED']='1'
            if mode=='reset':cells['a']['connections']['A']=['1']
            if mode=='width':base['modules']['M']['netnames']['position']['bits'].pop()
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                bind_position_monitor(base,'M',monitor)

    def test_state_or_assumption_cannot_enter_monitor(self):
        for kind in ('$assume','$dff'):
            monitor=copy.deepcopy(self.monitor)
            monitor['modules']['UsbOutPositionLemma']['cells']['extra']=dict(type=kind,connections={})
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                bind_position_monitor(self.base,'M',monitor)

    def test_input_driver_and_multiple_drivers_are_rejected(self):
        for mode in ('input','multiple'):
            monitor=copy.deepcopy(self.monitor)
            cells=monitor['modules']['UsbOutPositionLemma']['cells']
            cells['extra']=copy.deepcopy(cells['a'])
            cells['extra']['connections']['Y']=[5] if mode=='input' else [16]
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                bind_position_monitor(self.base,'M',monitor)


if __name__=='__main__':unittest.main()
