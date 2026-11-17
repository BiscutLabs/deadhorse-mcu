# T17 I2C controller contract

Standalone HF-domain controller with generated registers, trusted three-bit
owner, qualified active-low reset, shared CdcSync inputs and registered
open-drain `sclLow`/`sdaLow` outputs (one means pull low; zero means release).
There is no output that drives a line high. `sclIn`/`sdaIn` are resolved pad
levels. `irq`, `clockHold`, `quiescent` and `pinsEnable` are registered.
Base address is a configurable 256-byte-aligned window, not a frozen SoC map.

## Commands and software sequencing

One byte command runs at a time. Firmware writes address bytes (seven-bit
address plus R/W) using WRITE, followed by data bytes. READ receives one byte
and drives ACK if its command ACK bit is one, otherwise NACK. Final read uses
NACK followed by STOP. START while bus-owned emits a repeated START without
STOP, enabling register-address write followed by read. No automatic address
generation, FIFO, DMA, target behavior or sensor driver is implied.

For example, a register read is START, WRITE(address<<1), WRITE(register),
START, WRITE((address<<1)|1), READ with ACK for intermediate bytes, READ with
NACK for the final byte, STOP. Check every WRITE ACK and command result;
POP each received byte before the next READ. Sensor conversion delays and
initialization remain firmware policy.

START while unowned waits for both filtered lines high continuously for FREE
cycles, then asserts SDA low, waits FREE cycles, pulls SCL low, preserves SDA
for HOLD cycles, releases SDA and completes.
Bus-owned idle holds SCL low and releases SDA. WRITE emits MSB first, releases
SDA for the ninth clock and records ACK/NACK. NACK raises an event but retains
ownership so firmware can STOP or retry explicitly. READ retains its completed
byte until POP; a new READ with pre-edge unread data is rejected, even with
POP in that command. The independent POP still clears validity. POP does not
erase RX_DATA; it retains the last byte through POP/errors until reset or the
next completed READ. POP coincident with completion cannot discard the newly
received byte: arrival wins. last_ack changes only at a WRITE ninth-clock
sample and records true for ACK, false for NACK.

Repeated START preserves SDA for HOLD after command acceptance with SCL low,
releases SDA, waits LOW, releases SCL and respects stretching, waits FREE
with both lines high, asserts SDA low, waits FREE, pulls SCL low, then preserves
SDA for HOLD before release/completion. STOP similarly waits HOLD with SCL low,
asserts SDA low, waits LOW, releases SCL and respects stretching, waits FREE,
releases SDA, then requires FREE consecutive observed-high cycles before
reporting done/unowned. A fresh START also requires FREE, including after reset.

Every bit begins with SCL low and unchanged SDA for HOLD cycles, changes SDA
and waits LOW cycles, releases SCL, waits for filtered high, then holds HIGH
cycles before sampling and pulling SCL low. The same timing applies to ACK.
After the ninth falling edge, preserve SDA for HOLD before releasing it and
completing the command. FREE is also the START/STOP guard interval, independently
configurable from bit HIGH to satisfy their different timing minima.
During that high interval unexpected SCL low aborts as a bus fault. Sending a
released one on a WRITE data/address bit or READ NACK but observing SDA low
raises arbitration_lost and releases both
lines without a deliberate STOP; no automatic retry. This is contention
detection on a single-controller sensor bus, not full multi-controller support.
WRITE ACK, READ data/ACK and RECOVER clocks never use this arbitration test.

RECOVER is explicit and legal only when unowned and idle. It releases SDA,
generates exactly nine complete stretch-aware clock pulses, then attempts STOP
and FREE. STOP setup has its own SCL rise, distinct from those nine pulses.
Recovery cannot make a physically held-low SCL rise, nor force stuck SDA high.
Successful recovery sets recovered and done. A failed attempt times out and
releases both lines; firmware may need external sensor reset/power cycling.

TIMEOUT (16-bit, 1..65535 HF cycles) bounds each interval with no progress:
initial bus-free wait, each released-SCL wait, STOP completion and bus-owned
idle awaiting software. Entry to each such interval loads TIMEOUT-1; each
subsequent HF edge without successful phase completion decrements it, and an
edge with zero expires. Successful phase completion or an accepted next command
on the expiry edge wins. Thus exactly TIMEOUT waiting edges are allowed.
Pin chatter, register polling and rejected commands never reload this counter.
FREE counts only consecutive high samples; if TIMEOUT<FREE, that wait expires
unless it can complete on its deadline. Expiry releases both pins,
clears ownership and busy, and sets timeout. It is a controller policy, not an
I2C-standard stretch limit. Read data and ACK status survive errors. Firmware
must not assume a timed-out transaction had no target-side effect.

