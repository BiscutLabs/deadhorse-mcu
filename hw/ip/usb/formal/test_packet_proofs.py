"""Receipt and partition guards, using synthetic proof metadata (never RTL text)."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from packet_partition import predicate_hash, require_lemma, selected_model, qualified_assumptions, run_helpers
from packet_receipt import legacy_job


class PacketReceiptTests(unittest.TestCase):
    def setUp(self):
        self.model={'modules':{'M':{'cells':{
            'helper':{'type':'$assert','connections':{'A':[4],'EN':[5]}},
            'original':{'type':'$assert','connections':{'A':[6],'EN':[7]}},
            'reset_assumption':{'type':'$assume','connections':{'A':[8],'EN':['1']}}
        }}}}
        self.entry=dict(canonical_model_sha256='canonical',assertions=['helper'],
            predicate_sha256=predicate_hash(self.model,'M',{'helper'}),
            positive=dict(result='proved',mode='prove',solver_status='PASS',returncode=0,assumed_assertions=[]),
            negative=dict(result='fault_rejected'),real_negative=dict(result='fault_rejected'))

    def test_partition_preserves_guarded_predicate_and_existing_assumptions(self):
        original=copy.deepcopy(self.model)
        selected=selected_model(self.model,'M',{'original'},{'helper'})['modules']['M']['cells']
        self.assertEqual(self.model,original)
        self.assertEqual(selected['helper']['type'],'$assume')
        self.assertEqual(selected['helper']['connections'],{'A':[4],'EN':[5]})
        self.assertEqual(selected['original'],original['modules']['M']['cells']['original'])
        self.assertEqual(selected['reset_assumption'],original['modules']['M']['cells']['reset_assumption'])
        with self.assertRaises(ValueError):selected_model(self.model,'M',{'helper'},{'helper'})
        with self.assertRaises(ValueError):selected_model(self.model,'M',{'absent'},set())

    def test_missing_wrong_model_or_changed_guard_cannot_qualify(self):
        for change in ({},{'canonical_model_sha256':'different'},{'predicate_sha256':'different'}, {'assertions':['original']}):
            entry=dict(self.entry,**change) if change else {}
            with self.assertRaises(ValueError):require_lemma(entry,self.model,'M',{'helper'},'canonical')
        changed=copy.deepcopy(self.model);changed['modules']['M']['cells']['helper']['connections']['EN']=['1']
        with self.assertRaises(ValueError):require_lemma(self.entry,changed,'M',{'helper'},'canonical')

    def test_bounded_unknown_and_circular_evidence_cannot_qualify(self):
        for changes in ({'mode':'bmc'},{'result':'unresolved'},{'solver_status':'UNKNOWN'},
                        {'returncode':1},{'assumed_assertions':['original']},{'assumed_assertions':['helper']}):
            entry=copy.deepcopy(self.entry);entry['positive'].update(changes)
            with self.assertRaises(ValueError):require_lemma(entry,self.model,'M',{'helper'},'canonical')
        entry=copy.deepcopy(self.entry);entry['real_negative']={}
        with self.assertRaises(ValueError):require_lemma(entry,self.model,'M',{'helper'},'canonical')

    def test_missing_dependency_fails_closed(self):
        with self.assertRaises(ValueError):
            qualified_assumptions([dict(path='build/missing-packet-lemma/receipt.json',sha256='absent',assertions=['helper'])],
                                  self.model,'M','canonical')

    def test_wrong_geometry_and_conflicting_sources_fail_before_emission(self):
        base=Path('build/t19/packet-receipt-tests');base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            root=Path(folder);split=root/'split.json';refinement=root/'memory.json'
            split.write_text(json.dumps(dict(status='unresolved',jobs=[],source_sha256={'same':'first'})))
            refinement.write_text(json.dumps(dict(status='pass',expected_packet_bytes=8,source_sha256={'same':'first'})))
            with self.assertRaisesRegex(ValueError,'wrong-size'):
                run_helpers(root/'wrong-size',split,refinement,16)
            refinement.write_text(json.dumps(dict(status='pass',expected_packet_bytes=16,source_sha256={'same':'different'})))
            with self.assertRaisesRegex(ValueError,'Conflicting'):
                run_helpers(root/'wrong-source',split,refinement,16)

    def test_legacy_metadata_cannot_accept_changed_recipe(self):
        base=Path('build/t19/packet-receipt-tests');base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            directory=Path(folder)
            (directory/'job.sby').write_text('[options]\nmode bmc\ndepth 48\n')
            with self.assertRaisesRegex(ValueError,'Legacy job recipe'):
                legacy_job(dict(mode='prove',engine='abc pdr'),directory,'M')


if __name__=='__main__':unittest.main()
