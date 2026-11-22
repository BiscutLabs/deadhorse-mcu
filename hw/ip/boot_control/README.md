# Lite-first performance release

T28 implements the digital handoff in plans07/16. Existing recovery loading,
image checks, lite execution and shared reset primitives are adopted unchanged.
The two-core release coordination is new clocked Chisel; no upstream block
provided that interface. This is recovery-started sequencing, not flash boot.

The lite-owned AON window is0x40000300..0x400003ff. Generated MMIO preserves
the trusted origin tag; every other origin, unmapped or misaligned access
errors. All bus/pad/clock source contracts are unchanged.

| Offset | Register | Contract |
| --- | --- | --- |
| 0x00 | status | read-only boot_seen bit0, released bit1 |
| 0x04 | release_core | write-only full-word key0x50455246; reads zero |
| 0x08 | events | command_error bit0, W1C, hardware set wins |

boot_seen means a validated loader START was observed in this whole-reset
epoch. It does not certify current execution, image authenticity or lite
health. A correct RELEASE after boot_seen opens performance core/client
reset. A START and RELEASE on the same edge cannot release on that edge.
Correct repeated RELEASE is idempotent. Wrong key or RELEASE before boot_seen
sets command_error without withdrawing an existing release. Partial writes
error through the generated register block; zero-strobe writes do nothing.

Both retained flags reset false on cold, external whole reset or lite-watchdog
whole reset. Assertion is asynchronous. AON service reset clears the register
adapter, command pulses and error event but preserves both flags. A command
interrupted by reset cannot replay; callers may retry idempotently. Commands
are ignored while the service reset is asserted. Performance watchdog/core/
service resets preserve release. The output enters only the performance
core/client's existing ResetRelease, never shared-service or PWM resets.

External main/AON clocks remain required; main may be stopped while release
is requested, and its reset synchronizer waits for main edges. This controller
does not stop/start an oscillator or gate, and demand outputs are not permission
to stop the complete domain. Shared services remain available during initial
core hold. Existing loader programming lock and locked-image warm-reset
restart limitation remain unchanged.

BootRelease outputs and bus responses are registered. Epoch/service reset
inputs are the shared reset-release outputs for their respective cohorts.
Measured standalone mapped area is10793.7984µm², by the pinned
`python hw/ip/boot_control/check_timing.py --output build/t28/frozen01/timing`
subcommand, main HEAD72bcfacc plus receipt-hashed local sources. Worst measured
register path is11.160238ns against estimated0.60×1000/9=66.666667ns, with
zero electrical violations. This pre-layout block screen is conservative for
AON operation, not a whole-SoC area delta or routed timing qualification.
No area allowance is silently added to the SoC budget. Physical reset/RDC/hold
and complete production boot remain open. See the T28 report and formal/.
