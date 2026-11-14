# 06 Power, clocks and reset

## Power modes

| Mode | What is stopped | What is retained | Wake latency target | Basis |
| --- | --- | --- | --- | --- |
| **Run** | Nothing | Everything | n/a | |
| **Idle** | Performance core parked at `wfi`; region M handshakes at rest; island T gated | Everything | Under 10 microseconds | Free in a clockless design: no events, no switching |
| **Deep sleep** | Region M stopped; HF reference and 48 MHz off | All SRAM, registers, handshake phases, GPIO outputs | Under 200 microseconds | RISCay retained sleep, with the lite core left running |
| **Standby** (not in the prototype) | Region M supply gated | Region A only | Milliseconds | Needs isolation, retention and a power switch; see below |

Region A never stops. The lite core in region A is itself clockless: between
events it draws leakage only, and it needs no oscillator to compute, only to
be told the time.

### Why no power gating in the prototype

GF180 at 3.3 V is a long-channel, high-threshold process, so leakage is
expected to be small next to the always-on oscillator and pad currents.
Power gating would add isolation cells, retention or re-initialisation, a
switch and a supply sequencing protocol, none of which exist in the open
GF180 libraries. The plan is to **measure deep-sleep current first**
(R-PWR-3, Phase 4 extraction and then silicon) and add a gated standby mode
only if the number demands it. The region A and M split puts the boundary in
the right place if it does.

### Entering and leaving deep sleep

Carried over from RISCay and extended for two cores:

1. The performance core parks at `wfi` with no outstanding transaction.
2. Region M drains: no bus transaction, no island T
   activity, no pending wake.
3. The lite core issues the stop request. Region M stops through the
   persistent stop request and filtered mutex RISCay already defines. A stop
   never resets a live grant.
4. HF reference and 48 MHz sources are disabled after their final full pulse.

Wake sources (R-PWR-2), each of which restarts the HF reference if needed and
releases the stop:

| Source | Mechanism | Status |
| --- | --- | --- |
| LF tick or deadline | Region A timebase | Exists in RISCay |
| GPIO level change | Asynchronous compare against last observed level | Exists |
| I2C START on the target port | SDA event flop | Exists |
| UART start bit | Falling-edge event flop on RX; first byte may be lost and is treated as a wake probe, as RISCay does for I2C | New |
| USB resume | Bus state change on D+/D- | New |
| Lite core decision | Firmware writes the wake register | New |

**The stop mutex is the gating item for this whole section.** Its 1 FIT
target is not established and its production binding is disabled in RISCay.
See risk K1.

## Timing sources

| Source | Purpose | Target | Starting point |
| --- | --- | --- | --- |
| **LF oscillator**, always on | Timebase, watchdog, sleep deadlines, lite-core tick | 32 kHz nominal, within 5 percent after trim, under 1 microamp | RISCay's current-starved ring, redesigned: it runs at 7.7 Hz today and is untrimmed |
| **HF reference**, restartable | Island T bit timing: UART baud, SPI and I2C clocks, actuator pulses, capture timers | 12 or 24 MHz, within 2 percent after trim, start in 100 microseconds | RISCay's RC ring (8.6 to 17 MHz across corners), plus a trim register and a calibration procedure |
| **48 MHz**, on only with USB | Island U | Within 0.25 percent | External oscillator or crystal on a clock pad in the prototype |
| **External 32.768 kHz crystal** (option) | Calibrating the two RC sources; real-time clock | n/a | Not in RISCay; needs a crystal driver cell. Decision D6 |

Notes:

- **No PLL in the prototype.** USB needs 48 MHz and nothing else needs more
  than 24 MHz. Bringing 48 MHz in on a pad avoids designing and qualifying a
  PLL in an open PDK. The same pad can feed island T directly for boards
  that always fit the oscillator, which makes HF trim a fallback.
- **Trim.** Each RC source gets a trim register loaded by the boot ROM from a
  calibration word in external flash. Factory calibration measures against a
  known reference on the tester or bring-up board. If the 32 kHz crystal
  option is taken, firmware can also calibrate at run time.
- **The clockless regions use none of these.** Their timing comes from matched
  delays. That also means region M has no natural notion of elapsed time:
  every timeout, baud rate and pulse width is counted in island T or region A.

### Control-loop timing

The loop is triggered by the IMU data-ready pin (R-CTL-1), so the sample
period is set by the IMU's own oscillator. The performance core's variable,
voltage- and temperature-dependent speed changes how long the computation
takes, not when it starts. The actuator block latches outputs at a fixed
offset after data-ready so that computation jitter does not reach the motors.
The requirement on the core is only that the loop finishes before that
offset at the slow corner.

## Reset

Kept from RISCay:

- Supply monitor (bandgap and hysteretic comparator) drives an asynchronous
  assert; release is qualified by a 100,000-cycle hold, at least 5 ms.
- Ordered, quiescence-checked release: each region leaves reset only when its
  handshakes are at rest. Raw reset never crosses a region boundary.
- Watchdog reset returns to the boot ROM and preserves image validity and the
  programming lock; power-on reset and brownout clear them.

New for Deadhorse:

- **Two cores.** A watchdog in region A supervises the lite core. A second,
  windowed watchdog supervises the performance core and is serviced by the
  flight loop. Either can reset region M; only the first resets region A.
- **Reset reason** is latched in region A and readable by both cores.

## Actuator failsafe (R-CTL-4)

A reset of the flight controller in the air must not leave the motors at an
arbitrary level.

- The actuator block has a per-channel failsafe value and mode (drive a stop
  command, drive low, hold last, or release the pin).
- On performance-core watchdog expiry, brownout, or a firmware fault flag, the
  block switches to failsafe values autonomously. It stays there until
  firmware re-arms it with a keyed write.
- On power-on reset all nine pins are inputs, as RISCay's GPIO are, and board
  pull-downs define the level. ESCs then see no signal and stay disarmed.
- Because the failsafe generator must keep producing valid pulses while
  region M is in reset, it lives in island T with its own reset domain.

## Supply

The prototype is a single 3.3 V supply, regulated on the board. No on-chip
regulator. The supply monitor thresholds measured on RISCay's schematic
(rising 3.12 to 3.24 V, falling 3.02 to 3.14 V) leave little margin under a
3.3 V rail on a drone with ESC switching noise; the threshold is to be
revisited with the board's rail tolerance in hand (open question Q6).
