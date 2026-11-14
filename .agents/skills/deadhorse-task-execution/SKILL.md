---
name: "deadhorse-task-execution"
description: "Use when starting, carrying out or finishing a task brief in the Deadhorse MCU repository: reading the brief, tracking progress, running acceptance checks, writing the task report, and knowing when to stop and ask."
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
4. Check the inputs: tools, network access, repositories, environment
   variables. If one is missing, stop before doing partial work.
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
- Commit and push only when a person asks.

## When something does not match

Stop and ask when:

- a command in the brief fails and the brief's notes do not explain it;
- a measured value differs from the expected value by more than the stated
  tolerance;
- the brief conflicts with `AGENTS.md`, another brief or the plan;
- finishing would need an open decision, a file outside "May change",
  network access or credentials you were not given;
- proprietary material is about to enter the repository;
- you are about to delete something you did not create in this task.

Never do these to get past a problem:

| Temptation | Why it is wrong |
| --- | --- |
| Loosen a tolerance, deadline, budget or lint rule | The check exists to catch exactly this |
| Skip, delete or mark a test expected-fail | A hidden failure is worse than a reported one |
| Add an assumption to a formal proof | It can make any proof pass |
| Substitute an estimate for a measurement you could not take | The plan separates the two on purpose |
| Install a tool outside the pinned environment | The result will not reproduce |
| Edit a vendored file | Changes there are patches, or forbidden |
| Quietly do a nearby task instead | Nobody asked for it and nobody will review it |

A task that ends "blocked, here is exactly why" is a good outcome. A task
that ends "done" with a weakened check is a bad one.

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
4. the report is written.

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
- Anything using sbt needs Maven Central. If it is unreachable, the task is
  blocked; say so at the start, not after partial work.
- GitHub release assets and `git clone` usually work where raw-file and
  archive downloads are refused.
- Do not import proprietary material.