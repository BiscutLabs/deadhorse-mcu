# T41 Consolidate the reset architecture

## Goal and ordering

D103, user direction 2026-11-24: reduce the production reset architecture to
cold, warm, debug and unchanged USB-transport cohorts. The performance watchdog
joins warm reset. Preserve the single active-low reset pad, on-die POR/brownout
and static POR_BYPASS selection. This brief queues work after PLAN05; it does
not authorize starting reset RTL while PLAN05 is unfinished.

Use a separate `codex/` branch. Rebase the planning branch onto the completed
PLAN05 production implementation before inventory or RTL work; do not mix
uncommitted PLAN05 changes into this task. Reconcile with T40 if DMA changes
have landed. The current ten-row specification is an inventory starting point,
not a measured count of reset trees or flops.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 07, 10, 12-16; PLAN05 and T19/T32-T36
reports and outstanding debt; docs/spec/soc-power-reset.md, soc.md, bus.md,
boot-rom-proposal.md; production soc.yaml; shared ResetRelease/CDC primitives;
oscillator controller, reset controller, watchdog, boot-control and debug
contracts, RTL, formal harnesses and affected integration tests. Read D37,
D70, D76-D87, D91-D103 and their amendment table in plan10.

Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, formal-timeout-triage,
gf180-synth-timing-check; regmap-authoring only for necessary reviewed map work.

## May change

Production reset/power/clock/watchdog/boot/debug bindings; shared reset wiring
and necessary controller state; ROM warm restart and reset-cause handoff;
affected tests, formal jobs, CDC/RDC inventory, generated-map descriptions if
needed, measurements and task documentation. No peripheral feature work, USB
reset-behavior changes, analog macro-interface changes or new reset cohorts.
Do not commit generated output. Do not clear SRAM contents with reset logic.

## Work, in order

### 1. Inventory and commit before RTL

Produce `docs/spec/reset-consolidation-inventory.md`, bound to the production
source revision and emitted hierarchy. Enumerate every reset source, cohort,
ResetRelease instance and reset net, including nested block/CDC wrappers.
For each give sources, domain(s), consumers, reset-related flop count,
dependent proofs/tests, reason for existence and proposed disposition. Record
both unique instances/nets and unique affected flop counts without double
counting overlapping source cones. State exactly what main-service and
AON-service qualification mean, their predicates, when they fire, and any
documented behavior depending on them. Separate evidence from assumptions.

Review the inventory independently, then commit it before any RTL change.
Audit all decisions touched, explicitly amending any additional decision found;
do not silently contradict the retained plan. If qualification needs a source
outside the four cohorts, stop with the concrete dependency.

### 2. Implement the four cohorts

| Cohort | Assert sources | Reset scope |
| --- | --- | --- |
| Cold | POR/brownout in normal mode; external pin instead when POR_BYPASS is selected | Everything, including causes and debug; RAM contents are not reset-cleared |
| Warm | Normal-mode pin, lite watchdog, performance watchdog, software reset if already implemented, debug ndmreset | Main/AON/core/PWM/DMA/peripheral logic, except causes, debug and explicitly documented warm survivors |
| Debug | Cold only | Debug module and JTAG/DMI transport |
| USB transport | Existing T19 sources and behavior | Unchanged |

Each cohort has one source signal, asynchronous assertion and exactly one
ResetRelease per reached domain (AON, main, OSC_IN/USB, TCK as applicable).
Do not retain cascaded or redundant reset-release trees. Document cold's
assertion of warm-controlled logic without inventing another cohort.

Merge main-service and AON-service into warm. Remove performance-client reset:
performance watchdog records its cause and asserts warm; PWM outputs disable
immediately on assertion, without waiting for a stopped main clock. SRAM and
lite program RAM contents survive warm. Reset/watchdog causes, brownout record
and debug state survive warm and initialize only on cold. Preserve every other
documented warm survivor unless the user explicitly decides otherwise.

Oscillator-policy and source-qualification epochs are state, cleared on cold
and warm, not independent reset cohorts. OSC_EN low still requires fresh
qualification. For a stopped domain needing clear on restart, write the reason
and prefer its existing per-domain warm ResetRelease. Do not remove clock
qualification merely to remove a tree. No analog POR interface change.

