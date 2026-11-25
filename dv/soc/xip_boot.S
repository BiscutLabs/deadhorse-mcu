.section .start,"ax"
.globl _start
.option norvc
_start:
  li t0, 0x40013000
  li t1, 0x307
  sw t1, 256(t0)
  li t1, 0x58495021
  sw t1, 264(t0)
  li t0, 0x10000000
  jr t0
  .space 16
