# Split timer services (T21, D68)

D68, approved 2026-11-21, retains AON sleep deadlines at 0x40000000 and adds
the precise main-clock service at 0x40012100, within unused GPIO space. GPIO
itself stays at 0x40012000. Both low 256-byte windows use generated register
blocks and checked origins; other addresses still error.

## Main capture/compare

`MainTimers` has main clock/reset, owner (performance origin 1 in the top), LocalBus,
four asynchronous capture inputs, separate IMU DRDY, four registered compare
outputs/enables, a registered 32-bit `timeNow` for same-domain SPI timestamps,
IRQ and clockHold. `mainMHz` is an elaboration parameter 8 or 9, not a clock
source decision. Shared CdcSync synchronizes independent input bits.

RUN advances time once every mainMHz edges, in microseconds modulo 2^32. RUN0
holds time, resets submicrosecond phase and cancels active channels/disables
their outputs; pending events/results remain. LOAD_TIME is allowed only RUN0.
The service requests main clock throughout RUN1. It is not a sleep timebase.

Each channel mode: 0 disabled,1 rising capture,2 falling capture,3 one-shot
compare. Only compare may enable output driving. APPLY installs that channel's
shadow mode/deadline/OE atomically. A compare must be strictly future within
2^31-1us by modulo subtraction, otherwise reject and set its config_error.
APPLY while RUN0 also rejects. A valid APPLY wins an old capture/compare on
the same edge; invalid APPLY leaves the old channel operating. APPLY resets
output low. Compare match raises output once, leaves it held until APPLY or
RUN0/reset, and sets pending. Capture records the latest timestamp; overwriting
an uncleared capture sets overrun. The effective timestamp includes a tick
on the sampling edge, including when validating APPLY's deadline. Events set
wins W1C. Overrun uses pre-edge pending; simultaneous W1C does not suppress
that conservative overrun indication. IMU rising capture has its own
timestamp/event; it does not consume one of the four channels. Input pulses
must span at least three main sampling edges in the digital test model.

| Offset | Register | Meaning |
| --- | --- | --- |
| 0x00 | control | rw RUN0, reset0 |
| 0x04 | preload | rw32, reset0 |
| 0x08 | command | w1p channel APPLY bits3:0, LOAD_TIME4 |
| 0x0c | time_value | ro32 microseconds |
| 0x10 | events | w1c pending3:0, overrun7:4, config_error11:8, IMU12, load_error13 |
| 0x14 | irq_enable | rw bits13:0 reset0 |
| 0x18 | imu_capture | ro32 |
| 0x20..0x2c | channel_mode[4] | rw mode1:0, OE2, reset0 |
| 0x40..0x4c | deadline[4] | rw32 reset0 |
| 0x60..0x6c | captured[4] | ro32 latest capture |
| 0x70 | status | ro armed compare bits3:0 |

## AON deadlines

`AonTimers` has AON clock/reset, owner (lite origin 0), LocalBus, registered IRQ/wake
and clockHold. Four one-shot relative deadlines count AON clock edges, not
microseconds. Valid duration is 1..0x7fffffff. ARM loads a channel; the following
duration-th edge expires it. Valid ARM wins old expiry; invalid ARM sets error
and leaves old work running. CANCEL wins ARM and expiry. Completion sets sticky
pending; active completion wins software clearing. IRQ/wake have separate
four-bit masks, reset0. Pending is retained until W1C or service reset.
ClockHold covers active countdowns or pending masked IRQ/wake. Registered
IRQ/wake reflect a changed pending register on the following AON edge.
The top routes the OR of main IRQ and synchronized AON timer IRQ to fast11;
AON timer IRQ also reaches the lite stand-in, and wake requests main service.

| Offset | Register | Meaning |
| --- | --- | --- |
| 0x00 | command | w1p ARM3:0, CANCEL7:4 |
| 0x04 | events | w1c pending3:0, config_error7:4 |
| 0x08 | irq_enable | rw4 reset0 |
| 0x0c | wake_enable | rw4 reset0 |
| 0x10 | status | ro active3:0 |
| 0x20..0x2c | duration[4] | rw32 reset0 |
| 0x40..0x4c | remaining[4] | ro32 |

At an assumed 32 kHz AON clock, one tick is estimated 31.25 us; at the existing
1 MHz active-service test profile it is 1 us. Deadlines require AON edges, never
main edges. No oscillator accuracy/startup/pad timing is qualified. Mapped area and timing are recorded in the T21 report.

## T21 implementation evidence

The opt-in `EmitSocIo` profile binds this peripheral into the full SoC;
`EmitSocI1` retains its original stubs. See the [T21 report](../../../docs/plan/tasks/reports/T21.md)
for current focused simulation, formal and GF180 evidence and exact commands.
Formal scope and assumptions are in [formal/README.md](formal/README.md).
No CI was run. Full-chip clock, pad, hold/RDC and post-placement qualification
is not implied by these block checks.
