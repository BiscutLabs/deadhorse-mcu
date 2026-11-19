# 10 Decisions, risks and open questions

Approved planning baseline, reconciled 2026-11-13 from the user's explicit
decisions. D3, D14 and D16-D18 include decisions already recorded in the repository.
Approvals establish requirements, not measurements, implementation completion,
licence grants or signoff. This register supersedes the earlier alternatives.

## Decisions

| ID | Subject | Approved direction |
| --- | --- | --- |
| **D1** | RISCay import | Pinned one-time import of the clocked design and needed support code, restructured into Deadhorse conventions. Preserve provenance and licences; no live async dependency. |
| **D2** | Performance core | Convert a pinned, unmodified Ibex reference to clocked Chisel and prove the conversion equivalent module by module before any change (T10/T11); revised 2026-11-14. Then add full F and justified improvements as separate, measured changes (T12/T13), giving RV32IMFC with machine-mode interrupt/debug support. No alternative-core selection or bakeoff. Upstream verification transfers only to modules proved equivalent; everything changed afterwards needs new verification. The reference is never built into the chip; integrating it behind a BlackBox is a fallback that needs user approval. |
| **D3** | Internal NoC | Superseded by D43; no NoC in the initial MCU. |
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
| **D14** | NoC source ownership | Superseded by D43; no Coldfoot transport is imported. |
| **D15** | Standard-cell library | Use gf180mcu_fd_sc_mcu7t5v0 at nominal 3.3 V. Shuttle acceptance and corner qualification must still be verified. |
| **D16** | Design language | New digital RTL is Chisel. Existing permitted vendor RTL is unmodified behind BlackBoxes; emitted SystemVerilog is build output. |
| **D17** | Timing discipline | Entirely clocked initial MCU; shared reviewed CDC implementation, glitch-free clocks, registered boundaries and multicycle heavy operations. |
| **D18** | Historical lite-core option | Existing later Click option remains deferred and requires a separate explicit brief after a stable clocked design. It is not part of this initial implementation or its build dependencies. |
| **D19** | FPU inclusion | Full single-precision RISC-V F is required, including rounding modes, flags, conversions, fused operations and special values. Double precision excluded. Inclusion is mandatory. |
| **D20** | FPU implementation | Area-focused multicycle Chisel FPU with selective pinned HardFloat reuse. Integrate into the Chisel core; no new handwritten SystemVerilog. |
| **D21** | Actuator publication | Independent channel rates, atomic command publication, and application at each channel frame boundary. Channel assignment, direction and endpoints configurable. |
| **D22** | UART sleep modes | Per UART: receive (clock available), wake-only (first byte may be lost; sender needs wake preamble/retry), or disabled. |
| **D23** | Tool environment | Pinned Linux container through Docker/WSL; local checks use the same environment. User clarified local-only verification on 2026-11-14; no GitHub Actions. Pin versions and image digest; no host-specific implementation tools. |
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
| **D43** | Whole-chip bus | Approved 2026-11-14: remove the NoC and use a simple request/response bus per clock domain with a reviewed domain bridge, a two-way mailbox between the cores and the gateway as a bus master (T14). Ownership and memory checks of D24/D25 apply at the endpoints. Reserve one address window and one interrupt for a future NoC bridge; nothing is built behind it. Supersedes D3 and D14; T03, T04 and S2 are withdrawn. |
| **D44** | Multiply/divide formal | Approved 2026-11-14: the end-to-end riscv-formal multiply check does not finish (solver complexity, no counterexample). Split it into an integration check with arithmetic abstracted (ALTOPS), an integer-arithmetic lemma and required seeded simulation; keep the unabstracted check as a non-gating diagnostic recorded as unresolved. Applies to divide on the same evidence, and to the candidate core in T11. This is an approved change of acceptance, not a weakened check made by an agent. |
| **D45** | USB protocol multicycle timing | Approved by the user 2026-11-18: setup 4 / hold 3 only for paths whose launch and capture registers are both proved to update exclusively on the common protocol enable (`clk_gate_i` / `bitEnable`), in retained SIE and Chisel `UsbControl`. Estimated budget: 0.60 × 4 × 1000/48 = 50 ns. Production-source/mapped-pin certificates, reset-safe cadence, exhaustive path classification, negative controls and independent review remain mandatory. All other paths keep existing limits, including PHY, buffers, resume, CDC, reset, registers and IO. Approval does not establish qualification. Stop and report before further restructuring if a certified path exceeds 50 ns or EP0's failing path is not enable-gated. |
| **D46** | EP0 address predecode and small timing overrun | Approved by the user 2026-11-18: maintain an address-nonzero flag alongside the address register with identical reset/update priority and prove equivalence. The identified 12.649599 ns address-to-decode measurement is only slightly above the estimated 12.5 ns screening budget and is non-blocking for continued T19 work. Preserve measured margins, D45 eligibility, formal obligations and electrical/reset/hold checks; this is not a blanket numerical limit increase or qualification claim. |
| **D47** | Scoped USB packet proof engineering | Approved by the user 2026-11-18: one attempt of up to 45 minutes using a proved sparse-memory refinement and proved pointer/ownership invariants, extending the previous portfolio and lane-split triage. Existing assertions, assumptions, solver caps and acceptance requirements remain unchanged. No timeout or abstracted result alone qualifies the production buffers. |
| **D48** | USB value-stability certification | Approved by the user 2026-11-18: extend D45 eligibility to registers whose value is proved to change only on the common protocol-enable cycle, including reset assertion/release. Non-enable writes that preserve value do not disqualify a register. Prove the invariant on production source and bind exact mapped identities. Both endpoints must qualify; setup 4 / hold 3, estimated 50 ns budget and other D45 conditions remain unchanged. |
| **D49** | USB PHY multicycle eligibility | Approved by the user 2026-11-18: retained PHY RX/TX registers may qualify through D48. Actual full-rate sampler/synchronizer, clock-recovery/edge-detection, cadence and any uncertified register retain the estimated 12.5 ns budget. The approved PHY structural exception is unchanged. |
| **D50** | Conditional small-model USB packet proof | Approved by the user 2026-11-18: close the packet obligation only with unbounded original assertions on the same cleanly size-parametric production RTL at small size plus seeded full-size simulation, labelled "proved at small model, simulated at full size". List non-scaling constants and cover wrap/full/empty/retry/maximum packet. One attempt at most 60 minutes, existing caps, no new assumptions/assertion changes. If RTL is not cleanly parametric, restructuring is needed or time expires, stop; do not restructure the buffer. |
| **D51** | USB reset-aware timing closure | Approved 2026-11-18: extend D48 with a proved reset-aware exception only where affected captures are suppressed during reset and cannot resume early afterward. Exact production/mapped binding, common cadence, setup 4 / hold 3 and estimated 50 ns remain required; all other budgets/checks remain. Authorize focused enable fanout/placement investigation without changing enable phase, then pad-delay contract, fixture cleanup and pipeline audit. Packet proofs remain separate; no new packet attempt or buffer restructuring is authorized. |
| **D52** | USB full-rate timing and qualification pass | Approved 2026-11-19: address remaining full-rate paths with buffer/cell sizing and latency-preserving combinational factoring, preserving reset/ACK priority, protocol phase, interfaces and every limit. Then complete pad-delay reporting, sampling/exception qualification and a separately scoped control/ownership plus memory-composition packet attempt under existing solver caps/triage limits; no unchanged timed-out retries, new assumptions, assertion changes, buffer parameterization or SRAM swap. Freeze, check and publish results to the review branch; no merge. |

