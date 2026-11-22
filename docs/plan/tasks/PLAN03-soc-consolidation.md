# PLAN03 SoC consolidation and tape-out planning

## Goal

Consolidate the built MCU on main, pay down verification debt and plan the
remaining tape-out work. User assignment dated 2026-11-21. No new peripheral RTL.
Decisions A1–A5 are recorded as D72–D76.

## Read first

AGENTS.md; plan README, STATUS, 16, 03, 06, 07, 08, 09, 10;
docs/spec/soc.md and bus.md; T20–T31 reports.

Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, gf180-synth-timing-check, formal-timeout-triage.

## Inputs and may change

Built T20–T30 blocks and their existing tests, maps, fixtures and receipts.
May change SoC composition/configuration, affected verification tooling/tests,
documentation and task briefs. No peripheral behavior/register-map changes
except defects found by B2/B3, each with a regression. ADC retirement is the
explicit D74 exception. Keep all other assertions, assumptions, limits and
tolerances unchanged. Generated evidence belongs under build/plan03.

## Ordered deliverables and acceptance (all unverified)

Stop the sequence if a step cannot finish.

Approved B3 follow-up (user, 2026-11-22): complete the focused T19 closure
needed by fast CI. Audit/reuse closed packet proofs; finish retained EP0
sampling, SIE CRC/EOP spacing and timing-exception qualification; repair the
three routed failures under unchanged class limits and externally visible
behavior; qualify boundary hold/RDC only against justified interface contracts.
Keep existing caps, assertions, assumptions and negative controls. Independently
review, then rerun USB and fast CI. Stop for any needed behavior, assumption or
limit change. This is a prerequisite to B4, not a waiver or new peripheral task.

1. **B1 Freeze:** no T31 or new block work.
2. **B2 Consolidate:** DeadhorseSoc binds the faithful RV32IMFC/shared-MAC
   performance core, local memory, main/AON fabrics, bridge/mailbox, three
   UARTs, SPI, I2C, USB, GPIO, main/AON timers, PWM, DMA, pinmux, watchdog,
   lite core, boot release, QSPI command/XIP and frozen recovery loader.
   Only JTAG, clock/power and analog interfaces remain implementation stubs.
   One production soc.yaml; current contract in docs/spec/soc.md, profile
   history in an appendix. Inventory all focused SoC tests/emissions before
   and after; repoint to production or small named test configurations.
   Keep old profiles until the same tests pass, then delete them. Independently
   review no lost test or unintended behavior change. Only then delete ADC
   implementation/tests in a separate commit.
3. **B3 Fast CI:** run `python tools/env/run.py run -- python tools/ci.py --tier fast`
   (verify CLI before execution). Record wall time and deferrals; fix routine
   failures without weakening checks.
4. **B4 T20 measurements:** fresh whole-SoC mapped area, main/AON separately
   and per block; per-domain worst paths at 8/9 MHz under the 60% rule;
   integrated fixed/hard-float mean and worst cycles. Rebuild plan08 budget
   from measured blocks, 16 KiB + 3 KiB SRAM macros and named estimated
   JTAG/clock-power-reset/analog/pad/routing allowances against 12.92 mm2.
   Independent numerical review. Close T20 only if applicable checks pass
   with D75 recorded, otherwise list remaining obligations.
5. **B5 Debt:** STATUS table of every unresolved/deferred proof, its actual
   evidence, owner and closure plan. Include T13 depth160, T14 four, T17
   eight, T23 range, T25 full ISA/machine, T26 full-width watchdog, T19 and
   other open items. One budgeted formal-timeout-triage attempt on T23/T25/T26
   only; unchanged timed-out jobs are not rerun. Do not block B6 on these.
6. **B6 Re-plan:** update plans16/07/09, task index and STATUS. Write standard
   unimplemented briefs with unverified acceptance checks:
   T32 two-hart JTAG debug0.13.2/shared CDC/pinned OpenOCD, preferably pinned
   permissive riscv-dbg BlackBox; T33 clock/reset/power and retained sleep;
   T34 LF/HF/POR/supply-monitor interfaces/models and characterization targets
   (layout later); T35 GF180 SRAM wrappers and March BIST/JTAG status/fault;
   T36 lite-first CRC A/B/golden QSPI ROM boot and UART/existing-I2C recovery,
   no signed boot; T37 scan/test mode/ATPG feeding S4; T38 chip top/pads/ESD/
   map freeze/pad simulation/LibreLane import. Independently review briefs.
   Execution order: T32/T33 in parallel, then T35/T36, then T37/T38;
   T34 may start any time after PLAN03.

## Report and publication

Short PLAN03 report: recorded decisions, production block list, tests before/
after, fast result/time/deferrals, B4 measurements/budget, debt summary and
briefs. Label numbers measured (command/commit), estimated (arithmetic) or
assumed. Commit logical decisions/plan, consolidation, ADC retirement,
measurements and briefs after independent verification. Push main only once
fast CI passes. State full-tier status; run it at an integration-stage end.

## Stop conditions

Ask if consolidation changes externally visible block behavior beyond D74;
fast CI needs a design decision; the area budget including allowances exceeds
12.92 mm2; or a domain misses timing at both 8 and 9 MHz. No new feature
profile, check waiver, peripheral extension or unapproved acceptance change.
