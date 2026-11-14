# PLAN01 Reconcile approved MCU decisions

## Goal

Record the user's approved planning decisions throughout the plan and task
briefs without starting implementation. The user explicitly assigned this
documentation task and authorized committing and pushing its result.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../README.md](../README.md), [../STATUS.md](../STATUS.md), and the task index
- All plan documents, task briefs, and affected specifications
- The planning conversation, which is the authority for these decisions

## May change

`docs/plan/`, affected `docs/spec/` documents, root `README.md` and `AGENTS.md`.
Scratch validation scripts may live under ignored `scratch/`. No RTL, firmware,
build tools, dependencies, vendor imports, or implementation work.

## Deliverables

An approved decision register; consistent architecture, requirements, roadmap,
and briefs; explicit remaining evidence and external dependencies; updated
status with no implementation task marked complete; this task's report.
Update the actuator draft because its global frame and reset semantics conflict
with the approved decisions. Do not silently finalize unapproved register details.

## Acceptance checks

- `git diff --check`: no whitespace errors.
- `python scratch/check_plan.py`: local Markdown links and decision IDs resolve;
  review stale-decision search results manually. This documentation-only checker
  is created for this task and is not an RTL test or part of implementation.
- `git diff --name-only`: every change is in the allowed documentation scope.
- Inspect the decision register against every approval in the conversation.
- `python3 tools/ci.py` only if it exists; otherwise report that T01 has not
  created it. Do not create or run implementation tooling for this task.

## Out of scope

Implementation, hardware qualification, purchasing, selecting unapproved parts,
changing historical measurement artifacts, or claiming gates have passed.
