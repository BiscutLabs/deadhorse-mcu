# T42 Reduce lite-image boot transfer latency

## Goal and ordering

D104, user direction 2026-11-24: accept PLAN05's measured maximum-image
boot-load latency for now and schedule this follow-up. Restore the original
250 ms target for loading and fully verifying a supported 1024-byte lite image
at nominal 32 kHz AON. Do not increase AON frequency, shrink supported memory,
skip RAM readback or weaken integrity/ownership/reset checks.

Run after PLAN05. Coordinate with T41's revised warm boot before changing shared
boot/reset code. D104 is a named latency exception, not a bridge architecture
approval, physical timing waiver or statement that the 250 ms check passed.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 10, 12-16; PLAN05/T36 reports and D104;
T41 if implemented; docs/spec/bus.md, soc.md, boot-rom-proposal.md;
hw/ip/bus_bridge and CDC contracts, production main-to-AON binding, lite
program-RAM ownership, boot copy/readback code and serial-wire fixtures.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage.

## Inputs and evidence

At main5ba87bf plus source-hashed local PLAN05 firmware, the focused diagnostic
`python scratch/t36_load_optimized.py` measured 28,503,264 simulation quanta:
estimated296.909 ms at assumed96 MHz quantum and nominal32 kHz AON. The same
production generated model was copied with only its ROM filename relocated;
this is diagnostic evidence, not final acceptance. A CRC lookup saved only
estimated0.975625 ms versus the preserved297.884625 ms baseline, adding measured
1016 ROM bytes. Final PLAN05 wire receipts supersede these diagnostics for
production acceptance. The actual588-byte watcher previously met250 ms.

## Work and permitted scope

1. Inventory request/grant/response/retirement latency per word, AON edge
   counts, bridge/admission state and memory-service latency. Separate copy,
   readback, flash and CPU work. Count every write/read; use passive observers
   and independent data oracles, not source-text tests. Reuse valid evidence;
   do not rerun unchanged failures.
2. Propose the smallest transfer-path improvement. Explain CDC, ordering,
   backpressure, reset cancellation, owner admission, duplicate handling and
   area/timing consequences. Compare with the existing registered bridge.
   Obtain independent review and explicit user approval **before hardware or
   bridge architecture changes**. Current authorization is for investigation
   and a concrete proposal; no burst endpoint or faster AON clock is implied.
3. After approval, implement only that change. Preserve performance-only
   program writes while lite is held, all copied-RAM verification and the
   current accepted boot/reset contract. Use focused block/SoC tests and
   short capped proofs; defer expensive unresolved proof work with evidence,
   unchanged assertions and the formal-timeout-triage budget.
4. Re-run actual production boot loading for watcher and maximum images,
   malformed images, reset during transfer, denied owners, and data/ordering
   negative controls. Report the original250 ms outcome explicitly. Remove
   the D104 exception only after its original check passes without a bypass.
5. Measure changed block/whole-SoC area and affected-domain timing using the
   same GF180 budgets; report latency, flop/area changes and remaining debt.

## Acceptance and publication (unverified)

An independently reviewed proposal, scoped test/proof manifest and measured
baseline precede implementation. Record exact commands/revisions and time in
reports/T42.md. Production boot pin tests must retain all integrity/ownership
assertions and original latency target. At least wrong-data, duplicate/dropped
transfer and stale-response-after-reset controls must be caught. Run affected
map/structure checks and independent final review. Relevant tests only during
iterations; inherited PLAN05 phase-end checks are not waived by this brief.
Before execution, state the publication-check policy applicable to the approved
implementation; no aggregate CI is run merely to add this task.

## Stop conditions

Ask before architecture/behavior changes not covered by the reviewed proposal,
changed clocks, capacity, integrity checks, limits, USB behavior, or additional
reset cohorts. Stop on negative area headroom or main8 MHz timing failure.
Do not claim the latency target closed from an estimate or altered fixture.
