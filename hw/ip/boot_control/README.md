# Performance-owned lite boot control

PLAN05 E1/C3 replaces the former lite-first performance release. Performance
is the sole boot master. Lite is held in reset until performance explicitly
releases it at the retained program-RAM base. The AON register window remains
0x40000300; only performance-origin accesses are admitted.

| Offset | Register | Contract |
| --- | --- | --- |
| 0x00 | status | held0, released1, draining2, fresh_performance_reset3, context_ready4 |
| 0x04 | release_core | full-word key0x50455246; reads zero |
| 0x08 | events | command_error0, W1C, hardware set wins |
| 0x0c | hold_core | full-word key0x484f4c44; drain before writable held state |
| 0x10 | boot_mode | read-only reset-sampled strap0 |
| 0x14 | context_commit | full-word key0x434f4e54 records completed ROM context; reads zero |

`LiteBootState` distinguishes held, running and draining. HOLD stops lite at
its instruction boundary and drains outstanding memory/fabric operations before
acknowledging held. Debug ownership cannot become a writable boot hold, and
release waits for debug ownership to clear. Whole-chip/AON epoch reset returns
to held asynchronously; a performance-only reset preserves lite execution and
RAM. Register-service reset clears command transport/errors without replaying
commands. Invalid keys, origins, partial command writes or commands in unsafe
states do not grant release or memory permission.

C3 program write authority is enforced at retained-memory grant: performance
only, while the acknowledged boot hold is active. Lite and direct debug SBA
cannot write the program region. Debug may load it through performance-hart
execution under the same hold rule. Program/data memory stays powered across
sleep and reset. Production boot ROM implementation is a separate PLAN05/T36
phase; these controls do not validate image contents themselves.

`BootModeStrap` samples during the whole-reset qualification window and freezes
before serial pin ownership is enabled. Performance-only reset does not resample.
See [formal/README.md](formal/README.md), [soc.md](../../../docs/spec/soc.md) and
the [PLAN05 report](../../../docs/plan/tasks/reports/PLAN05.md) for exact evidence,
reset composition and outstanding work. Historical T28 measurements describe
the retired controller, not this implementation.

`BootResetContext` clears only on the AON/whole reset epoch. A new performance
watchdog hold edge sets `fresh_performance_reset`; a stale hold spanning whole
reset does not. The keyed context commit sets `context_ready` after firmware
has validated and committed its retained context. Both flags survive register
service and performance-only resets. They grant no memory access or hart release.
A wrong key has no effect and sets `command_error`; denied origins and partial
writes retain the adapter's bus-error behavior. C4 ROM fails closed if a fresh
performance reset lacks committed current-epoch context. The flags do not
replace the context/image CRC and bounds checks in firmware.
