# 10 Decisions, risks and open questions

Approved planning baseline, reconciled 2026-11-13 from the user's explicit
decisions. D3, D14 and D16-D18 include decisions already recorded in the repository.
Approvals establish requirements, not measurements, implementation completion,
licence grants or signoff. This register supersedes the earlier alternatives.

## Decisions

| ID | Subject | Approved direction |
| --- | --- | --- |
| **D1** | RISCay import | Pinned one-time import of the clocked design and needed support code, restructured into Deadhorse conventions. Preserve provenance and licences; no live async dependency. |
| **D2** | Performance core | Reimplement Ibex in clocked Chisel with full RV32IMFC and machine-mode interrupt/debug support. Improve the design where justified; no alternative-core selection or bakeoff. New verification is required; upstream verification does not transfer. |
| **D3** | Historical interconnect proposal | Details removed. |
| **D4** | Initial-chip scope | No chip-to-chip link and no neuromorphic IP in the initial MCU. Link framing, external discovery, interoperability and related pads are deferred. |
| **D5** | Debug hardware | Include JTAG debug for both cores. UART gateway and JTAG are the fallback if USB misses its cutoff; JTAG is not an area-cut option. |
| **D6** | Low-frequency clock | Internal nominal 32 kHz oscillator. No external low-frequency crystal driver is required for the baseline; numerical accuracy, startup and current remain characterization targets. |
| **D7** | Sleep peripherals | SPI, I2C and each UART selectively available while the performance core sleeps. HF clock requested only when needed; UART receive mode keeps its required clock running. Retained state, timer/event/JTAG wake; no power-gated standby. |
| **D8** | Production test | Include scan, SRAM self-test, and analog calibration/test access. Coverage, pattern generator, timing and macro qualification remain engineering work. |
| **D9** | Physical flow | Reuse Coldfoot LibreLane flow and pad-ring approach, restructured to Deadhorse conventions; import only authorized physical collateral. |
| **D10** | Clocked islands | Superseded by D17; no clockless-island architecture. |
| **D11** | USB cutoff | Optional USB is integrated last. Apply cutoff before Phase 3 floorplan freeze; proceed with UART and JTAG if USB is not ready. Reservation requires implementer evidence. |
| **D12** | Memory capacity | 16 KiB performance SRAM plus 3 KiB retained lite SRAM baseline. Configurable banking and room to increase if measurements justify it; larger memory is not a claim of physical fit. |
| **D13** | Control-loop target | Timer-driven 1 kHz target with documented, validated 500 Hz fallback. Timestamp sensor acquisition; do not require one IMU data-ready edge per iteration. |
| **D14** | Historical source policy | Details removed. |
| **D15** | Standard-cell library | Use gf180mcu_fd_sc_mcu7t5v0 at nominal 3.3 V. Shuttle acceptance and corner qualification must still be verified. |
| **D16** | Design language | New digital RTL is Chisel. Existing permitted vendor RTL is unmodified behind BlackBoxes; emitted SystemVerilog is build output. |
| **D17** | Timing discipline | Entirely clocked initial MCU; shared reviewed CDC implementation, glitch-free clocks, registered boundaries and multicycle heavy operations. |
| **D18** | Historical lite-core option | Existing later Click option remains deferred and requires a separate explicit brief after a stable clocked design. It is not part of this initial implementation or its build dependencies. |
| **D19** | FPU inclusion | Full single-precision RISC-V F is required, including rounding modes, flags, conversions, fused operations and special values. Double precision excluded. Inclusion is mandatory. |
| **D20** | FPU implementation | Area-focused multicycle Chisel FPU with selective pinned HardFloat reuse. Integrate into the Chisel core; no new handwritten SystemVerilog. |
| **D21** | Actuator publication | Independent channel rates, atomic command publication, and application at each channel frame boundary. Channel assignment, direction and endpoints configurable. |
| **D22** | UART sleep modes | Per UART: receive (clock available), wake-only (first byte may be lost; sender needs wake preamble/retry), or disabled. |
| **D23** | Tool environment | Pinned Linux container through Docker/WSL; same environment in CI. Pin versions and image digest; no host-specific implementation tools. |
| **D24** | Buses and ownership | Performance-local SRAM/XIP/actuators, AON lite SRAM/control, shared sleep-capable serial peripherals with exclusive ownership and clock-domain bridges. Wake/HF requests cannot depend on a stopped clock. |
| **D25** | DMA | Basic SPI/UART DMA with ownership and memory-access checks, bounded bursts and completion/error interrupts. No linked descriptors required initially. |
| **D26** | IMU | BMI270 with timestamped acquisition and timer-driven loop (D13). Stream initialization data from flash rather than reserving the whole blob in SRAM. |
| **D27** | Barometer | MS5611 over I2C; configurable acquisition rate, initial 50 Hz target. |
| **D28** | GPS and compass | External Holybro M10 with IST8310, SKU 12042, as baseline: UART GPS and I2C compass. |
| **D29** | Airspeed | No airspeed sensor in the baseline. Sensorless transition/estimation needs application validation, not an additional MCU sensor port. |
| **D30** | RC | RadioMaster Boxer ELRS and RP3 V2 baseline; CRSF UART connection. |
| **D31** | Actuator fault detection | Hardware command timeout with configurable deadline and per-channel failsafe actions. Deadline and recovery policy are explicitly deferred to testing; do not freeze automatic recovery or mandatory keyed re-arm. |
| **D32** | Actuator count | Three motors, two tilt servos, two ailerons, two V-tail servos: nine channels. Preserve configurable assignment, direction and endpoints. |
| **D33** | Actuator parts | Holybro Tekko32 F4 45A factory AM32 ESCs; GDW DS041MG positional tilt servos; EMAX ES08MA II surface servos. Electrical timing, load and mechanical compatibility still need bench validation. |
| **D34** | Boot authentication | No signed firmware for the initial MCU. Keep CRC integrity, image compatibility and recovery loading. CRC is not authentication. |
| **D35** | External clock | Include dedicated external clock input, divider and glitch-free source selection/fallback path. No seamless automatic failover policy has been approved. |
| **D36** | Performance SRAM access | Word-wide (32-bit) access with byte-write enables and configurable banks. Parallel byte-wide qualified macros are acceptable; actual macro choice and latency require qualification. |
| **D37** | Reset containment | Performance watchdog resets performance domain while AON lite core/retained SRAM and reset reason survive. Lite watchdog resets whole MCU; power-on/brownout reset whole MCU. Actuator reset is independent of performance reset and enters configured failsafe on either watchdog fault while clock/supply remain valid. |
| **D38** | Supply monitor | Keep on-chip supply monitor with selectable thresholds, hysteresis and qualified reset release; safe hardware default before firmware/flash settings. Defer early-warning detector. Numerical thresholds and implementation of selection remain to be characterized; no OTP added by this decision. |
| **D39** | Pin multiplexing | Limited register-selectable alternate functions; exact map before architecture freeze. General-purpose outputs disabled at reset; dedicated external clock/reset and JTAG pins. Approved interfaces must coexist. |
| **D40** | USB boundary | Full-speed CDC-ACM, separate clock/reset domain, reviewed CDC, TX/RX byte FIFOs, status/control, interrupts and wake. USB protocol contained in subsystem; identical stub until delivery. Implementer supplies area/pads, constraints and verification. |
| **D41** | Debug access policy | Unlocked debug for initial chip; explicit test-mode scan access. No permanent debug-disable fuses or authenticated debug. Physical debug/gateway access permits firmware and memory access; boot programming lock is not a security boundary. |
| **D42** | Fabrication target | wafer.space GF180MCU 1x1 slot; shuttle date open. Target approval does not qualify PDK options, libraries, SRAM, analog devices or pad ring. |

