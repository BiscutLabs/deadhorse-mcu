.section .start,"ax"
.globl _start
.option norvc
_start:
  li t0,0x40000200
  li t1,512
  sw t1,0(t0)
  sw zero,4(t0)
  sw zero,8(t0)
  li t1,0x57445354
  sw t1,12(t0)
1: j 1b
