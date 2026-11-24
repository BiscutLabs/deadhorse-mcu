.section .start,"ax"
.globl _start
.option norvc
_start:
  # Conventional GPIO ports report firmware results through all three pads.
  li t0, 0x40012000
  li t1, 5
  sw t1, 0(t0)
  li t1, 7
  sw t1, 4(t0)
  li t1, 1
  sw t1, 512(t0)
  sw t1, 516(t0)
  sw t1, 520(t0)
  li t2, 0x40001000
  li t1, 5
  sw t1, 0(t2)
  li t1, 1
  sw t1, 4(t2)
  li t1, 0x200000
  csrw mie, t1
wait:
  wfi
  lw t1, 12(t2)
  andi t1, t1, 2
  beqz t1, wait
  lw t1, 8(t2)
  sw t1, 0(t0)
  li t1, 2
  sw t1, 4(t2)
  j wait
