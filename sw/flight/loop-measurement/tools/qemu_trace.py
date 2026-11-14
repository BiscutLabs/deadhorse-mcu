#!/usr/bin/env python3
"""Capture buffered QEMU traces until the named terminal spin is observed."""
import argparse
from pathlib import Path
import subprocess
import sys
import threading

from qemu_count import symbol_address, trace_pc, count_instructions


def capture(command, output, errors, stop, finish, timeout=300):
    expired = threading.Event()
    with output.open('w', buffering=1024 * 1024) as log, errors.open('w') as err:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True)
        def expire():
            expired.set()
            try: proc.kill()
            except ProcessLookupError: pass
        timer = threading.Timer(timeout, expire)
        timer.start()
        found = False
        try:
            for line in proc.stdout:
                log.write(line)
                if trace_pc(line) == stop:
                    found = True
                    break
        finally:
            interrupted = found or sys.exc_info()[0] is not None
            if interrupted and proc.poll() is None: proc.terminate()
            # EOF can precede the process's successful exit. Keep the original
            # deadline active while waiting; do not turn normal cleanup into SIGTERM.
            try: proc.wait(timeout=5 if interrupted else timeout)
            except subprocess.TimeoutExpired:
                if not interrupted: expired.set()
                proc.kill(); proc.wait()
            timer.cancel()
            proc.stdout.close()
        if expired.is_set(): raise RuntimeError('QEMU exceeded the 300-second deadline')
        if not found and proc.returncode != 0:
            raise RuntimeError(f'QEMU ended without sim_spin (exit {proc.returncode}); see {errors}')
    with output.open() as trace:
        return count_instructions(trace, stop, finish, exited=not found and proc.returncode == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('symbols', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.symbols.open() as symbols: symbols = list(symbols)
    stop = symbol_address(symbols, 'sim_spin')
    finish = symbol_address(symbols, 'sim_finish')
    command = ['qemu-system-riscv32', '-M', 'virt', '-bios', 'none', '-kernel', str(args.elf),
               '-nographic', '-monitor', 'none', '-serial', 'null', '-d', 'nochain,exec',
               '-singlestep', '-D', '/dev/stdout']
    print(capture(command, args.output, args.output.with_suffix('.err'), stop, finish))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, RuntimeError) as exc: sys.exit(f'QEMU_TRACE: {exc}')