## Risks and evidence still required

| ID | Risk | Required work |
| --- | --- | --- |
| K2 | Chisel core/FPU speed and area unknown | Implement the selected architecture under T10, then S1/S4 measure it; no core bakeoff or silent removal of F |
| K3 | HF/LF accuracy, startup, jitter, duty cycle and power unqualified | Analog layout, extraction, corners and silicon characterization; D35 provides a clock fallback path |
| K4 | Analog layout and selectable monitor thresholds not implemented | Safe default must work without firmware; validate startup, slow ramps, mismatch, threshold changes and reset release |
| K5 | Full revised chip may exceed slot area | Rebuild area budget with FPU, DMA, ownership, debug and analog; retain approved requirements and report overruns |
| K6 | Sleep, CDC and reset races | Shared crossing implementation, transaction cancellation, independent actuator reset, gated-clock wake tests |
| K7 | Pin map not frozen | Recalculate without die link/crystal-driver requirement; include JTAG, USB reservation and limited muxing |
| K8 | Mixed proprietary packages in source transport | T03 blocked until sanitized transport-only source and licensing/visibility scope are approved; never copy mixed packages first |
| K9 | Historical flight workload differs from selected sensors and V-tail | Keep historical evidence; validate final float firmware, drivers and aircraft separately |
| K10 | USB electrical implementation and reservation unknown | Obtain implementer constraints and evidence; D11 cutoff and UART/JTAG fallback |
| K11 | Production test coverage unproven | S4 scan/ATPG demonstration, SRAM self-test and analog test access |
| K12 | Supply noise and brownout behavior | Thresholds based on qualified logic/SRAM limits and board tolerances; pulses not guaranteed during undervoltage |
| K13 | USB delivery late | Same-port stub; no tapeout dependency after approved cutoff |
| K15 | RISCay clean baseline not fully reproduced | T06, with independent receipt and no changes to upstream |
| K16 | New pinned environment/build unverified | T08 then T07; missing tools fail required checks |
| K17 | Performance/power improvements unmeasured | Document intended improvements and measure; do not inherit Ibex results |
| K18 | Formal engines may only reach bounded depth | Label bounded results honestly; retain negative controls and explicit assumptions |

