# T41 reset-consolidation planning receipt

## Outcome

Done: the requested reset-consolidation task is queued separately;
implementation, inventory measurements and all behavioral acceptance are unrun.

## What changed

- T41 brief: inventory-first commit, four cohorts, both watchdogs warm,
  retained causes/debug/RAM, warm CRC fast restart, scoped checks and stops.
- D103 and explicit amendments to D37/D70/D79/D83-D87/D92/D100, plus retained
  D38/D78/debug/USB and task-specific CI boundaries. STATUS and task index.
- Pending-target annotations in power/reset and boot specifications and
  PLAN05/T33/T36 briefs distinguish future T41 from the existing implementation.

## Checks run

- `python tools/env/run.py run -- env GIT_DIR=/work/.git/worktrees/t41-reset-consolidation-plan GIT_COMMON_DIR=/work/.git GIT_WORK_TREE=/work/scratch/t41-reset-consolidation-plan python tools/check_structure.py scratch/t41-reset-consolidation-plan --include-untracked`: PASS, exit0, no diagnostics; checks repository layout and local Markdown links. Explicit container git paths resolve the Windows worktree metadata.
- `git -c core.safecrlf=false diff --check` in the planning worktree: PASS,
  exit0, no diagnostics.
- Independent agent `t40_plan_review`: PASS for planning-only publication;
  all ten documents reviewed, stopped-clock watchdog wording clarified,
  no lost USB/analog boundary or implied implementation acceptance.
- Host command wall times were not retained as an end-to-end receipt; no timing
  measurement is claimed for these documentation checks.

The same structure/link and whitespace commands pass after the rebase;
independent review checks the resolved documents against completed main.
No RTL, simulation, formal, synthesis or aggregate CI was run to add the task.

## Numbers

Planning branch `codex/t41-reset-consolidation-plan` is based on
main`6572ecf`, the completed PLAN05/T36 publication. Original planning
commit1b92572 was based on5ba87bf; the rebase preserves D104/T42 and all
Phase3 evidence without changing any non-Markdown file. The specification
currently lists ten cohort rows; this is a documentation count, not a measured
tree/net/flop count. Four target cohorts are the user's requirement. Physical
area and savings are unmeasured; no estimated savings are credited.

## Deviations from the brief

This is task creation only. The separate branch is rebased onto completed
PLAN05 main6572ecf before any inventory or implementation. Three documentation
conflicts were reconciled by retaining both decisions/tasks and the final
PLAN05 results. No production RTL, test or firmware differs from main.

## Open issues

T41 is not started. Commit the independently reviewed production inventory
before RTL. Preserve dormant watchdog freeze; stopped-clock reset testing must
use an already pending reset or a test-injected source. Define retained bundle
metadata validation, failure behavior and cause ABI before warm-ROM changes.
USB transport, analog interface and undocumented retention changes require a
new user decision. Inherited proofs/physical qualification remain open.