### 3. Revise warm boot, preserving fast restart

Replace PLAN05 C4's performance-only reset path. On every warm reset, ROM
checks the existing performance **and lite** images against the selected
bundle CRCs. If both match, skip flash copies; otherwise reload from flash.
Lite remains held until its image is confirmed. Keep bundle integrity, bounds,
compatibility, commit-last updates, memory authority and recovery protections.
Report the reset cause to the application: cold, pin, lite watchdog,
performance watchdog, software (if present), or debug.

Remove obsolete surviving-watcher/performance-client recovery machinery only
after replacement tests pass. Define the retained selected-bundle metadata and
application cause ABI explicitly in the boot specification before changing ROM.
Do not invent a new bundle-selection policy. Dormant wake without reset still
resumes after WFI; reset during dormant follows warm/cold boot as applicable.

### 4. Scoped verification

No aggregate fast/full CI; run reset, power/clock, watchdog, boot ROM,
sleep/wake, debug and affected production integration checks only. List every
test changed because a cohort was removed, its old obligation and replacement.
Do not weaken any assertion that still applies.

Required cases (all unverified):

- Cold initializes all resettable state, causes and debug; each warm source
  resets its intended consumers and preserves causes, debug, SRAM and lite RAM.
- Performance-watchdog expiry causes warm reset, correct cause capture and
  immediate PWM disable. Check running-clock expiry and an already pending
  reset at clock stop (or a test-injected source). Do not make the watchdog
  count or fire during dormant: the D100 freeze contract remains unchanged.
- Reset during deep sleep, oscillator startup and an active DMA transfer
  recovers cleanly; every domain releases only after its clock is qualified.
- Warm ROM exercises both-image CRC-valid no-copy path and reload on corruption
  of either image; lite stays held until confirmation, cause reaches the app.
- A live debug session survives ndmreset. Both POR_BYPASS settings preserve the
  approved cold/warm source distinction and unchanged analog interface.
- Negative controls caught by a test or proof: warm clears a cause bit; a domain
  releases before qualification; performance watchdog leaves PWM enabled; ROM
  skips reload with a corrupted image.

Rerun existing reset-cause and ResetRelease proofs. Re-scope deferred T33
shutdown/startup claims, stating exactly which obligations disappear and which
remain. Use formal-timeout-triage with existing caps, no unchanged timeout
reruns, no weaker assumptions/assertions. Defer expensive unresolved proofs
with evidence; bounded is not proved. Update soc-power-reset.md's actual
cohort and CDC/RDC inventory only when it describes the implementation.

### 5. Measure and report

Before/after table: cohorts, ResetRelease instances, reset nets, unique
reset-related flops, mapped power/reset-controller area. Counts should decrease;
explain any growth rather than hiding it. State exact counting boundary and
derive both measurements with the same scripts and synthesis settings. Run
affected domain timing if reset/clock logic changes timing paths, preserving
existing budgets. Every figure is measured with command/revision or explicitly
estimated/assumed. No physical reset or analog signoff is implied.

Write reports/T41.md: inventory, amendments, removed/retained structures and
reasons, scoped test/proof results and measured command times, remaining debt.
Independent review of inventory, reset/boot changes and final evidence is
required before acceptance and logical commits/push. STATUS is the tracker.

## Acceptance commands (unverified until execution)

At inventory, record the exact pinned emission/count/synthesis commands and
the existing reset-cause/ResetRelease proof entrypoints. Before RTL, publish a
scoped manifest of existing affected tests plus the required cases above; run
that frozen manifest at completion. Missing entrypoints must be implemented,
not silently omitted. Also run in the pinned environment:

```text
python hw/top/reference/check_soc_map.py
python tools/check_structure.py --include-untracked
git diff --check
```

These structural checks supplement the scoped behavioral/formal/measurement
manifest. They do not replace it. No brief checkbox or stage gate is completed
by adding this task.

## Stop conditions

Ask before retaining any cohort beyond the four above, changing USB reset
behavior, changing cold/warm retention beyond this prompt, or modifying the
analog POR/brownout macro interface. A documented need for separate service
qualification must be reported rather than kept by default. Preserve all
other limits and outstanding proof/physical obligations.
