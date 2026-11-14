# Actuator block

Draft v0.1, 2026-11-13. Proposed; not yet implemented. Requirements R-CTL-2
to R-CTL-5 in [../plan/02-requirements.md](../plan/02-requirements.md).

Nine output channels. Each is a servo PWM output, an ESC PWM output, a DShot
output or a plain GPIO. The CPU writes values; the block does all bit timing.
The whole block is synchronous logic on `clk_main`. The tick counter, pulse
and frame generators and the failsafe logic sit on an ungated branch of that
clock with their own reset, so they keep running while the rest of the main
domain is in reset.

## Timing base

`tick` is the HF reference divided by `ctrl.tick_div`. All times below are in
ticks. The reference configuration is 12 MHz divided by 5: 2.4 MHz, 416.7 ns
per tick.

| Mode | Derived timing at 2.4 MHz |
| --- | --- |
| PWM | Pulse width = `value` ticks. 1.000 ms is 2400; 2.000 ms is 4800. Period = `period` ticks |
| DShot300 | Bit period 8 ticks (3.333 us). A 1 is high for 6 ticks, a 0 for 3 ticks. Frame is 16 bits, then idle low until the next frame |

DShot600 uses the same encoding at a 4.8 MHz tick.

## Registers

Offsets are bytes from the block base. All registers are 32 bits. The
machine-readable source will be `hw/ip/actuator/actuator.regmap.yaml`
([regmap-format.md](regmap-format.md)); this table is the intent.

| Offset | Name | Field | Bits | Access | Reset | Meaning |
| ---: | --- | --- | --- | --- | ---: | --- |
| 0x00 | `ctrl` | `enable` | 0 | rw | 0 | Run the generators. When 0 every channel is an input |
| | | `trigger_sel` | 1 | rw | 0 | 0 = free-running frames, 1 = frame starts `trigger_delay` ticks after the trigger input edge |
| | | `tick_div` | 15:8 | rw | 5 | HF reference divider, 1 to 255 |
| 0x04 | `commit` | `go` | 0 | w1p | | Copy every shadow `value` into the active set at the next frame boundary, all nine together |
| 0x08 | `period` | `ticks` | 23:0 | rw | 48000 | Frame period in ticks (48000 is 50 Hz at 2.4 MHz) |
| 0x0C | `trigger_delay` | `ticks` | 23:0 | rw | 0 | Delay from trigger edge to frame start |
| 0x10 | `status` | `armed` | 0 | ro | | Outputs are driven from active values |
| | | `failsafe` | 1 | ro | | Outputs are driven from failsafe values |
| | | `commit_pending` | 2 | ro | | A commit is waiting for a frame boundary |
| | | `overrun` | 3 | w1c | 0 | A second commit was requested while one was still pending |
| | | `bad_key` | 4 | w1c | 0 | A write to `arm` carried neither key |
| 0x14 | `arm` | `key` | 31:0 | wo | | Writing `0xA5C3_3C5A` arms; writing `0x0000_0000` disarms. Any other value is ignored and sets `status.bad_key` |
| 0x18 | `fault` | `force` | 0 | rw | 0 | Firmware-declared fault: enter failsafe |
| 0x40 + 4n | `mode[n]`, n = 0..8 | `kind` | 1:0 | rw | 0 | 0 = input (high impedance), 1 = PWM, 2 = DShot, 3 = GPIO output |
| | | `invert` | 2 | rw | 0 | Invert the pin |
| | | `fs_kind` | 5:4 | rw | 0 | Failsafe action: 0 = release pin, 1 = drive low, 2 = drive `fs_value`, 3 = hold last active value |
| 0x80 + 4n | `value[n]` | `v` | 15:0 | rw | 0 | Shadow value. PWM: pulse width in ticks. DShot: bits 10:0 throttle, bit 11 telemetry request. GPIO: bit 0 level |
| 0xC0 + 4n | `fs_value[n]` | `v` | 15:0 | rw | 0 | Failsafe value, same encoding as `value` |

## Behaviour

### Commit

`value[n]` writes only change shadow registers. `commit.go` requests a
transfer. At the next frame boundary all nine shadows are copied to the
active set in the same tick. If no commit is pending at a frame boundary the
previous active values are sent again.

### DShot frame

For a DShot channel the block builds the 16-bit frame from the active value:
bits 15:5 = throttle (11 bits), bit 4 = telemetry request, bits 3:0 =
checksum. The checksum is the exclusive-or of the three nibbles of the upper
12 bits. The most significant bit is sent first.

### States

| State | Outputs | Entered by | Left by |
| --- | --- | --- | --- |
| Disabled | All nine pins are inputs | Reset; `ctrl.enable` = 0 | `ctrl.enable` = 1 |
| Disarmed | Each channel performs its `fs_kind` action | Enable; a disarm write | A correct arm key with no fault present |
| Armed | Active values | Arm | Disarm, or any failsafe cause |
| Failsafe | Each channel performs its `fs_kind` action | Performance-core watchdog expiry, brownout warning, `fault.force` = 1, or main-domain reset | Cause cleared **and** a correct arm key |

Rules:

1. Entering failsafe needs no CPU and no bus activity. The failsafe logic
   generates the failsafe pulses on its own.
2. Failsafe is entered at the next frame boundary, or immediately for
   `fs_kind` 0 and 1.
3. A power-on reset leaves the block Disabled. A main-domain reset alone
   leaves `mode`, `fs_value` and `period` intact and forces Failsafe.
4. Arming with any channel in mode 0 is allowed; that channel stays an input.
5. For a DShot ESC, the usual failsafe is `fs_kind` 2 with `fs_value` 0, the
   motor-stop command. For a servo it is 2 with a neutral width, or 3.

## Checks an implementation must pass

1. Pulse width on a PWM channel equals `value` ticks exactly, for 2400, 3600
   and 4800, at `tick_div` 5.
2. A DShot frame for throttle 1046 with the telemetry bit clear is
   `0x82C6`. A frame for throttle 0 is `0x0000`.
3. Nine `value` writes followed by one commit change all nine outputs in the
   same frame; without the commit, none change.
4. From Armed, asserting the watchdog input produces failsafe outputs within
   one frame period while the bus is held in reset.
5. A wrong arm key leaves the state unchanged and sets `status.bad_key`.
6. With `trigger_sel` = 1, the frame start follows the trigger edge by
   `trigger_delay` ticks, within one tick.

## Open points

- Bidirectional DShot is out of scope.
- Whether the brownout warning is a separate comparator threshold or the
  supply monitor's falling edge (open question Q6).
- Confirm the 6-of-8 and 3-of-8 high times against the chosen ESCs (Q2).
