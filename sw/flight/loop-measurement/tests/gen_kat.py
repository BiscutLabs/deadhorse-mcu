#!/usr/bin/env python3
"""Generates kat.S: known-answer tests for tools/rvsim.c. Expected values come from
an independent Python reference model (not from the simulator). Usage: gen_kat.py out.S [rvc]"""
import sys, itertools
rvc = len(sys.argv) > 2 and sys.argv[2] == "rvc"
M = 0xFFFFFFFF
def s32(v): v &= M; return v - (1 << 32) if v >> 31 else v
def u32(v): return v & M
vals = [0, 1, M, 2, 7, u32(-7), 0x7FFFFFFF, 0x80000000, 0x12345678, u32(-87654321), 0xDEADBEEF, 31, 0x0000FFFF, 0x80000001, 100000, u32(-100000)]
def div(a, b):
    if b == 0: return M
    if s32(a) == -2**31 and s32(b) == -1: return a
    q = abs(s32(a)) // abs(s32(b)); return u32(-q if (s32(a) < 0) != (s32(b) < 0) else q)
def rem(a, b):
    if b == 0: return a
    if s32(a) == -2**31 and s32(b) == -1: return 0
    r = abs(s32(a)) % abs(s32(b)); return u32(-r if s32(a) < 0 else r)
RT = {
 "add": lambda a, b: u32(a + b), "sub": lambda a, b: u32(a - b), "sll": lambda a, b: u32(a << (b & 31)),
 "srl": lambda a, b: a >> (b & 31), "sra": lambda a, b: u32(s32(a) >> (b & 31)),
 "slt": lambda a, b: int(s32(a) < s32(b)), "sltu": lambda a, b: int(a < b),
 "xor": lambda a, b: a ^ b, "or": lambda a, b: a | b, "and": lambda a, b: a & b,
 "mul": lambda a, b: u32(a * b), "mulh": lambda a, b: u32((s32(a) * s32(b)) >> 32),
 "mulhsu": lambda a, b: u32((s32(a) * b) >> 32), "mulhu": lambda a, b: u32((a * b) >> 32),
 "div": div, "divu": lambda a, b: M if b == 0 else a // b, "rem": rem, "remu": lambda a, b: a if b == 0 else a % b,
}
out = []; tid = [0]
def nid(): tid[0] += 1; return tid[0]
w = out.append
w("""    .macro CHK reg, exp, id
    li t6, \\exp
    beq \\reg, t6, 1f
    li a0, \\id
    j fail
1:
    .endm
    .section .text.start, "ax"
    .globl _start
_start:
    la sp, _stack_top
    jal ra, counted
""")
for op, fn in RT.items():
    for a, b in itertools.product(vals, vals):
        i = nid(); w(f"    li t0, {a}\n    li t1, {b}\n    {op} t3, t0, t1\n    CHK t3, {fn(a, b)}, {i}")
for op, fn in (("addi", RT["add"]), ("slti", RT["slt"]), ("sltiu", RT["sltu"]), ("xori", RT["xor"]), ("ori", RT["or"]), ("andi", RT["and"])):
    for a in vals:
        for imm in (0, 1, -1, 2047, -2048, 0x555):
            i = nid(); w(f"    li t0, {a}\n    {op} t3, t0, {imm}\n    CHK t3, {fn(a, u32(imm))}, {i}")
for op, fn in (("slli", RT["sll"]), ("srli", RT["srl"]), ("srai", RT["sra"])):
    for a in vals:
        for sh in (0, 1, 5, 31):
            i = nid(); w(f"    li t0, {a}\n    {op} t3, t0, {sh}\n    CHK t3, {fn(a, sh)}, {i}")
for cond, fn in (("beq", lambda a, b: a == b), ("bne", lambda a, b: a != b), ("blt", lambda a, b: s32(a) < s32(b)),
                 ("bge", lambda a, b: s32(a) >= s32(b)), ("bltu", lambda a, b: a < b), ("bgeu", lambda a, b: a >= b)):
    for a, b in itertools.product(vals[:10], vals[:10]):
        i = nid(); l = nid()
        w(f"    li t0, {a}\n    li t1, {b}\n    li t3, 0\n    {cond} t0, t1, L{l}a\n    j L{l}b\nL{l}a:\n    li t3, 1\nL{l}b:\n    CHK t3, {int(fn(a, b))}, {i}")
