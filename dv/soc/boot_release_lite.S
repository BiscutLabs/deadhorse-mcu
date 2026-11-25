.section .start,"ax"
.globl _start
.option norvc
_start:
  li t0, 0x30000400
  li t1, 0x28
  sw t1, 0(t0)
1: wfi
  j 1b
