/* SPDX-License-Identifier: Apache-2.0 */
.section .text.start,"ax"
.global _start
.option norelax
_start:
  csrw mie, zero
  csrci mstatus, 8
  la t0, dh_fail
  csrw mtvec, t0
  # No stack or SRAM write before surviving DMA and QSPI have drained.
  csrr t0, mcycle
  li t1, 16000000
  li t2, 0x40011008
  li t3, 0x4001301c
  li t6, 1048576
1:
  lw t4, 0(t2)
  andi t4, t4, 15
  lw t5, 0(t3)
  andi t5, t5, 1
  or t4, t4, t5
  beqz t4, 2f
  csrr t4, mcycle
  sub t4, t4, t0
  bgeu t4, t1, dh_fail
  addi t6, t6, -1
  bnez t6, 1b
  j dh_fail
2:
  li sp, 0x20004000
  la t0, __bss_start
  la t1, __bss_end
3:
  bgeu t0, t1, 4f
  sw zero, 0(t0)
  addi t0, t0, 4
  j 3b
4:
  call boot_main
.balign 4
.global dh_fail
dh_fail:
  wfi
  j dh_fail
.global dh_run_recovery
dh_run_recovery:
  # Recovery never returns. Directory arguments point to static globals.
  # Discard the cold-boot call chain before servicing nested BUSY replies.
  li sp, 0x20004000
  tail dh_recovery_loop