All commands other than POP are mutually exclusive within one command write;
conflicts reject the entire write including POP. ACK modifies READ only and
otherwise has no effect. Busy commands reject without altering active work;
POP alone is allowed while busy. APPLY requires idle/unowned, captures shadow
enable/timing/timeout atomically and validates HOLD>=1, LOW>=4, HIGH>=4,
FREE>=4 and TIMEOUT>=1 when enabled. Disabled configuration may retain any
field values. WRITE/READ/STOP require ownership; START/RECOVER require enabled.
WRITE captures the latest completed TX staging write; later writes do not tear
it. APPLY and command errors are sticky events, not bus decode errors.

## Synchronization, timing and integration

Each pin uses shared two-flop CdcSync, followed by a three-consecutive-sample
digital stability filter. Sampling uses only filtered levels. Reset filters
to low, avoiding false bus-free acceptance during warm-up. The filter rejects
one/two-HF-sample spikes; it is not analog pad characterization. Configure
timing for the actual HF clock. Measured no-stretch periods within a byte include
feedback synchronizer/filter latency; stretching may only lengthen a low interval.
Firmware service gaps between byte commands additionally extend SCL low; the
nominal bit rate is not an autonomous transaction-throughput guarantee.
No asynchronous pin is used as an RTL clock.

Timing and protocol references: [NXP UM10204 rev7](https://www.nxp.com/docs/en/user-guide/UM10204.pdf),
sections 3.1 and 6. Standard/Fast requirements inform the pin-model tests.
External pull-ups, rise/fall times, pad hysteresis/filtering, MTBF, oscillator
tolerance and board capacitance remain physical qualification. A slow pull-up
is observed through feedback but does not itself establish electrical compliance.

Every register access, including reads, checks `origin == owner`; denied access
returns error/zero and has no register effect. Ownership transfer must externally
drain bus/commands and unread data before changing owner. All reset controls use
the existing domain-qualified reset; reset releases both lines, disables pins,
restores active timing/timeout defaults, and clears ownership, data-valid,
ACK status and events.

`sleepRequest` and `sleepEnable` are coherent HF inputs. New unowned START or
RECOVER requires run mode or sleepEnable. Commands completing an already owned
transaction remain legal so software can drain it; active commands continue.
clockHold remains asserted while busy or bus-owned, including stretching and
waiting for the next software command; timeout eventually releases abandoned
ownership. Unread data alone can be retained with HF stopped. The AON controller
must request/start HF before bus access and combine outstanding bus work with
clockHold before gating. No autonomous sensor acquisition or AON wake detector
is implemented here.

## Registers

All unspecified bits read zero. Generated decode enforces byte strobes,
alignment, reserved offsets and W1C set-over-clear priority.

| Offset | Name | Fields |
| --- | --- | --- |
| 00 | configuration | RW enable[0], reset0 |
| 04 | timing | RW hold[7:0]=8, low[15:8]=24, high[23:16]=22, free[31:24]=120 |
| 08 | timeout | RW cycles[15:0]=65535 |
| 0c | command | W1P start0, write1, read2, stop3, recover4, apply5, ack6, pop7 |
| 10 | tx_data | RW value[7:0]=0 |
| 14 | rx_data | RO value[7:0], zero until first completed READ |
| 18 | status | RO busy0, owned1, rx_valid2, last_ack3, scl4, sda5, enabled6 |
| 1c | events | W1C done0, nack1, arbitration_lost2, timeout3, command_error4, recovered5, bus_fault6 |
| 20 | irq_enable | RW event mask[6:0]=0, rx_valid7=0 |
| 24 | active_timing | RO hold[7:0], low[15:8], high[23:16], free[31:24] |
| 28 | active_timeout | RO cycles[15:0] |

IRQ is the registered OR of enabled sticky events and enabled RX-valid. A bus
write acknowledgement confirms decode only; firmware checks busy/events for
command acceptance/completion. Clear old done/errors before issuing a command.
