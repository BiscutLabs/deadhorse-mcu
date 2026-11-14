# 08 Physical implementation and verification

Deadhorse is entirely clocked (decision D17), so it uses a standard
synchronous flow: synthesis, clock-tree synthesis, static timing analysis,
scan insertion. Nothing in this document needs custom asynchronous tooling.

## Process and slot

| Item | Value | Source |
| --- | --- | --- |
| Process | GF180MCU, 3.3 V devices and I/O | RISCay, Coldfoot |
| Cells | 7-track. RISCay pins `gf180mcu_fd_sc_mcu7t5v0`; Coldfoot uses `gf180mcu_as_sc_mcu7t3v3`. D15 selects the former at nominal 3.3 V; shuttle qualification remains open | RISCay, Coldfoot |
| SRAM | `gf180mcu_ocd_ip_sram` 1024x8 (155,414 um2) and 512x8 (96,985 um2) | Coldfoot `tile_pkg.sv`, RISCay |
| Slot | wafer.space 1x1: die 3.932 by 5.122 mm, core 12.92 mm2 | Coldfoot slot file |
| Pad ring | 40 bidirectional, 12 input-only, 2 analog, clock and reset pads | Coldfoot pad document |

Coldfoot already has a pad ring, slot template and LibreLane configuration
for this shuttle, for a clocked design. Deadhorse reuses that flow for the
whole chip (decision D9).

### Cell library (decision D15)

Checked in the pinned PDK release: `gf180mcu_fd_sc_mcu7t5v0` has integrated
clock-gating cells (`icgtp`, `icgtn`) and scan flip-flops (`sdffq`,
`sdffrnq`). `gf180mcu_as_sc_mcu7t3v3` has about 40 cell types and neither. A
clocked design that relies on clock gating for its power modes and on scan
for production test needs both, so the approved choice is
`gf180mcu_fd_sc_mcu7t5v0`, subject to the shuttle accepting it at 3.3 V.

## Historical area budget (not a revised fit result)

The following component estimates do not establish whole-chip fit.

| Block | Mapped (mm2) | Basis |
| --- | --- | --- |
| Always-on domain: lite core, power, clock control, timebase, loader | 0.55 to 0.65 | RISCay's clocked design is 0.532 mm2 for its whole MCU (measured by RISCay) |
| Performance core | 0.6 to 1.0 | Assumed two to three times RISCay's CPU; S1 measures it |
| Local bus, flash controller, register blocks | 0.2 to 0.3 | Assumed |
| Serial peripherals, timers, actuator block | 0.3 to 0.5 | Assumed |
| USB (reserved; implemented separately) | 0.2 to 0.3 | Assumed until the implementer supplies a figure |
| SRAM: 16 KiB + 3 KiB | 2.96 | Macro footprints |
| Analog macros: two oscillators, supply monitor | 0.3 to 0.5 | Assumed; RISCay's LF resistor alone is about 0.13 mm2 today |
| --- | --- | --- |

D36 changes access organization, not stored-bit count: sixteen 1024x8 macros
give an estimated 2.487 mm2 performance SRAM footprint; wrapper/routing and
banking overhead still need measurement.

If the Click lite core option is exercised (decision D18), the always-on
domain needs room for the larger version, matched-delay cells characterised
at every corner, and its own timing and test treatment. None of that is in
the budget above; spike S5 measures it.

USB is integrated last. The floorplan reserves its region, pads and clock
route from G1, and the region stays a placement blockage until delivery or the cutoff before Phase 3 floorplan freeze ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)).

## Analog and mixed-signal deliverables

None of these has a qualified Deadhorse layout today. D42 selects wafer.space
GF180MCU 1x1, date open; verify actual slot/pad rules, SRAM and library acceptance
and analog process options before treating historical Coldfoot data as qualified.

| Macro | Starting point | Work |
| --- | --- | --- |
| LF oscillator, 32 kHz, trimmable | RISCay schematic (7.7 Hz) | Redesign, trim DAC, layout, extraction, mismatch and noise, corner campaign |
| HF reference, trimmable, restartable | RISCay schematic | Trim DAC, layout, extraction, glitch-free stop and start at the extracted level, duty cycle and jitter (it is now the main clock) |
| Supply monitor and reset hold | RISCay schematic | Selectable thresholds with safe hardware default, hysteresis, qualified release, layout/extraction, slow ramps, mismatch and test access; no separate early-warning detector |
| External clock fallback | Dedicated clock pad | Divider, glitch-free source selection and switching qualification; no LF crystal driver required |
| USB pad arrangement | Standard 3.3 V bidirectional pads with external series resistors and pull-up | With the USB implementer: validate drive, slew and input thresholds against the full-speed electrical spec |
| Pad ring, ESD, power pads | Coldfoot's wafer.space ring | Re-assign per the pad budget |

