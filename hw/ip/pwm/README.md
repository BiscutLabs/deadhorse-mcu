# General-purpose PWM (T22)

Nine independent main-clock channels use the reserved 0x40030000 window and
nine existing output pins. Legacy SoC map/pin names remain unchanged. The block
uses generated RegBlock decode and BusRegAdapter owner checks (performance
origin in the initial binding). Every observable output is registered.

## Channel contract

Each channel has shadow period-minus-one (16 bits), divider-minus-one (16 bits)
and high-time (17 bits). A period comprises period+1 ticks; a tick comprises
divider+1 main-clock edges. High-time ranges from zero through period+1 inclusive,
supporting constant-low and constant-high operation. Larger values are rejected.
No assumptions about external devices or physical timing accuracy follow.

APPLY snapshots all three shadow values. If stopped, it starts at phase zero
with output enabled. If running, it queues one snapshot for the next period
boundary; later shadow writes cannot change it. APPLY while a snapshot is
pending is rejected, including on the edge that consumes that snapshot. APPLY
on a boundary with no prior pending snapshot schedules the following boundary.
There is no inter-channel atomic publication engine.

STOP disables output and clears the active phase and pending snapshot on the
next edge; it wins APPLY and rollover. It is ordinary software output disable.
Reset asynchronously clears all state and disables outputs; release uses the
shared ResetRelease in the top. No new external break pin is allocated.

The block's functional and bus reset follow main-service reset, plus cold/warm
whole-chip reset. Core-only reset and AON-service reset preserve it, as for
other main-service peripherals. This defines the new functional profile's
previously unimplemented endpoint; legacy stub profiles retain their wiring.

Period rollover sets a sticky event. An optional DMA mask enables per-channel
level requests: rollover sets request, acknowledgement clears it, set wins a
simultaneous acknowledgement. Another rollover while an unacknowledged request
is outstanding sets overrun; acknowledgement on that edge avoids overrun.
Mask removal or STOP clears the request and wins request generation even on a
rollover. The DMA controller is not implemented here; its integration must
service and acknowledge within the programmed period.
Software may clear requests through the same acknowledge register. Events are
W1C with set winning clear. Channel rollover/error pulses appear immediately
after their sampling edge; register events and DMA requests consume those pulses
on the following edge. DMA mask/acknowledgement apply at that consumption edge;
overrun reaches its sticky register one further edge later. IRQ follows masked
sticky events by one edge. Clock demand reflects running channels or pending
requests with one registered edge of latency; keep the clock running through
the configuration bus response, as the SoC fabric does.

## Registers

All offsets below are relative; all writable state resets to zero. Only the low
256 bytes decode; higher addresses in the reserved window error without aliasing.
Unmapped, misaligned and non-owner accesses error without software side effects.

| Offset | Register | Fields |
| --- | --- | --- |
| 0x00 | apply | w1p channel mask 8:0 |
| 0x04 | stop | w1p channel mask 8:0 |
| 0x08 | running | ro channel mask |
| 0x0c | pending | ro buffered-update mask |
| 0x10 | events | w1c rollover 8:0, config error 17:9, DMA overrun 26:18 |
| 0x14 | irq_enable | rw event mask 26:0 |
| 0x18 | dma_enable | rw channel mask |
| 0x1c | dma_ack | w1p channel mask |
| 0x20 | dma_pending | ro channel mask |
| 0x40..0x60 | period[9] | rw period-minus-one 15:0 |
| 0x80..0xa0 | divider[9] | rw divider-minus-one 15:0 |
| 0xc0..0xe0 | high_time[9] | rw high ticks 16:0 |

Interfaces: clk/reset_n, LocalBus/owner, same-clock dmaAck[9], registered
pinsOut/pinsEnable[9], dmaRequest[9], irq and clockHold. The opt-in SoC binding
ties external DMA acknowledgement low until a real controller is connected;
software acknowledgement remains usable. No new asynchronous input is added.

Implemented with the opt-in `EmitSocPwm` profile; existing profiles remain intact.
The channel/DMA/ownership safety proofs, covers and fault controls pass; precise
scope and assumptions are in [formal/README.md](formal/README.md).

Mapped area is measured 271822.8352 um2; worst register path measured 34.134335 ns
against the existing 9 MHz trial budget, estimated 0.60 x 1000/9 = 66.666667 ns.
Command: `python3 hw/ip/pwm/check_timing.py --output build/t22/timing-first`,
in the pinned environment, dirty main based on `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47`.
Source hashes are in the receipt; GF180 SS/125 C/3.0 V, ideal clocks and no
placed-wire delay. Setup/electrical screen passes; physical pads/hold/RDC,
post-placement timing, complete DMA integration and application tests remain
separate qualifications. Neither CI tier ran.

## Optional watchdog output disable (T26/D70)

The opt-in watchdog profile adds watchdogReset_n and performanceReady ports.
Shared reset release asserts output disable asynchronously. Channel execution
and pending updates reset, while MMIO shadows and shared DMA survive. A
per-channel break latch starts inhibited in this profile; STOP acknowledges
it after the upstream CPU epoch is drained and the local command pipeline
has been idle, and a later APPLY starts execution. DMA emits no STOP and
cannot clear the break. APPLY while inhibited reports config_error. Ordinary
main-core reset and earlier profiles retain their prior behavior. See
[watchdog contract](../watchdog/README.md) for reset scope and qualification.
