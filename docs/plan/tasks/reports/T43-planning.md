# T43 planning receipt

## Outcome

Done: queued the official wafer.space physical-base task before T38;
implementation, PDK migration and physical acceptance remain unrun.

## What changed

D105 supersedes D9's physical source, records the narrow mixed-SV chip-top
exception and scoped no-aggregate verification policy. T43 carries all requested
pinning, comparison, measurement, pad-map, smoke and stop requirements. T38,
STATUS and the task index gain the dependency. Plans01/02/08/09/10/11 and the
plan README replace obsolete physical imports/provenance with the official
template; historical measured area/timing receipts retain their original scope.

## Checks run

Planning baseline main6572ecf. Read-only `git ls-remote
https://github.com/wafer-space/gf180mcu-project-template.git refs/heads/main`
returned d99f6e1ba14e549e80d5d83e113fbd82ed37ed5c in this session. This is a
planning observation, not the execution pin: T43 must recheck at execution.

Repository `rg -n -i coldfoot` and inspection of tracked physical files and
`git log --oneline -- phys/gf180-ws-1x1` found no Coldfoot-derived physical
file. The complete tracked physical subtree contains block-timing.json,
README.md and sram.md only; history records scaffold, project timing gate
and T35 handoff. No chip top, pad ring, slot or flow files exist there.
The timing configuration identifies the existing RISCay/T06 PDK provenance;
the SRAM handoff points to the separately locked public SRAM vendor. No
Coldfoot repository was opened or copied. This is a tracked-file/history and
provenance audit, not a claim to detect an unattributed copy by text search alone.

`python tools/env/run.py run -- env GIT_DIR=/work/.git/worktrees/t43-wafer-space-plan
GIT_COMMON_DIR=/work/.git GIT_WORK_TREE=/work/scratch/t43-wafer-space-plan
python tools/check_structure.py scratch/t43-wafer-space-plan --include-untracked`
passes (exit 0, no diagnostics); final host command wall time measured 9.300417s.
`git -c core.safecrlf=false diff --check` in that worktree passes (exit 0).
Independent agent review accepts the complete user scope, SRAM conflict and
planning-only publication; SV-rule, table and flow-stop wording findings fixed.
No RTL/functional/formal/PDK/physical run or
aggregate CI is claimed by this documentation-only task addition.

## Numbers

T43/D105 are the next free task/decision identifiers after T42/D104. The user
provides the target 3932 by 5122 um die, 12.92 mm2 core and 40/12/2 signal-pad
capacities; these are requirements to verify against the execution-pinned slot,
not new measured fit. Expected PDK792ef67 and upstream revisions are not yet
qualified; no new-PDK area, timing or pad result exists.

## Deviations from the brief

Planning only. The requested twenty1024x8 macro configuration conflicts with
completed PLAN05's sixteen1024x8 plus four512x8 production instances. The brief
records this as a pre-implementation clarification, preserving current RAM
capacity and views. PWM measurements target PLAN05's merged timer block.
Old-PDK historical receipts must keep accurate provenance; active pins migrate
only during execution. No SRAM, pad-library or PDK choice is silently made.

## Open issues

Execute T43 on its own branch before T38, after the assigned T41/T40/T42 work.
Obtain the required pad-library approval and reconcile macro configuration;
retain all supplied stop conditions. Pin/fetch/diff/measurement/smoke work is
unstarted. T38 retains global placement, full P&R and physical signoff.
