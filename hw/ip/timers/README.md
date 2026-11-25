# General timers

PLAN05 merges the former main timer and PWM into `GeneralTimers` at0x40030000.
The old GPIO timer window0x40012100 is unassigned. The authoritative ABI is
[timers.regmap.yaml](timers.regmap.yaml); the ownership/pin contract is in
[plan05-integration.md](../../../docs/spec/plan05-integration.md).

Three timers each share a16-bit period and prescaler across four channels.
All12 channels support disabled, PWM, output compare and input capture.
Seventeen-bit compare shadows are snapshotted by APPLY and adopted at the
period boundary while running. Unapplied shadow writes cannot alter a queued
snapshot. Period/prescaler/mode changes require STOP. PWM supports duty0 to
period+1; compare requires compare<=period. Input capture stores the32-bit
microsecond timestamp including the current tick. Timebase elaboration accepts
8/9MHz; production runs8MHz. Capture prevents timebase stop/load while running.

The register path checks ownership, alignment, decode and byte enables.
Sticky events have set-over-clear priority. IRQs are per bank. Registered hold
covers timebase activity, any running bank and pending DMA requests. The nine
existing DMA endpoints retain their order, serving channels0..8 through the
merged APPLY/pending registers and shared bank periods. Channels9..11 have no
DMA endpoint.

Performance-watchdog assertion disables timer-driven pads asynchronously.
Retained registers cannot rearm outputs until the ready, drained performance
epoch explicitly STOPs that bank. DMA APPLY cannot acknowledge the interlock.
`TimerBreak` implements the three-bank acknowledgement and `TimerDmaRequests`
preserves the nine-channel pending-event recurrence.

AON deadlines remain unchanged in `hw/ip/aon_timer`, including relative-duration,
cancellation, interrupt and wake semantics. They do not use this timebase.
See [formal/README.md](formal/README.md) and the
[PLAN05 report](../../../docs/plan/tasks/reports/PLAN05.md) for scoped evidence
and outstanding integration work. No physical pad/CDC sign-off is claimed.