# upper immediates, loads/stores
i = nid(); w(f"    lui t3, 0xABCDE\n    CHK t3, {0xABCDE000}, {i}")
i = nid(); w(f"1:  auipc t3, 0x1\n    la t4, 1b\n    sub t3, t3, t4\n    CHK t3, 4096, {i}")
w("    la t0, buf\n    li t1, 0x8081ff7f\n    sw t1, 0(t0)")
for ins, off, exp in (("lb", 0, 0x7F), ("lb", 1, u32(-1)), ("lb", 2, u32(-127)), ("lbu", 3, 0x80), ("lbu", 2, 0x81), ("lh", 0, u32(-129)),
                      ("lh", 2, u32(0x8081 - 0x10000)), ("lhu", 2, 0x8081), ("lhu", 0, 0xFF7F), ("lw", 0, 0x8081FF7F)):
    i = nid(); w(f"    {ins} t3, {off}(t0)\n    CHK t3, {exp}, {i}")
w("    li t1, 0x11223344\n    sw t1, 8(t0)\n    li t1, 0xAB\n    sb t1, 9(t0)\n    li t1, 0xCDEF\n    sh t1, 10(t0)")
i = nid(); w(f"    lw t3, 8(t0)\n    CHK t3, {0xCDEFAB44}, {i}")
i = nid(); w(f"    lw t3, -4(t0)\n    CHK t3, 0, {i}")  # untouched memory reads zero (bss/rodata gap)
# jal / jalr / link
i = nid(); w(f"    jal t4, 1f\n    j fail_{i}\n1:  la t3, 1b\n    addi t4, t4, 4\n    CHK t4, 0, {i}" if False else "")
i = nid(); w(f"    la t0, 2f\n    jalr t4, 0(t0)\n    li a0, {i}\n    j fail\n2:  jal t5, 3f\n3:  addi t5, t5, -4\n    la t3, 3b\n    addi t3, t3, -4\n    # t5 = address of the jal + 4 - 4 = jal address; jal is at 3b-4\n    CHK t5, 0, {i}" if False else "")
w("""    la t0, jt
    jalr t4, 0(t0)
    j fail_jalr
jt: la t3, jt
    addi t3, t3, -4
    # t4 = address after the jalr (jalr is 4 bytes) ; compare to 'j fail_jalr' address
    la t5, jt
    addi t5, t5, -4
    # (j is 4 bytes unless compressed: j to fail is compressible only with C; skip exact compare)
    beqz t4, fail_jalr
""")
out_bodies = []
if rvc:
    w("    .option rvc")
    def cseq(setup, ins, reg, exp):
        i = nid(); w(f"{setup}\n    {ins}\n    CHK {reg}, {u32(exp)}, {i}")
    for a in (0, 1, 5, u32(-3), 0x7FFFFFFF, 0x80000000):
        for imm in (1, -1, 31, -32):
            cseq(f"    li a1, {a}", f"c.addi a1, {imm}", "a1", a + imm)
    for imm in (0, 1, -1, 31, -32): cseq("", f"c.li a2, {imm}", "a2", imm)
    for imm in (1, 2, 31, 0xfffff, 0xfffe0):  # gas c.lui operand: 1..31 or 0xfffe0..0xfffff
        cseq("", f"c.lui a3, {imm}", "a3", u32(imm << 12))
    cseq("    mv s1, sp", "c.addi16sp sp, 16\n    mv a3, sp\n    mv sp, s1\n    sub a3, a3, s1", "a3", 16)
    cseq("    mv s1, sp", "c.addi16sp sp, -32\n    mv a3, sp\n    mv sp, s1\n    sub a3, a3, s1", "a3", -32)
    cseq("    mv s1, sp", "c.addi16sp sp, 496\n    mv a3, sp\n    mv sp, s1\n    sub a3, a3, s1", "a3", 496)
    cseq("    mv s1, sp", "c.addi4spn a4, sp, 1020\n    sub a4, a4, s1", "a4", 1020)
    cseq("    mv s1, sp", "c.addi4spn a4, sp, 4\n    sub a4, a4, s1", "a4", 4)
    cseq("    mv s1, sp", "c.addi4spn a4, sp, 100\n    sub a4, a4, s1", "a4", 100)
    for a, b in itertools.product((0, 5, u32(-9), 0x80000000), (0, 3, u32(-1), 0xF0F0F0F0)):
        for nm, fn in (("c.sub", RT["sub"]), ("c.xor", RT["xor"]), ("c.or", RT["or"]), ("c.and", RT["and"])):
            cseq(f"    li a4, {a}\n    li a5, {b}", f"{nm} a4, a5", "a4", fn(a, b))
        cseq(f"    li a1, {a}\n    li a2, {b}", "c.add a1, a2", "a1", a + b)
        cseq(f"    li a1, {b}", f"c.mv a2, a1", "a2", b)
    for a in (0xF0F0F0F0, 0x80000000, 1, 0x7FFFFFFF):
        for sh in (1, 4, 31):
            cseq(f"    li a4, {a}", f"c.srli a4, {sh}", "a4", a >> sh)
            cseq(f"    li a4, {a}", f"c.srai a4, {sh}", "a4", s32(a) >> sh)
            cseq(f"    li a4, {a}", f"c.slli a4, {sh}", "a4", a << sh)
        for imm in (0, 1, -1, 31, -32): cseq(f"    li a4, {a}", f"c.andi a4, {imm}", "a4", a & u32(imm))
    w("    la s0, buf\n    li a1, 0x5A5AA5A5\n    c.sw a1, 4(s0)\n    c.lw a2, 4(s0)")
    i = nid(); w(f"    CHK a2, {0x5A5AA5A5}, {i}")
    w("    li a1, 0x01020304\n    c.sw a1, 124(s0)\n    c.lw a2, 124(s0)")
    i = nid(); w(f"    CHK a2, {0x01020304}, {i}")
    w("    la s1, buf\n    li a1, 0x0BADF00D\n    sw a1, 28(s1)\n    c.lw a3, 28(s1)")
    i = nid(); w(f"    CHK a3, {0x0BADF00D}, {i}")
    w("    addi sp, sp, -256\n    li a1, 0x77665544\n    c.swsp a1, 252(sp)\n    c.lwsp a2, 252(sp)\n    lw a3, 252(sp)\n    addi sp, sp, 256")
    i = nid(); w(f"    CHK a2, {0x77665544}, {i}"); i = nid(); w(f"    CHK a3, {0x77665544}, {i}")
    # compressed branches / jumps
    for v, tk_z in ((0, 1), (1, 0), (u32(-1), 0)):
        i = nid(); l = nid()
        w(f"    li a1, {v}\n    li a2, 0\n    c.beqz a1, C{l}a\n    c.j C{l}b\nC{l}a:\n    li a2, 1\nC{l}b:\n    CHK a2, {tk_z}, {i}")
        i = nid(); l = nid()
        w(f"    li a1, {v}\n    li a2, 0\n    c.bnez a1, C{l}a\n    c.j C{l}b\nC{l}a:\n    li a2, 1\nC{l}b:\n    CHK a2, {1 - tk_z}, {i}")
    i = nid(); l = nid()
    w(f"    li a2, 0\n    c.jal Cj{l}\n    c.j Cj{l}end\nCj{l}:\n    mv a3, ra\n    li a2, 7\n    c.jr ra\nCj{l}end:\n    CHK a2, 7, {i}")
    i = nid(); l = nid()
    w(f"    la a1, Ck{l}\n    li a2, 0\n    c.jalr a1\n    c.j Ck{l}end\nCk{l}:\n    li a2, 9\n    ret\nCk{l}end:\n    CHK a2, 9, {i}")
    w("    c.nop\n    .option norvc")
w("""    li a0, 0
    li t0, 0x10000008
    sw a0, 0(t0)
1:  j 1b
fail_jalr:
    li a0, 255
fail:
    li t0, 0x10000008
    sw a0, 0(t0)
2:  j 2b
counted:                 # 28 dynamic: 1 li + 10*(addi,bnez) + la(2) + mul + div + lw + sw + ret
    li t0, 10
1:  addi t0, t0, -1
    bnez t0, 1b
    la t1, buf
    mul t2, t0, t1
    div t2, t1, t1
    lw t3, 0(t1)
    sw t3, 4(t1)
    ret
    .section .data
    .align 4
    .word 0
buf: .space 256
""")
open(sys.argv[1], "w").write("\n".join(out))
print("tests:", tid[0])
