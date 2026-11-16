import copy
import unittest

from float_compare import effect,interrupt_reentry
from lockstep import completion_window


class FloatComparisonTests(unittest.TestCase):
    def test_f0_and_operand_classes(self):
        x={i:0 for i in range(32)}; f={i:0x3f800000+i for i in range(32)}
        # FADD f0,f1,f2; FMV.X.W x0,f1; FSW f2,0(x3).
        self.assertEqual(effect(0x00208053,x,f),(0,0,{1:1,2:2},None))
        self.assertEqual(effect(0xe0008053,x,f),(0,None,{1:1},None))
        x[3]=0x80001000
        self.assertEqual(effect(0x0021a027,x,f),(0,None,{2:2},(True,0x80001000,4,f[2])))

    def test_only_identical_msip_clear_cause_read_reentry_is_removed(self):
        base=0x8000020c
        binary=b''.join(i.to_bytes(4,'little') for i in (0x000d2023,0x34202c73,0x30200073))
        x={i:0 for i in range(32)}; x[26]=0x02000000
        before=dict(pc=base,regs=x,fregs={i:0 for i in range(32)},mstatus=0x80007880,
                    mcause=0x80000003,mepc=0x80000080,mtvec=0x80000201)
        current=copy.deepcopy(before); current['pc']+=4
        rows=[before,current,copy.deepcopy(current)]
        normalized,duplicates=interrupt_reentry(rows,binary,base)
        self.assertEqual(normalized,rows[:2]); self.assertEqual(len(duplicates),1)
        for fault in ('float-state','integer-state','enabled-irq','wrong-cause','wrong-address','wrong-instruction'):
            broken=copy.deepcopy(rows); image=binary
            if fault=='float-state': broken[-1]['fregs'][0]=1
            elif fault=='integer-state': broken[-1]['regs'][24]=1
            elif fault=='enabled-irq':
                for row in broken: row['mstatus']|=8
            elif fault=='wrong-cause':
                for row in broken: row['mcause']=0x80000007
            elif fault=='wrong-address':
                for row in broken: row['regs'][26]=0x02000004
            else: image=binary[:4]+(0x34102c73).to_bytes(4,'little')+binary[8:]
            got,rejected=interrupt_reentry(broken,image,base)
            self.assertEqual(got,broken,fault); self.assertEqual(rejected,[],fault)

    def test_compressed_finisher_requires_inert_tail_and_unchanged_float_state(self):
        base=0x80000080
        # C.SW x15,0(x14); C.J . (real compiler-selected hard-float finisher).
        binary=(0xc31c).to_bytes(2,'little')+(0xa001).to_bytes(2,'little')+bytes(4)
        x={i:0 for i in range(32)}; x[14]=0x100000; x[15]=0x5555
        before=dict(pc=base,regs=x,fregs={i:0 for i in range(32)},mstatus=0x6000)
        after=copy.deepcopy(before); after['pc']+=2
        rows=[before,after,copy.deepcopy(after)]
        self.assertEqual(completion_window(rows,binary,base,True),rows[:2])
        with self.assertRaises(ValueError): completion_window(rows,binary,base)
        rows[-1]['fregs'][0]=1
        with self.assertRaises(ValueError): completion_window(rows,binary,base,True)


if __name__=='__main__': unittest.main()
