.section .text.start,"ax"
.global _start
_start:
  .option push
  .option norelax
  la sp, __stack_top
  .option pop
  la t0, __bss_start
  la t1, __bss_end
1:
  bgeu t0, t1, 2f
  sb zero, 0(t0)
  addi t0, t0, 1
  j 1b
2:
  li t0, 0x2000
  csrs mstatus, t0
  fscsr zero
  la t0, trap_entry
  csrw mtvec, t0
  call main
  tail finish

/* Explicit conservative interruption fixture: all GPRs except sp/x0 and all
 * 32 F registers plus fcsr. Synchronous ecall, not a pin-latency measurement. */
.section .text.trap_entry,"ax"
.balign 4
.global trap_entry
.type trap_entry,@function
trap_entry:
  addi sp, sp, -256
  sw ra, 0(sp)
  sw gp, 4(sp)
  sw tp, 8(sp)
  sw t0, 12(sp)
  sw t1, 16(sp)
  sw t2, 20(sp)
  sw s0, 24(sp)
  sw s1, 28(sp)
  sw a0, 32(sp)
  sw a1, 36(sp)
  sw a2, 40(sp)
  sw a3, 44(sp)
  sw a4, 48(sp)
  sw a5, 52(sp)
  sw a6, 56(sp)
  sw a7, 60(sp)
  sw s2, 64(sp)
  sw s3, 68(sp)
  sw s4, 72(sp)
  sw s5, 76(sp)
  sw s6, 80(sp)
  sw s7, 84(sp)
  sw s8, 88(sp)
  sw s9, 92(sp)
  sw s10, 96(sp)
  sw s11, 100(sp)
  sw t3, 104(sp)
  sw t4, 108(sp)
  sw t5, 112(sp)
  sw t6, 116(sp)
  .set off, 120
  .irp reg, f0,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18,f19,f20,f21,f22,f23,f24,f25,f26,f27,f28,f29,f30,f31
    fsw \reg, off(sp)
    .set off, off+4
  .endr
  frcsr t0
  sw t0, 248(sp)
  csrr a0, mcause
  call trap_handler
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  lw t0, 248(sp)
  fscsr t0
  .set off, 120
  .irp reg, f0,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18,f19,f20,f21,f22,f23,f24,f25,f26,f27,f28,f29,f30,f31
    flw \reg, off(sp)
    .set off, off+4
  .endr
  lw ra, 0(sp)
  lw gp, 4(sp)
  lw tp, 8(sp)
  lw t0, 12(sp)
  lw t1, 16(sp)
  lw t2, 20(sp)
  lw s0, 24(sp)
  lw s1, 28(sp)
  lw a0, 32(sp)
  lw a1, 36(sp)
  lw a2, 40(sp)
  lw a3, 44(sp)
  lw a4, 48(sp)
  lw a5, 52(sp)
  lw a6, 56(sp)
  lw a7, 60(sp)
  lw s2, 64(sp)
  lw s3, 68(sp)
  lw s4, 72(sp)
  lw s5, 76(sp)
  lw s6, 80(sp)
  lw s7, 84(sp)
  lw s8, 88(sp)
  lw s9, 92(sp)
  lw s10, 96(sp)
  lw s11, 100(sp)
  lw t3, 104(sp)
  lw t4, 108(sp)
  lw t5, 112(sp)
  lw t6, 116(sp)
  addi sp, sp, 256
  mret
.size trap_entry, .-trap_entry
