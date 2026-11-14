# PLAN01 report

## Outcome

Done: reconciled the approved planning decisions and task briefs without starting implementation.

## What changed

- Root README and AGENTS: current scope, approved core-reimplementation exception,
  transport-only import rules and explicit decision tracking.
- Plan README and documents 01-14: requirements, architecture, reset/sleep,
  selected devices, memory/FPU, USB, pin mux, fabrication and verification scope.
- Decision register D1-D42 and STATUS: approved direction distinguished from
  implementation and qualification; no implementation task or gate completed.
- Task index and T01-T07/S1-S4: direct Chisel build, no core bakeoff, required
  environment, no mixed neural import, no initial die link, appropriate fixtures.
- New PLAN01 documentation brief, T08 environment, T09 timing and T10 selected
  core/FPU briefs. New task commands are explicitly unverified.
- Actuator specification: per-channel application of atomic
  publications, ownership and reset semantics; final actuator ABI deferred.

## Checks run

- `git -c core.safecrlf=false diff --check`: exit 0, no output (whitespace clean).
- `python scratch/check_plan.py`: PASS for Markdown links/anchors, complete
  decision IDs, allowed documentation scope and no implementation/gate completion.
  Final output: `PASS: 35 Markdown files, 125 local links/anchors, 42 decision IDs; documentation-only scope; no implementation/gates marked done`.
  The scratch checker is documentation validation, not an RTL source-matching test.
- `git -c core.safecrlf=false diff --name-only` and untracked-file inspection:
  only root documentation, docs/plan and affected docs/spec files changed.
  The new files are the listed task briefs and report.
- Manual cross-check against the approval conversation and stale-direction
  searches: removed initial-chip die-link requirements, conditional/no FPU,
  SystemVerilog core adoption, simultaneous actuator updates and fixed recovery
  policy; remaining historical/deferred references are identified as such.
- `python3 tools/ci.py`: not run; tools/ci.py does not exist because T01 has
  not started. `Test-Path tools/ci.py` returned `False`. No implementation or
  hardware tests were run or claimed.

## Numbers

Decision IDs and approved capacities/rates/counts are planning requirements,
not hardware measurements. Historical synthesis/workload data retain their
original provenance and were not rerun. New arithmetic is explicitly estimated:
16 x 155,414 um2 = 2.487 mm2 SRAM macro footprint.
This does not establish routed fit. Analog area/power, frequencies and timing
remain assumptions pending the named qualification work.

## Deviations from the brief

None. User-authorized documentation scope includes correcting the contradictory
actuator draft and AGENTS core-adoption guidance. Implementation remains untouched.
Local Python/Git were used only to validate documentation; the future pinned
implementation environment has not been built.

## Open issues

- T03/T04/S2 sanitized transport handoff, dependencies and source-release rights.
- New core/reference/HardFloat pins and full-F verification setup.
- Remaining RISCay adoption, CDC, analog, physical and integration briefs.
- Macro/library/shuttle qualification, main frequency, area/power and test coverage.
- USB implementer sizing/PHY/clock/delivery evidence; approved cutoff remains.
- Actuator timeout/recovery, publication supersession/buffering and final ABI.
- Numerical supply thresholds and safe selection/calibration implementation.
- Exact pin map, board UART allocation, staffing and shuttle date.
