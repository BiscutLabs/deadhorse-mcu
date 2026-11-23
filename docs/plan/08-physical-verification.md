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

## T32 provisional physical-boundary budget: within ceiling

T32's uncommitted production integration on main `9b80375` replaces the assumed
JTAG allowance with measured whole-top logic. The same PLAN03 mapping method
and all other allowances remain unchanged. Following the approved SBA-routing
experiment, the user approved a broader area review. The independently checked
[physical boundary](../spec/soc-physical-boundary.md) excludes verification-only
RVFI observations from measurement while retaining them in every test. Complete
bottom-up reset-buffer layers retain the same cell and fanout bound. These
measurement refinements restore the estimate below the ceiling without a budget
exception. This is not physical fit or final T32 acceptance.
Commands, evidence hashes, qualifications and open checks are in the
[T32 report](tasks/reports/T32.md).

| Item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built functional production logic including debug, 8 MHz mapping trial | 3.480476429 | Measured, `python scratch/t32_area07_run.py` and area07 partition in the pinned environment; observers excluded only from physical measurement |
| Separate JTAG allowance | 0 | Removed to avoid double counting; actual integration is in mapped logic |
| Remaining digital allowances | 0.700000000 | Assumed: controller .10, ROM .50, BIST .05, scan glue .05 |
| Scan-flop uplift on built logic | 0.410504595 | Estimated from mapped flops and library scan areas; two negative-edge flops use an explicitly estimated scan-flop plus clock-inverter implementation, to qualify in T37 |
| Digital subtotal at unchanged 0.55 utilization | 8.347238225 | Estimated sum of digital rows / .55 |
| Performance and retained SRAM | 3.108271060 | Estimated from unchanged pinned macro footprints below |
| Analog, pad/keepout and halo/glue allowances | 1.400000000 | Assumed, unchanged .50 + .50 + .40 |
| Total core use | **12.855509285** | Estimated, `python scratch/t32_area07_budget.py`; area-only ceiling check passes |
| Headroom under unchanged 12.92 ceiling | **0.064490715** | Estimated subtraction; narrow, not placement margin qualification |

This supersedes the fit estimate below for the current T32 working tree, not
the published pre-T32 main baseline. No allowance, utilization or ceiling has
been revised. Independent graph, arithmetic and matched endpoint reviews resolve
the area-only stop. Original T32 validation resumes; final CI, complete timing
and implementation acceptance remain open. Raw reset-removal, USB exception
qualification and unbuffered core-clock pulse diagnostics remain visible.

## PLAN03 baseline measured logic and estimated chip budget

Measured on main `736ed5c`, unchanged production RTL, with the commands and
per-block/domain allocation in [production measurements](../spec/soc-production-measurements.md).
Whole mapped standard-cell logic is **3.322808384 mm2 at the 8 MHz trial** and
**3.3165169408 mm2 at the 9 MHz trial**. This includes real USB and observation
logic, excludes six SRAM/ROM interfaces, and is not a placed-area result.
The main/AON/USB allocation and explicit shared rows reconcile exactly to it.

| Budget item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built standard-cell logic, larger trial | 3.322808384 | Measured, `python scratch/plan03_area_partition.py`; pinned GF180 SS/125 C/3.0 V |
| Two-hart JTAG debug | 0.150000 | Assumed digital allowance, inclusive of eventual scan overhead; replace in T32 |
| Clock/reset/power controller | 0.100000 | Assumed digital allowance, inclusive of eventual scan overhead; replace in T33 |
| Boot-ROM realization | 0.500000 | Assumed digital allowance; content/implementation dependent, not a guarantee for arbitrary 64 KiB contents; T36/T38 |
| SRAM wrappers and memory BIST | 0.050000 | Assumed digital allowance, inclusive of eventual scan overhead; T35 |
| Scan/test control and insertion glue | 0.050000 | Assumed digital allowance; T37 |
| Scan-flop uplift on built logic | 0.378579802 | Estimated from measured 19,162 mapped FFs and pinned same-drive dff-to-sdff cell areas; T37 must measure actual insertion |
| Digital subtotal at existing 0.55 utilization | 8.275251247 | Estimated: sum of digital rows / 0.55; includes 3.723863061 mm2 whitespace/routing reserve |
| Performance SRAM, 16 KiB | 2.486616848 | Estimated: 16 x 301.300 x 515.810 um2 / 1e6 from pinned 1024x8 LEF |
| Retained SRAM, 3 KiB logical | 0.621654212 | Estimated: four 1024x8 macros, 4 KiB physical; unused 256 words do not enlarge the address map |
| Analog oscillator/POR/supply-monitor macros | 0.500000 | Assumed physical allowance; T34 characterization/layout must replace it |
| Pad interface and in-core keepout | 0.500000 | Assumed core allowance; full external ring is outside this core budget and must fit the die in T38 |
| SRAM halo/channels and other physical glue | 0.400000 | Assumed physical allowance, separate from standard-cell utilization |
| Total core use | **12.783522307** | Estimated, `python scratch/plan03_area_budget02.py` |
| Headroom to 12.92 mm2 | **0.136477693** | Estimated: 12.92 - 12.783522307, approximately 1.06% |

Pinned SRAM LEF SHA-256 is
`35bcf13111ab5029860ca7a2ef473fbf21b4938d6c6244b53b4480bd35f2776a`;
measured dimensions are 301.300 by 515.810 um. Scan uplift is estimated by
substituting each actual mapped dffq/dffrnq/dffsnq with the characterized
same-drive scan variant; no scan RTL or ATPG result is implied. The unbuilt
digital allowances include their eventual scan overhead.

Independent review recomputed the cell inventories, library areas, arithmetic
and headroom. This narrow planning margin is **not physical fit or tape-out
approval**. Macro timing, ROM contents, real analog layouts, pad ring, CTS,
routing and scan/BIST implementation must replace the allowances in T32-T38.
No SRAM macro swap or new peripheral RTL was implemented by PLAN03.

## Historical area budget (not a revised fit result)

The table below predates the PLAN03 budget above; see
[16-soc-integration.md](16-soc-integration.md) for the current inventory.

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
