"""Faults against the epoch monitor's fail-closed structural binding."""
import copy
from pathlib import Path
import unittest

from packet_epoch import bind_upper, bind_occupancy, run


class EpochMonitorTests(unittest.TestCase):
    def setUp(self):
        widths={'clock':1,'reset_n':1,'watching':1,'inPacket':1,'reject':1,'position':5,'queued':5,'packet':4}
        ports={};next_bit=1
        for name,width in widths.items():
            ports[name]=dict(direction='input',bits=list(range(next_bit,next_bit+width)));next_bit+=width
        def cell(kind,con):
            return dict(type=kind,connections=con,port_directions={p:'output' if p=='Y' else 'input' for p in con})
        self.observer={'modules':{'UsbEpochOwnership':dict(ports=ports,cells={
            'sum':cell('$add',{'A':ports['queued']['bits'],'B':ports['packet']['bits'],'Y':list(range(30,36))}),
            'lt':cell('$lt',{'A':ports['position']['bits'],'B':list(range(30,36)),'Y':[36]}),
            'assert__chisel3_builtin':cell('$assert',{'A':[36],'EN':ports['reset_n']['bits']})})}}
        self.base={'modules':{'M':dict(cells={'dut':cell('$assert',{'A':[98],'EN':[99]})},netnames={
            'subject.'+('d.reject' if n=='reject' else n):dict(bits=[b+100 for b in p['bits']]) for n,p in ports.items()})}}
        self.base['modules']['M']['netnames']['reset_n']=dict(bits=[200])

    def test_observer_preserves_dut_and_uses_transport_reset(self):
        original=copy.deepcopy(self.base);bound=bind_upper(self.base,'M',self.observer)
        self.assertEqual(self.base,original)
        self.assertEqual(bound['modules']['M']['cells']['dut'],original['modules']['M']['cells']['dut'])
        self.assertEqual(bound['modules']['M']['netnames'],original['modules']['M']['netnames'])
        self.assertEqual(bound['modules']['M']['cells']['ownership_upper.assert__chisel3_builtin']['connections']['EN'],[102])

    def test_wrong_width_state_and_assumptions_fail_closed(self):
        for fault in ('width','$dff','$assume'):
            base=copy.deepcopy(self.base);observer=copy.deepcopy(self.observer)
            if fault=='width':base['modules']['M']['netnames']['subject.position']['bits'].pop()
            else:observer['modules']['UsbEpochOwnership']['cells']['fault']=dict(type=fault,connections={})
            with self.subTest(fault=fault),self.assertRaises(ValueError):bind_upper(base,'M',observer)

    def test_observer_cannot_drive_dut_or_duplicate_driver(self):
        for driven in ([1],[36]):
            observer=copy.deepcopy(self.observer)
            observer['modules']['UsbEpochOwnership']['cells']['fault']=dict(type='$not',connections={'A':[1],'Y':driven},
                port_directions={'A':'input','Y':'output'})
            with self.subTest(driven=driven),self.assertRaises(ValueError):bind_upper(self.base,'M',observer)

    def test_duplicate_original_cannot_fake_complete_inventory(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            run(Path('build/unused-duplicate-test'),'in',16,['capacity']*6)


class OccupancyMonitorTests(unittest.TestCase):
    def setUp(self):
        widths={'clock':1,'reset_n':1,'head':4,'tail':4,'speculative':4,'reject':1,'queued':5,'packet':4,'appValid':1}
        ports={};next_bit=1
        for name,width in widths.items():
            ports[name]=dict(direction='input',bits=list(range(next_bit,next_bit+width)));next_bit+=width
        def assertion(bit):return dict(type='$assert',connections={'A':[bit],'EN':ports['reset_n']['bits']},port_directions={'A':'input','EN':'input'})
        self.observer={'modules':{'UsbOutOccupancyLemma':dict(ports=ports,cells={
            'assert__chisel3_builtin':assertion(ports['reject']['bits'][0]),
            'assert__chisel3_builtin_0':assertion(ports['appValid']['bits'][0])})}}
        self.base={'modules':{'M':dict(ports={'unused':dict(direction='input',bits=[9000])},cells={},netnames={
            'subject.'+('d.' if n in ('head','tail','speculative','reject','appValid') else '')+n:
                dict(bits=[b+100 for b in p['bits']]) for n,p in ports.items()})}}

    def test_original_model_preserved_and_transport_reset_bound(self):
        original=copy.deepcopy(self.base);bound=bind_occupancy(self.base,'M',self.observer)
        self.assertEqual(original,self.base)
        self.assertEqual(bound['modules']['M']['netnames'],original['modules']['M']['netnames'])
        self.assertEqual(bound['modules']['M']['cells']['occupancy.assert__chisel3_builtin']['connections']['EN'],[102])

    def test_bad_bindings_rejected(self):
        for fault in ('width','alias','state','assumption','driven_input','missing_assertion','collision'):
            base=copy.deepcopy(self.base);observer=copy.deepcopy(self.observer);m=observer['modules']['UsbOutOccupancyLemma']
            if fault=='width':base['modules']['M']['netnames']['subject.d.head']['bits'].pop()
            if fault=='alias':m['ports']['reject']['bits']=m['ports']['appValid']['bits']
            if fault in ('state','assumption'):m['cells']['fault']=dict(type='$dff' if fault=='state' else '$assume',connections={})
            if fault=='driven_input':m['cells']['fault']=dict(type='$not',connections={'A':[1],'Y':[2]},port_directions={'A':'input','Y':'output'})
            if fault=='missing_assertion':del m['cells']['assert__chisel3_builtin_0']
            if fault=='collision':base['modules']['M']['cells']['occupancy.assert__chisel3_builtin']=copy.deepcopy(m['cells']['assert__chisel3_builtin'])
            with self.subTest(fault=fault),self.assertRaises(ValueError):bind_occupancy(base,'M',observer)

    def test_unsupported_geometry_rejected_before_emission(self):
        with self.assertRaisesRegex(ValueError,'eight-byte'):
            run(Path('build/unused-occupancy-test'),'out',16,['integrity'],True,None,True,True)


if __name__=='__main__':unittest.main()