## Remaining questions (not resolved by approval)

| ID | Question / status | Required before |
| --- | --- | --- |
| Q1 | Actuator split resolved by D32 | No further architectural approval |
| Q2 | ESC/servo electrical thresholds, pulse timing, rates and load behavior | Bench integration and final clock accuracy budget |
| Q3 | Team capacity and shuttle date open | Schedule commitment |
| Q4 | External discovery/link compatibility deferred by D4 | A later chip-to-chip project |
| Q5 | Shuttle acceptance of selected cells, SRAM and analog process options | Architecture/physical freeze as applicable |
| Q6 | Supply tolerances, selectable reset thresholds and release interval | Analog specification and signoff |
| Q7 | Signed boot excluded by D34 | No further architectural approval |
| Q8 | Repository licence/visibility and permitted transport source release | Any source import/release requiring those rights |
| Q9 | Sensor/receiver/actuator baseline resolved by D26-D33 | Parts do not establish bench qualification |
| Q10 | Programmable sleep peripherals resolved by D7/D22/D24 | CDC, wake and ownership implementation tests |
| Q11 | Whether another tapeout is planned remains open | Product schedule; not a foundation blocker |
| Q12 | USB boundary approved; actual area, PHY/pads, clock tolerance, delivery and test collateral outstanding | Reservation freeze and integration cutoff |
| Q13 | Command-timeout deadline and recovery policy intentionally open | Actuator behavior/register freeze after testing |
| Q14 | UART board assignments and telemetry transport not approved | Board/firmware integration; not MCU foundation |

## Evidence policy

Historical measurements retain their original scope. All proposed frequencies,
current limits, area allowances and test limits remain targets/assumptions until
their named task reports evidence. Approved capacity and device counts are
requirements, not measured implementation results. Do not mark gates complete
merely because these decisions are recorded.
