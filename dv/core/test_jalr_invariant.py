"""Proof-harness transformations checked against small independent netlists."""
import copy
import unittest
from jalr_invariant import TOP, PREFIX, attach, cone, independent, property_cell
from audit_jalr_invariant import active_witness


class JalrInvariantTests(unittest.TestCase):
    def setUp(self):
        self.a='$flatten\\checker_inst.assertion'
        self.s='$flatten\\checker_inst.selection'
        nets={'checker_inst.reset':[2],'checker_inst.check':[3],
              'checker_inst.rvfi_valid':[4],'checker_inst.rvfi_insn':list(range(5,37)),
              'checker_inst.rvfi_rs1_addr':list(range(37,42)),PREFIX+'spec_valid':[42]}
        self.design={'modules':{TOP:{'attributes':{},'ports':{},
            'netnames':{n:dict(bits=b,attributes={}) for n,b in nets.items()},
            'cells':{'data':dict(type='$not',parameters={},attributes={},
                port_directions={'A':'input','Y':'output'},connections={'A':[4],'Y':[42]}),
                self.a:property_cell('assert',[42]),self.s:property_cell('assume',[42],[3]),
                'reset_constraint':property_cell('assume',[2])}}}}
        self.monitor={'ports':{
            'reset':dict(bits=[2]),'valid':dict(bits=[3]),
            'instruction':dict(bits=list(range(4,36))),
            'reportedAddress':dict(bits=list(range(36,41))),
            'active':dict(bits=[41]),'holds':dict(bits=[42])},
            'cells':{'active':dict(type='$not',parameters={},attributes={},
                port_directions={'A':'input','Y':'output'},connections={'A':[3],'Y':[41]}),
                'holds':dict(type='$eq',parameters={},attributes={},
                port_directions={'A':'input','B':'input','Y':'output'},
                connections={'A':list(range(36,41)),'B':list(range(19,24)),'Y':[42]})}}

    def test_graft_preserves_production_and_maps_actual_rvfi(self):
        result,signals=attach(self.design,self.monitor)
        m=result['modules'][TOP];orig=self.design['modules'][TOP]
        for n,c in orig['cells'].items(): self.assertEqual(m['cells'][n],c)
        self.assertEqual(m['cells']['__jalr_monitor_holds']['connections']['A'],list(range(37,42)))
        self.assertEqual(m['cells']['__jalr_monitor_holds']['connections']['B'],list(range(20,25)))
        self.assertTrue(set(signals['holds']).isdisjoint(range(2,43)))

    def test_only_selected_checker_properties_removed(self):
        attached,signals=attach(self.design,self.monitor)
        model,removed=independent(self.design,attached,signals)
        self.assertEqual(set(removed),{self.a,self.s})
        self.assertEqual(model['modules'][TOP]['cells']['reset_constraint'],
                         self.design['modules'][TOP]['cells']['reset_constraint'])
        for mutation in ('data','reset_constraint'):
            bad=copy.deepcopy(attached)
            bad['modules'][TOP]['cells'][mutation]['connections']['A']=['0']
            with self.assertRaises(ValueError): independent(self.design,bad,signals)
        bad=copy.deepcopy(attached);bad['modules'][TOP]['cells']['production_assert']=property_cell('assert',[4])
        with self.assertRaises(ValueError): independent(self.design,bad,signals)
        bad=copy.deepcopy(attached);bad['modules'][TOP]['cells'][self.s]['connections']['A']=['1']
        with self.assertRaises(ValueError): independent(self.design,bad,signals)

    def test_qualification_cuts_inputs_without_core_constraints(self):
        attached,signals=attach(self.design,self.monitor)
        cut=cone(attached['modules'][TOP],signals)['modules'][TOP]
        self.assertEqual(set(cut['cells']),{'__jalr_monitor_active','__jalr_monitor_holds'})
        inputs={b for p in cut['ports'].values() if p['direction']=='input' for b in p['bits']}
        self.assertEqual(inputs,{4,*range(20,25),*range(37,42)})
        self.assertTrue(all(c['type'] not in ('$assume','$assert') for c in cut['cells'].values()))

    def test_sequential_or_missing_qualification_driver_rejected(self):
        attached,signals=attach(self.design,self.monitor)
        for kind in ('$dff','$assume'):
            bad=copy.deepcopy(attached);bad['modules'][TOP]['cells']['__jalr_monitor_holds']['type']=kind
            with self.assertRaises(ValueError): cone(bad['modules'][TOP],signals)
        bad=copy.deepcopy(attached);del bad['modules'][TOP]['cells']['__jalr_monitor_holds']
        with self.assertRaises(ValueError): cone(bad['modules'][TOP],signals)


class WitnessTests(unittest.TestCase):
    def trace(self,reported=1,valid='1',reset='0',instruction=0x8067):
        return f"""$scope module rvfi_testbench $end
$var wire 1 v rvfi_valid $end
$var wire 32 i rvfi_insn $end
$var wire 5 a rvfi_rs1_addr $end
$scope module checker_inst $end
$var wire 1 r reset $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
1r
0v
b00000 a
#10
{reset}r
{valid}v
b{instruction:032b} i
b{reported:05b} a
#20
"""

    def test_cover_and_actual_address_fault_are_distinguished(self):
        self.assertEqual(active_witness(self.trace(),False)['expected_rs1'],1)
        self.assertEqual(active_witness(self.trace(reported=0),True)['reported_rs1'],0)
        for trace,fault in ((self.trace(),True),(self.trace(reported=0),False)):
            with self.assertRaises(ValueError): active_witness(trace,fault)

    def test_missing_unknown_reset_invalid_or_other_opcode_rejected(self):
        for text in ('',self.trace(valid='x'),self.trace(valid='0'),self.trace(reset='1'),
                     self.trace(instruction=0x8066),self.trace(instruction=0x67)):
            with self.subTest(text=text),self.assertRaises(ValueError): active_witness(text,False)


if __name__=='__main__': unittest.main()
