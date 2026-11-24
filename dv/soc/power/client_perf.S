.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li t0, 0x40000100
  li t1, 0x51a00110
  sw t1, 0(t0)
  lw t2, 0(t0)
  bne t2, t1, failed
done:
  wfi
  j done
failed:
  li t1, 0x0bad0011
  sw t1, 0(t0)
  j failed
