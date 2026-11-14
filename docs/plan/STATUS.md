# Status

The single place that shows progress. The plan and the briefs say what to
do; this file says what has been done. Rules for editing it are in
[../../AGENTS.md](../../AGENTS.md), "Tracking progress".

States: `[ ]` not started, `[~]` in progress, `[!]` blocked, `[x]` done.
A line is `[x]` only when its report exists and its acceptance checks passed.

Last updated: 2026-11-13

## Decisions

Tasks marked blocked name the decision they wait on. Details are in
[10-decisions-and-risks.md](10-decisions-and-risks.md).

| | ID | Decision | State |
| --- | --- | --- | --- |
| [ ] | D1 | How RISCay code enters Deadhorse | Open; needed by G0 |
| [ ] | D2 | Performance core | Open; needed by G0, confirmed by S1 |
| [x] | D3 | Interconnect proposal | Decided |
| [ ] | D4 | What is agreed with Coldfoot | Open; needed by G1 |
| [ ] | D5 | JTAG debug module | Open; needed by G1 |
| [ ] | D6 | 32.768 kHz crystal option | Open; needed by G1 |
| [ ] | D7 | Sensor port in the always-on domain | Open; needed by G1 |
| [ ] | D8 | Production test approach | Open; after S4 |
| [ ] | D9 | Physical flow | Open; needed by G1 |
| [x] | D10 | Clocked islands | Superseded by D17 |
| [~] | D11 | USB integrated last | Set; cut-off rule still to agree |
| [ ] | D12 | Performance SRAM size | Open; after S3 |
| [ ] | D13 | Loop rate commitment | Open; after S1 |
| [x] | D14 | interconnect source policy | Decided |
| [ ] | D15 | Standard-cell library | Open; needed by G1 |
| [x] | D16 | Chisel is the design language | Decided |
| [x] | D17 | Entirely clocked | Decided |
| [x] | D18 | Lite core clocked first, Click option later | Decided |
| [~] | D19 | FPU subject to area availability | Decided conditionally; resolves after S1 and S2 |

## Phase 0: Foundation

| | ID | Item | Owner | Depends on | Report |
| --- | --- | --- | --- | --- | --- |
| [ ] | T01 | [Repository scaffold, structure check, CI](tasks/T01-scaffold.md) | unassigned | none | |
| [ ] | T02 | [Flight-loop measurement under CI](tasks/T02-flight-loop-ci.md) | unassigned | T01 | |
| [ ] | T03 | Interconnect study | unassigned | T01 | |
| [ ] | T04 | Interconnect study | unassigned | T03 | |
| [ ] | T06 | [RISCay toolchain and baseline](tasks/T06-riscay-baseline.md) | unassigned | T01 | |
| [!] | T07 | [Chisel build skeleton](tasks/T07-chisel-build.md) | unassigned | T01, T06 | Brief needs rewriting without chisel-async before it can start |
| [ ] | T05 | [Register-map generator](tasks/T05-regmap-generator.md) | unassigned | T07 | |
| [ ] | P0-a | Confirm the nine-channel split against the Stallion wiring PDF (Q1) | person | none | |
| [ ] | P0-b | Choose sensor parts: IMU, barometer, compass, airspeed, GPS, receiver (Q9) | person | none | |
| [ ] | P0-c | Agree the USB integration contract with its implementer (Q12) | person | none | |
| [ ] | P0-d | Agree die-link terms with the Coldfoot team (D4) | person | none | |
| [ ] | P0-e | Start the analog track: oscillators, supply monitor | person | none | |

**Gate G0**

- [ ] D1 and D2 recorded
- [ ] USB integration contract agreed
- [ ] T01 done: skeleton and CI in place

## Phase 1: Measurement spikes

| | ID | Item | Owner | Depends on | Report |
| --- | --- | --- | --- | --- | --- |
| [!] | S1 | [Core speed and area](tasks/S-spikes.md#s1-core), including an FPU-capable core (D19) | unassigned | D2, T07 | Blocked on D2 |
| [ ] | S2 | Interconnect study | unassigned | T03, T04, T07 | |
| [ ] | S3 | [Memory and execute-in-place](tasks/S-spikes.md#s3-memory) | unassigned | T02 | |
| [!] | S4 | [Interrupt latency and scan](tasks/S-spikes.md#s4-latency-and-test-access) | unassigned | S1 | Blocked on S1 |

**Gate G1, architecture freeze**

- [ ] S1: at least 5 MIPS at the slow corner (or the 500 Hz fallback recorded)
- [ ] S3: SRAM size chosen (D12)
- [ ] S4: latency bound and test approach (D8)
- [ ] Decisions D4 to D9, D13, D15 recorded
- [ ] Main clock frequency, area budget, pad budget and clock-domain boundaries frozen
- [ ] No assumed value left that affects area, pads or clock domains

## Phase 2: SoC and FPGA prototype

Briefs are written after G1. Items from [09-roadmap.md](09-roadmap.md):

- [ ] Import RISCay's clocked design as the always-on domain; add clock mux, gates, crossing block
- [ ] Integrate adopted blocks on the local bus with the generated register map
- [ ] New blocks: actuator block, timers, serial peripherals, lite-core extensions, register-transaction layer
- [ ] Boot chain with two images; gateway monitor over UART; USB stub
- [ ] Flight logging: UART stream first, then the logging flash
- [ ] FPGA build flying the hardware-in-the-loop simulation; real actuators and sensors on the bench
- [ ] Scan inserted; suite passing on the gate-level netlist
- [ ] Optional: S5, the Click lite core (D18)

**Gate G2**

- [ ] Simulated Stallion flies hover, transition and forward flight on the FPGA
- [ ] Nine real actuators driven with correct timing
- [ ] Deep sleep entered and left with the main clock stopped
- [ ] Structural clock-domain-crossing check clean

## Phase 3: Physical

- [ ] Floorplan with SRAM, analog macros, pad ring, USB reservation
- [ ] Synthesis, scan, placement, clock tree, routing
- [ ] Timing closed at all corners with extracted RC
- [ ] Analog macro layouts integrated; DRC, LVS, antenna clean
- [ ] Deep-sleep current from extraction
- [ ] USB integrated, or the cut-off applied
- [ ] Lite core variant chosen (D18)

**Gate G3:** the ten signoff gates in [08-physical-verification.md](08-physical-verification.md)

- [ ] 1 Static timing
- [ ] 2 Clock tree and gating
- [ ] 3 Clock-domain crossings
- [ ] 4 Reset
- [ ] 5 Electrical rules
- [ ] 6 SRAM timing
- [ ] 7 DRC, LVS, antenna
- [ ] 8 Post-layout simulation
- [ ] 9 Scan
- [ ] 10 Deep-sleep current

## Phase 4: Silicon

- [ ] Tape-out
- [ ] Bring-up board
- [ ] Production test program; trim and calibration
- [ ] Characterisation
- [ ] Flight: bench, tethered hover, free hover, transition

**Gate G4:** the definition of done in [01-product-definition.md](01-product-definition.md)

## Log

One line per change of state, newest first: date, ID, old state to new state,
who, and the report path if there is one.

- 2026-11-13: tracker created. No task started.
