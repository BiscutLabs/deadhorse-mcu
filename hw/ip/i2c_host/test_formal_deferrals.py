"""Behavioral receipt tests for retained, explicitly unproved formal work."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

    def compatible_fixture(self):
        self.identity['environment_sha256']='f71eedeba5148822a8fd95764f3f931c6ea96f6c370d3aac1dc8ee14e8b51e2a'
        path=self.root/'build'/'environment.json'
        path.write_bytes((ROOT/'tools/env/lock.json').read_bytes())
        current=dict(self.identity,environment_sha256=deferred.environment_digest(path))
        # Exercise full original identity authentication as well as old rows
        # whose provenance predates that field.
        receipt=self.root/self.entry['provenance']['receipt']['path']
        content=json.loads(receipt.read_text())
        content['cases']['recover']['jobs'][0]['identity']=copy.deepcopy(self.identity)
        receipt.write_text(json.dumps(content))
        self.entry['provenance']['receipt']['sha256']=deferred.digest(receipt)
        return path,current

    def test_exact_openocd_extension_retains_timeout_and_both_environment_identities(self):
        path,current=self.compatible_fixture()
        content=path.read_bytes().replace(b'\r\n',b'\n')
        for value in (content,content.replace(b'\n',b'\r\n')):
            path.write_bytes(value)
            result=deferred.authenticate(self.entry,current,self.sources,self.root,path)
            self.assertEqual(result['status'],'deferred_unproved')
            self.assertTrue(result['retained']);self.assertFalse(result['solver_rerun'])
            self.assertEqual(result['original_identity'],self.identity)
            binding=result['environment_compatibility']
            self.assertEqual(binding['actual_environment_sha256'],current['environment_sha256'])
            self.assertEqual(binding['original_environment_sha256'],self.identity['environment_sha256'])
            self.assertNotEqual(binding['actual_environment_sha256'],binding['original_environment_sha256'])
        with self.assertRaisesRegex(ValueError,'model/job mismatch'):
            deferred.authenticate(self.entry,current,self.sources,self.root)

    def test_lock_compatibility_rejects_changed_tools_packages_config_and_serialization(self):
        path,current=self.compatible_fixture();original=json.loads(path.read_text())
        mutations=[]
        for field,value in [('base','changed'),('apt_snapshot','changed')]:
            changed=copy.deepcopy(original);changed[field]=value;mutations.append(changed)
        for field in ('archives','sources'):
            changed=copy.deepcopy(original);changed[field][0]['sha256']='0'*64;mutations.append(changed)
        changed=copy.deepcopy(original);changed['versions']['firtool']='changed';mutations.append(changed)
        changed=copy.deepcopy(original);changed['apt_packages'].append('extra');mutations.append(changed)
        changed=copy.deepcopy(original);changed['apt_packages'][-1]='changed';mutations.append(changed)
        changed=copy.deepcopy(original);changed['versions']['openocd']='changed';mutations.append(changed)
        for name in ('openocd.tar.gz','jimtcl.tar.gz'):
            changed=copy.deepcopy(original)
            next(a for a in changed['sources'] if a['name']==name)['commit']='0'*40
            mutations.append(changed)
        changed=copy.deepcopy(original);changed['openocd_configure'].append('--changed');mutations.append(changed)
        contents=[(json.dumps(m,indent=2)+'\n').encode() for m in mutations]
        canonical=(json.dumps(original,indent=2)+'\n').encode()
        contents.extend([canonical[:-1],canonical.replace(b'  "schema"',b' "schema"')])
        for index,content in enumerate(contents):
            path.write_bytes(content)
            # Both honest changed hashes and a forged claim of the approved
            # hash must fail against the actual file contents.
            for claimed in (current,dict(current,environment_sha256=deferred.environment_digest(path))):
                with self.subTest(index=index,identity=claimed),self.assertRaisesRegex(ValueError,'model/job mismatch'):
                    deferred.authenticate(self.entry,claimed,self.sources,self.root,path)

    def test_lock_bridge_cannot_hide_a_changed_job_model_or_old_policy(self):
        path,current=self.compatible_fixture()
        for field,value in [('depth',128),('engine','abc pdr'),('timeout_seconds',240)]:
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'model/job mismatch'):
                deferred.authenticate(self.entry,dict(current,**{field:value}),self.sources,self.root,path)
        with self.assertRaisesRegex(ValueError,'model/job mismatch'):
            deferred.authenticate(self.entry,current,{'Model.sv':'b'*64},self.root,path)
        changed=copy.deepcopy(self.entry);changed['identity']['environment_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'model/job mismatch'):
            deferred.authenticate(changed,current,self.sources,self.root,path)
        artifact=self.root/self.entry['provenance']['log']['path'];artifact.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            deferred.authenticate(self.entry,current,self.sources,self.root,path)

    def rename_fixture(self):
        # Opaque receipt-tool fixtures, not RTL behavior tests or HDL models.
        before=('fixture reset-value=0; assertion=original;\n'+'\n'.join(
            deferred.REGBLOCK_RENAMES)+'\n').encode()
        after=('fixture reset-value=0; assertion=original;\n'+'\n'.join(
            deferred.REGBLOCK_RENAMES.values())+'\n').encode()
        def sha(b):return hashlib.sha256(b).hexdigest()
        source=self.root/'build'/'RegBlock.sv';source.write_bytes(after)
        prop=self.root/'build'/'Property.sv';prop.write_bytes(b'original property fixture\n')
        old={'RegBlock.sv':sha(before),'Property.sv':deferred.digest(prop)}
        new=dict(old,**{'RegBlock.sv':sha(after)})
        self.entry['source_sha256']=old
        path=self.root/self.entry['provenance']['receipt']['path']
        receipt=json.loads(path.read_text())
        receipt['cases']['recover']['jobs'][0]['source_sha256']=old
        path.write_text(json.dumps(receipt));self.entry['provenance']['receipt']['sha256']=deferred.digest(path)
        return old,new,{'RegBlock.sv':source,'Property.sv':prop}

    def test_exact_rename_authenticates_original_timeout_and_current_files(self):
        old,new,files=self.rename_fixture()
        with patch.object(deferred,'REGBLOCK_HASH_PAIRS',{old['RegBlock.sv']:new['RegBlock.sv']}):
            row=deferred.authenticate(self.entry,self.identity,new,self.root,source_files=files)
            self.assertEqual(row['status'],'deferred_unproved')
            self.assertFalse(row['solver_rerun'])
            self.assertEqual(row['model_compatibility']['original_source_sha256'],old)
            self.assertEqual(row['model_compatibility']['actual_source_sha256'],new)
            self.assertTrue(all(row['historical_artifacts_available'].values()))
            with self.assertRaisesRegex(ValueError,'model/job mismatch'):
                deferred.authenticate(self.entry,self.identity,new,self.root)
            with self.assertRaisesRegex(ValueError,'model/job mismatch'):
                deferred.authenticate(self.entry,dict(self.identity,depth=128),new,self.root,source_files=files)

    def test_rename_cannot_hide_changed_reset_or_assertion_even_with_a_replaced_pair(self):
        old,new,files=self.rename_fixture();source=files['RegBlock.sv'];original=source.read_bytes()
        for needle,replacement in ((b'reset-value=0',b'reset-value=1'),
                                   (b'assertion=original',b'assertion=weakened')):
            source.write_bytes(original.replace(needle,replacement))
            changed=dict(new,**{'RegBlock.sv':deferred.digest(source)})
            with patch.object(deferred,'REGBLOCK_HASH_PAIRS',{old['RegBlock.sv']:changed['RegBlock.sv']}):
                with self.assertRaisesRegex(ValueError,'beyond reviewed'):
                    deferred.authenticate(self.entry,self.identity,changed,self.root,source_files=files)

    def test_rename_rejects_other_model_changes_and_forged_file_hashes(self):
        old,new,files=self.rename_fixture()
        with patch.object(deferred,'REGBLOCK_HASH_PAIRS',{old['RegBlock.sv']:new['RegBlock.sv']}):
            files['Property.sv'].write_bytes(b'changed assertion fixture\n')
            with self.assertRaisesRegex(ValueError,'Changed actual emitted model'):
                deferred.authenticate(self.entry,self.identity,new,self.root,source_files=files)
            changed=dict(new,**{'Property.sv':deferred.digest(files['Property.sv'])})
            with self.assertRaisesRegex(ValueError,'model/job mismatch'):
                deferred.authenticate(self.entry,self.identity,changed,self.root,source_files=files)

    def test_unreviewed_rename_pair_fails_closed(self):
        old,new,files=self.rename_fixture()
        with self.assertRaisesRegex(ValueError,'model/job mismatch'):
            deferred.authenticate(self.entry,self.identity,new,self.root,source_files=files)


if __name__=='__main__': unittest.main()
