.section .start,"ax"
.globl _start
.option norvc
_start:
  li s0, 0x40000500
  li s1, 0x40012000
  li t0, 7
  sw t0, 4(s1)
  li t0, 1
  sw t0, 512(s1)
  sw t0, 516(s1)
  sw t0, 520(s1)
ready:
  lw t0, 8(s1)
  andi t0, t0, 1
  beqz t0, ready
  lw t0, 0(s0)
  li t1, 1
  beq t0, t1, reason_valid
  li t1, 2
  bne t0, t1, failed
reason_valid:
  sw t0, 0(s1)
  li a0, 20000
reason_delay:
  addi a0, a0, -1
  bnez a0, reason_delay
  li t0, 4
  sw t0, 0(s1)
  li a0, 20000
switch_delay:
  addi a0, a0, -1
  bnez a0, switch_delay
  li t0, 1
  sw t0, 4(s0)
#ifdef WRONG_KEY
  li t0, 0x42524f56
#else
  li t0, 0x42524f57
#endif
  sw t0, 8(s0)
  lw t0, 12(s0)
  sltiu t1, t0, 2
  beqz t1, failed
  ori t0, t0, 6
  sw t0, 0(s1)
done:
  wfi
  j done
failed:
  sw zero, 0(s1)
  j done
