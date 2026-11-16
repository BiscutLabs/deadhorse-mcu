import unittest
from compose_jalr_operands import payload_invariant, active_witness


class OperandCompositionTest(unittest.TestCase):
    def evaluate(self, valid, jalr, op, a, b, source, instruction):
        fields={'ownerValid':(valid,1),'ownerJalr':(jalr,1),'ownerOp':(op,7),
                'ownerA':(a,32),'ownerB':(b,32),'sourceNow':(source,32),'idInstruction':(instruction,32)}
        ports={};values={};fresh=1
        for name,(value,width) in fields.items():
            ports[name]=list(range(fresh,fresh+width))
            values.update({fresh+i:(value>>i)&1 for i in range(width)});fresh+=width
        m={'cells':{'seed':{'connections':{'A':list(values)}}}}
        result=payload_invariant(m,ports)
        def number(bits):return sum((int(b) if isinstance(b,str) else values[b])<<i for i,b in enumerate(bits))
        for name,c in m['cells'].items():
            if name=='seed':continue
            a=number(c['connections']['A']);b=number(c['connections']['B']) if 'B' in c['connections'] else 0
            value={'$eq':lambda:a==b,'$not':lambda:not a,'$and':lambda:a&b,'$or':lambda:a|b}[c['type']]()
            values[c['connections']['Y'][0]]=int(value)
        return bool(values[result[0]])

    def test_payload_matches_signed_immediate(self):
        for imm in (0,1,2047,-1,-2048):
            insn=((imm&4095)<<20)|0x8067
            self.assertTrue(self.evaluate(1,1,0,0xdeadbeef,imm&0xffffffff,0xdeadbeef,insn))
            self.assertFalse(self.evaluate(1,1,0,0xdeadbeee,imm&0xffffffff,0xdeadbeef,insn))
            self.assertFalse(self.evaluate(1,1,1,0xdeadbeef,imm&0xffffffff,0xdeadbeef,insn))
            self.assertFalse(self.evaluate(1,1,0,0xdeadbeef,(imm^1)&0xffffffff,0xdeadbeef,insn))

    def test_unowned_or_non_jalr_is_not_constrained(self):
        for valid,jalr in ((0,0),(0,1),(1,0)):
            self.assertTrue(self.evaluate(valid,jalr,127,42,43,44,0xffffffff))

    def test_active_response_witness(self):
        header='$scope module rvfi_testbench $end\n$var wire 1 a __request_capture $end\n$var wire 1 b __request_responseValid $end\n$upscope $end\n#10\n'
        self.assertEqual(active_witness(header+'1a\n0b\n#20\n',True)['values'],{'capture':1,'responseValid':0})
        self.assertEqual(active_witness(header+'1a\n1b\n#20\n')['values'],{'capture':1,'responseValid':1})
        for body,fault in [('0a\n0b\n',True),('1a\nxb\n',True),('1a\n1b\n',True)]:
            with self.assertRaises(ValueError):active_witness(header+body+'#20\n',fault)


if __name__=='__main__':unittest.main()
