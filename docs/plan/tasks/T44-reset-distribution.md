# T44 Reset timing and distribution

## Goal and authority

User assignment 2026-11-27; decision D113. Pause T37 until this task
is complete. Fix production reset distribution and remove unobservable payload
resets, preserving the four cohorts and all register/interface behavior.
Work on a new codex/t44-reset-distribution branch from current main. Do not
use the T37 inserted-scan candidate or the rejected dlyb/dlyc experiment as a
baseline. This task explicitly requires fast CI before and after implementation;
the earlier scoped-only test policy does not waive these runs.

## Read first

AGENTS.md; plans README, STATUS, 03, 06, 08, 10, 11-14, 16; tasks/README;
docs/spec/soc.md, soc-power-reset.md, reset-consolidation-inventory.md,
t38-physical-measurement.md; T33/T41/T38/T37 reports; D103/D106/D107;
hw/lib Cdc/ResetRelease and CdcPulseCapture contracts; current production map,
reset-order checks, USB reset certificates and the existing physical locks.

Skills: deadhorse-task-execution, clocked-chisel-block-design,
chisel-formal-properties, reference-model-testing, gf180-synth-timing-check,
formal-timeout-triage.

## Ordered deliverables

1. Baseline gate: run the fast tier on unchanged current main first. Use the
   existing explicit USB evidence interface, with its full authenticity checks.
   Fix or report failures before implementation. Record command, source hash,
   wall time, all deferrals and the full-tier status. Create the task branch,
   record D113 and this brief, and mark T37 paused on T44 in STATUS.
2. Inventory, independently reviewed and committed before RTL changes: from
   current production mapping list every flop async reset/set pin, driver,
   cohort, sink/release-flop clock domains, fanout and control versus payload
   role. Summarize reset/non-reset flops and largest nets per block. Identify
   original modules/domains and root causes for all cited failing paths. Include
   protected Ibex/FPU sink counts/shares and remaining fanout; do not invent a
   numeric dominance threshold. Generated per-pin records stay under build/;
   the report records reproducible commands, hashes and summaries.
3. Write docs/spec/reset-physical-contract.md, independently reviewed before
   any constraint change. Account for every asynchronous control pin, classify
   reset-release arcs, and bind all exceptions structurally:
   - A: asynchronous assertion is untimed by design; STA deassertion checks
     remain. No assertion timing exception is needed.
   - B: only the first/second ResetRelease or CdcSync stage driven by a raw
     asynchronous source may exclude recovery/removal. Check actual topology,
     owning clock, source and polarity, not names. Bind exact source-to-pin
     recovery/removal arcs: a qualifying endpoint does not exempt unrelated
     synchronized-source paths. No downstream blanket
     exception, data-path exemption or pulse-width waiver.
   - C: synchronized release to its own domain is a real recovery/removal
     obligation at all corners, with no exception. SS/FF are the required
     measured screen here, not exhaustive all-corner qualification.
   - D: cross-domain release at an ordinary sink is illegal. Add a destination
     ResetRelease; stop for anything requiring wider architectural change.
   - E: document static reset during scan shift/capture, and deassertion at
     least N scan cycles before the first pulse. Define the tester timing
     precisely. Do not implement scan changes in this task.
   Any reset combinational logic other than the documented assertion OR of
   glitch-free sources and static test mux is a bug to register or remove.
   Assertion A is an edge policy, not a way to exempt an unclassified release.
   User approved the separate listing of the six AON GPIO functional event-set
   inputs, with all existing checks retained and no new exception. Distinguish
   their event contribution from the cohort-reset contribution; this does not
   broaden B or exempt any other unclassified pin.
4. Remove async reset only from payload whose value cannot be observed before
   write or is qualified by existing valid/FSM/handshake guarantees: pipeline
   payload, FIFO/mailbox/CDC data (not pointers), shift data, SRAM captures,
   DMA/UART/SPI/I2C/USB/AON SPI payload and similar justified banks.
   Keep reset on FSMs, valid/ready/pending, pointers, output-affecting counters,
   IRQ/events, every regmap reset value, pad enable/safe controls, watchdog,
   power/clock control and causes. Do not change converted Ibex/FPU reset
   behavior. If these dominate remaining fanout, stop with measured counts.
