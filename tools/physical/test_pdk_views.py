"""Focused guards for pinned physical files and mixed-revision receipts."""
import hashlib,json,pathlib,tempfile,unittest
from unittest.mock import patch
from tools.physical import pdk_views


class PhysicalPdkGuards(unittest.TestCase):
    def test_hash_and_revision_fail_closed(self):
        parent=pdk_views.ROOT/'build/t43/guard-fixtures';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root=pathlib.Path(directory);active=root/'active.json';views=root/'views.json';view=root/'test.lef'
            view.write_text('MACRO fixture\nEND fixture\n')
            active.write_text(json.dumps({'revision':'selected'}))
            views.write_text(json.dumps({'revision':'selected','files':{'test.lef':hashlib.sha256(view.read_bytes()).hexdigest()}}))
            with patch.object(pdk_views,'LOCK',active),patch.object(pdk_views,'VIEWS',views),patch.object(pdk_views,'root',return_value=root):
                self.assertEqual(pdk_views.view('test.lef'),view)
                valid={'pdk':pdk_views.manifest()};pdk_views.require_manifest(valid)
                valid['input_sha256']={view.relative_to(pdk_views.ROOT).as_posix():hashlib.sha256(view.read_bytes()).hexdigest()}
                pdk_views.require_prepared(valid)
                with self.assertRaises(ValueError):pdk_views.require_manifest({})
                view.write_text('changed physical layout')
                with self.assertRaises(ValueError):pdk_views.view('test.lef')
                with self.assertRaises(ValueError):pdk_views.require_prepared(valid)
                active.write_text(json.dumps({'revision':'different'}))
                with self.assertRaises(ValueError):pdk_views.manifest()
                with self.assertRaises(ValueError):pdk_views.require_manifest(valid)


if __name__=='__main__':unittest.main()
