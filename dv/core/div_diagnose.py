"""Required real-division stress against reference, candidate copy, QEMU and integers."""
import argparse
import copy
import json
import random
import sys

from common import output_dir, run
from lockstep import compile_sim, compare, qemu_trace

MASK = (1 << 32)-1
SEED = 0xDEAD0011


def expected(a, b, operation):
    if operation not in range(4,8):
        raise ValueError('Not a division/remainder operation')
    signed = operation in (4,6)
    dividend = a-(1<<32) if signed and a & (1<<31) else a
    divisor = b-(1<<32) if signed and b & (1<<31) else b
    if divisor == 0:
        return MASK if operation in (4,5) else a
    quotient = abs(dividend)//abs(divisor)
    if (dividend < 0) != (divisor < 0):
        quotient = -quotient
    remainder = dividend-quotient*divisor
    return (quotient if operation in (4,5) else remainder) & MASK


def check_divisions(trace, pairs):
    divisions = [r for r in trace if r['insn'] & 0xfe00007f == 0x02000033
                 and (r['insn'] >> 12) & 7 >= 4]
    if len(divisions) != len(pairs)*4:
        raise ValueError('Wrong number of divide/remainder retirements')
    for index, record in enumerate(divisions):
        a,b = pairs[index//4]
        operation = 4+index%4
        if (record['insn'] >> 12) & 7 != operation:
            raise ValueError('Wrong divide/remainder operation/order')
        if (record['rs1_rdata'],record['rs2_rdata']) != (a,b):
            raise ValueError('Divide operands differ from fixture')
        want = expected(a,b,operation)
        if record['rd_wdata'] != want:
            raise ValueError(f'Divide mismatch pair={index//4} op={operation} '
                             f'a={a:08x} b={b:08x} got={record["rd_wdata"]:08x} expected={want:08x}')
    return len(divisions)


def program(pairs):
    init = '\n'.join(f'addi x{n},x0,0' for n in range(1,32))
    words = '\n'.join(f'.word 0x{a:08x},0x{b:08x}' for a,b in pairs)
    return f'''.option norvc
.section .text
.globl _start
_start:
{init}
  la t0,operands
  li t1,{len(pairs)}
loop:
  lw a0,0(t0)
  lw a1,4(t0)
  div a2,a0,a1
  divu a3,a0,a1
  rem a4,a0,a1
  remu a5,a0,a1
  addi t0,t0,8
  addi t1,t1,-1
  bnez t1,loop
  li t0,0x100000
  li t1,0x5555
  sw t1,0(t0)
  j .
.section .rodata
.balign 4
operands:
{words}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output/'result.json').write_text('{"status":"running"}\n')
    run([sys.executable,'tools/env/check.py'],output,'environment')
    original = compile_sim(output/'original',original=True)
    adapted = compile_sim(output/'adapted')
    edges = [0,1,2,3,0x7fff,0x8000,0xffff,0x10000,0x10001,
             0x7ffffffe,0x7fffffff,0x80000000,0x80000001,0xffff0000,
             0xfffffffe,0xffffffff,0x55555555,0xaaaaaaaa]
    pairs = [(a,b) for a in edges for b in edges]
    rng = random.Random(SEED)
    pairs.extend((rng.getrandbits(32),rng.getrandbits(32)) for _ in range(4096))
    total = retirements = 0
    faults = []
    # Smaller batches fit the unchanged simulator cycle deadline, including
    # the full iterative divide latency for every instruction.
    for start in range(0,len(pairs),128):
        selected = pairs[start:start+128]
        batch = output_dir(output/f'batch-{start//128:02}')
        (batch/'operands.json').write_text(json.dumps(selected))
        (batch/'program.S').write_text(program(selected))
        elf,binary = batch/'program.elf',batch/'program.bin'
        run(['riscv64-unknown-elf-gcc','-march=rv32imc_zicsr','-mabi=ilp32','-nostdlib',
             '-Wl,--no-relax','-T','dv/core/link.ld',batch/'program.S','-o',elf],batch,'compile')
        run(['riscv64-unknown-elf-objcopy','-O','binary',elf,binary],batch,'binary')
        traces = []
        for label,sim in (('original',original),('adapted',adapted)):
            result = run([sim,binary],batch,label)
            trace = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            check_divisions(trace,selected)
            traces.append(trace)
        iss = qemu_trace(elf,batch)
        retirements += compare(*traces,iss,binary.read_bytes())
        total += check_divisions(traces[0],selected)
        for operation in range(4,8):
            bad = copy.deepcopy(traces[0])
            record = next(r for r in bad if r['insn'] & 0xfe00007f == 0x02000033
                          and (r['insn'] >> 12) & 7 == operation)
            record['rd_wdata'] ^= 1
            for name,check in (('integer oracle',lambda:check_divisions(bad,selected)),
                               ('ISS shared fault',lambda:compare(bad,bad,iss,binary.read_bytes()))):
                try:
                    check()
                except ValueError as exc:
                    faults.append(dict(check=name,batch=start//128,operation=operation,reason=str(exc)))
                else:
                    raise ValueError(f'Divide result fault escaped {name}')
        print(f'PASS divide batch {start//128}: {len(selected)} pairs, original/adapted/QEMU/Python agree',flush=True)
    (output/'result.json').write_text(json.dumps(dict(status='pass',seed=SEED,operand_pairs=len(pairs),
        division_retirements=total,all_retirements=retirements,fault_controls=len(faults),faults=faults,
        limits='Directed/random simulation, not a formal proof'),indent=2)+'\n')
    print(f'PASS divide diagnosis: {total} operations, {retirements} retirements, {len(faults)} faults rejected')


if __name__ == '__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError) as exc:
        print(f'FAIL divide diagnosis: {exc}',file=sys.stderr)
        sys.exit(1)
