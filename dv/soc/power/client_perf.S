.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  # Board GPIO0 triggers a single diagnostic transaction per reset epoch.
  li t0,0x40012008
wait:
  lw t1,0(t0)
  beqz t1,wait
#ifdef LITE_CLIENT
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
#else
  li t0,0x40000100
  li t1,0x51a00110
  sw t1,0(t0)
  lw t2,0(t0)
  bne t2,t1,failed
#endif
done:
  wfi
  j done
failed:
  li t1,0x0bad0011
  sw t1,0(t0)
  j failed
.balign 4
#ifdef LITE_CLIENT
image:
.incbin "build/t33/client-firmware/lite.bin"
image_end:
#endif
