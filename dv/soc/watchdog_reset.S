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
  sw zero, 0x30(s1)
  sw zero, 0x240(s2)
  li t0, 5
  sw t0, 0x80(s1)
  li t0, 999
  sw t0, 64(s1)
  li t0, 1000
  sw t0, 192(s1)
  li t0, 1
  sw t0, 0x14(s1)
  sw t0, 0x30(s1)
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
  # D103 warm reset clears ordinary DMA/GPIO/timer state, retaining causes.
  lw t0, 48(s3)
  bnez t0, failed
  lw t0, 0(s2)
  bnez t0, failed
  lw t0, 4(s2)
  bnez t0, failed
  lw t0, 0x30(s1)
  bnez t0, failed
  lw t0, 0x80(s1)
  bnez t0, failed
  li t0, 6
  sw t0, 4(s2)
  li t0, 3
  sw t0, 512(s2)
  li t0, 1
  sw t0, 516(s2)
  sw t0, 520(s2)
  li t0, 4
  sw t0, 0(s2)
2: j 2b
failed:
  li t0, 6
  sw t0, 4(s2)
  li t0, 3
  sw t0, 512(s2)
  li t0, 1
  sw t0, 516(s2)
  sw t0, 520(s2)
  li t0, 2
  sw t0, 0(s2)
3: j 3b
