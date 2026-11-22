.section .start,"ax",@progbits
.globl _start
_start:
  li t0, 0x40030000
  li t1, 1
  sw t1, 4(t0)
  li t1, 9999
  sw t1, 0x40(t0)
  li t1, 5000
  sw t1, 0xc0(t0)
  li t1, 1
  sw t1, 0(t0)
  li t1, 7
  sw t1, 0x40(t0)
  li t1, 2
  sw t1, 0xc0(t0)
  li t1, 1
  sw t1, 0(t0)
1:
  j 1b
