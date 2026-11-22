import copy
import unittest
from tools.timing.usb_async import boolean_function,audit_checks,split_violations


class AsyncTests(unittest.TestCase):
    def test_boolean_library_parser(self):
        for a in (False,True):
            for b in (False,True):
                for c in (False,True):
                    values={'A':a,'B':b,'C':c}
                    self.assertEqual(boolean_function('!(A & B) | C',values),not(a and b) or c)
                    self.assertEqual(boolean_function('A ^ B & C',values),a!=(b and c))
        for bad in ('__import__(x)','A;B','A B','(A','A)'):
            with self.assertRaises(ValueError):boolean_function(bad,{'A':True,'B':False})

    def test_every_endpoint_and_polarity_required(self):
        expected=[('reset/interstage',m,'a/Q','b/D') for m in ('max_rise','max_fall','min_rise','min_fall')]
        rows=[dict(zip(('kind','mode','start','end'),r)) for r in expected]
        audit_checks(rows,expected)
        for bad in (rows[:-1],rows+rows[:1],[dict(r,end='wrong/D') for r in rows],
                    [dict(r,mode='min_fall') for r in rows]):
            with self.assertRaises(ValueError):audit_checks(bad,expected)

    def test_only_exact_async_sinks_change_acceptance(self):
        qualified={'status':'pass','inventory':{'sinks':{'a/D':dict(kind='sampler',sources=['dpRx']),
                                                     'r/RN':dict(kind='reset-release')}}}
        rows=[dict(check='hold/min_rise',start=start,end=end,slack_ns=-1) for start,end in
              [('dpRx','a/D'),('bus_bits_wdata[0]','a/D'),('dpRx','b/D'),('x/Q','b/D')]]
        rows+=[dict(check='reset/min_rise',start='vbus',end='r/RN',slack_ns=-1)]
        retained,raw=split_violations(rows,qualified)
        self.assertEqual(len(retained),3);self.assertEqual(len(raw),2)
        self.assertEqual(rows[0]['slack_ns'],-1)
        bad=copy.deepcopy(qualified);bad['status']='fail'
        with self.assertRaises(ValueError):split_violations(rows,bad)


if __name__=='__main__':unittest.main()
