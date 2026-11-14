#!/usr/bin/env python3
"""Count single-instruction QEMU TBs before the ELF's explicit terminal spin.

The historical workload has no consecutive same-PC instructions before its
terminal spin. Such entries are QEMU MMIO re-entry records, counted once.
This is a workload-specific counter, not a general RISC-V trace decoder.
"""
import argparse
from pathlib import Path
import re
import sys

PROGRAM_BASE = 0x80000000
TRACE_PC = re.compile(r'\[[0-9a-fA-F]+/([0-9a-fA-F]+)/')


def symbol_address(symbols, name):
    addresses = [int(p[0], 16) for line in symbols for p in [line.split()]
                 if len(p) >= 3 and p[-1] == name]
    if len(addresses) != 1 or addresses[0] < PROGRAM_BASE:
        raise ValueError(f'expected one program {name} symbol')
    return addresses[0]


def trace_pc(line):
    if not line.startswith('Trace'): return None
    match = TRACE_PC.search(line)
    if not match: raise ValueError('malformed QEMU Trace record')
    return int(match.group(1), 16)


def count_instructions(lines, stop, finish=None, exited=False):
    count, previous = 0, None
    for line in lines:
        pc = trace_pc(line)
        if pc is None: continue
        if pc == stop:
            if not count: raise ValueError('empty program trace')
            if finish is not None and previous != finish:
                raise ValueError('terminal spin was not preceded by its exit store')
            return count
        if pc >= PROGRAM_BASE and pc != previous: count += 1
        previous = pc
    if exited and count and previous == finish:
        return count
    raise ValueError('incomplete trace: no terminal spin or confirmed exit store')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('symbols', type=Path)
    parser.add_argument('--finisher-exited', action='store_true',
                        help='caller confirmed QEMU returned success from its finisher')
    args = parser.parse_args()
    with args.symbols.open() as symbols, args.trace.open() as trace:
        symbols = list(symbols)
        print(count_instructions(trace, symbol_address(symbols, 'sim_spin'),
                                 symbol_address(symbols, 'sim_finish'), args.finisher_exited))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError) as exc: sys.exit(f'QEMU_COUNT: {exc}')
