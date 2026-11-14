"""Independent, hand-counted traces and deliberately incomplete controls."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from qemu_count import count_instructions, symbol_address
from qemu_trace import capture

START, FINISH, STOP = 0x80000000, 0x80000010, 0x80000014


def trace(*pcs):
    return [f'Trace 0: 0x1234 [00000000/{pc:016x}/07014003/ff020201]\n' for pc in pcs]


class CounterTests(unittest.TestCase):
    def test_named_boundary_and_mmio_reentry(self):
        lines = trace(0x1000, START, START+4, START+4, START+8, FINISH, FINISH, STOP, STOP)
        self.assertEqual(count_instructions(lines, STOP), 4)

    def test_tail_changes_do_not_change_count(self):
        prefix = trace(START, START+4, FINISH, STOP)
        for tail in ([], trace(STOP)*100, trace(START, START+4), ['Trace truncated']):
            with self.subTest(tail=tail[:1]):
                self.assertEqual(count_instructions(prefix + tail, STOP), 3)

    def test_real_loop_revisits_count(self):
        self.assertEqual(count_instructions(trace(START, START+4, START, FINISH, STOP), STOP), 4)

    def test_finisher_exit_requires_store_and_success(self):
        self.assertEqual(count_instructions(trace(START, FINISH, FINISH), STOP, FINISH, True), 2)
        for lines, exited in ((trace(START, FINISH), False), (trace(START), True), ([], True)):
            with self.subTest(lines=lines, exited=exited):
                with self.assertRaises(ValueError): count_instructions(lines, STOP, FINISH, exited)

    def test_truncation_negative_control(self):
        complete = trace(START, START+4, FINISH, STOP)
        for length in range(len(complete)):
            with self.subTest(length=length):
                with self.assertRaises(ValueError): count_instructions(complete[:length], STOP)

    def test_marker_without_exit_store_fails(self):
        with self.assertRaises(ValueError):
            count_instructions(trace(START, STOP), STOP, FINISH)

    def test_malformed_and_empty_traces_fail(self):
        for lines in (['Trace malformed'], trace(STOP), ['unrelated output\n']):
            with self.subTest(lines=lines):
                with self.assertRaises(ValueError): count_instructions(lines, STOP)

    def test_symbol_formats(self):
        for text in ('80000014 T sim_spin', '80000014 00000004 T sim_spin'):
            self.assertEqual(symbol_address([text], 'sim_spin'), STOP)

    def test_bad_symbols_fail(self):
        for symbols in ([], ['00001000 T sim_spin'], ['80000014 T sim_spin']*2):
            with self.subTest(symbols=symbols):
                with self.assertRaises(ValueError): symbol_address(symbols, 'sim_spin')


class CaptureTests(unittest.TestCase):
    def setUp(self):
        output = ROOT/'build/test_qemu'; output.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(temp.cleanup); self.output = Path(temp.name)

    def run_child(self, code, timeout=5):
        return capture([sys.executable, '-u', '-c', code], self.output/'trace.log',
                       self.output/'trace.err', STOP, FINISH, timeout=timeout)

    def test_stops_live_child_at_marker(self):
        lines = ''.join(trace(START, FINISH, STOP))
        self.assertEqual(self.run_child(f'import time; print({lines!r}, flush=True); time.sleep(60)'), 2)

    def test_clean_finisher_exit(self):
        lines = ''.join(trace(START, FINISH))
        self.assertEqual(self.run_child(f'print({lines!r})'), 2)

    def test_stdout_close_before_successful_exit(self):
        lines = ''.join(trace(START, FINISH))
        code = f'import os,time; print({lines!r}, flush=True); os.close(1); time.sleep(0.05); os._exit(0)'
        self.assertEqual(self.run_child(code), 2)

    def test_clean_exit_with_truncated_trace_fails(self):
        with self.assertRaises(ValueError): self.run_child(f'print({trace(START)[0]!r})')

    def test_failed_exit_at_store_fails(self):
        lines = ''.join(trace(START, FINISH))
        with self.assertRaises(RuntimeError): self.run_child(f'print({lines!r}); raise SystemExit(1)')

    def test_timeout_negative_control(self):
        with self.assertRaisesRegex(RuntimeError, 'deadline'):
            self.run_child('import time; time.sleep(60)', timeout=0.1)


if __name__ == '__main__': unittest.main()
