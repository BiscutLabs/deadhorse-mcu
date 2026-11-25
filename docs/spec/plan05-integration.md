# PLAN05 integration contract

Target contract under D92–D101; implementation and integrated acceptance remain
pending. This supplements the single production SoC map, not a selectable profile.

## Ownership and reset

Performance owns main UART/SPI/I2C/QSPI, including QSPI after reset. Lite cannot
reach main peripheral windows; remove general toMain and retain toAon/mailbox.
Keep the dedicated lite instruction-debug bridge and retained-memory debug path.
Boot, oscillator and power/reset control are performance-owned AON targets;
lite owns AON timers, SPI and GPIO. Watchdog channel owners remain unchanged.

Whole-chip reset holds lite until performance explicitly releases it at program
base. Program RAM is 0x30000000–0x300003ff; data RAM is 0x30000400–0x300007ff.
Only performance can write program RAM, while boot control acknowledges the
lite reset hold after the client has drained. Debug halt is not boot hold and
direct SBA cannot bypass the rule. Lite-only stop is retained across performance
reset. Existing lite-watchdog whole-chip scope remains; no new scope is added.

Boot-control offsets remain status0, keyed release4 and errors8; add keyed hold
at12. Status reports held/released/draining; program RAM writes while draining
are denied. A repeated keyed hold during drain is acknowledged without effect.
Release uses the existing opaque key0x50455246; hold uses key0x484f4c44.
Wrong key, release during drain/debug ownership or redundant release reports
command_error without side effects. Hold is idempotent once held; while draining
it does not restart the drain. Status bits0/1/2 are held/released/draining.
Program-size permissions are derived from map metadata, not magic loader
limits. No lite ROM, loader lock or ROM-phase seal survives.

## AON SPI and GPIO

| SPI offset | Register | Contract |
| ---: | --- | --- |
| 0 | control | enable bit0, mode3 bit1; reset disabled, mode0 |
| 4 | status | busy bit0; TX level bits7:4, RX level bits11:8 |
| 8 | tx_data | byte write pushes TX FIFO; full write errors without effect |
| 12 | rx_data | read pops RX byte; empty read errors without effect |
| 16 | divider | half-period AON ticks, nonzero; reset1 |
| 20 | length | bytes per CS frame1..8; reset1 |
| 24 | start | bit0 pulse; validate enabled/idle/config/TX/RX capacity atomically |
| 28 | events | completion bit0 W1C, error bit1 W1C; set wins clear |
| 32 | irq_enable | completion/error enable bits1:0; reset0 |

Two eight-byte FIFOs, one active-low CS; mode0 idle-low/sample rising and mode3
idle-high/sample rising, MSB first. Capture configuration at start; config writes
while busy error. Start requires the complete frame's TX bytes and RX space.
Never pause SCK mid-frame, hold CS across every byte, finish the last trailing
edge before releasing CS. Completion IRQ targets lite; no main clock request.

| GPIO offset | Register | Contract |
| ---: | --- | --- |
| 0 | input | six synchronized input levels |
| 4 | output | six output values, reset0 |
| 8 | output_enable | six enables, reset0 |
| 12 | pending | six captured events, read-only |
| 16 | event_enable | six capture/IRQ enables, reset0 |
| 20 | clear | six event clear pulses; new event wins |
| 24 | polarity | six bits, zero rising/one falling; reset0 |
| 28 | armed | six read-only rearmed indications |
| 32 | mux | pads0..2 main/AON selection, reset main; SPI selection pads0..3 |

Asynchronous edge capture belongs in the shared CDC library. Use an event
flip-flop with asynchronous assertion and synchronous consume/rearm, followed
by the shared synchronizer. No pulse can be promised below a cell's physical
minimum. Assumed initial board contract: active pulse at least1us (shorter than
the nominal31.25us AON period); inactive until armed returns after clear. Pulses
while pending coalesce. Reset/configuration suppresses delivery until rearmed;
polarity/mux changes require capture disarmed. Physical pulse-width/rearm and
reset-domain qualification remain T38 obligations; simulation/formal must cover
a legal sub-cycle pulse and event/clear collision with negative controls.

Six physical GPIO-capable pads: existing GPIO0..2, former loader pads3..4 and
one spare pad5. AON SPI alternates0=SCLK,1=MOSI,2=MISO,3=CSn; pads4/5 remain
radio IRQ/power. BOOT_MODE samples pad1 while reset holds outputs disabled,
then stays fixed. Board CS pull-up prevents selection during reset/strap sample.
The three original main GPIO alternate functions remain mutually exclusive
with AON ownership. Mux changes require both producers' output enables inactive
and an acknowledged ownership transition; reject unsafe changes. Ownership
lives in AON and survives performance-only reset. Never drive both owners or
route AON-owned radio IRQ into the main GPIO wake path.

## Unified timers

Use 0x40030000 for one main-clock timer block. Retire the old timer child at
0x40012100 and the independent PWM implementation after replacement tests pass.
Keep the microsecond timebase and three timers, each sharing a prescaler and
period across four channels. Channels0..3 use timer0,4..7 timer1,8..11 timer2.

