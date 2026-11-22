# Historical actuator-controller proposal

**Superseded as a hardware contract by D69 (2026-11-21). Do not implement this
specialized block.** Retained below as historical application requirements and
protocol examples. New RTL uses conventional timer/PWM/capture/compare and DMA;
firmware owns DShot encoding, command publication/freshness, arming/recovery,
endpoint mapping and per-actuator failsafe policy. Generic reset/watchdog and
ordinary timer output-disable behavior remain hardware concerns.

The replacement generic PWM/DMA brief has not been assigned. Existing output
stubs, pin reservations and register windows are unchanged by this note.
See [the current peripheral plan](../plan/07-peripherals-memory-boot.md).

## Historical draft (not current RTL acceptance)


Draft v0.2, 2026-11-13. Approved architectural behavior reconciled with
D21/D31/D32/D33/D37; not implemented. The previous global-period register
table is superseded. Final register offsets and recovery controls remain open.

## Channels and timing

Nine configurable channels: three motors, two tilt servos, two ailerons and
two V-tail servos. Configurable assignment, direction and endpoints. Modes:
servo PWM, ESC PWM, DShot or GPIO. Each channel has its own frame period.

The actuator runs on a required ungated branch of the main timing clock with
reset independent of the performance domain. An assumed tick example is
12 MHz / 5 = 2.4 MHz (estimated 416.7 ns per tick). DShot300 can use eight
ticks per bit, with six high for 1 and three for 0. These are design examples,
not measured tolerance of the selected ESCs. DShot600 remains a stretch;
bidirectional DShot remains out of scope.

Control computations use a timer-driven loop with timestamped sensor data.
Servo periods need not equal the loop period or motor frame period. Do not
require a single IMU event to start every channel frame.

## DShot frame encoding

Build a 16-bit frame from the active command: bits 15:5 throttle (11 bits),
bit 4 telemetry request, bits 3:0 checksum. Checksum is the XOR of the three
nibbles in the upper 12 bits; transmit MSB first. Preserve independent reference
checks: throttle 1046 with telemetry clear encodes as `0x82C6`; throttle zero
with telemetry clear encodes as `0x0000`. These are calculated protocol examples,
not measurements. At the example tick, PWM widths 2400/3600/4800 ticks must
decode exactly; direction and endpoints must be applied without truncating frames.

## Atomic publication and frame application

Firmware writes a shadow command set, then atomically publishes a coherent
snapshot. Later shadow writes must not mutate that published snapshot.
Each channel applies a published value only at its own frame boundary, without
changing an in-progress pulse or DShot frame. Channels at different rates may
apply the publication at different times; simultaneous application is not required.

The final design brief must specify publication generations, buffering and what
happens if a newer publication arrives before a slow channel consumes the prior
one. Latest-value replacement versus back-pressure has not been approved; do not
silently retain the old single-pending/global-frame rule. Expose enough status
to test coherent publication and per-channel application.

## Hardware fault handling

Include a configurable command-age timeout independent of firmware execution.
Define what constitutes a valid refreshing publication so partial writes or a
stalled CPU cannot accidentally keep stale commands alive. Fault causes include
timeout, either watchdog and firmware fault; performance reset forces configured
failsafe without resetting actuator configuration or generators.

Per-channel actions support stop command/defined value, drive low, hold last or
release as configured. The timeout deadline, reaction boundary details, recovery
and re-arm policy must be fixed through testing before the final behavior/register
brief. Neither automatic recovery nor mandatory keyed re-arm is approved.

Lite watchdog also causes whole-chip reset. The fault path acts while clock and
supply are valid; whole-chip reset disables outputs. POR/brownout disable outputs;
no early-warning detector is included. No valid pulse guarantee applies during
clock loss or undervoltage. Board inactive levels and ESC loss-of-signal handling
must be tested. Deep sleep is refused while armed.

## Register groups to specify

Global enable/timing controls; shadow command arrays; atomic publication and
generation/status; per-channel mode, period, endpoint/direction controls;
failsafe actions/values; timeout configuration/status; fault causes; arm/disarm
and recovery controls after policy tests. Offsets, widths, reset encodings and
pending-publication behavior are not frozen by this draft.

T05 must use a dedicated format-coverage fixture rather than turn these unresolved
controls into an accidental hardware ABI. Final actuator YAML comes with the
actuator implementation brief after the open behavior questions are resolved.

## Verification requirements

- Independent PWM/DShot decoder/reference model; no RTL text matching.
- Mixed channel rates, publication immediately before/after boundaries and
  concurrent shadow writes; no torn commands or truncated frames.
- Final publication-overrun policy tested once specified, including slow servos
  receiving commands computed at the faster control-loop cadence.
- Timeout during stalled CPU/bus, watchdog faults and performance reset;
  autonomous configured outputs with valid clock/supply.
- Whole-chip reset/brownout output disable; no early-warning assumption.
- Formal properties, listed assumptions, covers and negative controls beside RTL.
- Bench tests with Holybro Tekko32 F4 45A AM32, positional GDW DS041MG and EMAX
  ES08MA II; verify timing, levels, mechanical endpoints and fault behavior.

## Open before implementation freeze

Timeout deadline and recovery policy (Q13); publication supersession/buffering;
exact register map; accepted ESC timing and servo rates (Q2). These do not block
the repository scaffold, tool environment or core work.
