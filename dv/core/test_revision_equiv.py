"""A failed proof-control run must never leave a passing aggregate receipt."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import ROOT
import revision_equiv


class RevisionReceiptTests(unittest.TestCase):
    def test_fault_control_exception_invalidates_positive_receipt(self):
        base = ROOT/'build/test_revision_equiv'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            out = Path(directory)/'result'
            data = dict(schema=2, parameters={}, implementation='registered-execution-v1', excluded={})

            def positive(*args):
                (out/'result.json').write_text(json.dumps(dict(status='proved')))
                return 'proved'

            argv = ['revision_equiv', '--before', directory, '--after', directory, '--output', str(out)]
            with patch('sys.argv', argv), \
                 patch.object(revision_equiv, 'parameters', return_value={}), \
                 patch.object(revision_equiv, 'manifest', return_value=data), \
                 patch.object(revision_equiv, 'elaborate', return_value=out/'design.json'), \
                 patch.object(revision_equiv, 'compare', side_effect=positive), \
                 patch.object(revision_equiv, 'negatives', side_effect=RuntimeError('fault survived')):
                with self.assertRaisesRegex(RuntimeError, 'fault survived'):
                    revision_equiv.main()
            receipt = json.loads((out/'result.json').read_text())
            self.assertEqual(receipt['status'], 'failed')
            self.assertEqual(receipt['error'], 'fault survived')


if __name__ == '__main__':
    unittest.main()
