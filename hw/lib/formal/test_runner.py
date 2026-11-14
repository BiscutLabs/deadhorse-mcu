"""Regression tests for formal-result acceptance and startup constraints."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('formal_smoke', ROOT / 'tools/formal_smoke.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FormalRunnerTests(unittest.TestCase):
    def test_complete_induction_only(self):
        proven = 'unsat\nb0\nunsat\nb1\nfound 0 reachable and 2 unreachable bad state properties\n'
        self.assertEqual(runner.btor_outcome(proven, True), 'proved')
        for text, induction in [(proven, False), ('unsat\nb0\n', True),
                                ('unknown\n', True), ('', True),
                                (proven + 'unknown\n', True),
                                (proven.replace('b1', 'b0'), True)]:
            with self.subTest(text=text, induction=induction), self.assertRaises(RuntimeError):
                runner.btor_outcome(text, induction)

    def test_witness_requires_property(self):
        self.assertEqual(runner.btor_outcome('sat\nb0\n#0\n.\n', False), 'witness')
        for text in ('sat\n', 'sat\nb0\n', 'sat\nb0\n#0\n'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                runner.btor_outcome(text, False)

    def test_startup_constraints_leave_later_reset_free(self):
        # Tiny BTOR protocol fixture, not an RTL source-text test.
        model = '1 sort bitvec 1\n2 input 1 reset_n\n3 input 1 checking\n4 bad 2\n'
        base = ROOT / 'build/t07/runner-tests'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as work:
            source, target = Path(work) / 'in.btor2', Path(work) / 'out.btor2'
            source.write_text(model)
            runner.constrained_btor(source, target, 1)
            rows = [line.split() for line in target.read_text().splitlines()
                    if line and not line.startswith(';')]
            # Evaluate the small adapter's Boolean constraints independently for
            # every combination of state, reset and validity.
            for started in (0, 1):
                for reset in (0, 1):
                    for checking in (0, 1):
                        values = {'2': reset, '3': checking}
                        constraints = []
                        for row in rows:
                            node, op, *args = row
                            if op == 'zero': values[node] = 0
                            elif op == 'one': values[node] = 1
                            elif op == 'state': values[node] = started
                            elif op == 'not': values[node] = 1 - values[args[1]]
                            elif op == 'or': values[node] = values[args[1]] | values[args[2]]
                            elif op == 'eq': values[node] = int(values[args[1]] == values[args[2]])
                            elif op == 'constraint': constraints.append(values[args[0]])
                            elif op == 'init': self.assertEqual(values[args[2]], 0)
                            elif op == 'next': self.assertEqual(values[args[2]], 1)
                        self.assertEqual(all(constraints), checking == started and (started == 1 or reset == 0))
            with self.assertRaises(RuntimeError):
                runner.constrained_btor(source, target, 2)


if __name__ == '__main__':
    unittest.main()
