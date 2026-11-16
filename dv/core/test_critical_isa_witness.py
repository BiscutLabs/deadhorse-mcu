import unittest
from critical_isa_witness import active_witness


def trace(insn=0x00002083,check=1,result=9,trap=0):
    names={'reset':0,'check':check,'spec_valid':1,'spec_rd_wdata':9}
    rows=['$scope module rvfi_testbench $end','$scope module checker_inst $end']
    values=[]
    for i,(name,value) in enumerate(names.items()):
        token='c'+str(i);rows.append(f'$var wire 32 {token} {name} $end');values.append(f'b{value:b} {token}')
    rows.append('$upscope $end')
    for i,(name,value) in enumerate({'rvfi_valid':1,'rvfi_insn':insn,'rvfi_trap':trap,'rvfi_rd_wdata':result}.items()):
        token='r'+str(i);rows.append(f'$var wire 32 {token} {name} $end');values.append(f'b{value:b} {token}')
    return '\n'.join(rows+['$upscope $end','$enddefinitions $end','#0']+values+['#10'])


class WitnessTests(unittest.TestCase):
    def test_checked_cover_and_bit_fault(self):
        self.assertEqual(active_witness(trace(),'lw',False)['expected'],9)
        self.assertEqual(active_witness(trace(result=8),'lw',True)['values']['result'],8)
        self.assertEqual(active_witness(trace(insn=0x9086),'c_add',False)['expected'],9)
    def test_wrong_instruction_inactive_and_nonfault_rejected(self):
        for text,kind,fault in [(trace(check=0),'lw',False),(trace(insn=0x13),'lw',False),(trace(),'lw',True),(trace(trap=1),'lw',False)]:
            with self.assertRaises(ValueError):active_witness(text,kind,fault)


if __name__=='__main__':unittest.main()
