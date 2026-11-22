.section .start,"ax",@progbits
.globl _start
_start:
  li t0, 0x40012000
  li t1, 5
  sw t1, 0(t0)
  li t1, 7
  sw t1, 4(t0)
  li t1, 1
  sw t1, 0x200(t0)
  sw t1, 0x204(t0)
  sw t1, 0x208(t0)
1:
  j 1b
