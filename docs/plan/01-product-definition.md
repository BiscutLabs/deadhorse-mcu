# 01 Product definition

PLAN05 D92-D101 extends the general-purpose MCU with a dormant/IoT watcher.
Performance is the sole ROM boot master; lite executes only from program RAM
after performance releases it. UART ROM recovery and JTAG replace the I2C
loader. These are approved target contracts; implementation is tracked in STATUS.

D69 (2026-11-21): this is a moderately general-purpose MCU. Flight control is
the first reference application. Peripheral scope stays comparable to ordinary
MCUs; no flight-specific command controller or automatic application policy
belongs in silicon. Peripheral scope follows Deadhorse requirements.

Deadhorse is a clocked, two-core RISC-V MCU on GF180MCU at nominal 3.3 V.
It rebuilds RISCay's clocked foundation using Deadhorse conventions, with a
simple whole-chip bus and no NoC (D43). The initial chip
contains **no neuromorphic IP and no chip-to-chip link**.

## Approved MCU scope

- Chisel Ibex-derived RV32IMFC performance core with an area-focused multicycle
  FPU, selective HardFloat reuse, and measured improvement work; no core bakeoff.
- Clocked lite coprocessor watches radios/sensors on nominal 32 kHz using its
  own AON SPI/GPIO. It filters requests before waking performance by mailbox.
  Main serial peripherals and DMA are performance-owned; all RAM stays powered.
- Baseline 16 KiB word-wide performance SRAM and watcher-sized 2 KiB retained lite SRAM (PLAN05 implementation pending),
  byte-write enables and configurable banking; external QSPI boot/XIP.
- On-die nominal 32 kHz LF RC, external 48 MHz oscillator with standby,
  main divide-by-six and reset-selected LF fallback; no internal HF oscillator.
- General-purpose timer/PWM/capture/compare and DMA support. Application
  protocols and command/failsafe policy are firmware responsibilities (D69).
  The first board's output capacity remains a planning input, not fixed motor
  or servo roles in hardware.
- JTAG for both cores, unlocked debug, explicit test mode, scan, SRAM self-test,
  analog calibration/test access; no signed firmware.
- On-chip supply monitor with selectable thresholds, hysteresis and qualified
  reset release; defer separate early-warning detector.
- Optional USB CDC-ACM integrated last; cutoff before Phase 3 floorplan freeze,
  UART/JTAG fallback. Limited pin alternate functions frozen at G1.
- Official wafer.space template/LibreLane flow pinned under D105/T43; library
  `gf180mcu_fd_sc_mcu7t5v0`; wafer.space GF180MCU 1x1 target, date open.

These are approved requirements, not a claim of timing, power, area or shuttle
qualification. See [10-decisions-and-risks.md](10-decisions-and-risks.md).

## First application: Flightory Stallion VTOL

| Function | Approved baseline |
| --- | --- |
| Motors | Three: two tilting front motors, one fixed rear motor |
| ESCs | Three Holybro Tekko32 F4 45A, factory AM32 |
| Tilt | Two GDW DS041MG positional servos |
| Surfaces | Two ailerons and two V-tail servos; four EMAX ES08MA II |
| IMU | BMI270 over SPI, timestamped acquisition |
| Barometer | MS5611 over I2C, configurable rate with initial 50 Hz target |
| GPS/compass | Holybro M10 with IST8310, SKU 12042; UART/I2C |
| RC | RadioMaster Boxer ELRS and RP3 V2; CRSF UART |
| Airspeed | No sensor |
| Control | Timer-driven 1 kHz target, documented 500 Hz fallback |

Channel assignment, direction and endpoints remain configurable. Actuator
timeout deadline and recovery policy are determined by testing. Rates and
counts above are approved targets/configurations, not measurements of this MCU.

Flightory's [base airframe](https://flightory.com/product/stallion/) and
[VTOL specification](https://flightory.com/product/stallion-vtol/) are the
airframe references; manufacturer data and bench testing must qualify the
selected components. Stock and price are not architectural requirements.

The application informs interface capacity, not fixed board pin assignments
or immutable flight policy in the MCU. Lite supervises and can service selected
peripherals while performance sleeps; the performance core runs the flight stack.

## Out of scope

Neuromorphic integration, chip-to-chip link, embedded flash, on-chip ADC or
regulator, double-precision FPU, signed boot, production debug locks, USB host
or high-speed mode, and power-gated standby. No port of an existing autopilot
has been approved. The existing fixed-point workload is reference evidence;
new firmware may use the approved single-precision hardware.

The historical D18 Click option requires a later separate brief; it is not
part of initial implementation. Deferred features do not reserve mandatory
pads or force new implementation dependencies.

## MCU qualification and first-application validation

MCU qualification covers the generic peripheral contracts and physical signoff.
The first application additionally requires that qualified, packaged silicon
runs the validated flight firmware through hover,
transition and forward flight, and enters/leaves retained sleep on the ground.
Before flight: independent block verification, formal checks, FPGA/system
simulation, bench sensor/actuator tests and full physical signoff. Approval of
this plan does not satisfy those gates. No implementation starts in PLAN01.