5. Retain each existing two-flop ResetRelease per cohort/domain. Add a small
   same-domain release pipeline tree with asynchronous assertion, one cycle
   per level, equal root-to-leaf release depth, and initial group bound
   32-64 sinks (or placement-region groups). A parent-release async-reset
   connection with D=1 is the reviewed candidate: it propagates assertion
   asynchronously while making every added stage a real class-C release
   check. Direct raw-cohort RN on new leaves does not acquire a B exemption.
   Place leaves near sinks on the same clock tree; USB leaves stay within its
   48 MHz placement group and get recovery checked first. Resolve gated versus
   ungated clock lineage explicitly. Verify assertion propagation and pulse
   preservation; equal RTL depth alone is not physical timing closure.
   Preserve D103 release order, ROM/boot, lite hold and USB transport; update
   ordering expectations to the justified latency and prove/test the order.
   Do not add reset delay cells or hold buffers as the fix, and do not change
   cohorts or their consumers. Preserve reset presence, values, polarity and
   behavior inside the converted Ibex/FPU. The external release tree may add
   the latency authorized above; validate integration and ordering against its
   actual delayed inputs without changing protected RTL or reusing old
   system-level timing claims unchanged. Define each redistributed sink set.
6. New netlist audit with actual faults: allowed driver for every RN/SN pin,
   no class D, no unapproved reset logic, bounded leaf fanout, and excluded
   source-to-pin recovery/removal arcs exactly B. Retain all non-B checks and
   pulse/electrical checks. Reject cross-domain release, gated-reset and excluded
   non-synchronizer faults. Keep any unresolved classification visible.
7. Reset-independence per changed block: two-copy formal miter within triage
   budget, otherwise simulation with differing random initial values. Compare
   contract-observable outputs and register reads after reset under identical
   inputs. List every existing validity qualification explicitly; no assertion
   weakening or new assumptions. Catch reset removed from a valid bit.
8. Run all reset/boot/sleep-wake/debug/USB-reset and flight-loop SoC tests,
   deterministic plus Verilator random initialization with at least three
   seeds per test. Catch a release leaf one cycle late in the order checks.
   Run fast CI on the final frozen branch, with independent review.
9. Fresh production mapping and the same T38 cts02 flow/PDK/constraints except
   reviewed reset classes. Repeat placement, repair and CTS; no scan insertion.
   Report before/after reset/non-reset flop counts, largest reset fanout,
   reset buffers, logic area at global placement/repair/CTS, class-specific
   recovery/removal worst slack and failing endpoints at SS/FF, and reset-net
   electrical violations. Required: zero C recovery/removal violations at SS
   and FF, zero reset-net electrical violations, and logic area after CTS
   below 5.113576 mm2. Preserve and report other failures without fixing them.
   Post-CTS hold/timing repair is out of scope except where a reset arc needs
   it; report that need. Use placement-estimated RC labels, not routed signoff.
10. Task report: inventory, reviewed contract, per-block reset removals,
    distribution, fault controls, verification commands/times, physical table,
    deferrals and remaining issues. Commit/push only reviewed work; no merge
    to main is implied by creating the branch. STATUS alone tracks progress.

## Acceptance interfaces (unverified)

Existing baseline/final entry point:
`python tools/env/run.py run -- python tools/ci.py --tier fast --output build/t44/OUTPUT --usb-evidence QUALIFIED_MANIFEST`.

Deliver new proposed interfaces under tools/physical for reset inventory,
structural classification, fault controls and class-aware physical reports;
exact commands and production evidence must be recorded before acceptance.
Use existing block/SoC tests and pinned flow, not invented passing receipts.
No checks are marked complete by this brief. Full CI is not required by this
assignment; state explicitly whether it ran.

## May change

Own decision/task/status/report and reset contract; production reset bindings
and shared release helpers; proven-eligible non-core/FPU payload reset choices;
affected properties/tests; physical reset classification, grouping and audit
scripts/constraints. No regmap reset values, interfaces, non-reset timing fixes,
new cohorts, vendor-source edits or T37 scan changes.

## Stop and ask

- Protected Ibex/FPU reset behavior would need to change, or these dominate
  remaining reset fanout (report measured counts first).
- Any regmap reset value or functional behavior would change.
- A class-D fix needs architecture beyond a destination ResetRelease.
- Release ordering cannot absorb the extra cycles.
- Logic area does not go down, or any class-C violation remains after the
  distribution change.

The reported context numbers are historical measurements, not fresh baselines:
functional raw recovery/removal approximately -9.77/-13.60 ns SS, main removal
-7.36 ns SS/-2.43 ns FF, test-reset recovery -5.04 ns SS, about 24,221 reset-root
buffers, and T38 CTS logic 5.113575712 mm2. T37's failed delay-family experiment
had 24,185 dedicated delay cells and added 0.4841228224 mm2. Preserve their
original source/candidate identities in comparisons; do not mix candidates.
