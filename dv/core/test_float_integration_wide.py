"""Boundary graft controls using small netlist fixtures, without RTL text tests."""
import copy
import unittest
from check_float_integration_wide import CHOICES, graft


def fixture():
    ports={'clock':{'direction':'input','bits':[2]},'reset':{'direction':'input','bits':[3]},
           'ready':{'direction':'output','bits':[4]}}
    old={'attributes':{},'ports':ports,'netnames':{},'cells':{}}
    parent={'attributes':{},'ports':{'clock':{'direction':'input','bits':[2]}},'netnames':{},
        'cells':{'fpu':{'type':'Fpu$test','parameters':{},'attributes':{},
            'port_directions':{p:v['direction'] for p,v in ports.items()},
            'connections':{p:v['bits'] for p,v in ports.items()}},
            'property':{'type':'$assert','parameters':{},'attributes':{},
                'port_directions':{'A':'input','EN':'input'},'connections':{'A':[4],'EN':['1']}}}}
    design={'modules':{'Top':parent,'Fpu$test':old}}
    new=copy.deepcopy(old);bit=5
    for name,width in CHOICES.items():
        new['ports'][name]={'direction':'input','bits':list(range(bit,bit+width))};bit+=width
    return design,new


class GraftTests(unittest.TestCase):
    def test_independent_choices_and_unchanged_property(self):
        original,model=fixture();snapshot=copy.deepcopy(original)
        changed,_=graft(original,model)
        self.assertEqual(original,snapshot)
        p=changed['modules']['Top'];self.assertEqual(p['cells']['property'],snapshot['modules']['Top']['cells']['property'])
        choices=[p['cells']['fpu']['connections'][n] for n in CHOICES]
        self.assertEqual(sum(map(len,choices)),len(set(sum(choices,[]))))
        self.assertTrue(all(p['cells']['__wide_choice_'+n]['type']=='$anyseq' for n in CHOICES))

    def test_changed_existing_port_rejected(self):
        original,model=fixture();model['ports']['ready']['direction']='input'
        with self.assertRaisesRegex(ValueError,'Existing FPU port'):graft(original,model)

    def test_missing_choice_or_duplicate_instance_rejected(self):
        original,model=fixture();del model['ports']['io_finish']
        with self.assertRaisesRegex(ValueError,'port inventory'):graft(original,model)
        original,model=fixture();original['modules']['Top']['cells']['second']=copy.deepcopy(original['modules']['Top']['cells']['fpu'])
        with self.assertRaisesRegex(ValueError,'not unique'):graft(original,model)


if __name__=='__main__':unittest.main()
