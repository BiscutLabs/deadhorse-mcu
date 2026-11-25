.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li s0, 0x40000100
  li s1, 0x40012000
  lw t0, 20(s0)
  andi t0, t0, 8
  bnez t0, restarted
trigger:
  lw t0,8(s1)
  andi t0,t0,4
  beqz t0,trigger
  li t0, 1
  sw t0, 512(s1)
  sw t0, 516(s1)
  li t0, 3
  sw t0, 4(s1)
  li t0, 1
  sw t0, 0(s1)
#ifdef OFFERED
  li t0, 16
#endif
  sw t0, 0(s0)
#ifndef OFFERED
  sw zero, 4(s0)
#endif
  sw zero, 8(s0)
  li t0, 0x57445354
#ifdef WRONG_START
  addi t0, t0, 1
#endif
  sw t0, 12(s0)
#ifdef OFFERED
#ifndef DELAY_NOPS
#define DELAY_NOPS 1024
#endif
  .rept DELAY_NOPS
  nop
  .endr
  li t0, 0x51a00210
  sw t0, 4(s0)
#endif
waiting:
  wfi
  j waiting
restarted:
  lw t0, 4(s1)
  li t1, 3
  bne t0, t1, failed
  lw t0, 0(s1)
  li t1, 1
  bne t0, t1, failed
  lw t0, 28(s0)
  bne t0, t1, failed
#ifdef OFFERED
  lw t0, 4(s0)
  li t1, 0x51a00210
  bne t0, t1, failed
#endif
  li t0, 2
  sw t0, 0(s1)
done:
  wfi
  j done
failed:
  sw zero, 0(s1)
  j failed
