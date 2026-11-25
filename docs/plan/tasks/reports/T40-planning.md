# T40 planning receipt

## Outcome

Done: T40 is scheduled after PLAN05 design changes; DMA implementation and
its acceptance checks remain unstarted.

## What changed

- T40-dma-circular-uart-rx.md: UART-RX-only contract, confirmed baseline
  selectors/free register fields, driver, scoped tests/proofs, area cap and
  stop conditions.
- Decision D102, task index and STATUS registration. D92-D101 were reserved
  for concurrent PLAN05 work during isolated planning, then reconciled without
  changing those decisions when the planning records were merged.
- Plan08: explicit T40 reservation alongside the historical T35 budget.

## Checks run

- `python tools/env/run.py run -- python tools/check_structure.py scratch/t40-uart-circular-plan --include-untracked`: failed with `ROOT_FILES .git: unexpected root file`; the container could not resolve the Windows worktree gitdir and fell back to filesystem inventory. No project source/check was changed.
- `python tools/env/run.py run -- env GIT_DIR=/work/.git/worktrees/t40-uart-circular-plan GIT_COMMON_DIR=/work/.git GIT_WORK_TREE=/work/scratch/t40-uart-circular-plan python tools/check_structure.py scratch/t40-uart-circular-plan --include-untracked`: PASS, exit 0, no diagnostics; measured wall time 8.486 s. Explicit container paths restore the actual worktree inventory. This includes local Markdown links and repository layout.
- `git -c core.safecrlf=false diff --check` in the planning worktree: PASS, exit 0, no diagnostics.
- Independent agent review (`t40_plan_review`): no substantive omission; corrected the extra-storage stop wording and clarified that execution is scheduled after PLAN05. Reviewed endpoint/field evidence, numeric provenance, area arithmetic and scope.
- `git status --short` and `git branch --show-current` in main: PLAN05 remains uncommitted on main; T40 edits are confined to the separate worktree. No PLAN05 files were edited or included by this planning operation.
- Merge reconciliation: `python tools/env/run.py run -- python tools/check_structure.py --include-untracked` and `git -c core.safecrlf=false diff --check` pass; independent review preserves the entire T40 contract and verifies the current reservation arithmetic.
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

The planning merge updates the reservation to accepted PLAN05 Phase2 evidence:
`python hw/top/reference/measurements/t35_budget.py --base
build/plan05/timing03`, source-hashed measurement at base `29cab7e` and
published implementation `f96ad0d`. Estimated total including the T40 cap is
12.020820470908 + 0.010 / 0.55 = 12.039002289090 mm2; estimated provisional
headroom is 0.880997710910 mm2. Additional T40 scan remains excluded and must
be measured before final fit. No Phase3 ROM savings are credited.

## Deviations from the brief

This is the requested scheduling/documentation step, not execution of T40.
It was prepared separately on `codex/t40-uart-circular-plan` while PLAN05
was open on main. After reviewed Phase2 publication through `f96ad0d`, only
these planning records were merged; no DMA implementation was included.

## Open issues

All T40 implementation, scoped tests/proofs and fresh area/timing measurements
remain to run after PLAN05's design migration. The planning merge preserves
D92-D101 and the open Phase3 status of PLAN05.
No chip-fit, stage exit or inherited proof closure is claimed.
