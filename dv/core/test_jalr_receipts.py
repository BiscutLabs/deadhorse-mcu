"""Receipt recovery must preserve exact historical hashes, never invent evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from common import ROOT
from jalr_receipts import combine_hashes, recover_audit_blob, verify_hashes


class ReceiptTests(unittest.TestCase):
    def test_exact_logged_audit_reconstruction(self):
        audit={'status':'pass','qualification_negative':{'seconds':1.25,'status':'rejected'}}
        original=(json.dumps(audit,indent=2)+'\n').encode();expected=hashlib.sha256(original).hexdigest()
        audit['qualification_negative']['seconds']=9.0
        self.assertEqual(recover_audit_blob(audit,[{'elapsed_seconds':2.5},{'elapsed_seconds':1.25}],expected),original)
        with self.assertRaises(ValueError): recover_audit_blob(audit,[{'elapsed_seconds':2.5}],expected)
        audit['status']='failed'
        with self.assertRaises(ValueError): recover_audit_blob(audit,[{'elapsed_seconds':1.25}],expected)

    def test_relocation_verifies_old_digest_and_rejects_unknown_input(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as directory:
            actual=Path(directory)/'original';archive=Path(directory)/'archive'
            actual.write_bytes(b'new metadata');archive.write_bytes(b'old metadata')
            hashes={str(actual):hashlib.sha256(b'old metadata').hexdigest()}
            with self.assertRaises(ValueError): verify_hashes(hashes)
            verify_hashes(hashes,{str(actual):str(archive)})
            with self.assertRaises(ValueError): verify_hashes(hashes,{'unknown':str(archive)})
            archive.write_bytes(b'changed archive')
            with self.assertRaises(ValueError): verify_hashes(hashes,{str(actual):str(archive)})

    def test_conflicting_inventory_cannot_override_digest(self):
        self.assertEqual(combine_hashes({'a':'one'},{'a':'one','b':'two'}),{'a':'one','b':'two'})
        with self.assertRaises(ValueError): combine_hashes({'a':'one'},{'a':'different'})


if __name__=='__main__': unittest.main()
