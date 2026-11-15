"""Fail-closed provenance controls; no RTL-source behavioral tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import common
from riscv_formal import ArithmeticTimeout, run_partitions, sby_status
from lockstep import BASE, completion_window


class AdaptationGuards(unittest.TestCase):
    def test_exact_hash_and_match_count(self):
        # Synthetic bytes exercise the transformation mechanism, not RTL logic.
        base = common.output_dir('build/t10/input-tests')
        with tempfile.TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            vendor = root / 'vendor'
            vendor.mkdir()
            (root/'dv/core').mkdir(parents=True)
            data = b'prefix\nunused declaration\nsuffix\n'
            source = vendor/'input.sv'
            source.write_bytes(data)
            manifest = dict(id='test', source='input.sv', source_sha256=hashlib.sha256(data).hexdigest(),
                            remove='unused declaration\n')
            path = root/'dv/core/adaptations.json'
            path.write_text(json.dumps(manifest))
            out = root/'out'
            out.mkdir()
            with patch.object(common, 'ROOT', root), patch.object(common, 'VENDOR', vendor):
                result = common.adapted_sources(out, dict(sources=['input.sv']))
                self.assertEqual(Path(result[0]).read_bytes(), b'prefix\nsuffix\n')
                self.assertEqual(source.read_bytes(), data)
                source.write_bytes(data+b'changed')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    common.adapted_sources(out, dict(sources=['input.sv']))
                source.write_bytes(data)
                for removal in ('missing', 'e'):
                    changed = copy.deepcopy(manifest)
                    changed['remove'] = removal
                    path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, 'exactly once'):
                        common.adapted_sources(out, dict(sources=['input.sv']))


class FormalDispatch(unittest.TestCase):
    def test_all_partitions_are_required(self):
        results = []
        run_partitions(list(range(7)), lambda value: value * value, results.append)
        self.assertEqual(results, [0, 1, 4, 9, 16, 25, 36])

    def test_failure_prevents_next_batch(self):
        called = []
        def worker(value):
            called.append(value)
            if value == 0:
                raise RuntimeError('deliberate solver failure')
            return value
        with self.assertRaisesRegex(RuntimeError, 'deliberate solver failure'):
            run_partitions(list(range(7)), worker, lambda value: None)
        self.assertEqual(set(called), {0, 1, 2})


class ShutdownBoundary(unittest.TestCase):
    def fixture(self):
        # SW x6,0(x5), followed by JAL x0,0.
        binary = (0x0062a023).to_bytes(4, 'little') + (0x6f).to_bytes(4, 'little')
        regs = {n: 0 for n in range(32)}
        regs.update({5: 0x100000, 6: 0x5555})
        return [dict(pc=BASE, regs=regs), dict(pc=BASE+4, regs=dict(regs))], binary

    def test_exact_idle_tail_is_allowed(self):
        trace, binary = self.fixture()
        self.assertEqual(completion_window(trace, binary), trace)
        self.assertEqual(completion_window(trace + [copy.deepcopy(trace[-1])] * 5, binary), trace)

    def test_corrupt_or_missing_tail_is_rejected(self):
        trace, binary = self.fixture()
        for mutation in ('pc', 'register', 'missing', 'instruction'):
            changed = copy.deepcopy(trace)
            code = binary
            if mutation == 'pc':
                changed.append(dict(pc=BASE+8, regs=changed[-1]['regs']))
            elif mutation == 'register':
                changed.append(copy.deepcopy(changed[-1]))
                changed[-1]['regs'][8] = 1
            elif mutation == 'missing':
                changed.pop()
            else:
                code = binary[:4] + (0x13).to_bytes(4, 'little')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                completion_window(changed, code)


class SolverOutcomes(unittest.TestCase):
    def test_status_requires_matching_exit_code(self):
        base = common.output_dir('build/t10/input-tests')
        with tempfile.TemporaryDirectory(dir=base) as directory:
            work = Path(directory)
            for status, code in (('PASS', 0), ('FAIL', 2)):
                (work/'status').write_text(status)
                self.assertEqual(sby_status(work, code), status)
                with self.assertRaises(RuntimeError):
                    sby_status(work, 2 if code == 0 else 0)
            (work/'status').write_text('ERROR')
            with self.assertRaises(RuntimeError):
                sby_status(work, 16)

    def test_only_witness_free_timeout_is_arithmetic_unresolved(self):
        base = common.output_dir('build/t10/input-tests')
        with tempfile.TemporaryDirectory(dir=base) as directory:
            work = Path(directory)
            (work/'status').write_text('TIMEOUT')
            with self.assertRaises(ArithmeticTimeout):
                sby_status(work, 8)
            (work/'engine_0').mkdir()
            (work/'engine_0/trace.aiw').write_text('partial witness')
            with self.assertRaises(RuntimeError) as error:
                sby_status(work, 8)
            self.assertNotIsInstance(error.exception, ArithmeticTimeout)


if __name__ == '__main__':
    unittest.main()
