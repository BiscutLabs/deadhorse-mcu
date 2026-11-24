# T40 planning receipt

## Outcome

Done: T40 is scheduled after PLAN05 design changes; DMA implementation and
its acceptance checks remain unstarted.

## What changed

- T40-dma-circular-uart-rx.md: UART-RX-only contract, confirmed baseline
  selectors/free register fields, driver, scoped tests/proofs, area cap and
  stop conditions.
- Decision D102, task index and STATUS registration. D92-D101 are reserved
  by concurrent PLAN05 work; this branch does not duplicate or change it.
- Plan08: explicit T40 reservation alongside the historical T35 budget.

## Checks run

- `python tools/env/run.py run -- python tools/check_structure.py scratch/t40-uart-circular-plan --include-untracked`: failed with `ROOT_FILES .git: unexpected root file`; the container could not resolve the Windows worktree gitdir and fell back to filesystem inventory. No project source/check was changed.
- `python tools/env/run.py run -- env GIT_DIR=/work/.git/worktrees/t40-uart-circular-plan GIT_COMMON_DIR=/work/.git GIT_WORK_TREE=/work/scratch/t40-uart-circular-plan python tools/check_structure.py scratch/t40-uart-circular-plan --include-untracked`: PASS, exit 0, no diagnostics; measured wall time 8.486 s. Explicit container paths restore the actual worktree inventory. This includes local Markdown links and repository layout.
- `git -c core.safecrlf=false diff --check` in the planning worktree: PASS, exit 0, no diagnostics.
- Independent agent review (`t40_plan_review`): no substantive omission; corrected the extra-storage stop wording and clarified that execution is scheduled after PLAN05. Reviewed endpoint/field evidence, numeric provenance, area arithmetic and scope.
- `git status --short` and `git branch --show-current` in main: PLAN05 remains uncommitted on main; T40 edits are confined to the separate worktree. No PLAN05 files were edited or included by this planning operation.
No RTL simulation, synthesis, formal job or aggregate CI is required or
claimed for adding this brief. Implementation checks remain unverified.

## Numbers

Baseline commit: `29cab7e500488d18fd9699f03fa34db70edac67f`.
T23's historical measured DMA area is 0.159020288 mm2, from
`python hw/ip/dma/check_timing.py --output build/t23/timing-first` on
`72bcfac` plus receipt-hashed local sources (T23 report); not rerun here.

Assumed planning reservation: the approved 0.010 mm2 maximum mapped-cell
increase. Estimated placed allowance at existing assumed 0.55 utilization:
0.010 / 0.55 = 0.018181818 mm2. Added to the historical T35 estimate of
12.699799240 mm2 gives 12.717981058 mm2, with estimated provisional headroom
12.92 - 12.717981058 = 0.202018942 mm2. Additional scan substitution is
unmeasured and excluded from that provisional subtotal; final T40 accounting
must include it and rebase on PLAN05 measurements.

## Deviations from the brief

This is the requested scheduling/documentation step, not execution of T40.
It is isolated on `codex/t40-uart-circular-plan` while PLAN05 remains open on
main. No PLAN05 changes are included and this branch is not merged now.

## Open issues

All T40 implementation, scoped tests/proofs and fresh area/timing measurements
remain to run after PLAN05's design migration. Reconcile the planning records
with PLAN05 when integrating this branch, preserving D92-D101 and its status.
No chip-fit, stage exit or inherited proof closure is claimed.
