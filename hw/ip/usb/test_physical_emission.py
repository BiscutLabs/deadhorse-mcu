"""Provenance-normalizer faults; these do not test behavior by RTL text."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import physical_emission as identity


class PhysicalEmissionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.old = 'wire _rd_released; wire _wr_released; assign reset_n = _wr_released; assign out = _rd_released;'
        self.new = 'wire writeReleased; wire readReleased; assign reset_n = writeReleased; assign out = readReleased;'

    def test_explicit_wire_bijection(self):
        identity.verify_text('CdcFifo.sv', self.old, self.new)

    def test_changed_reset_and_output_rejected(self):
        for token in ('reset_n', 'out'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                identity.verify_text('CdcFifo.sv', self.old, self.new.replace(token + ' =', token + ' = !'))

    def test_initialized_declaration_rejected(self):
        with self.assertRaisesRegex(ValueError, 'declaration'):
            identity.verify_text('CdcFifo.sv', self.old, self.new.replace('wire readReleased;', 'wire readReleased = 0;'))

    def test_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, 'collision'):
            identity.verify_text('CdcFifo.sv', self.old, self.new + ' wire _rd_released;')

    def test_whitespace_cannot_join_identifiers(self):
        self.assertNotEqual(identity.tokens('one two'), identity.tokens('onetwo'))

    def test_unknown_hash_and_extra_file_rejected(self):
        build = Path(__file__).resolve().parents[3] / 'build'
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build) as directory:
            root = Path(directory); old = root / 'old'; new = root / 'new'
            old.mkdir(); new.mkdir()
            a=old/'CdcFifo.sv'; b=new/'CdcFifo.sv'
            a.write_text(self.old); b.write_text(self.new)
            expected = {'CdcFifo.sv': identity.digest(a)}
            with self.assertRaisesRegex(ValueError, 'revision'):
                identity.compatible(new, old, expected)
            with patch.dict(identity.PAIRS, {'CdcFifo.sv': (identity.digest(a), identity.digest(b))}):
                self.assertEqual(identity.compatible(new, old, expected)['status'], 'compatible')
                (new/'extra.sv').write_text('extra')
                with self.assertRaisesRegex(ValueError, 'inventory'):
                    identity.compatible(new, old, expected)


if __name__ == '__main__':
    unittest.main()
