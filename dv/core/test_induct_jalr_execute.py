"""Behavioral fixtures for exact transition-cone extraction boundaries."""
import copy
import unittest
from induct_jalr_execute import cut_cone


class ExecuteConeTests(unittest.TestCase):
    def fixture(self):
        return {'ports':{'external':dict(direction='input',bits=[1])},'cells':{
            'state':dict(type='$aldff',parameters={},port_directions=dict(D='input',Q='output'),
                         connections=dict(D=[99],Q=[2])),
            'mix':dict(type='$xor',parameters={},port_directions=dict(A='input',B='input',Y='output'),
                       connections=dict(A=[1],B=[2],Y=[3])),
            'irrelevant':dict(type='$mul',parameters={},port_directions=dict(A='input',B='input',Y='output'),
                       connections=dict(A=[22],B=[23],Y=[24]))}}

    def test_state_is_universal_boundary_and_combination_is_exact(self):
        original=self.fixture();before=copy.deepcopy(original)
        result=cut_cone(original,{'observed':[3]})
        self.assertEqual(result['cells'],{'mix':original['cells']['mix']})
        self.assertEqual({p['bits'][0] for p in result['ports'].values() if p['direction']=='input'},{1,2})
        self.assertEqual(original,before)

    def test_reject_missing_or_ambiguous_internal_driver(self):
        original=self.fixture()
        with self.assertRaises(ValueError):cut_cone(original,{'bad':[99]})
        original['cells']['duplicate']=copy.deepcopy(original['cells']['mix'])
        with self.assertRaises(ValueError):cut_cone(original,{'bad':[3]})


if __name__=='__main__':unittest.main()
