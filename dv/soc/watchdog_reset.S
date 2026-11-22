.section .start,"ax"
.globl _start
_start:
  li s0, 0x40000100
  li s1, 0x40030000
  li s2, 0x40012000
  li s3, 0x40011000
  lw t0, 20(s0)
  andi t0, t0, 8
  bnez t0, restarted
  li t0, 1
  sw t0, 4(s1)
  li t0, 999
  sw t0, 64(s1)
  li t0, 1000
  sw t0, 192(s1)
  li t0, 1
  sw t0, 0(s1)
  li t0, 6
  sw t0, 0(s2)
  sw t0, 4(s2)
  li t0, 3
  sw t0, 512(s2)
  li t0, 1
  sw t0, 516(s2)
  sw t0, 520(s2)
  li t0, 17
  sw t0, 48(s3)
  li t0, 200
  sw t0, 0(s0)
  li t0, 32
  sw t0, 8(s0)
  li t0, 0x57445354
  sw t0, 12(s0)
1: j 1b
restarted:
  lw t0, 48(s3)
  li t1, 17
  bne t0, t1, failed
  lw t0, 0(s2)
  li t1, 6
  bne t0, t1, failed
  li t0, 1
  sw t0, 0(s1)
  lw t0, 8(s1)
  bnez t0, failed
  li t0, 4
  sw t0, 0(s2)
2: j 2b
failed:
  li t0, 2
  sw t0, 0(s2)
3: j 3b
