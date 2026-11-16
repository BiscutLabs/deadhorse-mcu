"""Partition transformation/fail-closed accounting against synthetic models."""
import copy
import unittest
from assertion_partitions import TOP,assertions,partition,validate_partition,validate_union,stabilize_generated_names

class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.design={'creator':'fixture','modules':{TOP:{'attributes':{'top':1},
            'ports':{'clock':{'bits':[1],'direction':'input'}},'netnames':{},'cells':{
            'a':{'type':'$assert','connections':{'A':[2],'EN':[3]},'parameters':{},'attributes':{'src':'a'}},
            'b':{'type':'$check','connections':{'A':[4],'EN':[5]},'parameters':{'FLAVOR':'assert'},'attributes':{}},
            'env':{'type':'$assume','connections':{'A':[6],'EN':['1']},'parameters':{},'attributes':{}},
            'data':{'type':'$not','connections':{'A':[7],'Y':[8]},'parameters':{},'attributes':{}}
        }}}}
    def test_partition_preserves_actual_expressions_and_environment(self):
        for name in ['a','b']:
            model=partition(self.design,[name]);cells=model['modules'][TOP]['cells']
            self.assertEqual(set(cells),{name,'env','data'})
            for item in cells: self.assertEqual(cells[item],self.design['modules'][TOP]['cells'][item])
        self.assertEqual(assertions(self.design),['a','b'])
    def test_mutations_rejected(self):
        valid=partition(self.design,['a'])
        for target in ('a','env','data'):
            bad=copy.deepcopy(valid);bad['modules'][TOP]['cells'][target]['connections']['A']=['0']
            with self.subTest(target=target),self.assertRaises(ValueError): validate_partition(self.design,bad,['a'])
        bad=copy.deepcopy(valid);bad['modules'][TOP]['cells']['a']['connections']['EN']=['0']
        with self.assertRaises(ValueError): validate_partition(self.design,bad,['a'])
        bad=copy.deepcopy(valid);bad['modules'][TOP]['cells']['b']=copy.deepcopy(self.design['modules'][TOP]['cells']['b'])
        bad['modules'][TOP]['cells']['b']['parameters']['FLAVOR']='assume'
        with self.assertRaises(ValueError): validate_partition(self.design,bad,['a'])
        other=copy.deepcopy(self.design);other['modules'][TOP]['ports']['clock']['bits']=[9]
        with self.assertRaises(ValueError): validate_partition(other,valid,['a'])
    def test_inventory_omission_duplication_and_unknown_rejected(self):
        validate_union(['a','b'],[['a'],['b']])
        for groups in ([['a']],[['a'],['a'],['b']],[['a'],['b'],['unknown']],[['a','b'],[]]):
            with self.subTest(groups=groups),self.assertRaises(ValueError): validate_union(['a','b'],groups)
        for selected in ([],['missing'],['a','a']):
            with self.assertRaises(ValueError): partition(self.design,selected)
    def test_generated_names_are_reversible_only(self):
        model=copy.deepcopy(self.design)
        model['modules'][TOP]['cells']['$auto$setundef.cc:1:execute$42']={
            'type':'$anyseq','parameters':{'WIDTH':'1'},'connections':{'Y':[42]},'attributes':{}}
        stable,mapping=stabilize_generated_names(model)
        self.assertEqual(len(mapping),1)
        old,new=next(iter(mapping.items()))
        self.assertEqual(stable['modules'][TOP]['cells'][new],model['modules'][TOP]['cells'][old])
        stable['modules'][TOP]['cells'][old]=stable['modules'][TOP]['cells'].pop(new)
        self.assertEqual(stable,model)
        model['modules'][TOP]['ports'][new]={'direction':'input','bits':[99]}
        with self.assertRaises(ValueError): stabilize_generated_names(model)
    def test_empty_or_unsupported_property_fails(self):
        bad=copy.deepcopy(self.design);bad['modules'][TOP]['cells']={}
        with self.assertRaises(ValueError): assertions(bad)
        bad=copy.deepcopy(self.design);bad['modules'][TOP]['cells']['b']['parameters']['FLAVOR']='unknown'
        with self.assertRaises(ValueError): assertions(bad)

if __name__=='__main__': unittest.main()
