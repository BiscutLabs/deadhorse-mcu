"""Link harness checks use synthetic netlists and independent VCD fixtures."""
import copy
import unittest
from check_jalr_link import TOP, attach, cone, link_witness, mutate_increment


class LinkHarnessTests(unittest.TestCase):
    def setUp(self):
        nets={'checker_inst.reset':[2],'checker_inst.rvfi_valid':[3],
              'checker_inst.rvfi_insn':list(range(4,36)),
              'checker_inst.rvfi_pc_rdata':list(range(36,68)),
              'checker_inst.rvfi_rd_wdata':list(range(68,100))}
        self.original={'modules':{TOP:{'attributes':{},'ports':{},
            'netnames':{n:dict(bits=b,attributes={}) for n,b in nets.items()},
            'cells':{'cpu':dict(type='$anyseq',parameters={'WIDTH':'1100010'},attributes={},
                port_directions={'Y':'output'},connections={'Y':list(range(2,100))})}}}}
        ports={'reset':[2],'valid':[3],'instruction':list(range(4,36)),
               'retiredPc':list(range(36,68)),'reportedValue':list(range(68,100)),
               'active':[100],'holds':[101],'coverZero':[102],'coverLink':[103]}
        def cell(kind,conn):
            return dict(type=kind,parameters={},attributes={},connections=conn,
                        port_directions={p:'output' if p=='Y' else 'input' for p in conn})
        self.monitor={'ports':{n:dict(bits=b) for n,b in ports.items()},'cells':{
            'active':cell('$and',{'A':[2],'B':[3],'Y':[100]}),
            'sum':cell('$add',{'A':list(range(36,68)),'B':list(reversed(format(4,'032b'))),'Y':list(range(104,136))}),
            'holds':cell('$eq',{'A':list(range(68,100)),'B':list(range(104,136)),'Y':[101]}),
            'zero':cell('$not',{'A':[100],'Y':[102]}),
            'link':cell('$not',{'A':[102],'Y':[103]})}}

    def test_graft_preserves_original_and_binds_full_pc_and_value(self):
        attached,signals=attach(self.original,self.monitor);m=attached['modules'][TOP]
        self.assertEqual(m['cells']['cpu'],self.original['modules'][TOP]['cells']['cpu'])
        self.assertEqual(m['cells']['__jalr_link_monitor_sum']['connections']['A'],list(range(36,68)))
        self.assertEqual(m['cells']['__jalr_link_monitor_holds']['connections']['A'],list(range(68,100)))
        self.assertEqual(set(signals),{'active','holds','coverZero','coverLink'})
        qualified=cone(m,{'holds':signals['holds']})['modules'][TOP]
        self.assertEqual(set(qualified['cells']),{'__jalr_link_monitor_sum','__jalr_link_monitor_holds'})
        inputs={b for p in qualified['ports'].values() if p['direction']=='input' for b in p['bits']}
        self.assertEqual(inputs,set(range(36,100)))

    def test_increment_fault_handles_optimized_constant_width(self):
        for width in (3,32):
            m={'modules':{TOP:{'cells':{'__jalr_link_monitor_add':{
                'type':'$add','parameters':{'A_WIDTH':'100000','Y_WIDTH':'100000',
                    'B_WIDTH':format(width,'b'),'A_SIGNED':'0','B_SIGNED':'0'},
                'connections':{'A':list(range(32)),'B':list(reversed(format(4,f'0{width}b'))),
                               'Y':list(range(32,64))}}}}}}
            mutate_increment(m);c=m['modules'][TOP]['cells']['__jalr_link_monitor_add']
            self.assertEqual(int(''.join(reversed(c['connections']['B'])),2),8)
            self.assertEqual(int(c['parameters']['B_WIDTH'],2),32)
            c['connections']['B']=list(reversed(format(4,'032b')));c['parameters']['A_SIGNED']='1'
            with self.assertRaises(ValueError): mutate_increment(m)

    def test_sequential_qualification_and_width_mismatch_rejected(self):
        bad=copy.deepcopy(self.monitor);bad['ports']['retiredPc']['bits'].pop()
        with self.assertRaises(ValueError): attach(self.original,bad)
        attached,signals=attach(self.original,self.monitor)
        attached['modules'][TOP]['cells']['__jalr_link_monitor_sum']['type']='$dff'
        with self.assertRaises(ValueError): cone(attached['modules'][TOP],{'holds':signals['holds']})


class LinkWitnessTests(unittest.TestCase):
    def trace(self,rd=1,pc=0x100,value=0x104,valid='1',reset='0'):
        insn=0x67|(rd<<7)  # rs1=0 remains in scope.
        return f"""$scope module rvfi_testbench $end
$var wire 1 v rvfi_valid $end
$var wire 32 i rvfi_insn $end
$var wire 32 p rvfi_pc_rdata $end
$var wire 32 d rvfi_rd_wdata $end
$scope module checker_inst $end
$var wire 1 r reset $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
{reset}r
{valid}v
b{insn:032b} i
b{pc:032b} p
b{value:032b} d
#10
"""

    def test_link_zero_and_wraparound(self):
        self.assertEqual(link_witness(self.trace(),'cover-link')['reported'],'0x104')
        self.assertEqual(link_witness(self.trace(rd=0,value=0),'cover-zero')['reported'],'0x0')
        self.assertEqual(link_witness(self.trace(pc=0xfffffffc,value=0),'cover-link')['expected'],'0x0')
        self.assertEqual(link_witness(self.trace(value=0x105),'fault')['encoded_rd'],1)

    def test_fault_requires_nonzero_destination_and_real_mismatch(self):
        for text in (self.trace(),self.trace(rd=0,value=1),self.trace(valid='0'),
                     self.trace(value=0x105,reset='1'),self.trace(value=0x105,valid='x'),''):
            with self.assertRaises(ValueError): link_witness(text,'fault')
        with self.assertRaises(ValueError): link_witness(self.trace(value=0x108),'cover-link')


if __name__=='__main__': unittest.main()
