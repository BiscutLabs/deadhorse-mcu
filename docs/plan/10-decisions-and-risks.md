# 10 Decisions, risks and open questions

## Decisions needing approval

Each has a recommendation. None is final.

| ID | Decision | Recommendation | Alternative | Decide by |
| --- | --- | --- | --- | --- |
| **D1** | How RISCay code enters Deadhorse | One-time import of RISCay's clocked design, shared code, firmware and tests at a recorded commit. With no generator to track, a live dependency has little value | Pinned sbt dependency on RISCay-MCU, which also pulls in its async designs | G0 |
| **D2** | Performance core | Adopt Ibex RV32IMC (SystemVerilog, behind a Chisel black box), used clocked as designed | Extend RISCay's Chisel core to RV32IMC with interrupts, which keeps the whole design in Chisel | G0, confirmed by S1 |
| **D3** | Historical interconnect proposal | Details removed. | | |
| **D4** | External integration | Required a separate agreement. | | G1 |
| **D5** | JTAG debug module in the prototype | Include, as removable | Gateway monitor only | G1 |
| **D6** | 32.768 kHz crystal option | Include the driver if analog capacity allows; it removes the calibration problem for both RC sources | RC sources with factory trim only | G1 |
| **D7** | Dedicated low-power sensor port in the always-on domain | No; the lite core restarts the HF clock and uses the main-domain peripherals | Add one I2C controller in the always-on domain | G1 |
| **D8** | Production test approach | Standard scan chains per clock domain with generated stuck-at patterns; SRAM march from ROM. Open: which pattern generator the open flow supports and its coverage | Functional test only | G1, after S4 |
| **D9** | Physical flow | Coldfoot's LibreLane flow and pad ring for the whole chip | A custom OpenROAD flow | G1 |
| **D10** | Two clocked islands in a clockless MCU | **Superseded by D17.** The whole chip is clocked, so there are no islands; serial and actuator timing count the main clock directly | | Closed |
| **D11** | USB integration | **Set 2026-11-13:** implemented separately, integrated last, space reserved from G1. Still to agree: a cut-off at the Phase 4 floorplan freeze with the UART gateway as fallback | Hold the tape-out for USB | Cut-off at G0 |
| **D12** | Performance SRAM size | 16 KiB baseline; 32 KiB only if S1 to S3 show the area | 32 KiB from the start | G1, after S3 |
| **D14** | Historical source policy | Details removed. | | |
| **D15** | Standard-cell library | `gf180mcu_fd_sc_mcu7t5v0` chip-wide. It has integrated clock-gating cells and scan flip-flops, which a clocked design with gated power modes and scan test needs. Confirm the shuttle accepts it at 3.3 V | `gf180mcu_as_sc_mcu7t3v3`. It has neither cell, so gating and scan would be built from discrete gates and muxes | G1 |
| **D16** | Design language | **Decided 2026-11-13:** Chisel for everything Deadhorse writes and for the SoC top. SystemVerilog only as vendored blocks behind a black box. chisel-async is no longer used (D17) | SystemVerilog throughout | Done |
| **D17** | Timing style | **Decided 2026-11-13:** entirely clocked and synchronous. The clockless plan (desynchronized bundled-data regions generated from a clocked reference) is abandoned | Clockless regions with clocked islands, as in the earlier drafts | Done |
| **D18** | Lite core timing style | **Decided 2026-11-13:** implement the lite core clocked first. Once the design is stable (after gate G2), a coarse Click pipeline version (two-phase bundled data, two or three stages) may be built as a drop-in alternative. The clocked version is the default for tape-out | Clocked only; or clockless from the start | Done; the option is exercised or dropped before the Phase 3 floorplan freeze |
| **D13** | Loop rate commitment | 1 kHz target, 500 Hz accepted fallback | Commit to 500 Hz and relax R-CPU-1 to 2.5 MIPS | G1, after S1 |

D17 replaces the earlier direction. The reasoning recorded for the clockless
plan (D10 and the generator) is kept in the repository history, not here.

## Risks

Ranked by how much of the plan they can stop.

| ID | Risk | Why it matters | Mitigation | Owner phase |
| --- | --- | --- | --- | --- |
| **K2** | The performance core's clock frequency on GF180 is unmeasured | R-CPU-1 needs about 10 MHz at two cycles per instruction. A two-stage core should reach it, but nothing has been timed | S1. Levers: word-wide SRAM, the core's multiplier option, the 500 Hz fallback (D13) | P1 |
| **K3** | The HF oscillator becomes the main clock | An untrimmed RC ring was acceptable as a service clock; as the clock for synchronous logic its jitter and duty cycle enter timing closure, and it has no layout | Characterise jitter and duty cycle at the extracted level; fall back to the 48 MHz pad, divided, as the main clock | P1 to P3 |
| **K4** | Analog layout capacity | Three macros need layout, extraction and corner campaigns; none exists | Start in P0. Reduce scope first by taking 48 MHz from a pad and making the crystal driver optional | P0 to P4 |
| **K5** | Area overrun | Whole-chip fit requires measurement. | Measure block areas and qualify the floorplan. |
| **K6** | Clock-domain crossings and clock switching | Two crossings, a clock mux and many clock gates are where clocked low-power designs fail in silicon | One reviewed crossing block; structural CDC check in CI; glitch tests on every gate and the mux; stop and restart tested at every phase | P2 to P3 |
| **K7** | Pad budget has three spare pads | Any board-driven addition breaks it | Freeze pinout at G1 with the board designer; identify shared pins | P1 |
| **K9** | Flight firmware scope | We are writing our own fixed-point stack instead of porting an existing autopilot. Estimator and transition tuning are real work | Start the airframe model and firmware in P0; fly it on the FPGA at G2, long before silicon | P0 to P2 |
| **K10** | USB on GF180 pads | Full-speed signalling on generic 3.3 V pads is unproven here | Validate electrically with the USB implementer in P2 on paper and in P5 on silicon; UART gateway fallback (D11) | P2, P5 |
| **K11** | Production test coverage in the open flow | Scan insertion is standard, but open pattern generation and its coverage are unproven for this project | S4, then D8 | P1 |
| **K17** | The product loses what distinguished it | RISCay and its library exist to demonstrate clockless design. An entirely clocked Deadhorse is a conventional small MCU  | D18 keeps one route open: a Click lite core as a later, contained option | P0 |
| **K13** | USB arrives late, or does not fit the reserved area, pads, clock or interface | It is integrated last, so a mismatch is found when there is least room to absorb it | Agree the contract in P0; stub with final ports from P2; reserve with margin; cut-off rule (D11) | P0 to P4 |
| **K16** | The Chisel toolchain has not been run by this project | sbt and the Scala suites need Maven Central, which was unreachable while planning; every Chisel task depends on it | Tasks T06 and T07, on a machine with full network access | P0 |
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
is ready to freeze when none remains that affects area, pads or clock-domain
boundaries.
