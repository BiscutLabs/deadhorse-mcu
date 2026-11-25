.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  # Diagnostic external-clock fixture: let AON release before requesting it.
  li t0,4096
settle:
  addi t0,t0,-1
  bnez t0,settle
  li t0,0x40000300
  lw t1,0(t0)
  andi t1,t1,1
  beqz t1,done
  li t1,0x30000000
  li t2,0x0000006f
  sw t2,0(t1)
  li t1,0x50455246
  sw t1,4(t0)
done:
  wfi
  j done
