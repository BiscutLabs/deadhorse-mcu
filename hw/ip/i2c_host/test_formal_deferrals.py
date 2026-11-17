"""Behavioral receipt tests for retained, explicitly unproved formal work."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('i2c_deferred',Path(__file__).parent/'formal/deferred.py')
deferred=importlib.util.module_from_spec(spec);spec.loader.exec_module(deferred)


class RetainedDeferralTest(unittest.TestCase):
    def setUp(self):
        (ROOT/'build').mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=ROOT/'build')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name); (self.root/'build').mkdir()
        self.ident='T17-RECOVER-CORRECT'
        self.identity=dict(mode='bmc',engine='btor btormc',depth=256,timeout_seconds=120)
        self.sources={'Model.sv':'a'*64}
        row=dict(id=self.ident,solver_status='TIMEOUT',returncode=8,source_sha256=self.sources,
                 mode='bmc',engine='btor btormc',depth=256)
        artifacts={'receipt':json.dumps(dict(cases={'recover':dict(jobs=[row])})),
                   'status':'TIMEOUT 120\n','log':'DONE (TIMEOUT, rc=8)\n'}
        provenance={}
        for name,value in artifacts.items():
            path=self.root/'build'/name;path.write_text(value)
            provenance[name]=dict(path=path.relative_to(self.root).as_posix(),sha256=deferred.digest(path))
        self.entry=dict(id=self.ident,solver_status='TIMEOUT',returncode=8,identity=self.identity,
                        source_sha256=self.sources,provenance=provenance)

    def check(self, entry=None, identity=None, sources=None):
        return deferred.authenticate(entry or self.entry, identity or self.identity, sources or self.sources,self.root)

    def test_matching_timeout_is_explicitly_unproved_without_solver_execution(self):
        result=self.check()
        self.assertEqual(result['status'],'deferred_unproved')
        self.assertFalse(result['solver_rerun'])
        self.assertTrue(all(result['historical_artifacts_available'].values()))

    def test_environment_line_endings_preserve_historical_identity_and_raw_evidence(self):
        path=self.root/'build'/'environment.json'
        crlf=b'{\r\n  "tool": "version1"\r\n}\r\n'
        expected=hashlib.sha256(crlf).hexdigest()
        self.identity['environment_sha256']=expected
        for content in (crlf,crlf.replace(b'\r\n',b'\n')):
            path.write_bytes(content)
            actual=deferred.environment_digest(path)
            self.assertEqual(actual,expected)
            self.assertEqual(self.check(identity=dict(self.identity,environment_sha256=actual))['status'],'deferred_unproved')
            self.assertEqual(deferred.digest(path),hashlib.sha256(content).hexdigest())
        self.assertNotEqual(deferred.digest(path),expected)
        for content in (crlf.replace(b'version1',b'version2'),crlf[:-2],
                        crlf.replace(b'  "tool"',b' "tool"'),crlf.replace(b'version1',b'version\r1')):
            with self.subTest(content=content):
                path.write_bytes(content)
                actual=deferred.environment_digest(path)
                self.assertNotEqual(actual,expected)
                with self.assertRaisesRegex(ValueError,'model/job mismatch'):
                    self.check(identity=dict(self.identity,environment_sha256=actual))

    def test_missing_historical_build_artifacts_are_reported_not_fabricated(self):
        for artifact in self.entry['provenance'].values(): (self.root/artifact['path']).unlink()
        result=self.check()
        self.assertEqual(result['status'],'deferred_unproved')
        self.assertFalse(any(result['historical_artifacts_available'].values()))

    def test_changed_model_or_solver_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'model/job mismatch'):
            self.check(sources={'Model.sv':'b'*64})
        for field,value in (('depth',128),('engine','abc pdr'),('timeout_seconds',240)):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'model/job mismatch'):
                self.check(identity=dict(self.identity,**{field:value}))

    def test_present_tampered_evidence_fails_closed(self):
        for name in ('receipt','status','log'):
            with self.subTest(name=name):
                path=self.root/self.entry['provenance'][name]['path']; original=path.read_bytes()
                path.write_bytes(original+b'tamper')
                with self.assertRaisesRegex(ValueError,'hash mismatch'): self.check()
                path.write_bytes(original)

    def test_original_pass_or_wrong_attempt_cannot_be_relabeled_timeout(self):
        path=self.root/self.entry['provenance']['receipt']['path']
        original=json.loads(path.read_text())
        for field,value in (('solver_status','PASS'),('id','T17-WRITE-CORRECT'),('depth',128),('retained',True)):
            data=copy.deepcopy(original);data['cases']['recover']['jobs'][0][field]=value
            path.write_text(json.dumps(data)); entry=copy.deepcopy(self.entry)
            entry['provenance']['receipt']['sha256']=deferred.digest(path)
            with self.subTest(field=field),self.assertRaises(ValueError): self.check(entry=entry)

    def test_provenance_cannot_escape_repository_build(self):
        entry=copy.deepcopy(self.entry);entry['provenance']['log']['path']='../outside'
        with self.assertRaises(ValueError): self.check(entry=entry)

    def test_policy_rejects_unknown_duplicate_non_timeout_and_missing_hashes(self):
        path=self.root/'policy.json'
        def load(entries):
            path.write_text(json.dumps(dict(version=1,task='T17',entries=entries)))
            return deferred.load_policy(path,{self.ident})
        self.assertEqual(set(load([self.entry])),{self.ident})
        bad=copy.deepcopy(self.entry);bad['source_sha256']={}
        for entries in ([self.entry,self.entry],[dict(self.entry,id='unknown')],
                        [dict(self.entry,solver_status='PASS')],[bad]):
            with self.subTest(entries=entries),self.assertRaises(ValueError): load(entries)


if __name__=='__main__': unittest.main()
