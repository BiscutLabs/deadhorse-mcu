.section .start,"ax"
.option norvc
.option norelax
.space 16
.globl _start
_start:
  lui s0, 0x30001
  addi s0, s0, -2048
  lui s1, 0x40001
  lui a0, 0x40000
  sw zero, 0(s0)
  la t0, handler
  csrw mtvec, t0
  li t0, 2048
  csrw mie, t0
  li t0, 1
  sw t0, 8(a0)
  li t0, 1000
  sw t0, 32(a0)
  li t0, 1
  sw t0, 0(a0)
  csrsi mstatus, 8
sleep:
  wfi
  j sleep
handler:
  csrr t0, mcause
  li t1, 0x8000000b
  bne t0, t1, unexpected
  lw t0, 4(a0)
  andi t0, t0, 1
  beqz t0, mailbox
  sw t0, 4(a0)
  li a1, 0x100
  j answer
mailbox:
  lw t0, 12(s1)
  andi t0, t0, 2
  beqz t0, return
  lw a1, 8(s1)
  li t0, 2
  sw t0, 4(s1)
answer:
  lw a2, 0(s0)
  addi a2, a2, 1
  sw a2, 0(s0)
  add a1, a1, a2
ready:
  lw t0, 12(s1)
  andi t0, t0, 1
  beqz t0, ready
  sw a1, 0(s1)
  li t0, 1
  sw t0, 4(s1)
return:
  mret
unexpected:
  li t0, -1
  sw t0, 0(s0)
  j unexpected
