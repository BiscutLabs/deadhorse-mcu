# 02 Requirements

Each requirement carries a provenance tag: **M** measured, **E** estimated
from measured inputs, **A** assumed placeholder. Assumed values name the task
that replaces them. **D** means an approved design requirement, not a measured
result. The decision register controls scope; numerical targets still need
qualification. Historical workload results below were not rerun by PLAN01.

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
tilt-rotor mixer, two ailerons, elevator, rudder). This historical workload
is not the approved V-tail firmware or a validation of the selected sensor stack. It excludes drivers,
failsafe, navigation, interrupt overhead and motor linearisation. Counts are
instructions, not cycles.

## CPU

| ID | Requirement | Tag |
| --- | --- | --- |
| R-CPU-1 | Performance core sustains at least 5 MIPS at the slow corner (SS, 125 C, 3.0 V) with routed delays. Stretch 10 MIPS. Basis: 2,171 instructions at 1 kHz is 2.2 MIPS; doubled for the excluded work and rounded up. | E |
| R-CPU-2 | Clocked Chisel conversion of a pinned Ibex reference, proved equivalent before F is added (T10-T13), RV32IMFC, machine CSRs, vectored interrupts, wfi, debug/RVFI; full single-precision F, no D. Area-focused multicycle FPU with selective HardFloat reuse; no alternative-core selection. | D2, D19, D20 |
| R-CPU-3 | Hardware multiply completes in at most 3 core cycles. Divide may be iterative. | E |
| R-CPU-4 | Interrupt latency from pin to first handler instruction is bounded and at most 50 microseconds at the slow corner. | A, replaced by spike S4 |
| R-CPU-5 | Lite core is RV32E (optionally C) with a minimal interrupt and CSR set. At least 0.2 MIPS on the divided HF clock; a few thousand instructions per second on the 32 kHz clock. | A |
| R-CPU-6 | JTAG debug for both cores: halt, resume, single-step, register and memory access; unlocked initial chip, explicit test mode. | D5, D41 |

## Control and I/O timing

| ID | Requirement | Tag |
| --- | --- | --- |
| R-CTL-1 | Timer-driven 1 kHz target, validated/documented 500 Hz fallback; timestamp BMI270 acquisition independently of loop cadence. | D13, D26 |
| R-CTL-2 | First-application target: nine outputs serving servo/ESC PWM (1 to 2 ms pulse, 50 to 333 Hz, resolution 1 microsecond or better) or firmware-generated DShot300. DShot600 remains a stretch. Use generic timer/PWM/DMA hardware; no dedicated protocol engine. | E; D69 |
| R-CTL-3 | Firmware publishes coherent application commands using the generic timer buffered-update/DMA contract. Independent hardware command generations/publication engine are not required. | D69 supersedes D21 hardware scope |
| R-CTL-4 | Application firmware/board supervision define command timeout and failsafe policy. Hardware provides generic watchdog/reset/output-disable semantics; POR/brownout disable outputs. No per-actuator fallback/arming engine. | D69 supersedes actuator portions of D31/D37 |
| R-CTL-5 | The timing reference for actuator and UART bit timing is accurate to 2 percent or better after trim, over temperature and supply. Confirm the tolerance against the actual ESCs. | A |

## Peripherals

| ID | Requirement | Tag |
| --- | --- | --- |
| R-PER-1 | Three UARTs, 8N1, up to 921,600 baud, with signal inversion (for SBUS-style receivers) and receive FIFOs. | E |
| R-PER-2 | One SPI controller, at least 4 MHz SCLK, two chip selects, for the IMU. A 14-byte read must complete in under 150 microseconds. | E |
| R-PER-3 | I2C controller for MS5611 and IST8310, 100/400 kHz targets; retained I2C loader. No airspeed sensor. | D27-D29; rates A |
| R-PER-4 | Optional full-speed CDC-ACM with separate clock/reset and FIFO boundary; same-port stub. Obtain reservation evidence; cutoff before Phase 3 floorplan freeze, UART/JTAG fallback ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)). | D11, D40 |
| R-PER-5 | At least four general-purpose timers or capture channels, one free-running microsecond timebase. | A |
| R-PER-6 | Battery voltage and current through an external SPI or I2C ADC. The RISCay SPI ADC player is retained for this. | E |
| R-PER-7 | GPIO with wake-on-level, as in RISCay. | M (exists) |
| R-PER-8 | Flight logging: at least 64 bytes per control-loop iteration at 1 kHz (64 kB/s) to non-volatile storage for a 10-minute flight (estimated 38.4 MB before metadata; provision at least the existing 40 MiB allowance), without the control loop or in-place code execution ever waiting on a write. | E |

## Memory and boot

