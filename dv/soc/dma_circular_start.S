.section .start,"ax"
.globl _start
_start:
  li sp, 0x20003ff0
  call main
1: j 1b
