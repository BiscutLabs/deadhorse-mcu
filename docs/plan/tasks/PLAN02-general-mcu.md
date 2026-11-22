# PLAN02 General-purpose MCU scope reconciliation

## Goal

Record the user's 2026-11-21 direction: Deadhorse is not constrained to drones;
use conventional MCU capabilities rather than a specialized flight-actuator
controller. Documentation only; no CI and no RTL/register-map changes.

## Read first

AGENTS.md, plan README/STATUS/task index and skills15; product definition,
requirements, architecture, power/reset, peripheral and integration plans;
actuator draft; T21 report. Apply deadhorse-task-execution.

## May change

Affected documentation in docs/plan and docs/spec, root README, this brief and
report. Scratch validation under scratch. Preserve unrelated local T20/T21 work.

## Deliverables and checks

- Record D69 and reconcile the current hardware/application boundary.
- Mark the old actuator hardware draft superseded, preserving history.
- Identify existing application-specific RTL needing a later scoped change;
  do not silently alter an implemented ABI or claim that change is complete.
- Check changed-file scope, local Markdown links and decision uniqueness;
  run git diff --check and obtain independent review.
- Preserve numerical baselines, actual tests/proofs, open physical items and
  the no-CI instruction. No implementation or physical gate is closed here.