## Risks and evidence still required

| ID | Risk | Required work |
| --- | --- | --- |
| K2 | Chisel core/FPU speed and area unknown | Convert and prove under T10/T11, build the FPU under T12, integrate under T13, then S1/S4 measure it; no core bakeoff or silent removal of F |
| K19 | Conversion may not reach equivalence on every module, or only to bounded depth | T11 localizes module by module and labels bounded results; BlackBox fallback needs user approval |
| K20 | F is new design outside the equivalence proof | T12 vectors against TestFloat, T13 lockstep against the pinned simulator; riscv-formal F support recorded, not assumed |
| K3 | HF/LF accuracy, startup, jitter, duty cycle and power unqualified | Analog layout, extraction, corners and silicon characterization; D35 provides a clock fallback path |
| K4 | Analog layout and selectable monitor thresholds not implemented | Safe default must work without firmware; validate startup, slow ramps, mismatch, threshold changes and reset release |
| K5 | Full revised chip may exceed slot area | Rebuild area budget with FPU, DMA, ownership, debug and analog; retain approved requirements and report overruns |
| K6 | Sleep, CDC and reset races | Shared crossing implementation, transaction cancellation, independent actuator reset, gated-clock wake tests |
| K7 | Pin map not frozen | Recalculate without die link/crystal-driver requirement; include JTAG, USB reservation and limited muxing |
| K8 | Closed by D43: no Coldfoot source is imported | Never copy Coldfoot packages into this repository without a new decision |
| K9 | Historical flight workload differs from selected sensors and V-tail | Keep historical evidence; validate final float firmware, drivers and aircraft separately |
| K10 | USB electrical implementation and reservation unknown | Obtain implementer constraints and evidence; D11 cutoff and UART/JTAG fallback |
| K11 | Production test coverage unproven | S4 scan/ATPG demonstration, SRAM self-test and analog test access |
| K12 | Supply noise and brownout behavior | Thresholds based on qualified logic/SRAM limits and board tolerances; pulses not guaranteed during undervoltage |
| K13 | USB delivery late | Same-port stub; no tapeout dependency after approved cutoff |
| K14 | Domain bridge and mailbox are new and cross a stopped clock | T14 proves one response per request, no lost wake, cancel on reset; independent models |
| K21 | A later neuromorphic or chip-to-chip project must add a NoC | Reserved address window and interrupt (D43); that project carries its own router, source rights and area |
| K22 | Multiplier arithmetic rests on an algebraic lemma, review and simulation, not an end-to-end proof | T10 attempts the stronger abstract-function check once; lockstep and the stress fixture stay in CI; module equivalence carries the conversion |
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
| Q8 | Repository licence/visibility. No Coldfoot transport release is needed after D43 | Publication, and any vendor import requiring those rights; no longer blocks a task |
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
