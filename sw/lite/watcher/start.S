/* SPDX-License-Identifier: Apache-2.0 */
.section .start,"ax",@progbits
.global _start
_start:
  la sp, __stack_top
  la t0, __bss_start
  la t1, __bss_end
1:
  bgeu t0, t1, 2f
  sw zero, 0(t0)
  addi t0, t0, 4
  j 1b
2:
  call watcher
3:
  wfi
  j 3b
