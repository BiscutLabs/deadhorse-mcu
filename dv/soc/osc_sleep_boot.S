.section .start,"ax"
.globl _start
.option norvc
_start:
  li t0, 0x40012000
  li t1, 5
  sw t1, 0(t0)
  sw t1, 4(t0)
  li t1, 1
  sw t1, 512(t0)
  sw t1, 520(t0)
#ifdef GPIO_WAKE
  # Configure GPIO1 as a positive-level AON wake before reporting ready.
gpio_ready:
  lw t1, 40(t0)
  andi t1, t1, 8
  beqz t1, gpio_ready
  li t1, 2
  sw t1, 28(t0)
  sw t1, 32(t0)
  li t1, 1
  sw t1, 36(t0)
gpio_armed:
  lw t1, 40(t0)
  andi t1, t1, 3
  li t2, 2
  bne t1, t2, gpio_armed
#endif
#ifdef USB_WAKE
  li t2, 0x40040800
  li t1, 1
  sw t1, 0(t2)
usb_connected:
  lw t1, 16(t2)
  andi t1, t1, 8
  beqz t1, usb_connected
  li t1, 2
  sw t1, 8(t2)
#endif
  li t2, 0x40001000
  li t1, 5
  sw t1, 0(t2)
  li t1, 1
  sw t1, 4(t2)
  li t1, 0x200000
  csrw mie, t1
1: wfi
  lw t1, 12(t2)
  andi t1, t1, 2
  beqz t1, 1b
  lw t1, 8(t2)
  sw t1, 0(t0)
  li t1, 2
  sw t1, 4(t2)
  j 1b
