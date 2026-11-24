.section .start,"ax"
.globl _start
.option norvc
.option norelax
.space 16
_start:
  li s0, 0x40000400
  li t0, 0x40000300
  li t1, 0x50455246
  sw t1, 4(t0)
  li a0, 0x40001000
booted:
  lw t0, 12(a0)
  andi t0, t0, 2
  beqz t0, booted
  lw t0, 8(a0)
  li t1, 5
  bne t0, t1, failed
  li t0, 2
  sw t0, 4(a0)
  li t0, 4
  sw t0, 8(s0)
  li t0, 6
  sw t0, 12(s0)
  li t0, 64
  sw t0, 40(s0)
  li t0, 1
  sw t0, 28(s0)
  li t0, 0x15
  sw t0, 36(s0)
#ifdef LITE_WD_RESET
  # Use the real lite watchdog; no testbench reset or wake injection.
  li a1, 0x40000200
  li t0, 1024
  sw t0, 0(a1)
  sw zero, 8(a1)
  li t0, 0x57445354
  sw t0, 12(a1)
  li t0, 1
  sw t0, 0(s0)
reset_wait:
  j reset_wait
#elif defined(SKIP_SLEEP)
  # Paired flight-loop baseline: same firmware handshake, no sleep request.
#elif defined(HOST_WAKE)
  li s1, HOST_WAKE
  sw s1, 4(s0)
  li t0, 200
host_settle:
  addi t0, t0, -1
  bnez t0, host_settle
  li t0, 1
  sw t0, 0(s0)
host_off:
  lw t0, 16(s0)
  andi t0, t0, 3
  li t1, 2
  bne t0, t1, host_off
host_run:
  lw t0, 16(s0)
  andi t0, t0, 3
  bnez t0, host_run
  lw t0, 24(s0)
  bne t0, s1, failed
#elif defined(EXTRA_WAKE)
  # Timer and mailbox are real AON producers; the host supplies no wake pin.
  li s1, 1
  sw s1, 4(s0)
  li a1, 0x40000000
  li t0, 512
  sw t0, 32(a1)
  sw s1, 12(a1)
  sw s1, 0(a1)
  sw s1, 0(s0)
timer_off:
  lw t0, 16(s0)
  andi t0, t0, 3
  li t1, 2
  bne t0, t1, timer_off
timer_run:
  lw t0, 16(s0)
  andi t0, t0, 3
  bnez t0, timer_run
  lw t0, 24(s0)
  bne t0, s1, failed
  sw s1, 4(a1)
  li s1, 64
  sw s1, 4(s0)
  li t0, 1
  sw t0, 0(s0)
mailbox_off:
  lw t0, 16(s0)
  andi t0, t0, 3
  li t1, 2
  bne t0, t1, mailbox_off
  li t0, 200
mailbox_delay:
  addi t0, t0, -1
  bnez t0, mailbox_delay
  li t0, 5
  sw t0, 0(a0)
  li t0, 1
  sw t0, 4(a0)
mailbox_run:
  lw t0, 16(s0)
  andi t0, t0, 3
  bnez t0, mailbox_run
  lw t0, 24(s0)
  bne t0, s1, failed
#else
  li s1, 4
next_uart:
  sw s1, 4(s0)
  li t0, 200
settle:
  addi t0, t0, -1
  bnez t0, settle
  li t0, 1
  sw t0, 0(s0)
wait_off:
  lw t0, 16(s0)
  andi t0, t0, 3
  li t1, 2
  bne t0, t1, wait_off
wait_run:
  lw t0, 16(s0)
  andi t0, t0, 3
  bnez t0, wait_run
  # Causes are latched on the first RUN edge after qualification.
  lw t0, 24(s0)
  bne t0, s1, failed
  slli s1, s1, 1
  li t0, 32
  bne s1, t0, next_uart
#endif
  li t0, 1
  j report
failed:
  li t0, 0
report:
  li t1, 0x40001000
  sw t0, 0(t1)
  li t0, 1
  sw t0, 4(t1)
done:
  wfi
  j done
