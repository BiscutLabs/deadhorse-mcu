import unittest
from audit_request_kind import witness


class RequestKindWitnessTests(unittest.TestCase):
    def trace(self,capture,kind,first):
        return '\n'.join(['$scope module rvfi_testbench $end',
            '$var wire 1 a __phase_capture $end','$var wire 2 b __phase_requestKind $end',
            '$var wire 1 c __phase_requestFirst $end','$upscope $end','$enddefinitions $end',
            '#5',f'b{capture} a',f'b{kind:02b} b',f'b{first} c','#10'])

    def test_exact_active_capture_and_mutated_values(self):
        for role,kind,first in [('capture-cover',0,1),('kind-fault',1,1),('first-fault',0,0)]:
            self.assertEqual(witness(self.trace(1,kind,first),role)['values'],
                dict(capture=1,requestKind=kind,requestFirst=first))
            for c,k,f in [(0,kind,first),(1,kind^2,first),(1,kind,first^1)]:
                with self.assertRaises(ValueError):witness(self.trace(c,k,f),role)


if __name__=='__main__':unittest.main()
