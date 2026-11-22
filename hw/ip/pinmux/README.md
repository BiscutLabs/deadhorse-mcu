# Limited GPIO output pin mux (T24)

Three main-domain GPIO output pads have the same per-index selection table:

| Select | Output source for GPIO pad i |
| --- | --- |
| 0 | Disconnected: data0, output-enable0 |
| 1 | GPIO output i and its enable |
| 2 | Main timer compare i and its enable |
| 3 | PWM output i and its enable |

These are logical alternatives on the existing GPIO pads, not a physical pad
map freeze. Dedicated timer/PWM outputs remain connected and can operate
simultaneously. GPIO synchronized input, edge IRQ and AON wake still observe
the same raw GPIO input pins. No peripheral input routing, clocks, resets,
JTAG, serial pins or new CDC are introduced.

All inputs to the output selector are synchronous main-domain signals. Output
data and enable are flops. With a stable selection, they sample the selected
source on each main edge (one-edge latency). When the requested selection
differs from the active selection, the next edge records the new selection
and drives data/enable0 for a whole sample interval. The following edge may
drive the new source, provided the selection has not changed again. Repeated
changes keep it disabled. Selecting0 always disables, and a disabled source
always produces data0. No glitch-free whole-pulse handover is promised;
firmware must stop/quiesce a source if truncated pulses are unacceptable.

Main-service reset asynchronously clears selection and output flops. Release
comes from the existing shared reset-release block. Cold/warm reset includes
main-service reset. Core-only/AON reset preserves the mux; existing GPIO AON
wake transport retains its separately documented reset semantics.

Generated MMIO at 0x40012200 in the opt-in profile, size256 bytes. Performance
owner1; the standard adapter rejects other origins and out-of-window accesses.
Reserved bits read0, byte strobes use ordinary RegBlock semantics.

| Offset | Register | Meaning |
| --- | --- | --- |
| 0x00..0x08 | select[3] | rw bits1:0, requested source, reset0 |
| 0x10..0x18 | active[3] | ro bits1:0, selection captured by output engine |
| 0x20 | settling | ro bits2:0, pads disabled for selection handover |

Each pad is independently configured; no group-atomic update is promised.
The mux adds no IRQ or wake source. Registered clock demand covers incoming
requests, propagation through the register adapter and the full disabled
handover interval; selected running peripherals retain
their existing clock demands. This is not permission to stop the whole SoC.

Estimated engine state: 3 × (2 active + 1 data + 1 enable + 1 settling) =
15 flops, excluding generated register/adapter state. See the
[formal scope](formal/README.md) and [task report](../../../docs/plan/tasks/reports/T24.md)
for checks and measured area/timing. CI is explicitly disabled for this task.

## Optional watchdog reset (T26/D70)

The watchdog profile separates each pad's PWM output registers from its
GPIO/timer output registers. Both banks preserve the disabled selection-change
interval; their mutually exclusive registered outputs feed a short OR. The
PWM bank alone has the shared watchdog reset release, so PWM-selected outputs
disable with main stopped while GPIO/timer outputs survive. No select decode
appears in an asynchronous reset tree. Earlier profiles are unchanged.
Physical reset/pad qualification remains separate.
