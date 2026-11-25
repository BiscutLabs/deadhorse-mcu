/* SPDX-License-Identifier: Apache-2.0 */
.section .text.start,"ax"
.global _start
.option norelax
_start:
  csrw mie, zero
  csrci mstatus, 8
  la t0, dh_fail
  csrw mtvec, t0
  # T41 warm reset flushes DMA/QSPI with the cores before ROM release.
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