The clockless plan's mutex, C-elements and matched-delay cells are no longer
needed. One new demand appears: the HF oscillator is now a clock source for
synchronous logic, so its duty cycle and cycle-to-cycle jitter enter timing
closure.

RISCay's LF design requires the GF180 high-resistance poly option. Confirm the
shuttle includes it before investing in the redesign (open question Q5).

## Verification strategy

### One design

There is one RTL source. The same Chisel is simulated, prototyped on FPGA
and taped out. The clockless plan's second, generated design and the checks
that compared the two are gone.

The test environment (tooling, reference models, the four test targets and
the flight simulation) is specified in
[13-test-environment.md](13-test-environment.md).

### Layers

| Layer | What | Source |
| --- | --- | --- |
| Adopted IP | Each actually adopted block keeps its upstream suite, run in our CI | RISCay carryover, selected HardFloat components, serial cores, USB |
| Converted core | Formal equivalence to the pinned Ibex reference per module and whole core, riscv-formal, lockstep against reference and simulator | T10/T11 |
| FPU and F integration | TestFloat vectors, lockstep with F against the simulator, formal properties; outside the equivalence proof | T12/T13/S1 |
| ISA | RISC-V architectural tests; lockstep comparison with an instruction-set simulator for both cores | Standard suites |
| Block | ScalaTest suites per block, each with a negative control | New |
| SoC, directed | Boot, both images, sleep and wake from every source, reset during every committed operation, bridged bus transactions and mailbox, shared-peripheral ownership/DMA and reset containment | RISCay's clocked chip-test bodies extended |
| SoC, firmware | The real flight firmware against a simulated airframe and sensor models | New |
| Clock-domain crossing | Structural CDC check that every signal crossing a domain goes through the crossing block; simulation with randomised clock phase and frequency ratio; reset during crossing traffic | New |
| Clocking | Glitch checks on every gate and on the always-on clock mux; HF stop and restart at every phase | RISCay's oscillator stop-phase tests extended |
| Formal | The first choice for control logic: full proofs for the crossing FIFO, domain bridge, mailbox, register blocks, bus, watchdogs, power and clock controller, boot lock and actuator block; riscv-formal on both cores; equivalence checks on the netlists. See [12-formal-verification.md](12-formal-verification.md) | Chisel properties, SymbiYosys, riscv-formal |
| FPGA | The SoC on an FPGA board, flying a hardware-in-the-loop simulation, then driving real ESCs, servos and sensors on the bench; no external-link requirement | Coldfoot's FPGA flow |

### Deadlines

These existing budgets are assumed targets checked at the chosen clock
frequency. LF wake/qualification and USB have their own clock-domain bounds.
Keep control-loop publication separate from each channel's frame boundary.

| Deadline | Budget |
| --- | --- |
| Control iteration completes and publishes its command set; each output applies at its own boundary | Existing target under 800 microseconds at 1 kHz; not an actuator timeout setting |
| IMU frame read | Under 150 microseconds |
| UART receive service before FIFO overflow at 921,600 baud | 16 bytes, about 170 microseconds |
| Interrupt latency, pin to first handler instruction | Under 50 microseconds |
| Wake from deep sleep to first main-domain instruction | Under 200 microseconds |

## Production test (R-PHY-4)

Standard for a clocked design:

- **Scan.** Flip-flops are replaced with scan flip-flops and stitched into
  chains, one set per clock domain, with test clocks and scan enable on
  shared pads. Clock gates are forced open in test mode.
- **Patterns.** Stuck-at patterns from an automatic pattern generator.
  Which generator the open flow can use, and what coverage it reaches, is
  the open part (decision D8, spike S4).
- **SRAM.** A march routine run by the lite core from ROM, with results
  readable through the gateway.
- **Analog.** Oscillator frequency and supply-monitor threshold measured and
  characterized through calibration/test access on the tester or bring-up board.
  Validate threshold selection and safe default separately from oscillator trim;
  no permanent trim storage technology has been selected.

## Signoff gates

None may be waived without written approval.

1. Static timing clean at every corner with extracted RC: setup and hold in
   each domain, with clock uncertainty that includes the HF oscillator's
   measured jitter and duty cycle.
2. Clock tree built to every sink, checked by an independent sink count per
   domain; every clock gate and the clock mux shown glitch-free.
3. Every clock-domain crossing passes the structural CDC check and has a
   stated MTBF.
4. Reset: asynchronous assert reaches every flop; synchronous release per
   domain; recovery and removal timing clean.
5. Electrical rules (slew, capacitance, fanout) clean at every corner.
6. SRAM pin setup, hold, access time and pulse widths met.
7. DRC, LVS, antenna clean on the full chip including analog macros and ring.
8. Full simulation suite passing on the post-layout netlist with back-
   annotated delays at the slow and fast corners.
9. Scan chains shift and capture in gate-level simulation; coverage reported.
10. Deep-sleep current from extracted leakage within R-PWR-3, or the
    requirement formally revised.