| ID | Requirement | Tag |
| --- | --- | --- |
| R-MEM-1 | 16 KiB performance SRAM baseline, word-wide interface with byte-write enables and configurable banks; increase only with supporting fit/timing evidence. | D12, D36 |
| R-MEM-2 | Cold code executes in place from external QSPI NOR flash. | A, replaced by spike S3 |
| R-MEM-3 | 3 KiB retained lite-core SRAM baseline, configurable banking. | D12 |
| R-MEM-4 | RISCay A/B/golden recovery, CRC, compatibility and programming lock adapted to two images. No signed firmware; CRC is not authentication. | D1, D34 |

## Power

| ID | Requirement | Tag |
| --- | --- | --- |
| R-PWR-1 | Retained clock-gated sleep; selected SPI/I2C/UART available with HF on demand. HF stops only when no consumer needs it; UART receive mode may keep it running. | D7, D22, D24 |
| R-PWR-2 | Timer/event/JTAG wake; GPIO, loader, UART activity, internal events and optional USB resume captured without dependence on stopped clocks. | D7, D22 |
| R-PWR-3 | Quiescent retained-sleep target below 50 microamps at 25 C with HF consumers off; report receive-mode UART/sensor activity separately. | A; extracted estimate in Phase 3, silicon measurement in Phase 4 |
| R-PWR-4 | Always-on low-frequency timebase of nominally 32 kHz (approved), within 5 percent after trim (assumed target). RISCay's 7.7 Hz source is too slow for sensor cadence. | A |

## Bus (replaces the NoC requirements, D43)

R-NOC-1 to R-NOC-6 are withdrawn. No NoC, chip-to-chip link, link pads or
interoperability gate exists in the initial MCU (D4, D43).

| ID | Requirement | Tag |
| --- | --- | --- |
| R-BUS-1 | One simple request/response bus per clock domain using the Ibex memory interface signals, with byte enables and explicit error responses. | D24, D43 |
| R-BUS-2 | Either core can reach permitted registers in the other domain through the domain bridge, subject to exclusive ownership and memory-access checks at the endpoint. | D24, D43 |
| R-BUS-3 | A bridged request toward a stopped clock raises the clock request and completes after wake. No request, response or mailbox word is lost or duplicated across a sleep transition or a single-domain reset. | A |
| R-BUS-4 | The flight loop never waits on the bridge. Loop-critical memory and peripherals are local to the performance core. | A |
| R-BUS-5 | A two-way mailbox between the cores with interrupt and wake on non-empty. | D43 |
| R-BUS-6 | One address window and one interrupt line reserved for a future NoC bridge; nothing built behind them. | D43 |
| R-BUS-7 | Bus fabric, bridge and mailbox together about 0.05 mm2 mapped. T14 measures it. | A target |

## Physical

| ID | Requirement | Tag |
| --- | --- | --- |
| R-PHY-1 | GF180MCU, 3.3 V, 7-track cells, wafer.space 1x1 slot: 3.932 by 5.122 mm die, 12.92 mm2 core. | M (Coldfoot slot data) |
| R-PHY-2 | Fits the slot's pad ring: 40 bidirectional, 12 input-only, 2 analog pads. | M (Coldfoot slot data) |
| R-PHY-3 | The performance core and main domain close timing at the chosen `clk_main` frequency (12 or 24 MHz) at the slow corner with extracted delays. | A, replaced by spike S1 |
| R-PHY-4 | Every production die can be tested for stuck faults in logic and for SRAM defects through a documented access path. | A |


## Additional approved requirements

| ID | Requirement | Provenance |
| --- | --- | --- |
| R-PER-9 | Basic SPI/UART DMA; ownership/private-memory checks, bounded bursts and IRQs | D25 |
| R-PER-10 | Limited pin alternate functions; dedicated clock/reset/JTAG; reset-disabled GPIO outputs; exact map at G1 | D39 |
| R-PWR-5 | External clock input, divider and glitch-free fallback selection | D35 |
| R-PWR-6 | Selectable on-chip reset thresholds, safe default, hysteresis and qualified release; no early-warning detector | D38 |
| R-PWR-7 | Performance watchdog resets performance domain; lite watchdog/POR/brownout reset MCU; generic peripheral reset containment and output-disable contracts, with application failsafe policy in firmware | D37, D69 |
| R-ENV-1 | Pinned Linux container through Docker/WSL and identical CI environment | D23 |
| R-PHY-5 | Selected library at nominal 3.3 V and wafer.space GF180MCU 1x1; qualification/date still open | D15, D42 |

The old fixed-point loop model, assumed flash timings and area estimates do
not qualify the revised FPU/sensor/DMA architecture. Retain their provenance
and replace assumptions with S1-S4 and physical evidence before signoff.
