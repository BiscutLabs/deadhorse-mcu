.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  # Own AON watchdog period only; deliberately never ARM the watchdog.
  li t0,0x40000200
  li t1,0x51a03110
  sw t1,0(t0)
  lw t2,0(t0)
  bne t2,t1,failed
done:
  wfi
  j done
failed:
  li t1,0x0bad0311
  sw t1,0(t0)
  j failed
