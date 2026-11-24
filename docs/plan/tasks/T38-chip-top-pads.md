# T38 Chip top, pad ring and physical-flow import

## Goal, inputs and readiness

Complete the I5 chip-level digital/pad assembly and import the D9 LibreLane
flow. Start after T35/T36 and coordinate T37; T34 macro contracts are required.
D88/D89 also require current T39 scoped core/SoC regression evidence for
physical acceptance, including its documented limitations and affected replay
after T35/T36/T37 changes. Preliminary physical work does not substitute for
that evidence or authorize bypassing other stage/physical prerequisites.
Read plan08, selected slot/PDK locks, soc.yaml and USB physical/boundary reports.
Analog extracted views/layout need their separate later brief; do not invent
signoff views or claim tape-out readiness while those are absent.

## Deliverables

1. hw/top/chip production wrapper binding DeadhorseSoc, qualified pad/ESD cells,
   supply/ground and test/debug/clock/reset interfaces. Freeze the simultaneous
   pin map against soc.yaml and slot capacity after review. Keep unused/retired
   ADC functions unassigned; reset-disabled outputs and USB electrical behavior
   must match their contracts.
2. Pin and license every pad/macro/flow dependency. Import/restructure only the
   allowed LibreLane flow/configuration under D9, never Coldfoot RTL/packages.
   If licensing or an import requires prohibited source, stop and report.
3. Floorplan the measured logic, selected SRAM, ROM, actual analog/pad views,
   halos, PDN and routing channels. Separate core and total-die budgets; replace
   allowances with measured placement. No fit claim from standard-cell area.
4. Production clock/reset/IO constraints, approved exact USB exception
   certificates, CDC/RDC inventory, propagated clocks and extracted wires at
   required corners. Carry all raw diagnostics and justified boundary contracts.

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

hw/top/chip, soc.yaml physical pin metadata, locked pad/macro manifests, phys/
gf180-ws-1x1, tools/physical flow scripts, dv/chip, own specs/ledgers/report.
No new peripherals, feature profiles, pin-capacity increase or hidden timing
exception. Functional RTL changes require separate authorization.

## Task acceptance (unverified)

- `python dv/chip/check.py --output build/t38/pads`: pad-level production boot,
  debug, selected peripheral wire traffic, reset-safe output/tri-state and mux
  conflicts; independent pin oracle; swapped-pin and enabled-at-reset faults.
- `python tools/physical/chip.py --output build/t38/physical`: reproducible
  LibreLane import, macro/pad completeness, synthesis/placement/CTS/routing and
  actual area; setup/hold/gate/pulse/recovery/removal/electrical checks at pinned
  corners. USB warning paths receive the mandatory real-wire recheck.
- Functional equivalence through final netlist, scan/BIST integration with T37,
  complete CDC/RDC and pin-map audits, PDN/IR/EM and foundry DRC/LVS/antenna
  results or explicitly blocked missing views. A router DRC file is not foundry
  signoff. Run full CI at I5 exit and report FPGA/system acceptance still owed.

## Stop conditions

Stop for simultaneous pin-map failure, core use beyond12.92 mm2, missing legal
macro/pad views, unqualified cells/corners, functional changes or waived signoff
checks. No tape-out claim until the independent plan08 signoff gates pass.
