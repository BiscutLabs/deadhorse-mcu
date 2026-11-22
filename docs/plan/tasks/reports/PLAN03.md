# PLAN03 SoC consolidation and tape-out planning

## Outcome

In progress: B2 consolidation passed its comparison, cleanup checks and
independent review; ADC retirement and B3–B6 remain.

## What changed

- D72–D76 record the user's one-top rule, T31 withdrawal/loader freeze, ADC
  retirement, historical T20 overhead exception and CI policy. Commit `7999bed`.
- `DeadhorseSoc` defaults to the complete feature set through fixed
  `SocProduction` configuration. `SocMinimalI0` preserves the named minimal
  boot/performance fixture. Production contains the faithful RV32IMFC/shared-MAC
  performance core, local memory, main/AON fabrics, bridge, mailbox, three UARTs,
  SPI, I2C, USB, GPIO, main/AON timers, PWM, DMA, pinmux, watchdogs, lite hart,
  boot release, QSPI command/XIP and the frozen I2C recovery loader.
- `soc.yaml` and the current section of `docs/spec/soc.md` describe that single
  assembly. The old contract is retained in a historical appendix. The ADC
  window, pins and IRQ are unassigned in the production map.
- Focused tests use the complete peripheral set, with a named bus-stimulus
  boundary where needed. Real-core tests use the actual recovery wire, lite
  firmware and boot-release register. Existing behavioral assertions and faults
  remain. Historical ADC integration is temporarily isolated for comparison.
- Preparation/emission and focused runners target production or the explicitly
  named USB-stub/minimal-I0 test configurations. After the comparison passed,
  the ten old profile emitters and unreachable profile alternatives were removed;
  both focused memory emitters remain. ADC source is still retained pending
  final B2 acceptance and the separate retirement commit.

## Checks run

All commands below use `python tools/env/run.py run --` and the pinned tools.

- Baseline at `51332b513caf85ed9cac216c3bd4f85121442119`:
  `python tools/sbt.py 'hw/testOnly deadhorse.top.*'`.
  Output: `Total number of tests run: 82`; `Suites: completed 24, aborted 0`;
  `Tests: succeeded 82, failed 0, canceled 0, ignored 0, pending 0`;
  `All tests passed.` Measured sbt wall time: 1100 seconds. Baseline compiled
  classes and shared generated inputs were preserved during this run; source
  migration began after compilation. Source inventory, log and original XML
  reports are archived under `build/plan03/baseline/`.
- Updated map tests initially exposed stale ADC pad-count/overflow fault
  expectations. These were updated for D74 while preserving the physical limits.
  `python -m unittest discover -s hw/top/reference -p test_soc_map.py -v`
  subsequently passed; evidence `build/plan03/map-tests02.log`.
- `python dv/soc/check_production.py --output build/plan03/consolidation01`:
  preparation, map tests, fixture-tool tests, control-tool tests and structure
  passed. Simulation: 82 tests, 78 passed, four failed at the inherited GPIO
  wake/retention assertion; measured sbt wall time 1563 seconds. The old fixture
  expected raw GPIO data 6 with enables 3 at the pad boundary; the existing
  production pinmux correctly outputs 2 with enables 3. Independent review
  confirmed the fixture correction: exact pad value 2 at the original stopped
  clock observation, plus retained GPIO data 6/enables 3 through MMIO after the
  original wake-flush check. No RTL, bound or reset assumption changed. Failed
  evidence and XML reports are preserved in the output directory.
- `python dv/soc/check_production.py --output build/plan03/consolidation02`:
  PASS on the corrected frozen implementation at `7999bed` plus receipt-hashed
  changes. All 82 tests across 24 suites passed, with no skipped/cancelled/pending
  tests; measured runner-monotonic simulation time 1392.70 seconds (sbt separately
  reports 1544 seconds). Measured aggregate runner time was 1454.41 seconds.
  All four complete top emissions
  (production/USB-stub, 8/9 MHz) and minimal-I0 simulator compilation passed.
  Independent review compared runtime XML: no test-name differences from baseline.
  Post-cleanup comparison passed: every emitted SystemVerilog file is byte-identical
  in all four configurations. Commands: `python tools/sbt.py` with four
  `hw/runMain deadhorse.top.EmitSoc build/plan03/profile-cleanup/soc-<MHz>-<variant> <variant> <MHz>`
  arguments, then `python scratch/plan03_compare_emissions.py build/plan03/consolidation02 build/plan03/profile-cleanup`.
  Evidence: `build/plan03/profile-cleanup/comparison.json` and the emission log.
  Post-cleanup structure, `git diff --check` and updated ADC runner syntax checks
  also passed. No production source changed between emission and comparison.
  A final reserved-hole metadata correction (`gateway_reserved`: stub to reserved)
  passed map tests and regeneration; `build/plan03/final-b2/comparison.json`
  again shows exact identity against the passing snapshot in all four variants.
- Fast CI: not yet run in this task; B3 follows B2.
- Full CI: not run in this task.

The baseline suite inventory is below. Exact runtime test names are
in `build/plan03/baseline/test-inventory.json`.

| Baseline suites | Consolidated target | After comparison |
| --- | --- | --- |
| SocBootSpec, SocBootReleaseSpec, SocI1CoreResetSpec | Production plus named minimal-I0 boot fixture | PASS |
| SocPwmCoreResetSpec, SocPinmuxCoreResetSpec, SocWatchdogCoreSpec, SocXipSpec | Production, USB-stub test substitution | PASS |
| SocI1Spec, SocIoSpec, SocPwmSpec, SocDmaSpec, SocPinmuxSpec, SocWatchdogSpec, SocWatchdogEpochSpec, SocQspiSpec | Complete production peripherals, named bus stimulus boundary | PASS |
| SocLiteSpec, SocI1UsbSpec | Complete production peripherals with real hart / real USB respectively | PASS |
| SocMemorySpec, SocDmaMemorySpec, SocXipMemorySpec | Existing focused memory configurations | PASS |
| SocI1ResetSpec, SocI1SupportSpec, SocNestedSpec, SocInactiveSpec | Production crossing / existing focused helper fixtures | PASS |

Map-test changes are explicit: obsolete ADC owner/size cases are replaced with
rejection of ADC binding/pin reintroduction; mandatory DMA and real-lite checks
are added. ADC pin-width validation is retired with the approved pin removal.
No ADC behavioral test has yet been deleted.

## Numbers

- Measured baseline: 82 tests, 24 suites, 1100 seconds, command/commit above.
- Estimated pad demand after ADC retirement: 40 − 2 = 38 output-capable and
  10 − 1 = 9 input-only pads, against unchanged 40/12 logical capacities.
- B4 whole-SoC area, domain timing, integrated workload and revised area-budget
  measurements have not been performed. No I0 fixture result is claimed as a
  production-top measurement.

## Deviations from the brief

None accepted. Independent reviewer `plan03_consolidation_review` accepted B2
after comparing runtime inventories, independently recomputing all final emitted
file hashes, and reviewing the fixture correction and cleanup. This does not
accept CI, ADC source deletion or B3–B6.

## Open issues

Separate ADC deletion; B3 fast CI;
B4 measurements and review; B5 verification-debt register/limited triage;
B6 plan reconciliation and T32–T38 briefs. No new block work has started.
Nothing from this task has been pushed; pushing remains conditional on fast CI.
