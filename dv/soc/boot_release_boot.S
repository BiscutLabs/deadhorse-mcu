.section .start,"ax"
.globl _start
.option norvc
_start:
  li t0, 0x40012000
  li t1, 5
  sw t1, 0(t0)
  sw t1, 4(t0)
  li t1, 1
  sw t1, 512(t0)
  sw t1, 520(t0)
1: j 1b
