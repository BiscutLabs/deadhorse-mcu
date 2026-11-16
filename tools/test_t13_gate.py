"""Fail-closed evidence graph controls for the focused T13 gate."""
import json
from pathlib import Path
import tempfile
import unittest
from t13_gate import verify_hashes, ROOT, add_recorded, equal_emission, read_receipt, sha, validate_critical, validate_shape, equivalence


class GateTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'build').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'build');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_stale_dependency_rejected_without_overwrite(self):
        p=self.root/'input';p.write_text('original');h=sha(p);protected={}
        add_recorded(protected,{str(p):h});p.write_text('changed')
        add_recorded(protected,{str(p):h})
        with self.assertRaisesRegex(ValueError,'mismatch'):verify_hashes(protected)
        self.assertEqual(protected[str(p)],h)
    def test_receipt_status_must_be_exact(self):
        p=self.root/'result.json';p.write_text(json.dumps({'status':'unresolved'}))
        with self.assertRaisesRegex(ValueError,'Incomplete'):read_receipt(p,{},'pass')
    def test_emission_addition_and_change_rejected(self):
        a=self.root/'a';b=self.root/'b';a.mkdir();b.mkdir()
        (a/'unit.sv').write_text('netlist');(b/'unit.sv').write_text('netlist')
        equal_emission(a,b,{})
        (a/'extra.sv').write_text('other')
        with self.assertRaisesRegex(ValueError,'differs'):equal_emission(a,b,{})
    def test_incomplete_equivalence_and_wrong_solver_outcome_rejected(self):
        source=self.root/'source';source.write_text('input')
        gold=self.root/'gold.json';gold.write_text('{}')
        candidate=self.root/'candidate.json';candidate.write_text('{}')
        metadata={'source_sha256':{str(source):sha(source)},'netlist_sha256':sha(gold)}
        result={'status':'failed','engine':'Yosys SAT','elaborations':{'gold':metadata},
            'gold':str(gold),'candidate':str(candidate)}
        receipt=self.root/'result.json';receipt.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'binding roles'):equivalence(receipt,{},'failed')
        result['elaborations']['candidate']=metadata;receipt.write_text(json.dumps(result))
        (self.root/'compare.ys').write_text('fixture')
        (self.root/'compare.log').write_text('SAT proof finished - no model found: SUCCESS!')
        with self.assertRaisesRegex(ValueError,'solver outcome'):equivalence(receipt,{},'failed')
        (self.root/'compare.log').write_text('SAT proof finished - model found: FAIL!')
        equivalence(receipt,{},'failed')

    def test_missing_protocol_role_rejected_despite_summary(self):
        data={'status':'pass','results':{'base':{'status':'proved'}}}
        with self.assertRaisesRegex(ValueError,'role inventory'):
            validate_shape('fpu-protocol-wide-confirmed',self.root,data,{})

    def test_missing_critical_and_abstract_cover_rejected(self):
        dependency=self.root/'input';dependency.write_text('stable')
        item={'checks':{'bmc':{'status':'PASS','concrete':False},
            'cover':{'status':'PASS','concrete':True,'witnesses':['trace']},
            'negative':{'status':'FAIL','concrete':True,'witnesses':['trace']}}}
        d={'status':'pass (bounded critical ISA only); no unbounded ISA proof','input_sha256':{str(dependency):sha(dependency)},
           'results':{'lw':item},'depth':144,'check_cycle':64,'timeout_seconds':120}
        p=self.root/'result.json';p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'inventory'):validate_critical(p,{})
        d['results']['c_add']=item
        for name in ('lw','c_add'):
            for role in ('bmc','cover','negative'):
                folder=self.root/name/role/'work';folder.mkdir(parents=True);(folder/'status').write_text('FAIL' if role=='negative' else 'PASS')
                item['checks'][role]['returncode']=2 if role=='negative' else 0
        d['results']['lw']['checks']['cover']['concrete']=False;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'not concrete'):validate_critical(p,{})


if __name__=='__main__':unittest.main()
