"""Target harness checks use synthetic netlists and independent VCD fixtures."""
import copy
import unittest
from check_jalr_target import TOP, attach, cone, target_witness, mutate_extension


class TargetHarnessTests(unittest.TestCase):
    def setUp(self):
        nets={'checker_inst.reset':[2],'checker_inst.rvfi_valid':[3],
              'checker_inst.rvfi_insn':list(range(4,36)),
              'checker_inst.rvfi_rs1_rdata':list(range(36,68)),
              'checker_inst.rvfi_pc_wdata':list(range(68,100))}
        self.original={'modules':{TOP:{'attributes':{},'ports':{},
            'netnames':{n:dict(bits=b,attributes={}) for n,b in nets.items()},
            'cells':{'cpu':dict(type='$anyseq',parameters={'WIDTH':'1100010'},attributes={},
                port_directions={'Y':'output'},connections={'Y':list(range(2,100))})}}}}
        ports={'reset':[2],'valid':[3],'instruction':list(range(4,36)),
               'sourceValue':list(range(36,68)),'reportedPc':list(range(68,100)),
               'active':[100],'holds':[101],'coverZero':[102],'coverOdd':[103],'coverNegative':[136],'faultActive':[137]}
        def cell(kind,conn):
            return dict(type=kind,parameters={},attributes={},connections=conn,
                        port_directions={p:'output' if p=='Y' else 'input' for p in conn})
        self.monitor={'ports':{n:dict(bits=b) for n,b in ports.items()},'cells':{
            'active':cell('$and',{'A':[2],'B':[3],'Y':[100]}),
            'sum':cell('$add',{'A':list(range(36,68)),'B':list(reversed(format(4,'032b'))),'Y':list(range(104,136))}),
            'holds':cell('$eq',{'A':list(range(68,100)),'B':list(range(104,136)),'Y':[101]}),
            'zero':cell('$not',{'A':[100],'Y':[102]}),
            'odd':cell('$not',{'A':[102],'Y':[103]}),
            'negative':cell('$not',{'A':[102],'Y':[136]}),
            'faultActive':cell('$not',{'A':[102],'Y':[137]})}}

    def test_graft_preserves_original_and_binds_full_pc_and_value(self):
        attached,signals=attach(self.original,self.monitor);m=attached['modules'][TOP]
        self.assertEqual(m['cells']['cpu'],self.original['modules'][TOP]['cells']['cpu'])
        self.assertEqual(m['cells']['__jalr_target_monitor_sum']['connections']['A'],list(range(36,68)))
        self.assertEqual(m['cells']['__jalr_target_monitor_holds']['connections']['A'],list(range(68,100)))
        self.assertEqual(set(signals),{'active','holds','coverZero','coverOdd','coverNegative','faultActive'})
        qualified=cone(m,{'holds':signals['holds']})['modules'][TOP]
        self.assertEqual(set(qualified['cells']),{'__jalr_target_monitor_sum','__jalr_target_monitor_holds'})
        inputs={b for p in qualified['ports'].values() if p['direction']=='input' for b in p['bits']}
        self.assertEqual(inputs,set(range(36,100)))

    def test_sign_extension_fault_changes_only_upper_immediate_bits(self):
        m={'modules':{TOP:{'cells':{'__jalr_target_monitor_add':{
            'type':'$add','parameters':{'A_WIDTH':'100000','B_WIDTH':'100000','Y_WIDTH':'100000',
                'A_SIGNED':'0','B_SIGNED':'0'},
            'connections':{'A':list(range(32)),'B':list(range(32,44))+[43]*20,
                           'Y':list(range(64,96))}}}}}}
        before=copy.deepcopy(m);mutate_extension(m)
        c=m['modules'][TOP]['cells']['__jalr_target_monitor_add']
        self.assertEqual(c['connections']['B'],list(range(32,44))+['0']*20)
        c['connections']['B']=before['modules'][TOP]['cells']['__jalr_target_monitor_add']['connections']['B']
        self.assertEqual(m,before)
        c['connections']['B'][12]=42
        with self.assertRaises(ValueError): mutate_extension(m)

    def test_sequential_qualification_and_width_mismatch_rejected(self):
        bad=copy.deepcopy(self.monitor);bad['ports']['sourceValue']['bits'].pop()
        with self.assertRaises(ValueError): attach(self.original,bad)
        attached,signals=attach(self.original,self.monitor)
        attached['modules'][TOP]['cells']['__jalr_target_monitor_sum']['type']='$dff'
        with self.assertRaises(ValueError): cone(attached['modules'][TOP],{'holds':signals['holds']})


class TargetWitnessTests(unittest.TestCase):
    def trace(self,rs1=1,source=0x100,imm=1,value=0x100,valid='1',reset='0'):
        insn=0x67|(rs1<<15)|((imm&0xfff)<<20)
        return f"""$scope module rvfi_testbench $end
$var wire 1 v rvfi_valid $end
$var wire 32 i rvfi_insn $end
$var wire 32 s rvfi_rs1_rdata $end
$var wire 32 d rvfi_pc_wdata $end
$scope module checker_inst $end
$var wire 1 r reset $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
{reset}r
{valid}v
b{insn:032b} i
b{source:032b} s
b{value:032b} d
#10
"""

    def test_zero_normalization_odd_sum_signed_offset_and_wrap(self):
        self.assertEqual(target_witness(self.trace(),'cover-odd')['expected'],'0x100')
        self.assertEqual(target_witness(self.trace(rs1=0,source=0xdeadbeef,value=0),'cover-zero')['expected'],'0x0')
        self.assertEqual(target_witness(self.trace(source=0,imm=-1,value=0xfffffffe),'cover-negative')['expected'],'0xfffffffe')
        self.assertEqual(target_witness(self.trace(source=0xffffffff,imm=2,value=0),'cover-odd')['expected'],'0x0')
        self.assertEqual(target_witness(self.trace(value=0x102),'fault')['encoded_rs1'],1)

    def test_fault_and_covers_require_actual_active_conditions(self):
        for text in (self.trace(),self.trace(rs1=0,value=2),self.trace(valid='0'),
                     self.trace(value=0x102,reset='1'),self.trace(value=0x102,valid='x'),''):
            with self.assertRaises(ValueError): target_witness(text,'fault')
        with self.assertRaises(ValueError): target_witness(self.trace(imm=0),'cover-odd')
        with self.assertRaises(ValueError): target_witness(self.trace(),'cover-negative')
        with self.assertRaises(ValueError): target_witness(self.trace(value=0x101),'cover-odd')


if __name__=='__main__': unittest.main()
