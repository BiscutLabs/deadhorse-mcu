.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li s0,0x40001000
  li s1,0x40000000
next:
  lw t0,12(s0)
  andi t0,t0,2
  beqz t0,next
  lw a0,8(s0)
  li t0,2
  sw t0,4(s0)
  li t0,1
  beq a0,t0,arm
  li t0,2
  beq a0,t0,clear
  li t0,8
  beq a0,t0,watchdog
  # Delayed mailbox wake (only for the mailbox-source case).
  li t0,50
delay:
  addi t0,t0,-1
  bnez t0,delay
  j reply
arm:
  li t0,512
  sw t0,32(s1)
  li t0,1
  sw t0,8(s1)
  sw t0,12(s1)
  sw t0,0(s1)
  j reply
clear:
  li t0,1
  sw t0,4(s1)
reply:
  li t0,1
  sw t0,0(s0)
  sw t0,4(s0)
  j next
watchdog:
  li t1,0x40000200
  li t0,1024
  sw t0,0(t1)
  sw zero,8(t1)
  li t0,0x57445354
  sw t0,12(t1)
hung: j hung
