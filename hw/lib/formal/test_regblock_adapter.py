"""Behavioral solver checks of the native first-failure observer adapter.

These tiny BTOR2 transition-system fixtures test the formal file adapter, not
the RTL. Hardware behavior is checked by RegBlockSpec and RegBlockFormal.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from regblock_proof import startup_btor


def sequence_model(failures):
    # A saturating step index drives a fixed truth-table property. Keep literal
    # widths/constants distinct from node IDs to exercise reference renumbering.
    rows = ['1 sort bitvec 1', '2 zero 1', '3 one 1', '4 input 1 reset_n',
            '5 state 1 historyValid', '6 next 1 5 3', '7 sort bitvec 8',
            '8 zero 7', '9 one 7', f'10 constd 7 {len(failures) - 1}',
            '11 state 7 tick', '12 init 7 11 8', '13 eq 1 11 10',
            '14 add 7 11 9', '15 ite 7 13 11 14', '16 next 7 11 15']
    def add(body):
        node = len(rows) + 1
        rows.append(f'{node} {body}')
        return node
    bad = 2
    for index, fail in enumerate(failures):
        if fail:
            constant = add(f'constd 7 {index}')
            hit = add(f'eq 1 11 {constant}')
            bad = add(f'or 1 {bad} {hit}')
    add(f'bad {bad}')
    return '\n'.join(rows) + '\n'


class NativeObserverTests(unittest.TestCase):
    def test_solver_preserves_first_delayed_repeated_and_absent_failures(self):
        Path('build/t05/adapter').mkdir(parents=True, exist_ok=True)
        for failures in ([True], [False, False, True], [True, False, True],
                         [False, True, False, True], [False, False, False]):
            with self.subTest(failures=failures), tempfile.TemporaryDirectory(dir='build/t05/adapter') as directory:
                source, target = Path(directory) / 'source.btor2', Path(directory) / 'adapted.btor2'
                source.write_text(sequence_model(failures))
                startup_btor(source, target)
                for path in (source, target):
                    command = ['btormc', '--trace-gen', '1', '-v', '-kmax', '8']
                    if not any(failures):
                        command.append('--kind')
                    result = subprocess.run(command + [str(path)], capture_output=True, text=True, timeout=30)
                    self.assertIn(result.returncode, (0, 10, 20), result.stderr)
                    if any(failures):
                        self.assertRegex(result.stdout, r'(?m)^sat$')
                        # Input timestamps occur at every witness step; state
                        # snapshots can be omitted when all states are constant.
                        frames = [int(n) for n in re.findall(r'(?m)^@(\d+)$', result.stdout)]
                        self.assertEqual(max(frames), failures.index(True), result.stdout)
                    else:
                        self.assertRegex(result.stdout, r'(?m)^unsat$')
                        self.assertIn('1 unreachable bad state properties', result.stdout)


if __name__ == '__main__':
    unittest.main()
