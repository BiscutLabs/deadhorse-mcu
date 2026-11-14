# 02 Requirements

Each requirement carries a provenance tag: **M** measured, **E** estimated
from measured inputs, **A** assumed placeholder. Assumed values name the task
that replaces them.

## Flight-loop measurement (input to the CPU requirements)

Measured 2026-11-13 by compiling a fixed-point hover, fixed-wing and
transition inner loop for RV32IM (GCC 13.2.0, `-O2`) and counting retired
instructions over 2,000 iterations per mode. The counter was cross-checked
against QEMU and a native build.

| Quantity | Value |
| --- | --- |
| Instructions per iteration, hover / fixed-wing / transition (mean) | 1,737 / 1,768 / 2,101 |
| Worst observed iteration | 2,171 |
| Multiplies per iteration | 339 to 391 |
| Same loop without a hardware multiplier | about 32 times more instructions |
| Same loop in soft-float | about 17 times more instructions |
| Loop code size (RV32IMC `-Os` to RV32IM `-O2`) | 3.8 to 5.6 KiB |
| Loop state / stack frame | 780 bytes / 208 bytes |

Limits: the loop content is our own design (Mahony estimator, cascaded PID,
tilt-rotor mixer, two ailerons, elevator, rudder). It excludes drivers,
failsafe, navigation, interrupt overhead and motor linearisation. Counts are
instructions, not cycles.

## CPU

| ID | Requirement | Tag |
| --- | --- | --- |
| R-CPU-1 | Performance core sustains at least 5 MIPS at the slow corner (SS, 125 C, 3.0 V) with routed delays. Stretch 10 MIPS. Basis: 2,171 instructions at 1 kHz is 2.2 MIPS; doubled for the excluded work and rounded up. | E |
| R-CPU-2 | Performance core is RV32IMC with machine-mode CSRs, vectored interrupts and `wfi`. No FPU. | M (multiplier), A (C extension, for code size) |
| R-CPU-3 | Hardware multiply completes in at most 3 core cycles. Divide may be iterative. | E |
| R-CPU-4 | Interrupt latency from pin to first handler instruction is bounded and at most 50 microseconds at the slow corner. | A, replaced by spike S4 |
| R-CPU-5 | Lite core is RV32E (optionally C) with a minimal interrupt and CSR set. At least 0.2 MIPS on the divided HF clock; a few thousand instructions per second on the 32 kHz clock. | A |
| R-CPU-6 | Both cores are debuggable: halt, resume, single-step, register and memory access. | A |

## Control and I/O timing

| ID | Requirement | Tag |
| --- | --- | --- |
| R-CTL-1 | Inner loop rate 1 kHz, with 500 Hz as the accepted fallback. The loop is triggered by the IMU data-ready pin. | E |
| R-CTL-2 | Nine actuator channels, each independently configurable as servo PWM (1 to 2 ms pulse, 50 to 333 Hz, resolution 1 microsecond or better) or DShot300. DShot600 is a stretch. Standard PWM for ESCs is the fallback. | E |
| R-CTL-3 | All nine channels update from one atomic register commit per loop iteration. | A |
| R-CTL-4 | On watchdog reset, brownout or a firmware-declared fault, ESC channels go to a defined stop command or idle level and servo channels hold or release as configured, without CPU involvement. | A |
| R-CTL-5 | The timing reference for actuator and UART bit timing is accurate to 2 percent or better after trim, over temperature and supply. Confirm the tolerance against the actual ESCs. | A |

## Peripherals

| ID | Requirement | Tag |
| --- | --- | --- |
| R-PER-1 | Three UARTs, 8N1, up to 921,600 baud, with signal inversion (for SBUS-style receivers) and receive FIFOs. | E |
| R-PER-2 | One SPI controller, at least 4 MHz SCLK, two chip selects, for the IMU. A 14-byte read must complete in under 150 microseconds. | E |
| R-PER-3 | One I2C controller at 100 and 400 kHz for barometer, compass and airspeed. The RISCay I2C target is retained for the host loader. | E |
| R-PER-4 | USB 2.0 full-speed device, sufficient for a CDC-ACM serial port. Implemented separately and integrated last; area, pads, clock and a bus window are reserved from architecture freeze ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)). | A |
| R-PER-5 | At least four general-purpose timers or capture channels, one free-running microsecond timebase. | A |
| R-PER-6 | Battery voltage and current through an external SPI or I2C ADC. The RISCay SPI ADC player is retained for this. | E |
| R-PER-7 | GPIO with wake-on-level, as in RISCay. | M (exists) |
| R-PER-8 | Flight logging: at least 64 bytes per control-loop iteration at 1 kHz (64 kB/s) to non-volatile storage for a 10-minute flight (about 40 MiB), without the control loop or in-place code execution ever waiting on a write. | E |

## Memory and boot

| ID | Requirement | Tag |
| --- | --- | --- |
| R-MEM-1 | Performance core: at least 16 KiB on-chip SRAM for hot code and data. 32 KiB if the area budget allows. | E |
| R-MEM-2 | Cold code executes in place from external QSPI NOR flash. | A, replaced by spike S3 |
| R-MEM-3 | Lite core: at least 2 KiB program and 1 KiB data SRAM, retained in deep sleep. | E (RISCay baseline) |
| R-MEM-4 | Boot keeps RISCay's A/B slots, golden image, CRC and compatibility checks and programming lock. | M (exists) |

## Power

| ID | Requirement | Tag |
| --- | --- | --- |
| R-PWR-1 | Retained deep sleep: the fast clock sources are stopped so the main domain has no clock, SRAM and registers retained, lite core running on the 32 kHz clock. | M (RISCay retained sleep), A (lite core running) |
| R-PWR-2 | Wake sources: low-frequency tick, GPIO level, I2C START, UART activity, USB resume. | M for the first three, A for the rest |
| R-PWR-3 | Deep-sleep current target for the whole chip below 50 microamps at 25 C. | A, replaced by leakage measurement in Phase 4 |
| R-PWR-4 | Always-on low-frequency timebase of nominally 32 kHz, within 5 percent after trim. RISCay's 7.7 Hz source is too slow for sensor cadence. | A |

## Interconnect

The historical interconnect requirements have been removed.

## Physical

| ID | Requirement | Tag |
| --- | --- | --- |
| R-PHY-1 | GF180MCU, 3.3 V, 7-track cells, wafer.space 1x1 slot: 3.932 by 5.122 mm die, 12.92 mm2 core. | M (Coldfoot slot data) |
| R-PHY-2 | Fits the slot's pad ring: 40 bidirectional, 12 input-only, 2 analog pads. | M (Coldfoot slot data) |
| R-PHY-3 | The performance core and main domain close timing at the chosen `clk_main` frequency (12 or 24 MHz) at the slow corner with extracted delays. | A, replaced by spike S1 |
| R-PHY-4 | Every production die can be tested for stuck faults in logic and for SRAM defects through a documented access path. | A |
