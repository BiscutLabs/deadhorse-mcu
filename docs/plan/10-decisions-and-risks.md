# 10 Decisions, risks and open questions

## Decisions needing approval

Each has a recommendation. None is final.

| ID | Decision | Recommendation | Alternative | Decide by |
| --- | --- | --- | --- | --- |
| **D1** | How RISCay code enters Deadhorse | Pinned dependency on RISCay-MCU for the generator and shared code | Fork and prune | G0 |
| **D2** | Performance core | Adopt Ibex RV32IMC, desynchronize it | Extend RISCay's core to RV32IMC with interrupts | G0, confirmed by S1 |
| **D3** | Historical interconnect proposal | Details removed. | | |
| **D4** | External integration | Required a separate agreement. | | G1 |
| **D5** | JTAG debug module in the prototype | Include, as removable | Gateway monitor only | G1 |
| **D6** | 32.768 kHz crystal option | Include the driver if analog capacity allows; it removes the calibration problem for both RC sources | RC sources with factory trim only | G1 |
| **D7** | Dedicated low-power sensor port in region A | No; the lite core borrows island T | Add one I2C controller in region A | G1 |
| **D8** | Production test approach | Latch-enable override giving level-sensitive scan in regions A and M; ordinary scan in islands; SRAM march from ROM | Functional test only | G1, after S4 |
| **D9** | Physical flow | Coldfoot's LibreLane chip level and pad ring; RISCay's OpenROAD scripts for clockless regions | One flow for everything | G1 |
| **D10** | Accept two clocked islands (timed I/O, USB) in a clockless MCU | **Approved 2026-11-13.** A written obligation each and a frozen clocked-state ceiling | Self-timed peripherals with delay-line bit timing | Done |
| **D11** | USB integration | **Set 2026-11-13:** implemented separately, integrated last, space reserved from G1. Still to agree: a cut-off at the Phase 4 floorplan freeze with the UART gateway as fallback | Hold the tape-out for USB | Cut-off at G0 |
| **D12** | Performance SRAM size | 16 KiB baseline; 32 KiB only if S1 to S3 show the area | 32 KiB from the start | G1, after S3 |
| **D14** | Historical source policy | Details removed. | | |
| **D15** | Standard-cell library | `gf180mcu_fd_sc_mcu7t5v0` chip-wide. RISCay's async primitives and delay characterisation are on it. Confirm the shuttle accepts it at 3.3 V | `gf180mcu_as_sc_mcu7t3v3`, and re-characterise RISCay's primitives | G1 |
| **D13** | Loop rate commitment | 1 kHz target, 500 Hz accepted fallback | Commit to 500 Hz and relax R-CPU-1 to 2.5 MIPS | G1, after S1 |

D10 is approved. The reasoning, for the record: RISCay's rule is that no clock is added to fix an async
problem, and clocks stay only where an obligation demands one. Serial bit
timing and USB bit recovery are obligations of that kind: the external
protocol defines an absolute period. The islands are small, gated when idle,
and counted. The alternative, generating baud and pulse timing from delay
lines, would trade a few hundred clocked bits for an analog accuracy problem
on every peripheral.

## Risks

Ranked by how much of the plan they can stop.

| ID | Risk | Why it matters | Mitigation | Owner phase |
| --- | --- | --- | --- | --- |
| **K1** | Mutex cannot be shown to meet its failure-rate target | Deep sleep stops region M through it. Without it there is no retained sleep | Start characterisation in P0. Fallback to be designed: a synchronizer-based stop with a stated MTBF, at the cost of slower sleep entry | P0 to P4 |
| **K2** | Desynchronized core is too slow | RISCay's generated design models 358.9 ns per cycle; R-CPU-1 needs roughly 70 to 100 ns | S1 before anything else. Levers: more banks with local delays, the core's own pipeline, word-wide SRAM, the 500 Hz fallback (D13) | P1 |
| **K3** | Routed async timing has never been closed in this flow | Every RISCay margin is zero-wire or schematic. Guard sizing after routing may cost area and speed | Take one bank through full routed relative-timing closure during P1 or P2, not P4 | P1 to P4 |
| **K4** | Analog layout capacity | Three macros plus mutex need layout, extraction and corner campaigns; none exists | Start in P0. Reduce scope first by taking 48 MHz from a pad and making the crystal driver optional | P0 to P4 |
| **K5** | Area overrun | Whole-chip fit requires measurement. | Measure block areas and qualify the floorplan. |
| **K6** | Ibex does not pass cleanly through a generator built around Chisel exports | The flow may assume naming, reset or clock-gating conventions of RISCay's own netlist | S1. Fallback is D2's alternative | P1 |
| **K7** | Pad budget has three spare pads | Any board-driven addition breaks it | Freeze pinout at G1 with the board designer; identify shared pins | P1 |
| **K9** | Flight firmware scope | We are writing our own fixed-point stack instead of porting an existing autopilot. Estimator and transition tuning are real work | Start the airframe model and firmware in P0; fly it on the FPGA at G2, long before silicon | P0 to P2 |
| **K10** | USB on GF180 pads | Full-speed signalling on generic 3.3 V pads is unproven here | Validate electrically with the USB implementer in P2 on paper and in P5 on silicon; UART gateway fallback (D11) | P2, P5 |
| **K11** | Production test coverage | The latch-override scheme is a proposal | S4, then D8 | P1 |
| **K13** | USB arrives late, or does not fit the reserved area, pads, clock or interface | It is integrated last, so a mismatch is found when there is least room to absorb it | Agree the contract in P0; stub with final ports from P2; reserve with margin; cut-off rule (D11) | P0 to P4 |
| **K15** | RISCay's full gate has not been run on a clean machine by this project | Only the tool bootstrap and the Python gate were verified; the Scala suites and export need Maven Central | Task T06 | P0 |
| **K12** | Supply noise from ESCs trips the supply monitor in flight | Schematic thresholds sit 60 to 280 mV below a nominal 3.3 V rail | Revisit threshold with the board; board-level filtering; failsafe behaviour on brownout defined | P2 |

## Open questions

| ID | Question | Needed for |
| --- | --- | --- |
| Q1 | Exact actuator list for the Stallion: are the four surfaces two ailerons, elevator and rudder, or elevons or a V-tail? | Mixer, pad budget |
| Q2 | What bit-timing tolerance do the chosen ESCs accept on DShot300? | R-CTL-5, HF trim spec |
| Q3 | Team size and target shuttle date | Turning phases into a schedule |
| Q5 | Does the target shuttle include the high-resistance poly option the oscillators assume? | Analog track |
| Q6 | Board supply rail tolerance and noise in flight | Supply monitor threshold |
| Q7 | Is authenticated boot needed for the product? | Boot ROM, key storage |
| Q8 | Repository visibility and licence, including any third-party dependencies | Publication |
| Q9 | Which IMU, barometer, compass, airspeed sensor, GPS and receiver? | Peripheral requirements, firmware |
| Q10 | What must the lite core do in deep sleep for the first product: supervise only, or sample sensors continuously? | D7, R-PWR-3 |
| Q11 | Is a second tape-out planned? | How much to mark removable versus defer |
| Q12 | USB implementation: expected area, clock source and accuracy, pad and PHY approach, interface at its boundary, source language, verification deliverables, delivery date | Sizing the reservation, the integration contract |

## Assumptions to retire

Every **A**-tagged requirement in [02-requirements.md](02-requirements.md)
and every "assumed" row in the area budget names what replaces it. The plan
is ready to freeze when none remains that affects area, pads or region
boundaries.
