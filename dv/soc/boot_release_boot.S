.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li t0, 0x40000300
  lw t1, 0(t0)
  andi t1, t1, 1
  beqz t1, configured
  la t1, lite_image
  la t2, lite_end
  li a0, 0x30000000
copy:
  lw a1, 0(t1)
  sw a1, 0(a0)
  addi t1, t1, 4
  addi a0, a0, 4
  bltu t1, t2, copy
  li t1, 0x50455246
  sw t1, 4(t0)
configured:
  li t0, 0x40012000
  li t1, 5
  sw t1, 0(t0)
  sw t1, 4(t0)
  li t1, 1
  sw t1, 512(t0)
  sw t1, 520(t0)
1: j 1b
.balign 4
lite_image:
.incbin "build/t28/firmware/lite.bin"
.balign 4
lite_end:
