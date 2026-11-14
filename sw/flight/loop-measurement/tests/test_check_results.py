"""Fail-closed regression checks, with altered summaries and result rows."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_results import verify, HEADER

GOOD = HEADER + '\n' + '\n'.join([
    'A (rv32im -O2 ) | 10 | 10 | MATCH',
    'C (rv32i -O2 ) | 20 | 20 | MATCH',
    'D (rv32im -O2 -DNUM_FLOAT) | 30 | 30 | MATCH',
    'E (rv32imc -Os ) | 40 | 40 | MATCH',
]) + '\n'


class ResultsTests(unittest.TestCase):
    def test_exact_results_pass(self): verify(b'baseline', b'baseline', GOOD)

    def test_changed_summary_negative_control(self):
        with self.assertRaisesRegex(ValueError, 'summary.json changed'):
            verify(b'changed', b'baseline', GOOD)

    def test_changed_summary_line_endings_fail(self):
        with self.assertRaises(ValueError): verify(b'baseline\r\n', b'baseline\n', GOOD)

    def test_incomplete_or_extra_rows_fail(self):
        for bad in ('', HEADER, '\n'.join(GOOD.splitlines()[:-1]),
                    GOOD+GOOD.splitlines()[1]+'\n', GOOD+'\n'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): verify(b'x', b'x', bad)

    def test_mismatches_cannot_be_labelled_match(self):
        for bad in (GOOD.replace('| 10 | 10 |', '| 10 | 9 |'), GOOD.replace('MATCH', 'DIFF'),
                    GOOD.replace('| 10 | 10 |', '| 0 | 0 |'),
                    GOOD.replace('| 10 | 10 |', '| nan | nan |'), GOOD.replace('A (rv32im', 'Z (rv32im')):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): verify(b'x', b'x', bad)

    def test_missing_qemu_fails_without_skip(self):
        output = ROOT/'build/test_tools'; output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output) as temp:
            (Path(temp)/'dirname').symlink_to('/usr/bin/dirname')
            result = subprocess.run(['/bin/bash', str(ROOT/'tools/qemu_xcheck.sh')],
                                    env={'PATH': temp}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('qemu-system-riscv32 not installed', result.stderr)


if __name__ == '__main__': unittest.main()
