# Instructions for agents working in deadhorse-mcu

Deadhorse is the production rebuild of RISCay-MCU: an entirely clocked, two-core
RISC-V microcontroller on GF180MCU, first used as a VTOL flight controller.
Read this file fully before doing anything.

## Where to start

1. [docs/plan/README.md](docs/plan/README.md): what is being built and why.
2. [docs/plan/STATUS.md](docs/plan/STATUS.md): what is done and what is
   open. Then [docs/plan/tasks/README.md](docs/plan/tasks/README.md): the
   task list.
   **Work only on a task brief assigned to you.** Do not start work that has
   no brief.
3. The brief's "Read first" list. Read those files before writing anything.
4. [docs/plan/15-skills.md](docs/plan/15-skills.md): load the skills it
   lists for your task from `.agents/skills/` before you start.

## Standing rules

1. **Adopt before building.** Do not write new RTL where a brief names an
   existing block to adopt. D2/D19/D20 explicitly require the performance core
   to be reimplemented in Chisel with a multicycle FPU and selective HardFloat
   reuse; do not substitute a vendored SystemVerilog core or reopen a core bakeoff.

   **New RTL is Chisel, and it is clocked.** The only exception is a later,
   explicitly briefed Click version of the lite core (decision D18).
   Otherwise do not use chisel-async, and
   do not add handshake controllers, matched delays, latches used as
   storage, or any other clockless structure (decision D17). Every signal
   that crosses a clock domain goes through the one crossing block. Do not write SystemVerilog or
   Verilog source. SystemVerilog exists only under `hw/vendor/`, unmodified,
   and is used through a Chisel `BlackBox`. Emitted SystemVerilog is build
   output under `build/`.
1b. **New blocks ship with formal properties.** Follow
   [docs/plan/12-formal-verification.md](docs/plan/12-formal-verification.md):
   properties beside the RTL, a negative control per proof, every
   assumption listed, and a bounded result never reported as a proof.
1c. **Tests follow [docs/plan/13-test-environment.md](docs/plan/13-test-environment.md).**
   Check behaviour against an independent reference model. Never write a
   test that reads or matches RTL source text. Use only tools from the
   pinned environment, and no paths outside the repository.
1d. **Follow [docs/plan/14-timing-design-rules.md](docs/plan/14-timing-design-rules.md).**
   Register block outputs, break ready/valid chains, keep heavy operations
   multi-cycle. FPGA timing passing says nothing about GF180.
2. **Every number has a provenance.** Mark each figure you report as
   *measured* (name the command and commit), *estimated* (show the
   arithmetic) or *assumed*. Never present an estimate as a measurement.
3. **Run it before you claim it.** A check passes only if you ran the command
   in this session and saw it pass. Say so explicitly when you could not run
   something, and why.
4. **Never weaken a check to make it pass.** Do not relax an assertion, a
   deadline, a tolerance, an area ceiling or a lint rule. Do not skip, mark
   expected-fail or delete a failing test. Report the failure.
5. **Nothing generated is committed.** Output goes under `build/`. Scratch
   goes under `scratch/`. Both are ignored.
6. **Vendored code is not edited in place.** `hw/vendor/*` changes only
   through its lock file and `patches/`. Do not import proprietary IP.
7. **The plan changes only by decision.** If your work shows the plan is
   wrong, do not edit `docs/plan/` to match. Report it (see below).
8. **Stay inside the brief.** Do not refactor, rename or tidy anything the
   brief does not mention.
9. **Follow [docs/plan/11-repository-structure.md](docs/plan/11-repository-structure.md)**
   for where files go.
10. **Commit and push after independent verification.** The user has given
    standing authorization to commit and push completed work once an independent
    agent has verified it and all required checks pass. Resolve review findings
    before committing. Keep unrelated user changes in separate commits; do not
    include them without authorization. Leave work uncommitted until verified.

There is no asynchronous circuit work in this project. If a brief seems to
ask for some, stop and ask.

## Stop and ask

Stop, write down what you found, and wait for a person when any of these
happens. Do not work around them.

User authorization: fix routine tooling issues and resume without asking,
including checkout line endings and tool invocation problems. Keep every
required check and tolerance intact, obtain independent agent review, then
commit and push. This does not authorize changed measurement baselines,
architecture decisions, or expanded proprietary-IP imports.

- A command in the brief fails and the brief's own notes do not explain it,
  unless the cause is a routine tooling issue covered by the authorization above.
- A measured result differs from the brief's expected value by more than the
  stated tolerance.
- The brief conflicts with this file, with another brief, or with the plan.
- Completing the task would need a decision listed as open in
  [docs/plan/10-decisions-and-risks.md](docs/plan/10-decisions-and-risks.md).
- You would need to touch a file outside the brief's "May change" list.
- You need network access, credentials or a repository you were not given.
- You find proprietary material about to enter this repository.
- You are about to delete anything you did not create in this task.

## Done means

A task is done only when all of these hold (documentation-only PLAN01 has
its own acceptance checks and does not start implementation):

1. Every deliverable in the brief exists at the stated path.
2. Every acceptance check in the brief was run by you and passed. Paste the
   command and the last lines of its output into your report.
3. `python3 tools/ci.py` passes, once task T01 has created it.
4. You wrote the task report.

## Tracking progress

[docs/plan/STATUS.md](docs/plan/STATUS.md) is the only progress tracker.

- When you start a task, set its line to `[~]`, put your name in Owner, and
  add a line to the Log.
- When you finish, write the task report first. Then set the line to `[x]`
  only if every acceptance check passed, link the report, and add a Log line.
- If you stop without finishing, set `[!]`, say why in the Report column,
  and add a Log line.
- Change only your own task's line and the Log during implementation. A
  person-assigned planning reconciliation may update the decision/task register.
  Do not tick gate conditions. Record decisions only from explicit approval;
  approval does not mark implementation or a gate complete.
- Never tick boxes inside a brief, and never edit a brief to record progress.
- Update the "Last updated" date.

## Task report

Write `docs/plan/tasks/reports/<task id>.md` with these sections, in this
order: **Outcome** (done, blocked, or failed, in one sentence), **What
changed** (files), **Checks run** (command and result for each acceptance
check), **Numbers** (each with its provenance), **Deviations from the
brief**, **Open issues**. Keep it factual. Do not describe effort.

## Environment notes

Learned while preparing the briefs; they save time.

- RISCay-MCU's tools need **Python 3.12 with tkinter** (`python3-tk`).
- RISCay's Scala suites need **Maven Central**. If it is unreachable, the
  Python gate still runs; the Scala gate cannot.
- GitHub release assets and `git clone` usually work where raw file and
  archive downloads do not.
