# T39 Focused core and SoC regression

## Goal, inputs and readiness

Run a finite regression of the existing cores and their current integration
on main before further physical work. D89 (user direction 2026-11-24) narrows
the original D88 qualification campaign substantially: use existing tests and
reference models, with no new ISA framework, observer, peripheral or proof
campaigns/retries of deferred proofs. Fast CI retains its existing formal jobs.
The original broad brief remains in git at `fa21f70`.
All acceptance checkboxes below are **unverified**; execution results belong
only in the report and STATUS.

A pass means these scoped regressions pass. It does not establish complete
ISA compliance, independent two-hart instruction-reference equivalence,
formal closure, integration-stage exit or tape-out readiness. T35/T36/T37 must
replay affected checks after memory, boot or scan changes; T38 consumes current
evidence with its limitations, not an obsolete or broader qualification claim.

## Read first

AGENTS.md; plan README, STATUS, decisions D76/D88/D89, plans 12–16;
docs/spec/soc.md and bus.md; core/FPU/lite and T32–T34 reports and ledgers;
dv/core/README.md and ADAPTATIONS.md; hw/ip/lite_core/README.md;
tools/env/lock.json and existing CI definitions.
Skills: deadhorse-task-execution and reference-model-testing;
formal-timeout-triage only if an existing check fails or a defect needs proof.
RTL fixes additionally require the relevant Chisel/formal/timing skills.

## Deliverables

1. `docs/spec/core-qualification.md`: exact finite scope, existing oracle and
   fixture limitations, and deferred broader qualification.
2. Fresh logs, receipts, exact Scala case lists and workload results under
   `build/t39/`, bound to the revision, working sources and pinned environment.
3. `docs/plan/tasks/reports/T39.md`, own STATUS entry and scoped evidence-ledger
   updates. Preserve all inherited deferrals and failed/partial attempts.

No new persistent campaign runner or test-framework integration is required.
The proposed new command interfaces in the original brief are deferred, not
implemented or claimed to have passed.

## Required finite campaign

Use the pinned environment. Freeze production RTL, test/tool source and
firmware source; retain hashes. Do not change assertions, faults, seeds,
memory capacity, interfaces or existing deadlines. List all selected cases
and every failure; no post-result selection or silent expected-fail.

| Group | Required existing command/scope | Scope limit |
| --- | --- | --- |
| Fast CI | `python tools/ci.py --tier fast --output <fresh> --usb-evidence <fresh-production-binding-manifest>` | Keep all original checks and inherited deferrals; no full ISA sweep |
| Lite | `python tools/sbt.py "hw/testOnly deadhorse.lite_core.LiteBaselineSpec deadhorse.lite_core.LiteHartSpec deadhorse.lite_core.LiteMachineSpec deadhorse.lite_core.LiteDebugSpec"` | Existing model and fault controls; IRQ test follows DUT interrupt boundary, so no independent IRQ-equivalence claim |
| Loader/boot diagnostics | `python tools/sbt.py "hw/testOnly deadhorse.top.SocLiteSpec deadhorse.top.SocBootReleaseSpec"` | Existing USB-stub/peripheral-test and external-clock configurations, explicitly diagnostic |
| Production clocks/reset | `python tools/sbt.py "hw/testOnly deadhorse.top.SocClockResetSpec"` | Actual production clock/reset top with digital analog models; no analog signoff |
| Debug | `python dv/soc/debug/check.py --output <fresh>` | Existing positive scenarios and missing-halt fault; production digital/TAP assembly with independently driven test clocks |
| Faithful performance core | `python dv/core/lockstep.py --candidate <fresh-faithful-floating> --isa rv32imfc --suite arch,flight-float --output <fresh>` | Existing pinned RV32UI/UM/UC and F/flight checks; standalone default debug addresses differ from production; retain fast-tier random smoke |
| Production flight after wake | `python hw/top/reference/measurements/plan04_flight.py --prepared <fresh-prepared> --output <fresh>` | Fresh fixed/hard-float execution before/after oscillator-off UART wake; hash-authenticated historical target-QEMU checksums, not fresh whole-program ISS lockstep |

Prepare existing inputs with `python dv/soc/prepare_production.py` and
`python hw/top/reference/measurements/plan03_production_benchmark04.py <fresh-prepared>`.
Retain map validation, lite provenance checks and existing fixture faults.
Scala commands may be grouped without changing the selected suites. Archive
fresh XML case lists; require nonempty expected suites with no failed,
skipped or aborted cases. Existing simulation/command bounds remain unchanged.
The standalone candidate may be emitted separately with the existing
`EmitLeaves`, `EmitCore`, `EmitFaithfulFloatCore` and `package_candidate.py --float`
flow used by fast CI, allowing those unchanged suites to run concurrently.

Report measured before/after-wake mean/worst cycles, commands and source
hashes. Keep D75's recorded exception and existing test limits. A fresh
checksum result does not establish full architectural-state equivalence.

## Deferred from the original campaign

- New `riscv-arch-test`/RISCV-DV/tool integration and full source-case accounting.
- New external RV32E ISS, independently aligned IRQ events and full CSR/FP
  state observation; the existing tests retain their documented limitations.
- The planned seeds 0–31 with 1024 non-padding retirements per hart/level.
- New production two-hart integrated ISS lockstep and exhaustive
  opcode/operand/CSR/trap/interrupt/reset/contention coverage matrix.
- Expanded temporary-RTL/common-mode trace fault campaign and coverage audit.
- All inherited unbounded proofs; simulation never discharges them.

These are explicit remaining verification gaps, not waived claims or evidence
that all executions work. Research clones and diagnostic size probes are not
qualification inputs. No new tools or production memory changes are authorized
to resolve the oversized architectural-suite cases in this scoped task.

## Acceptance and publication (unverified)

- [ ] Every required finite command passes on freshly emitted/compiled inputs;
      original faults are rejected for their intended reasons.
- [ ] Receipts authenticate sources, environment, case lists and workload
      checks; failed/partial attempts remain visible.
- [ ] Fast CI passes with its inherited deferrals on the frozen RTL/test/tool/
      firmware snapshot. D89 scopes publication to documentation afterward,
      checked separately for structure/links, diff hygiene and independent
      review. Any code/test/tool/firmware change requires refreshed affected
      evidence and final fast CI. No functional CI check is waived.
- [ ] Full-tier status is explicit. No integration-stage exit is claimed, so
      this finite campaign does not itself require full CI.
- [ ] Independent review accepts scope, fixture/oracle limitations, evidence,
      any fixes and final code identity; documentation checks pass.
- [ ] Report and STATUS accurately distinguish this scoped pass from deferred
      broader qualification; commit and push completed reviewed work to main.

## May change and stop conditions

Only scoped documentation/evidence tracking is expected. A reproduced defect
may receive the smallest authorized fix with a permanent regression, independent
review and affected equivalence/formal/GF180 checks at unchanged limits.
Stop for architecture/ISA/ownership/reset changes, changed acceptance limits,
unavailable required references or a failure not repairable within scope.
Do not add new peripheral RTL, extend old proof waivers or retry unchanged
timed-out jobs. No acceptance command or assertion may be silently removed.
