"""Diagnostic multiplication stress test; does not replace formal acceptance."""
import argparse
import copy
import json
import random
import sys

from common import ROOT, output_dir, run
from lockstep import compile_sim, compare, qemu_trace

MASK = (1 << 32) - 1
SEED = 0xDEAD0010


def expected(a, b, operation):
    signed_a = a if a < (1 << 31) else a - (1 << 32)
    signed_b = b if b < (1 << 31) else b - (1 << 32)
    if operation == 0:
        return (a * b) & MASK
    product = (signed_a * signed_b if operation == 1 else
               signed_a * b if operation == 2 else a * b)
    return (product >> 32) & MASK


def check_products(trace, pairs):
    products = [r for r in trace if r['insn'] & 0xfe00007f == 0x02000033
                and (r['insn'] >> 12) & 7 < 4]
    if len(products) != len(pairs) * 4:
        raise ValueError('Wrong number of multiply retirements')
    for index, record in enumerate(products):
        a, b = pairs[index // 4]
        operation = index % 4
        if (record['insn'] >> 12) & 7 != operation:
            raise ValueError('Wrong multiply operation/order')
        if record['rs1_rdata'] != a or record['rs2_rdata'] != b:
            raise ValueError('Multiply operands differ from fixture')
        want = expected(a, b, operation)
        if record['rd_wdata'] != want:
            raise ValueError(f'Multiply mismatch pair={index//4} op={operation} '
                             f'a={a:08x} b={b:08x} got={record["rd_wdata"]:08x} expected={want:08x}')
    return len(products)


def program(pairs):
    init = '\n'.join(f'addi x{n}, x0, 0' for n in range(1, 32))
    words = '\n'.join(f'.word 0x{a:08x}, 0x{b:08x}' for a, b in pairs)
    return f'''.option norvc
.section .text
.globl _start
_start:
{init}
  la t0, operands
  li t1, {len(pairs)}
loop:
  lw a0, 0(t0)
  lw a1, 4(t0)
  mul a2, a0, a1
  mulh a3, a0, a1
  mulhsu a4, a0, a1
  mulhu a5, a0, a1
  addi t0, t0, 8
  addi t1, t1, -1
  bnez t1, loop
  li t0, 0x100000
  li t1, 0x5555
  sw t1, 0(t0)
  j .
.section .rodata
.balign 4
operands:
{words}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output/'result.json').write_text('{"status":"running"}\n')
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    originals = compile_sim(output/'original', original=True)
    adapted = compile_sim(output/'adapted')
    edges = [0, 1, 2, 3, 0x7fff, 0x8000, 0xffff, 0x10000, 0x10001,
             0x1ffff, 0x7fffffff, 0x80000000, 0x80000001, 0xffff0000,
             0xfffffffe, 0xffffffff, 0x55555555, 0xaaaaaaaa]
    pairs = [(a, b) for a in edges for b in edges]
    rng = random.Random(SEED)
    pairs.extend((rng.getrandbits(32), rng.getrandbits(32)) for _ in range(4096))
    total = retirements = 0
    faults = []
    for start in range(0, len(pairs), 512):
        selected = pairs[start:start+512]
        batch = output_dir(output/f'batch-{start//512:02}')
        (batch/'operands.json').write_text(json.dumps(selected))
        (batch/'program.S').write_text(program(selected))
        elf = batch/'program.elf'
        run(['riscv64-unknown-elf-gcc', '-march=rv32imc_zicsr', '-mabi=ilp32', '-nostdlib',
             '-Wl,--no-relax', '-T', 'dv/core/link.ld', batch/'program.S', '-o', elf], batch, 'compile')
        binary = batch/'program.bin'
        run(['riscv64-unknown-elf-objcopy', '-O', 'binary', elf, binary], batch, 'binary')
        traces = []
        for label, sim in (('original', originals), ('adapted', adapted)):
            result = run([sim, binary], batch, label)
            trace = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            check_products(trace, selected)
            traces.append(trace)
        iss = qemu_trace(elf, batch)
        retirements += compare(*traces, iss, binary.read_bytes())
        total += check_products(traces[0], selected)
        for operation in range(4):
            bad = copy.deepcopy(traces[0])
            r = next(r for r in bad if r['insn'] & 0xfe00007f == 0x02000033
                     and (r['insn'] >> 12) & 7 == operation)
            r['rd_wdata'] ^= 1
            try:
                check_products(bad, selected)
            except ValueError as exc:
                faults.append(str(exc))
            else:
                raise ValueError('Arithmetic fault escaped independent oracle')
        print(f'PASS multiply batch {start//512}: {len(selected)} pairs, original/adapted/QEMU/Python agree', flush=True)
    (output/'result.json').write_text(json.dumps(dict(status='pass', seed=SEED, operand_pairs=len(pairs),
        multiplication_retirements=total, all_retirements=retirements, fault_controls=len(faults),
        limits='Directed/random simulation only; not a formal proof',
        faults=faults), indent=2)+'\n')
    print(f'PASS multiply diagnosis: {total} products, {retirements} retirements, {len(faults)} faults rejected')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'FAIL multiply diagnosis: {exc}', file=sys.stderr)
        sys.exit(1)
