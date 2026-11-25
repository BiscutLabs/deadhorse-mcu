.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li s0,0x40012000
  li s1,0x40000400
  li s2,0x40001000
  li t0,5
  sw t0,0(s0)
  sw t0,4(s0)
  li t0,1
  sw t0,512(s0)
  sw t0,520(s0)
  # After the whole-chip watchdog reset this diagnostic reports recovery and
  # leaves lite held, rather than immediately restarting the intentionally hung helper.
  li t0,0x40000500
  lw t0,0(t0)
  andi t0,t0,16
  bnez t0,success
#ifdef IDLE_ONLY
  j done
#endif
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
#ifdef GPIO_WAKE
gpio_ready:
  lw t0,40(s0)
  andi t0,t0,8
  beqz t0,gpio_ready
  li t0,2
  sw t0,28(s0)
  sw t0,32(s0)
  li t0,1
  sw t0,36(s0)
gpio_armed:
  lw t0,40(s0)
  andi t0,t0,3
  li t1,2
  bne t0,t1,gpio_armed
#endif
#ifdef USB_WAKE
  li t2,0x40040800
  li t0,1
  sw t0,0(t2)
usb_connected:
  lw t0,16(t2)
  andi t0,t0,8
  beqz t0,usb_connected
  li t0,2
  sw t0,8(t2)
#endif
  li t0,4
  sw t0,8(s1)
  li t0,6
  sw t0,12(s1)
  li t0,64
  sw t0,40(s1)
  li t0,1
  sw t0,28(s1)
  li t0,0x15
  sw t0,36(s1)
#ifdef LITE_WD_RESET
  li a0,8
  jal ra,send
  li t0,1
  sw t0,0(s1)
  wfi
  j failed
#elif defined(EXTRA_WAKE)
  li s3,1
#elif defined(HOST_WAKE)
  li s3,HOST_WAKE
#else
  li s3,4
#endif
next_wake:
  sw s3,4(s1)
  li t0,64
  beq s3,t0,mail_wake
  # Lite owns the AON timer. Its IRQ lets WFI finish after the externally
  # selected wake has restarted main; masking timer wake preserves source attribution.
  li a0,1
  jal ra,exchange
  li t0,0x08000000
  csrw mie,t0
  j sleep
mail_wake:
  li a0,3
  jal ra,send
  li t0,0x200000
  csrw mie,t0
sleep:
  csrci mstatus,8
  li t0,1
  sw t0,0(s1)
  wfi
wait_run:
  lw t0,16(s1)
  andi t0,t0,3
  bnez t0,wait_run
  lw t0,24(s1)
  bne t0,s3,failed
  li t0,64
  beq s3,t0,mail_done
  li a0,2
  jal ra,exchange
#ifdef EXTRA_WAKE
  li s3,64
  j next_wake
#elif !defined(HOST_WAKE)
  slli s3,s3,1
  li t0,32
  bne s3,t0,next_wake
#endif
  j success
mail_done:
  li t0,2
  sw t0,4(s2)
success:
  li t0,1
  sw t0,0(s0)
done: wfi
  j done
failed:
  sw zero,0(s0)
  j failed
send:
  lw t0,12(s2)
  andi t0,t0,1
  beqz t0,send
  sw a0,0(s2)
  li t0,1
  sw t0,4(s2)
  ret
exchange:
  mv s4,ra
  jal ra,send
wait_reply:
  lw t0,12(s2)
  andi t0,t0,2
  beqz t0,wait_reply
  lw t0,8(s2)
  li t1,1
  bne t0,t1,failed
  li t0,2
  sw t0,4(s2)
  jr s4
.balign 4
image:
.incbin "build/plan04/sleep-firmware/lite-helper.bin"
.balign 4
image_end:
