.section .start,"ax"
.globl _start
.option norvc
.space 16
_start:
  li t0, 200
1: addi t0, t0, -1
  bnez t0, 1b
  li t0, 0x40000300
  li t1, 0x50455246
  sw t1, 4(t0)
2: wfi
  j 2b
