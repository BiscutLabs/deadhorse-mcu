# T39 brief preparation

## Outcome

Done: the T39 brief and plan integration passed documentation checks and
independent review; T39 implementation and campaign acceptance remain unrun.

## What changed

- Added `T39-core-soc-qualification.md`: standalone and production two-hart
  ISA/CSR/trap qualification, independent instruction-reference comparison,
  architectural tests, seeded stress, coverage and actual fault controls.
- Recorded D88 and added T39 as not started in STATUS and the task index.
  Roadmap and integration sequence place qualification before T38 acceptance.
- T35/T36/T37 require affected replay after memory/boot/scan integration;
  T38 requires current evidence. Existing proof, CI and physical gates remain.

## Checks run

`python tools/env/run.py run -- python tools/check_structure.py --include-untracked`
passed (exit 0, no diagnostics), checking structure and local Markdown targets.
`git diff --check` passed (exit 0). Independent review approved the final brief,
dependencies, oracle/event/coverage requirements and retained CI/proof policy;
the reviewer also independently ran both checks successfully.
No RTL changed. No core simulation, formal campaign or CI tier ran for this
brief-writing request; proposed T39 commands are explicitly unverified.

## Numbers

The new campaign's seeds 0–31 and minimum 1024 non-padding retirements per seed,
hart and test level are **planned workload requirements**, not measurements
or a correctness guarantee. Existing test deadlines/solver caps and performance
limits are unchanged; required coverage bins remain separate acceptance.

## Deviations from the brief

This is the user-assigned planning/publication task, not execution of T39.
T39 remains unassigned/not started and does not claim an integration-stage exit.
No T33/T34 no-CI exception is extended to future work by this document.

## Open issues

T39 must qualify exact ISA/platform reference and generator support, implement
the proposed orchestration and production trace adapters, and execute the
campaign before reporting a pass. Tool/model incompatibility, missing coverage
or reproduced defects remain blockers, not automatic exclusions. Existing
unbounded proof debt and physical signoff remain with their original owners.
