.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li s0, 0x20003f00
#if HOLD_KIND == 1
  li t0, 0x40030000
  sw zero, 0x30(t0)
  li t1, 15
  sw t1, 0x40(t0)
  li t1, 5
  sw t1, 0x80(t0)
  li t1, 4
  sw t1, 0xc0(t0)
  li t1, 1
  sw t1, 0x14(t0)
  sw t1, 0x30(t0)
#elif HOLD_KIND == 2
  li t0, 0x40011000
  li t1, 0x20003000
  sw t1, 0x20(t0)
  li t1, 4
  sw t1, 0x30(t0)
  li t1, 1
  sw t1, 0x40(t0)
  sw t1, 0(t0)
#elif HOLD_KIND == 3
  li t0, 0x40040800
  li t1, 1
  sw t1, 0(t0)
connected:
  lw t1, 16(t0)
  andi t1, t1, 8
  beqz t1, connected
#endif
  li t0, 0x40000400
  li t1, 1
  sw t1, 28(t0)
  li t2, 0x51051000+HOLD_KIND
  sw t2, 0(s0)
  sw t1, 0(t0)
  wfi
1: j 1b
