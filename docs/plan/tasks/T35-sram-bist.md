# T35 SRAM macros and memory self-test

## Goal, inputs and readiness

Replace production memory models with selected GF180 SRAM wrappers and add
March-style self-test for I5. Start after T32/T33 completion; coordinate with
T36. Read S3, current SocLocalMemory/SocRetainedMemory and pinned SRAM views.
Performance memory remains16 KiB, retained memory3 KiB logical. Boot ROM is T36.

## Deliverables

1. Lock selected foundry macro views and licensing. Preserve existing word,
   byte-enable and banked interfaces. Current planning uses16 1024x8 macros
   for performance SRAM and four for retained SRAM, with the unused256 words
   inaccessible. Report any better qualified organization without changing
   logical capacity/map or silently changing the area budget.
2. Match existing model latency and read-during-write behavior; define unused
   addresses and reset behavior. SRAM contents are arbitrary after power-on;
   reset does not imply RAM initialization. If latency cannot match, stop with
   measured integrated cycle impact before accepting an interface change.
3. March-style algorithm with explicit cell/address fault model and sequence,
   run only in authorized test mode after both cores/DMA are quiescent. Provide
   start/busy/pass/fail/failing-address status over T32 JTAG; prohibit functional
   accesses during destructive BIST. Preserve byte lanes and bank coverage.
4. BlackBox wrappers around pinned macros, corresponding independent simulation
   memories and test-mode muxes. Update physical macro pins/placement/timing
   contracts and plan08 with real views, area/halos and scan integration needs.

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

hw/ip/sram or hw/lib memory wrappers, locked macro manifests/views references,
hw/top memory bindings, narrow JTAG/test interfaces, dv/soc memory tests,
phys constraints and own specs/ledger/report. No buffer-SRAM swap or capacity
increase, caching, or arbitration micro-optimization.

## Task acceptance (unverified)

- `python dv/soc/sram/check.py --output build/t35/sram`: exhaustive lane/bank
  boundaries plus seeded accesses, masked writes, collisions, reset, ownership
  and full production boot/workload tests against independent memory model.
- Prove wrapper address/lane mapping, request/response latency and BIST exclusive
  ownership with covers and wrong-lane/early-completion faults. State separately
  what is proved about digital wrappers and assumed from the macro datasheet.
- BIST covers every accessible address and lane; injected stuck-at, transition
  and address-alias faults reject with readable failure status. Report actual
  tested fault coverage; never claim all physical defects from a March name.
- Measure macro+wrapper timing at required corners including IO/hold/removal;
  remeasure production workload cycles and area. Retention requires qualified
  voltage/power characterization, not an inferred simulation result.

## Stop conditions

Stop for incompatible macro license/views, latency or read/write contract
change, logical memory-map change, budget overrun or insufficient physical
retention limits. Do not use an unqualified macro as a passing model.
