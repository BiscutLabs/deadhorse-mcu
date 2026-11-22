.section .start,"ax"
.globl _start
.option norvc
_start:
  li t0, 0x10000000
  jr t0
  .space 16