| Offset | Register | Contract |
| ---: | --- | --- |
| 0 | time_control | run bit0 |
| 4 | time_value | microsecond counter, read-only |
| 8 | time_preload | next load value |
| 12 | time_command | load pulse, only while stopped |
| 16 | pending | twelve pending compare updates, read-only |
| 20 | apply | twelve commit pulses; adopt at corresponding period boundary |
| 24 | events | twelve sticky channel events, W1C |
| 28 | irq_enable | channel bits11:0, timer errors14:12, DMA overrun23:15 |
| 32 | dma_enable | nine channel masks, reset0 |
| 36 | dma_ack | nine acknowledge pulses |
| 40 | dma_pending | nine level requests, read-only |
| 44 | dma_overrun | nine sticky overrun bits, W1C |
| 48 | timer_run | three enable bits, reset0; clear stops corresponding timer |
| 52 | config_error | three sticky timer configuration errors, W1C |
| 64+4*t | period[t] | three shared16-bit period-minus-one values |
| 80+4*t | prescaler[t] | three dividers, value+1 main edges per tick |
| 128+4*c | mode[c] | off0/PWM1/compare2/capture3; output-enable bit2, falling-capture bit3 |
| 192+4*c | compare[c] | twelve17-bit shadow compare values |
| 256+4*c | captured[c] | twelve32-bit microsecond timestamps |
| 320+4*t | counter[t] | three16-bit period counters, read-only |

Capture timestamps use the timebase; starting capture requires timebase run,
and stopping/loading the timebase while capture runs is rejected. PWM is active
while counter<compare; compare mode starts low and toggles on match, setting
its channel event. PWM rollover and capture edges set their channel events.
A running timer advances from0 through period inclusive at prescaler+1 main
edges per tick, then rolls to0. Compare may equal period+1 for constant-high
PWM, but compare mode requires a reachable count. Counter and prescale phase
clear on stop; start begins at0. Stop disables outputs and clears queued duty
updates/requests, winning apply and rollover. Existing accepted DMA bus work
still drains under DMA's own clock hold; stop never cancels a bus transaction.
Any enabled timer holds main clock, including when its channels are off;
running capture and output channels therefore always retain the clock. Out-of-range commits
and starting with invalid configuration error without effect. Prescaler,
period and mode changes require that timer stopped; duty commits alone may
update while running, with all selected channels adopting together at boundary.
Watchdog output disable suppresses every output without resetting shared buses.
Timebase run also requests main clock. Pending DMA requests retain clock hold.
DMA request semantics remain the previous PWM contract: rollover sets a sticky
level request for enabled channels0..8; hardware/software acknowledgement clears
it, with a new rollover winning a simultaneous acknowledgement. Repeated
rollover without acknowledgement sets overrun; same-edge acknowledgement avoids
overrun. Mask removal or timer stop clears the request and wins generation.
Preserve the existing registered pulse-to-request/event/IRQ pipeline. DMA
writes shadow compare then applies the channel at the next shared period edge.
Timer IRQs are10,12,13; AON timer remains11.

All nine existing PWM and four timer pads remain. Pinmux selects one of twelve
channels or disconnected for each of thirteen pads. Capture inputs come from
the four bidirectional timer pads, each selecting one channel; disallow duplicate
capture ownership. Twelve simultaneous outputs fit nine PWM plus three timer
pads. Four simultaneous external captures fit the four input-capable timer pads;
any channel may be selected, not twelve simultaneous input pins. GPIO alternates
remain separate. Keep existing UART/SPI DMA endpoints; migrate the nine existing
PWM DMA endpoints to channels0..8 with shared-period metadata. Additional DMA
channels/endpoints are not required by E6 and are not added here.

Pinmux keeps its original GPIO select0x00..08, active0x10..18 and settling0x20
fields. Add timer_select[13] at0x40+4*p (pads0..8 are PWM pins,9..12 timer
pins), capture_select[4] at0x80+4*p, timer_active[13] at0xa0+4*p and
capture_active[4] at0xe0+4*p. Selectors are four bits:0..11 channel,15 disconnected
(reset);12..14 reject. route_events.rejected is W1C at0xf0. Route changes require
both old/new channels stopped and outputs disabled. Capture selection rejects
duplicate channel ownership; a pad in capture mode cannot simultaneously enable
output drive. Accepted output changes keep the existing registered disabled
handover interval; capture changes suppress edge detection until synchronized
input settles. Read-only active selectors report completed changes. The mux
holds main clock through transition/response; it adds no interrupt source.

## Verification boundary

Watcher opt05 is an independently reviewed Phase1 measurement only. Phase2
must replay it with actual AON blocks and stopped OSC_IN, prove reset/write
permissions, verify every timer mode/channel and preserve/remove tests only
under explicit E2/E3/E6 changes. RVFI production removal requires non-RVFI
equivalence; no timeout is a proof. Record source hashes and retained failures.

PLAN05 BOOT_MODE readback: performance reads bit0 of boot-control offset0x10
(`0x40000310`), read-only. GPIO1/AON MOSI is sampled on AON edges while
whole-chip reset qualification is pending and frozen before AON clients release.
Main-only or AON service reset does not resample it; a new whole-chip reset does.
A board strap must remain stable through whole-chip reset qualification.
