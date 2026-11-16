"""Independent architectural arithmetic samples for the transport invariant."""
import random
import unittest
from compose_jalr_target import expected


def evaluate(module,values,output):
    def read(bits):return sum((int(b) if isinstance(b,str) else values[b])<<i for i,b in enumerate(bits))
    for c in module['cells'].values():
        p=c['connections'];a=read(p['A']);b=read(p['B']);kind=c['type']
        if kind=='$eq':result=int(a==b)
        elif kind=='$add':result=(a+b)&0xffffffff
        elif kind=='$mux':result=b if read(p['S']) else a
        else:raise ValueError(kind)
        for i,bit in enumerate(p['Y']):values[bit]=(result>>i)&1
    return read(output)


class TargetInvariantTests(unittest.TestCase):
    def test_signed_wrapping_and_x0_normalized_target(self):
        insn=list(range(1,33));source=list(range(33,65))
        m={'cells':{'placeholder':{'connections':{'A':insn+source}}}}
        target=expected(m,insn,source);del m['cells']['placeholder']
        rng=random.Random(178)
        for immediate in (-2048,-1,0,1,2047):
            for address in (0,1,0x7fffffff,0x80000000,0xffffffff,rng.getrandbits(32)):
                for rs1 in (0,1,31):
                    instruction=((immediate&4095)<<20)|(rs1<<15)|0x67
                    values={i+1:instruction>>i&1 for i in range(32)}
                    values.update({i+33:address>>i&1 for i in range(32)})
                    architectural=((0 if rs1==0 else address)+immediate)&0xfffffffe
                    self.assertEqual(evaluate(m,values,target),architectural)


if __name__=='__main__':unittest.main()
