.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  la t0,image
  la t1,image_end
  li t2,0x30000000
copy:
  lw a0,0(t0)
  sw a0,0(t2)
  addi t0,t0,4
  addi t2,t2,4
  bltu t0,t1,copy
  li t0,0x40000300
  li t1,0x50455246
  sw t1,4(t0)
  li t0,0x40000400
  li t1,1
  sw t1,28(t0)
  li t2,0x20003f00
  li t3,0x51052000
  sw t3,0(t2)
  sw t1,0(t0)
  wfi
1: j 1b
.balign 4
image:
.incbin "build/plan05/hung-firmware/lite.bin"
.balign 4
image_end:
