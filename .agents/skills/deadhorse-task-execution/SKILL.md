---
name: "deadhorse-task-execution"
description: "Use when starting, carrying out or finishing a task brief in the Deadhorse MCU repository: reading the brief, tracking progress, running acceptance checks, writing the task report, resolving routine issues with independent review, and recognizing critical approval decisions."
---

# Carrying out a Deadhorse task brief

The authority is the repository's `AGENTS.md`. Read it fully at the start of
every session; this skill adds the working method and examples. Briefs are in
`docs/plan/tasks/`, progress is in `docs/plan/STATUS.md`.

## Start

1. Read `AGENTS.md`, then `docs/plan/STATUS.md`, then your brief.
2. Read every file in the brief's "Read first" list before writing anything.
3. Check the brief's dependencies in the tracker. If one is not done, or the
   brief is marked as needing revision, stop and say so.
4. Check tools, network access, repositories and environment variables.
   Repair routine setup issues within existing authorization. Continue useful
   independent work while diagnosing unavailable inputs; never claim an unrun
   check passed.
5. Note the "May change" list. You touch nothing outside it.
6. In the tracker, set your task's line to `[~]`, put your name in Owner,
   add a Log line and update the date. Change no other line.

## While working

- Follow the steps in order. Run each command the brief gives before
  writing your own variant of it.
- Keep a scratch note of every command you ran and its result. The report is
  written from this, not from memory.
- Output goes under `build/`, scratch under `scratch/`. Neither is committed.
- Do not refactor, rename or tidy anything the brief does not mention.
- Do not edit `docs/plan/` or a brief to match what you found. Report it.
- Use existing user authorization, including standing authorization to commit
  and push after all required checks and independent agent review pass.

## Resolve routine issues without approval

The user authorizes minor fixes and verification refinements within the assigned
brief and agreed design. A failed command, test, timing check or proof timeout
is a diagnostic result, not by itself a reason to request approval.

1. Preserve the failing command, result and relevant inputs. Diagnose the cause.
2. Do quick, targeted research: check repository history and existing patterns,
   then relevant upstream examples or primary documentation when available.
   Record the useful source and why it applies. If no useful information is
   available, state that and proceed from the evidence; do not invent support.
3. Make the smallest justified fix within authorized scope. Routine tooling,
   implementation defects and proof decomposition may be repaired without
   asking again. Keep all acceptance obligations, assumptions and limits intact.
   A composed proof must discharge every premise and retain the original claim;
   an unchecked assumption or a timeout is never a passing result.
4. Run affected checks in the pinned environment. Keep unsuccessful attempts
   recorded. Avoid repeated unchanged retries and long formal sweeps; use the
   agreed runtime limits and focused diagnostics.
5. Obtain independent agent review of the fix, research applicability and
   verification evidence. Resolve findings before accepting or committing it.
   Independent review supplements required checks; it does not replace them.

## Approval is for critical decisions

Ask only when existing authorization does not cover a consequential decision:

- changing architecture, externally visible behavior, acceptance requirements,
  measurement baselines, assumptions, tolerances, deadlines or budgets;
- resolving a substantive conflict with the plan, an open decision, an unmet
  dependency that prevents safe progress, or work outside the authorized scope;
- obtaining new credentials, privileges or access to an unprovided repository;
- destructive or irreversible actions, or external actions outside existing
  authorization (ordinary public documentation research needs no new approval);
- importing prohibited or proprietary IP, or deleting pre-existing material
  without authorization;
- an impasse or material unresolved risk that requires user information or a
  decision after focused diagnosis and independent review.

Prepare a concrete, reviewable explanation before asking. Identify the exact
remaining decision and its consequence. Do not ask again for standing approvals.
A measurement outside tolerance may be repaired within the agreed design; only
changing its limit or baseline needs approval. Continue independent authorized
work while a genuinely necessary decision is pending.

Never do these to get past a problem:

| Temptation | Why it is wrong |
| --- | --- |
| Loosen a tolerance, deadline, budget or lint rule | The check exists to catch exactly this |
| Skip, delete or mark a test expected-fail | A hidden failure is worse than a reported one |
| Add an unchecked assumption or silently narrow a proof | It can hide the behavior being checked |
| Substitute an estimate for a measurement you could not take | The plan separates the two on purpose |
| Install a tool outside the pinned environment | The result will not reproduce |
| Edit a vendored file | Changes there are patches, or forbidden |
| Quietly do a nearby task instead | Nobody asked for it and nobody will review it |

Report a genuine blocker accurately. Do not turn a routine diagnostic failure
into an approval checkpoint, or call a task done with a weakened check.

## Numbers

Every figure you report carries one of three labels:

- **measured**: a tool produced it; give the command, tool version and
  commit;
- **estimated**: derived by hand from measured inputs; show the arithmetic;
- **assumed**: a placeholder; say what would replace it.

Never present an estimate as a measurement. Say "mapped, pre-layout" or
"bounded to depth N" when that is what the number is.

## Finish

A task is done only when:

1. every deliverable exists at the stated path;
2. you ran every acceptance check in this session and saw it pass;
3. `python3 tools/ci.py` passes, once it exists;
4. the report is written;
5. an independent agent reviewed the changes and evidence, and findings are resolved.

Then, in this order: write the report; set the tracker line to `[x]` and
link the report only if every check passed; add a Log line. If you stopped
early, set `[!]`, give the reason in the Report column, and still write the
report. Never tick a gate condition or a decision: a person does that.

## The report

`docs/plan/tasks/reports/<task id>.md`, with these sections in this order:

1. **Outcome**: done, blocked or failed, in one sentence.
2. **What changed**: files added or modified.
3. **Checks run**: each acceptance check, the exact command and the last
   lines of its output.
4. **Numbers**: each with its label and source.
5. **Deviations from the brief**: anything done differently, and why.
6. **Open issues**: what the next person needs to know.

Keep it factual. Do not describe effort or narrate the steps.

### A good Checks entry

```
python3 tools/check_structure.py --include-untracked
  -> exit 0
```

### Entries that are not acceptable

- "All checks pass." (which commands, what output?)
- "The block fits." (measured how, with what, at which commit?)
- "Test X was flaky so I increased the timeout." (that is a weakened check)
- "Could not reach Maven Central, so I verified the logic by inspection."
  (the task is blocked; say so)

## Environment notes that save time

- RISCay-MCU's tools need Python 3.12 with tkinter.
- Anything using sbt needs Maven Central. Diagnose routine connectivity issues
  and continue independent work if it is unreachable; report checks not run.
- GitHub release assets and `git clone` usually work where raw-file and
  archive downloads are refused.
- Do not import Coldfoot source: decision D43 removed the NoC.