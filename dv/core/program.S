.section .text
.global _start
_start:
.option norvc
.irp n,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
  addi x\n, zero, 0
.endr
  lui sp, 0x80008
  li a0, -123
  li a1, 37
  add a2, a0, a1
  sub a3, a1, a0
  slt a4, a0, a1
  sltu a5, a0, a1
  xor a6, a0, a1
  or a7, a0, a1
  and t0, a0, a1
  sll t1, a0, a1
  srl t2, a0, a1
  sra t3, a0, a1
  mul t0, a0, a1
  mulh t1, a0, a1
  mulhsu t2, a0, a1
  mulhu t3, a0, a1
  div t4, a0, a1
  divu t5, a0, a1
  rem t6, a0, a1
  remu s0, a0, a1
  div s1, a0, zero
  rem s2, a0, zero
  li t0, 0x80000000
  li t1, -1
  div s3, t0, t1
  rem s4, t0, t1
  sw a0, 0(sp)
  lb s5, 0(sp)
  lbu s6, 0(sp)
  lh s7, 0(sp)
  lhu s8, 0(sp)
  lw s9, 0(sp)
  sb a1, 1(sp)
  sh a2, 2(sp)
  lw s10, 0(sp)
  auipc s11, 0
  addi t0, zero, 4
loop:
  addi t0, t0, -1
  bne t0, zero, loop
  jal ra, subroutine
  beq zero, zero, after_sub
subroutine:
  addi a0, a0, 1
  jalr zero, ra, 0
after_sub:
  csrrw a2, mscratch, a1
  csrrs a3, mscratch, zero
  csrrc a4, mscratch, a0
  fence
.option rvc
  c.li s0, 3
  c.addi s0, 2
  c.mv s1, s0
  c.add s1, s0
  c.slli s1, 2
  c.swsp s1, 4(sp)
  c.lwsp s2, 4(sp)
  c.j compressed_target
  c.ebreak
compressed_target:
  c.nop
.option norvc
  lui t0, 0x100
  li t1, 0x5555
  sw t1, 0(t0)
  j .
