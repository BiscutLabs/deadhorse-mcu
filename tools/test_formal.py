"""T14 gate-policy tests use synthetic result/IR fixtures, never RTL source text."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import formal


class FormalGateTests(unittest.TestCase):
    def setUp(self):
        base=formal.ROOT/'build/t14/formal-runner-tests'
        base.mkdir(parents=True,exist_ok=True)
        self.work=tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.work.cleanup)
        self.root=Path(self.work.name)

    def witness(self, name='trace.vcd'):
        directory=self.root/'engine_0'
        directory.mkdir(exist_ok=True)
        (directory/name).write_text('$enddefinitions $end\n#0\n#10\n')

    def test_exact_four_authorized_deferrals_and_active_counts(self):
        bus=formal.approved_plan('bus')
        bridge=formal.approved_plan('bus_bridge')
        self.assertEqual([i for p in (bus,bridge) for i,_ in p['deferred']],[
            'T14-BUS-FAIR-M0','T14-BUS-FAIR-M1','T14-BUS-FAIR-M2','T14-BRIDGE-RETURN-DATA'])
        self.assertEqual([len(g) for g in bus['groups'].values()],[31])
        self.assertEqual([len(g) for g in bridge['groups'].values()],[3,2,8])
        self.assertEqual(bridge['deferred'][0][1],'assert__chisel3_builtin_6')

    def test_unapproved_exclusion_relabel_missing_and_duplicate_groups_fail(self):
        original=formal.approved_plan('bus_bridge')
        variations=[]
        p=copy.deepcopy(original);p['deferred']=(('T14-BRIDGE-RETURN-DATA','assert__chisel3_builtin_7'),);variations.append(p)
        p=copy.deepcopy(original);p['full']=p['full'][:-1]+('renamed',);variations.append(p)
        p=copy.deepcopy(original);del p['groups']['control'];variations.append(p)
        p=copy.deepcopy(original);p['groups']['duplicate']=p['groups']['target_dispatch'];variations.append(p)
        for value in variations:
            with self.subTest(value=value),self.assertRaises(ValueError):
                formal.validate_plan(value)

    def test_harness_integrity_binding_rejects_reordered_content(self):
        source=b'reviewed property a\nreviewed property b\n'
        digest=hashlib.sha256(source).hexdigest()
        with patch.dict(formal.PROPERTY_BINDINGS,{'bus':('synthetic',digest)}):
            self.assertEqual(formal.validate_binding('bus',source.replace(b'\n',b'\r\n')),digest)
            with self.assertRaises(ValueError):
                formal.validate_binding('bus',b'reviewed property b\nreviewed property a\n')

    def test_real_yosys_exact_name_guards_reject_same_count_rename(self):
        names=formal.assertion_names(34)
        def execute(actual,label):
            fixture=self.root/(label+'.json')
            fixture.write_text(json.dumps({'modules':{'fixture':{'attributes':{},'ports':{},
                'netnames':{},'cells':{name:{'type':'$assert','parameters':{},'attributes':{},
                    'port_directions':{'A':'input','EN':'input'},'connections':{'A':['1'],'EN':['1']}}
                    for name in actual}}}}))
            script=self.root/(label+'.ys')
            script.write_text('\n'.join(['read_json '+str(fixture),*formal.property_guards('assert',names)]))
            result=subprocess.run(['yosys','-Q','-T','-s',str(script)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            (self.root/(label+'.log')).write_text(result.stdout)
            return result.returncode
        self.assertEqual(execute(names,'correct'),0)
        self.assertNotEqual(execute(('unknown',)+names[1:],'renamed'),0)

    def test_every_active_group_cover_and_fault_is_required(self):
        jobs=['cover','corrupt','correct_source_dispatch','correct_target_dispatch','correct_control']
        good=dict.fromkeys(jobs,'pass')
        self.assertEqual(formal.gate_status(jobs,good,True),'pass_with_deferrals')
        for missing in jobs:
            result=good.copy();del result[missing]
            with self.subTest(missing=missing),self.assertRaises(RuntimeError):
                formal.gate_status(jobs,result,True)
        for status in ('TIMEOUT','unresolved','failed','bounded'):
            result=good.copy();result['correct_control']=status
            with self.subTest(status=status),self.assertRaises(RuntimeError):
                formal.gate_status(jobs,result,True)

    def test_timeout_unknown_and_wrong_exit_fail_even_with_witness(self):
        self.witness()
        for mode,code,status in [('proof',8,'TIMEOUT'),('proof',0,'UNKNOWN'),
                ('proof',1,'PASS'),('negative',0,'FAIL'),('negative',0,'PASS')]:
            with self.subTest(mode=mode,code=code,status=status),self.assertRaises(RuntimeError):
                formal.validate_job(self.root,mode,code,status)

    def test_cover_and_negative_require_concrete_noninduction_witness(self):
        for mode,code,status in [('cover',0,'PASS'),('negative',2,'FAIL')]:
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):
                formal.validate_job(self.root,mode,code,status)
        self.witness('trace_induct.vcd')
        with self.assertRaises(RuntimeError):
            formal.validate_job(self.root,'negative',2,'FAIL')
        self.witness()
        formal.validate_job(self.root,'cover',0,'PASS')

    def test_named_fault_must_hit_intended_data_property(self):
        self.witness()
        log=self.root/'logfile.txt'
        log.write_text('failed assertion BridgeFormal.assert__chisel3_builtin_6 at fixture:1 step 38\n')
        expected=formal.FAULT_PROPERTIES['bus_bridge']
        self.assertEqual(formal.validate_job(self.root,'negative',2,'FAIL',expected),['assert__chisel3_builtin_6'])
        log.write_text('failed assertion BridgeFormal.assert__chisel3_builtin_2 at fixture:1 step 12\n')
        with self.assertRaises(RuntimeError):
            formal.validate_job(self.root,'negative',2,'FAIL',expected)
        log.write_text('')
        with self.assertRaises(RuntimeError):
            formal.validate_job(self.root,'negative',2,'FAIL',expected)

    def test_btor_fault_index_requires_matching_property_and_concrete_trace(self):
        self.witness()
        (self.root/'logfile.txt').write_text('')
        (self.root/'model').mkdir()
        (self.root/'model/design_btor.btor').write_text(
            '1 sort bitvec 1\n2 input 1 x\n3 bad 2 assert__chisel3_builtin_2\n4 bad 2 assert__chisel3_builtin_6\n')
        witness=self.root/'engine_0/trace.wit'
        witness.write_text('sat\nb1\n#0\n.\n')
        expected=formal.FAULT_PROPERTIES['bus_bridge']
        self.assertEqual(formal.validate_job(self.root,'negative',2,'FAIL',expected),['assert__chisel3_builtin_6'])
        witness.write_text('sat\nb0\n#0\n.\n')
        with self.assertRaises(RuntimeError):
            formal.validate_job(self.root,'negative',2,'FAIL',expected)
        witness.write_text('sat\nb99\n#0\n.\n')
        with self.assertRaises(ValueError):
            formal.validate_job(self.root,'negative',2,'FAIL',expected)


if __name__=='__main__':
    unittest.main()
