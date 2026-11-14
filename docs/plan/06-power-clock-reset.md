# 06 Power, clocks and reset

Deadhorse is entirely clocked (decision D17). Low power comes from clock
gating and from stopping the fast clock source, not from clockless logic.

## Power modes

| Mode | What is stopped | What is retained | Wake latency target | Basis |
| --- | --- | --- | --- | --- |
| **Run** | Idle subsystems are clock-gated | Everything | n/a | |
| **Idle** | Performance core clock gated at `wfi`; unused peripherals gated | Everything | A few `clk_main` cycles | Standard clock gating |
| **Deep sleep** | HF source and 48 MHz stopped, so the whole main domain has no clock | All SRAM, registers, GPIO outputs | Under 200 microseconds | RISCay's clocked design already implements retained clock-stop sleep |
| **Standby** (not in the prototype) | Main-domain supply gated | Always-on domain only | Milliseconds | Needs isolation, retention and a power switch; see below |

The always-on domain keeps its 32 kHz clock in every mode. Its dynamic power
at that frequency is small, and the lite core gates its own clock at `wfi`.

### Why no power gating in the prototype

GF180 at 3.3 V is a long-channel, high-threshold process, so leakage is
expected to be small next to the always-on oscillator and pad currents.
Power gating would add isolation cells, retention or re-initialisation, a
switch and a supply sequencing protocol, none of which exist in the open
GF180 libraries. The plan is to **measure deep-sleep current first**
(R-PWR-3, from extraction and then silicon) and add a gated standby mode
only if the number demands it. The domain boundary is already in the right
place if it does.

### Entering and leaving deep sleep

RISCay's clocked sequence, extended for two cores:

1. The performance core parks at `wfi` with no outstanding transaction.
2. The main domain drains: no bus transaction, no
   peripheral mid-frame, no pending wake.
3. The lite core clears the HF enable. The enable is sampled so the source
   stops only after a complete final high pulse and then holds low; no
   runt pulse reaches the main domain. No arbiter or mutex is involved.
4. The 48 MHz input buffer is disabled.

Wake sources (R-PWR-2). Each sets an asynchronous wake latch in the
always-on domain, which re-enables the HF source; the main domain resumes
after the source has started and the wake has been synchronized.

| Source | Mechanism | Status |
| --- | --- | --- |
| LF tick or deadline | Always-on timebase | Exists in RISCay |
| GPIO level change | Asynchronous compare against last observed level | Exists |
| I2C START on the target port | SDA event flop | Exists |
| UART start bit | Falling-edge event flop on RX; the first byte may be lost and is treated as a wake probe, as RISCay does for I2C | New |
| USB resume | Bus state change on D+/D- | New |
| Lite core decision | Firmware writes the wake register | New |

## Clock sources

| Source | Feeds | Target | Starting point |
| --- | --- | --- | --- |
| **LF oscillator**, always on | `clk_aon`, watchdog, timebase, sleep deadlines | 32 kHz nominal, within 5 percent after trim, under 1 microamp | RISCay's current-starved ring, redesigned: it runs at 7.7 Hz today and is untrimmed |
| **HF reference**, restartable | `clk_main`, and a divided copy the lite core can select | 12 or 24 MHz, within 2 percent after trim, start in 100 microseconds | RISCay's RC ring (8.6 to 17 MHz across corners), plus a trim register and a calibration procedure |
| **48 MHz**, on only with USB | `clk_usb` | Within 0.25 percent | External oscillator or crystal on a clock pad in the prototype |
| **External 32.768 kHz crystal** (option) | Calibrating the two RC sources; real-time clock | n/a | Not in RISCay; needs a crystal driver cell. Decision D6 |

Notes:

- **No PLL in the prototype.** USB needs 48 MHz and nothing else needs more
  than 24 MHz. Bringing 48 MHz in on a pad avoids designing and qualifying a
  PLL in an open PDK. The same pad, divided by two or four, can be
  `clk_main` on boards that always fit the oscillator, which makes HF trim a
  fallback.
- **Trim.** Each RC source gets a trim register loaded by the boot ROM from a
  calibration word in external flash. Factory calibration measures against a
  known reference. With the 32 kHz crystal option, firmware can also
  calibrate at run time.
- **Baud rates, pulse widths and timeouts are counted on `clk_main`,** so
  their accuracy is the HF reference's accuracy (R-CTL-5).
- **Main clock frequency** is set by spike S1: the highest of 12 or 24 MHz
  that the performance core closes at the slow corner with margin.

### Clock structure

- `clk_aon` is a glitch-free two-input mux: the LF oscillator, or the HF
  reference divided down. The lite core selects it by register; the switch
  completes in a bounded number of cycles of both clocks.
- `clk_main` fans out through one integrated clock-gating cell per
  subsystem. Gate enables are registered in the gated clock's own domain.
- Clock gates and the mux use the library's integrated clock-gating cell.
  `gf180mcu_fd_sc_mcu7t5v0` has one; `gf180mcu_as_sc_mcu7t3v3` does not,
  which bears on decision D15.

### Control-loop timing

The loop is triggered by the IMU data-ready pin (R-CTL-1), so the sample
period is set by the IMU's own oscillator. The actuator block latches outputs
at a fixed offset after data-ready, so the time the computation takes does
not reach the motors. The requirement on the core is that the loop finishes
before that offset. In a clocked design the loop's duration is a fixed number
of cycles, which makes that bound straightforward to state and test.

## Reset

Kept from RISCay's clocked design:

- Supply monitor (bandgap and hysteretic comparator) drives an asynchronous
  assert; release is qualified by a 100,000-cycle hold, at least 5 ms.
- Reset is asserted asynchronously and released synchronously in each clock
  domain through a reset synchronizer.
- Watchdog reset returns to the boot ROM and preserves image validity and the
  programming lock; power-on reset and brownout clear them.

New for Deadhorse:

- **Two cores.** A watchdog in the always-on domain supervises the lite core.
  A second, windowed watchdog supervises the performance core and is serviced
  by the flight loop. Either can reset the main domain; only the first resets
  the always-on domain.
- **Reset crossings.** A main-domain reset must not corrupt the crossing
  FIFO to the always-on domain; both sides of each crossing reset together
  or the crossing has an explicit flush.
- **Reset reason** is latched in the always-on domain and readable by both
  cores.

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
- The failsafe generator must keep producing valid pulses while the rest of
  the main domain is in reset. It therefore has its own reset domain and an
  ungated branch of `clk_main`, and deep sleep is refused while the block is
  armed.

## Supply

The prototype is a single 3.3 V supply, regulated on the board. No on-chip
regulator. The supply monitor thresholds measured on RISCay's schematic
(rising 3.12 to 3.24 V, falling 3.02 to 3.14 V) leave little margin under a
3.3 V rail on a drone with ESC switching noise; the threshold is to be
revisited with the board's rail tolerance in hand (open question Q6).
