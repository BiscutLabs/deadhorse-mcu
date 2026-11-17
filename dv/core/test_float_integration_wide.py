"""Boundary graft controls using small netlist fixtures, without RTL text tests."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from check_float_integration_wide import CHOICES, graft
from common import ROOT

sys.path.insert(0,str(ROOT/'hw/ip/perf_core/formal'))
import check_float_integration as integration


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


class IntegrationInputTests(unittest.TestCase):
    def setUp(self):
        directory=ROOT/'build/test_float_integration_inputs';directory.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name)
        self.production=self.directory/'production';self.production.mkdir()
        self.module=self.production/'core.sv';self.module.write_bytes(b'production fixture')
        self.source=self.directory/'source.txt';self.source.write_bytes(b'emission input fixture')
        self.qualification=self.directory/'qualification.json';self.qualification.write_bytes(b'qualification fixture')
        self.protected={}
        integration.protect(self.protected,[self.module,self.source,self.qualification])
        self.production_hashes={str(self.module.relative_to(ROOT)):self.protected[str(self.module)]}
        self.source_paths=[str(self.source)]
        self.patch=patch.object(integration,'emission_inputs',return_value=[self.source])
        self.patch.start();self.addCleanup(self.patch.stop)

    def verify(self):
        integration.verify_inputs(self.protected,self.production,self.production_hashes,self.source_paths)

    def test_frozen_inputs_pass_without_refreshing_hashes(self):
        original=copy.deepcopy(self.protected)
        self.verify();self.verify()
        self.assertEqual(self.protected,original)

    def test_production_emitter_and_qualification_mutations_rejected(self):
        for path in (self.module,self.source,self.qualification):
            with self.subTest(path=path.name):
                original=path.read_bytes();path.write_bytes(original+b' changed')
                with self.assertRaisesRegex(ValueError,'Proof input hash mismatch'):self.verify()
                path.write_bytes(original)
                self.verify()

    def test_added_or_removed_production_source_rejected(self):
        extra=self.production/'extra.sv';extra.write_bytes(b'extra fixture')
        with self.assertRaisesRegex(ValueError,'Production source inventory changed'):self.verify()
        extra.unlink();self.module.unlink()
        with self.assertRaisesRegex(ValueError,'Production source inventory changed'):self.verify()

    def test_emission_inventory_change_rejected(self):
        with patch.object(integration,'emission_inputs',return_value=[self.source,self.qualification]):
            with self.assertRaisesRegex(ValueError,'Emission input inventory changed'):self.verify()

    def test_controls_description_distinguishes_concrete_and_cutpoints(self):
        self.assertIn('no arithmetic cutpoints',integration.controls_description(True))
        self.assertIn('T12 combinational arithmetic cutpoints',integration.controls_description(False))
        self.assertNotIn('no arithmetic cutpoints',integration.controls_description(False))


if __name__=='__main__':unittest.main()
