.section .start,"ax"
.globl _start
.option norvc
.option norelax
_start:
  li s0, 0x20003f00
  li t0, 0x51050001
  sw t0, 0(s0)
  la t0, watcher_image
  la t1, watcher_end
  li t2, 0x30000000
copy:
  lw a0, 0(t0)
  sw a0, 0(t2)
  addi t0, t0, 4
  addi t2, t2, 4
  bltu t0, t1, copy
  li t0, 0x51050002
  sw t0, 0(s0)
  li t0, 0x40000300
  li t1, 0x50455246
  sw t1, 4(t0)
  # Let the real LF watcher complete pad handoff and initial configuration.
  # A fixed diagnostic delay; not a boot-ROM policy or a latency measurement.
  li t0, 250000
settle:
  addi t0, t0, -1
  bnez t0, settle
  li t0, 0x40012000
  li t1, 5
  sw t1, 0(t0)
  li t1, 0x13579bdf
  sw t1, 4(s0)
  li s1, 0x40000400
  li t0, 64
  sw t0, 4(s1)
  li t0, 4
  sw t0, 8(s1)
  li t0, 6
  sw t0, 12(s1)
  li t0, 64
  sw t0, 40(s1)
  li t0, 1
  sw t0, 28(s1)
  li t1, 0x40000100
  li t0, 1000
  sw t0, 0(t1)
  sw zero, 4(t1)
  sw zero, 8(t1)
  li t0, 0x57445354
  sw t0, 12(t1)
  li t0, 0x200000
  csrw mie, t0
  csrci mstatus, 8
  li t0, 0x51050003
  sw t0, 0(s0)
  li t0, 1
  sw t0, 0(s1)
  wfi
  # Resume path must execute without another ROM entry or image copy.
  lw t0, 4(s0)
  li t1, 0x13579bdf
  bne t0, t1, failed
  li t0, 0x40012000
  lw t1, 0(t0)
  li t2, 5
  bne t1, t2, failed
  li t0, 0x40001000
  lw t1, 8(t0)
  li t2, 0x57071234
  bne t1, t2, failed
  li t1, 2
  sw t1, 4(t0)
  li t0, 0x51050004
  sw t0, 0(s0)
done:
  wfi
  j done
failed:
  li t0, 0x0bad0505
  sw t0, 0(s0)
  j failed
.balign 4
watcher_image:
.incbin "build/plan05/watcher-opt05/watcher.bin"
.balign 4
watcher_end:
