#!/usr/bin/env python3
"""Enforce the immutable historical summary and complete, exact QEMU matches."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'config | rvsim retired | QEMU executed insns | match'
CONFIGS = {'A (rv32im -O2 )', 'C (rv32i -O2 )',
           'D (rv32im -O2 -DNUM_FLOAT)', 'E (rv32imc -Os )'}


def verify(summary, baseline, crosscheck):
    if summary != baseline: raise ValueError('historical summary.json changed')
    lines = crosscheck.splitlines()
    if not lines or lines[0] != HEADER: raise ValueError('missing QEMU results header')
    seen = set()
    for line in lines[1:]:
        fields = [part.strip() for part in line.split('|')]
        if len(fields) != 4: raise ValueError(f'malformed QEMU row: {line}')
        name, simulator, qemu, result = fields
        if name not in CONFIGS or name in seen: raise ValueError(f'unexpected/duplicate configuration: {name}')
        if not all(re.fullmatch(r'[0-9]+', n) and int(n) > 0 for n in (simulator, qemu)):
            raise ValueError(f'invalid instruction counts: {line}')
        if simulator != qemu or result != 'MATCH': raise ValueError(f'QEMU mismatch: {line}')
        seen.add(name)
    if seen != CONFIGS: raise ValueError('missing QEMU configurations')


def main():
    baseline = subprocess.check_output(['git', 'show', 'HEAD:sw/flight/loop-measurement/results/summary.json'], cwd=ROOT)
    verify((ROOT/'results/summary.json').read_bytes(), baseline,
           (ROOT/'results/qemu_xcheck.txt').read_text())
    print('PASS flight-loop: historical summary unchanged; four exact QEMU matches')


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc: sys.exit(f'LOOP_CHECK: {exc}')
