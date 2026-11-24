.section .start,"ax"
.globl _start
.option norvc
.option norelax
.space 16
_start:
  li s0, 0x40000500
  li s1, 0x40001000
  li t0, 0x40000300
  li t1, 0x50455246
  sw t1, 4(t0)
ready:
  lw t0, 12(s1)
  andi t0, t0, 2
  beqz t0, ready
  lw t0, 8(s1)
  li t1, 5
  bne t0, t1, failed
  li t0, 2
  sw t0, 4(s1)
  # Return the actual software-visible reason over the mailbox/GPIO path.
  lw t0, 0(s0)
  li t1, 1
  beq t0, t1, reason_valid
  li t1, 2
  bne t0, t1, failed
reason_valid:
  jal ra, report
  li a0, 100
reason_delay:
  addi a0, a0, -1
  bnez a0, reason_delay
  li t0, 4
  jal ra, report
  # Host changes only the supply model while this ordinary firmware runs.
  li a0, 100
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
  jal ra, report
done:
  wfi
  j done
failed:
  li t0, 0
  jal ra, report
  j done
report:
  sw t0, 0(s1)
  li t1, 1
  sw t1, 4(s1)
  ret
