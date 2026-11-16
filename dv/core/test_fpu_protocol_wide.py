import unittest
from unittest.mock import patch
from pathlib import Path
from qualify_fpu_protocol_wide import invariant, states, protect


class FpuProtocolWideTest(unittest.TestCase):
    def evaluate(self,state,ready,busy,valid):
        s={'state':[1,2,3,4],'ready':[5],'busy':[6],'valid':[7]}
        values={i+1:(state>>i)&1 for i in range(4)};values.update({5:ready,6:busy,7:valid})
        m={'cells':{'seed':{'connections':{'A':list(values)}}}}
        result=invariant(m,s)
        def number(bits):return sum((int(b) if isinstance(b,str) else values[b])<<i for i,b in enumerate(bits))
        for n,c in m['cells'].items():
            if n=='seed':continue
            a=number(c['connections']['A']);b=number(c['connections']['B']) if 'B' in c['connections'] else 0
            v={'$eq':lambda:a==b,'$le':lambda:a<=b,'$not':lambda:not a,'$and':lambda:a&b}[c['type']]()
            values[c['connections']['Y'][0]]=int(v)
        return bool(values[result[0]])

    def test_control_state_table(self):
        for state in range(16):
            expected=(1,0,0) if state==0 else (0,1,1) if state==13 else (0,1,0)
            for flags in range(8):
                values=((flags>>2)&1,(flags>>1)&1,flags&1)
                self.assertEqual(self.evaluate(state,*values),state<14 and values==expected)

    def test_state_clock_and_reset_rejected(self):
        m={'ports':{'clock':{'bits':[1]},'reset':{'bits':[2]}},'netnames':{'valid':{'bits':[3]}},
           'cells':{'q':{'type':'$aldff','parameters':{'CLK_POLARITY':'1','ALOAD_POLARITY':'1','WIDTH':'1'},
               'connections':{'Q':[3],'D':[4],'CLK':[1],'ALOAD':[2],'AD':['0']}}}}
        self.assertIn('valid',states(m,('valid',)))
        m['cells']['q']['connections']['CLK']=[5]
        with self.assertRaises(ValueError):states(m,('valid',))

    def test_protected_hash_never_overwritten(self):
        p=Path('source');inventory={str(p):'old'}
        with patch('qualify_fpu_protocol_wide.digest',return_value='new'):
            with self.assertRaises(ValueError):protect(inventory,[p])
        self.assertEqual(inventory[str(p)],'old')


if __name__=='__main__':unittest.main()
