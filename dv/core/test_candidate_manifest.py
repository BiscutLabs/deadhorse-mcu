"""Provenance/selection tests using synthetic bytes, never RTL behavior tests."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from candidate import INACTIVE, parameters, sources
from common import CONFIG, ROOT


class CandidateManifestTests(unittest.TestCase):
    def setUp(self):
        base=ROOT/'build/test_candidate_manifest'; base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.directory=Path(self.temp.name)
        self.lock={'sources':['rtl/ibex_alu.sv','rtl/ibex_top.sv',*INACTIVE]}
        self.data=dict(schema=2,kind='fixed',parameters=CONFIG['parameters'],excluded=dict(INACTIVE),
                       source_sha256={},extra_sources={},module_views={})
        for name in ('rtl/ibex_alu.sv','rtl/ibex_top.sv'):
            self.data['source_sha256'][name]=self.write(name,('primary:'+name).encode())
        self.data['extra_sources']['ClockGate.sv']=self.write('ClockGate.sv',b'gate fixture')
        digest=self.write('modules/alu/view.sv',b'standalone view fixture')
        self.data['module_views']['ibex_alu']={'rtl/ibex_alu.sv':dict(path='modules/alu/view.sv',sha256=digest)}
        self.save()
        self.mock=patch('candidate.inputs',return_value=self.lock); self.mock.start()

    def tearDown(self):
        self.mock.stop(); self.temp.cleanup()

    def write(self,name,data):
        path=self.directory/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def save(self):
        (self.directory/'candidate.json').write_text(json.dumps(self.data))

    def test_complete_manifest_and_separate_views(self):
        self.assertEqual(parameters(self.directory),{})
        out=self.directory/'out'; out.mkdir()
        top=sources(self.directory,self.lock,out)
        leaf=sources(self.directory,self.lock,out,module='ibex_alu')
        self.assertIn(str(self.directory/'rtl/ibex_alu.sv'),top)
        self.assertNotIn(str(self.directory/'modules/alu/view.sv'),top)
        self.assertIn(str(self.directory/'modules/alu/view.sv'),leaf)
        self.assertNotIn(str(self.directory/'rtl/ibex_alu.sv'),leaf)

    def test_active_source_and_extra_tampering_rejected(self):
        for name in ('rtl/ibex_alu.sv','ClockGate.sv'):
            path=self.directory/name; original=path.read_bytes(); path.write_bytes(original+b'changed')
            with self.assertRaises(ValueError): parameters(self.directory)
            path.write_bytes(original)

    def test_active_module_cannot_be_excluded(self):
        self.data['excluded']['rtl/ibex_alu.sv']='pretend disabled'
        self.data['source_sha256'].pop('rtl/ibex_alu.sv'); self.save()
        with self.assertRaises(ValueError): parameters(self.directory)

    def test_missing_module_and_changed_configuration_rejected(self):
        digest=self.data['source_sha256'].pop('rtl/ibex_alu.sv'); self.save()
        with self.assertRaises(ValueError): parameters(self.directory)
        self.data['source_sha256']['rtl/ibex_alu.sv']=digest
        self.data['parameters']=dict(CONFIG['parameters'],PMPEnable='1'); self.save()
        with self.assertRaises(ValueError): parameters(self.directory)

    def test_view_hash_and_path_escape_rejected(self):
        item=self.data['module_views']['ibex_alu']['rtl/ibex_alu.sv']
        original=item['sha256']; item['sha256']='0'*64; self.save()
        with self.assertRaises(ValueError): parameters(self.directory)
        item['sha256']=original; item['path']='../outside.sv'; self.save()
        with self.assertRaises(ValueError): parameters(self.directory)

    def test_unknown_extra_and_view_module_rejected(self):
        self.data['extra_sources']['unapproved.sv']=self.write('unapproved.sv',b'extra'); self.save()
        with self.assertRaises(ValueError): parameters(self.directory)
        self.data['extra_sources'].pop('unapproved.sv')
        self.data['module_views']['ibex_pmp']=self.data['module_views']['ibex_alu']; self.save()
        with self.assertRaises(ValueError): parameters(self.directory)

    def test_top_view_cannot_replace_primary_candidate(self):
        self.data['module_views']['ibex_top']={'rtl/ibex_top.sv':dict(
            path='rtl/ibex_top.sv',sha256=self.data['source_sha256']['rtl/ibex_top.sv'])}
        self.save()
        with self.assertRaises(ValueError): parameters(self.directory)

    def test_schema_one_cannot_smuggle_exclusions_or_views(self):
        self.data['schema']=1
        for source in INACTIVE:
            self.data['source_sha256'][source]=self.write(source,source.encode())
        for field in ('excluded','extra_sources','module_views'):
            original=dict(self.data)
            self.data={k:v for k,v in original.items() if k not in ('excluded','extra_sources','module_views') or k==field}
            self.save()
            with self.assertRaises(ValueError): parameters(self.directory)
            self.data=original

    def test_registered_profile_authenticates_extras_and_forbids_views(self):
        self.data['implementation']='registered-execution-v1'
        self.data['module_views']={}
        for name in ('ClockedExecute.sv','IterativeMultiply.sv'):
            self.data['extra_sources'][name]=self.write(name,('fixture:'+name).encode())
        self.save()
        self.assertEqual(parameters(self.directory),{})
        for name in ('ClockedExecute.sv','IterativeMultiply.sv'):
            original=self.data['extra_sources'].pop(name); self.save()
            with self.assertRaises(ValueError): parameters(self.directory)
            self.data['extra_sources'][name]='0'*64; self.save()
            with self.assertRaises(ValueError): parameters(self.directory)
            self.data['extra_sources'][name]=original
        self.data['module_views']={'ibex_alu':{'rtl/ibex_alu.sv':dict(
            path='rtl/ibex_alu.sv',sha256=self.data['source_sha256']['rtl/ibex_alu.sv'])}}
        self.save()
        with self.assertRaisesRegex(ValueError,'cannot substitute'): parameters(self.directory)


if __name__=='__main__': unittest.main()
