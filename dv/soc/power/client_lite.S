.section .start,"ax"
.globl _start
.option norvc
.option norelax
.space 16
_start:
#ifdef RELEASE_PERF
  li t0, 0x40000300
  li t1, 0x50455246
  sw t1, 4(t0)
#else
  li t0, 0x4001300c
  li t1, 0x51a03110
  sw t1, 0(t0)
  lw t2, 0(t0)
  bne t2, t1, failed
#endif
done:
  wfi
  j done
#ifndef RELEASE_PERF
failed:
  li t1, 0x0bad0311
  sw t1, 0(t0)
  j failed
#endif
