# T37 Test mode and scan insertion

## Goal, inputs and readiness

Implement I5 digital production test and measure ATPG coverage feeding S4.
Start after T35/T36 and stable T32/T33 test interfaces; coordinate T38.
Read D8/D15/D41, plan08 and pinned GF180 scan/clock-gate cells. No coverage
target is waived or inferred from cell-library availability.

## Deliverables

1. Reviewed explicit test-mode entry, pin/JTAG access, safe reset/output states,
   clock/reset bypass and core/memory ownership. Test mode is unlocked physical
   access, not authentication. Prevent accidental entry during normal traffic.
2. Insert scan chains with pinned tools/cell mapping; document ordering, clock
   domains, lockup/hold treatment, excluded state, async-reset controls and SRAM
   BIST isolation. Use qualified scan FFs and the shared gate test controls.
3. Generate/replay ATPG patterns; report stuck-at and supported transition fault
   coverage with total/detected/untestable/aborted/excluded denominators and
   explicit exclusions. List actual tool limits and coverage holes for S4.
4. Measure area, chain length, shift/capture timing/power estimates, test duration
   and routing cost against the chip budget. Generated netlists/patterns stay
   in build/; source configuration and pinned recipes are versioned.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 07, 08, 10, 11–14 and 16;
docs/spec/soc.md and bus.md; PLAN03 report and the verification-debt register.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage; regmap-authoring for new registers.

## Shared acceptance and publication (unverified)

All acceptance below is **unverified**. Proposed new checker interfaces are
deliverables to create, not existing or passing tools. Each checker must emit
source/tool hashes, commands, classified results, assumptions, covers and actual
fault controls under build/. No source-text matching tests. Preserve existing
tests, assertions, solver caps, timing budgets and inherited debt.

Integrate in the single production DeadhorseSoc and soc.yaml; no feature
profiles. Use named test fixtures only. Obtain independent contract review before
RTL, then independent implementation/evidence review. Run the fast tier on main
before starting and on the frozen final snapshot, and the full tier if completing
I2, I3, I4 or I5 (D76). Record both tier statuses and all deferrals. Update the task
report and STATUS; commit/push only after required checks/review. Do not tick
this brief's acceptance boxes or a gate.

Pinned invocation prefix: `python tools/env/run.py run --`. Existing checks:
`python hw/top/reference/check_soc_map.py`,
`python tools/check_structure.py --include-untracked`,
`python tools/ci.py --tier fast --output build/<task>/fast`.
Use the reviewed USB evidence interface when required; never skip USB.

## May change

tools/physical test/scan tooling, phys test constraints, narrow shared gate/reset
test hooks, hw/top test access, dv/soc/test_mode, own specs/ledgers/report.
No functional peripheral behavior changes or hidden scan exclusions.

## Task acceptance (unverified)

- `python tools/physical/test_scan.py --output build/t37/scan`: reproducible
  production-top insertion, every eligible sequential cell accounted for,
  independent pattern replay and injected stuck-at/chain-break detection.
- Prove functional-mode equivalence before/after insertion, all outputs/state
  modulo explicit scan-cell mapping; reject a changed functional D/reset pin.
  Exercise safe outputs, reset/watchdog/JTAG interaction and test-mode exit.
- ATPG report with exact denominators and comparison against any explicitly approved S4 target; if none exists, report
  the open target decision without inventing a coverage floor. Check chain shift/
  capture timing with gate enable, pulse, hold and reset checks. No pre-CTS
  hold RTL padding. Reconcile area/coverage with T38 and S4.

## Stop conditions

Stop for unavailable pinned ATPG/insertion capability, a proposed change to an approved S4 coverage
target, unexplained exclusions/equivalence failure or exceeded area. Do not
substitute scan connectivity for fault coverage, or simulation for equivalence.
