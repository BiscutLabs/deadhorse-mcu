.section .start,"ax"
.globl _start
.option norvc
_start:
  // Both instruction fetch and an ordinary data load traverse native flash.
  la t0, signature
  lw t1, 0(t0)
  li t2, 0x13579b05
  bne t1, t2, fail
  li t0, 0x40012000
  andi t1, t1, 7
  sw t1, 0(t0)
  sw t1, 4(t0)
  li t1, 1
  sw t1, 512(t0)
  sw t1, 520(t0)
1: j 1b
fail:
  j fail
.balign 4
signature:
  .word 0x13579b05
