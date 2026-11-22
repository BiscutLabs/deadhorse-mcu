# PLAN02 General-purpose MCU scope reconciliation

## Outcome

Documentation reconciliation completed under D69; implementation and physical
qualification remain separate work.

## What changed

- Recorded D69 in the decision register and STATUS: conventional MCU
  timer/PWM/capture/compare, buffered updates, DMA, interrupts and generic
  watchdog/reset/output-disable mechanisms; application protocols and fault
  policy belong in firmware.
- Reconciled root/plan READMEs, product requirements, architecture, carryover,
  power/reset, peripherals, roadmap, formal/test obligations, integration plan
  and task index. Preserved first-application numerical requirements and tests.
- Marked `docs/spec/actuator-block.md` historical and superseded. Clarified
  `docs/spec/soc.md`: the inactive legacy endpoint has no functional failsafe
  state; its existing reset wiring is unchanged.
- Identified T21 ADC board-unit scaling as a later scoped firmware migration;
  preserved the current tested ABI. No RTL or register-map changes.

## Checks run

- `python tools/env/run.py run -- python3 scratch/d69/check.py`: PASS;
  documentation-only delta against the pre-task working-tree snapshot, local
  Markdown links, unique decision identifiers and unchanged open gates.
- `git diff --check`: PASS, exit zero; only line-ending conversion warnings.
- Independent review: reset-language contradictions identified and corrected;
  final review cleared the reconciliation, preserving generic reset contracts
  and confirming no RTL, ABI, test or numerical acceptance changes.
- Neither fast nor full CI ran, following the user's no-CI instruction.

## Numbers

No new performance, area, timing or capacity measurements. Existing numerical
baselines retain their original provenance and acceptance limits.

## Deviations from the brief

None. Checks apply to the local documentation delta; they do not qualify
pre-existing T20/T21 implementation changes in this working tree.

## Open issues

- Generic PWM and required DMA integration need scoped implementation briefs;
  no dedicated DShot/publication/failsafe engine is authorized by this decision.
- ADC board-unit conversion requires a scoped migration to firmware, including
  an explicit ABI and test update. Existing behavior remains in place.
- External device electrical behavior and application safety remain board and
  firmware validation obligations. T19/T20/T21 qualification gaps remain open.
- Changes remain local alongside prior uncommitted work; no blanket commit of
  that incomplete dependency set is made by this documentation task.
