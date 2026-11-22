.section .start,"ax"
.globl _start
.option norvc
.space 16
_start:
  li t0, 0x40013000
  li t1, 0x307
  sw t1, 256(t0)
  li t1, 0x58495021
  sw t1, 264(t0)
  li t0, 0x40000300
  li t1, 0x50455246
  sw t1, 4(t0)
1: wfi
  j 1b
