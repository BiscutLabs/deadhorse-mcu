.section .start, "ax"
.global _start
.option norelax
_start:
  la sp, __stack_top
  li t0, 0x2000
  csrs mstatus, t0
  call main
1:
  wfi
  j 1b
