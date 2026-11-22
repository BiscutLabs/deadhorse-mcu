# PLAN03 SoC consolidation and tape-out planning

## Outcome

In progress at B4: B2 consolidation, ADC retirement and the frozen B3 fast tier
passed their required checks and independent review; production-SoC measurements
are next, with B5/B6 still open.

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
  remain. Historical ADC integration was temporarily isolated for comparison,
  then removed under D74.
- Preparation/emission and focused runners target production or the explicitly
  named USB-stub/minimal-I0 test configurations. After the comparison passed,
  the ten old profile emitters and unreachable profile alternatives were removed;
  both focused memory emitters remain. Consolidation is committed locally as
  `5d47869`; ADC retirement is the separate local commit `2504a31`.
- Removed the retired ADC implementation, ports, isolated legacy test binding,
  ADC-only runner/formal/timing references and stale links. The general SPI
  host, DMA and software conversion helper/tests remain. Added exact error
  checks at the retired window's base/end and for writes by either master.
- The B3 historical USB-equivalence fixture failed because the newer
  verification-only `UsbSiePacketContract.scala` uses an API absent from the
  pinned baseline. Exclude that file only from historical compilation, as
  already done for `UsbPacketProof.scala`; complete candidate compilation,
  pinned baseline HDL hashes, state matching, fault controls and caps stay intact.
- Approved B3 follow-up adds production-bound sampling monitors and real-wire
  fault witnesses, complete evidence inventories, wrapper-context equivalence,
  applied timing-exception audits and actual class-delay faults. Physical tooling
  qualifies explicit drive-strength substitutions and audits fixed-launch
  rise/fall enumeration. No production peripheral RTL changed.
- D77 records the approved, narrowly enumerated asynchronous boundary contract.
  Its mapped-graph audit identifies every sampler/release chain, checks actual
  cell reset semantics and rejects bypass, clock, alias and reset-root faults.
  Two physical data buffers repair ordinary VBUS data hold; those paths receive
  no asynchronous exception. A separate mapped production bus-slot/USB fixture
  measures both directions with real shared CTS and extracted wires.

## Checks run

All commands below use `python tools/env/run.py run --` and the pinned tools.

- Final frozen B3 acceptance, base `2504a31` plus receipt-hashed changes:
  `python hw/ip/usb/check.py --output build/plan03/usb-acceptance01 --acceptance-evidence build/plan03/usb-closure/acceptance-manifest01.json`
  passed with no unresolved acceptance obligations; measured wall time
  **1648.642472 seconds**. Then
  `python tools/ci.py --tier fast --output build/plan03/fast02 --usb-evidence build/plan03/usb-closure/acceptance-manifest01.json`
  printed `PASS fast tier active checks; 12 deferred, unproved (see receipt)`:
  **34 commands**, all exit zero, measured wall time **3637.986439 seconds**.
  Fresh USB simulation passed **29 tests in 9 suites**; packet audit closed
  all twelve original claims, sampling/physical audits passed, and integrated
  engine/wrapper timing stayed within approved warning limits. Standalone SIE
  remains diagnostic-only, with its failing row retained. The final physical
  collector, including actual-library identity guards, executed and passed in
  both runs. Full tier was **not run**.
  Independent review recomputed **1448 CI source hashes**, **1561 USB
  source/evidence hashes** and **14 child receipt hashes**, with zero mismatches.
  The retained deferrals are T14 BUS-FAIR-M0/M1/M2 and BRIDGE-RETURN-DATA;
  T17 WRITE-COVER/CORRECT, READ-COVER/CORRUPT/CORRECT and
  RECOVER-COVER/CORRUPT/CORRECT. None is reported proved.

Earlier checkpoints below preserve failed attempts and intermediate scopes;
the final frozen result above supersedes their pending-run statements.

- D77 collector and aggregate preflight: `physical_evidence.py` validates the
  sealed standalone candidate, exact fresh production emission, all fifteen
  asynchronous/ordinary boundary cases and the separately routed two-way bus
  fixture. `physical-evidence04` passed; the final additional actual-library
  identity guard is covered by focused tests and will execute in the frozen
  aggregate. Final read-only packet preflight prints
  `PASS USB evidence; closed=12 unresolved=[]`.
- Latest focused checks: USB evidence **21 tests**, physical tools **27 tests**,
  timing/fanout tools **38 tests**, CI tier routing **18 tests**, all `OK`;
  structure check exits zero. Independent review accepted exact query/path and
  candidate linkage; the aggregate still requires actual frozen execution.
- Frozen acceptance inputs are explicitly provisioned in
  `build/plan03/usb-closure/acceptance-manifest01.json`, linking the packet,
  sampling and physical manifests. Planned execution (not a passing result):
  `python hw/ip/usb/check.py --output build/plan03/usb-acceptance01 --acceptance-evidence build/plan03/usb-closure/acceptance-manifest01.json`,
  then `python tools/ci.py --tier fast --output build/plan03/fast02 --usb-evidence build/plan03/usb-closure/acceptance-manifest01.json`.
  These require the authenticated generated evidence; a clean checkout without
  those artifacts fails. No closed packet solver is rerun.

- B3 follow-up, base `2504a31` plus receipt-bound sources: exact
  sampling/equivalence/witness/timing commands and final outputs are in
  [the sampling report](../../../spec/usb-sampling-proof.md). Eleven unbounded
  assertions, wrapper context and five actual DUT faults qualify. Fresh EP0
  timing prints `PASS UsbControl`; engine/wrapper print `FAIL UsbEngine` /
  `FAIL Usb` due to retained pad hold, while sampling and exception qualification
  each pass. Independent review checks all 7/10/17 populated-class faults.
- `python scratch/plan03_fullsize.py`: underlying
  `python3 tools/sbt.py 'testOnly deadhorse.usb.UsbThroughputSpec'` passes both
  unchanged tests; output `Tests: succeeded 2, failed 0` / `All tests passed.`
  Measured runner wall time **741.497 s**; sbt independently prints 820 s.
  Simultaneous measured payload is **1,022,483.316 bit/s each way**; unchanged
  slow-service control measures **286,567.164 bit/s** and is correctly rejected.
  `fullsize01/result.json` binds the complete current simulation source inventory.
- `python scratch/plan03_final_evidence_audit.py`:
  `packet pass 12 None`; `sampling UsbControl pass`; `sampling UsbEngine pass`;
  `sampling Usb pass`. Read-only audit, no packet solver rerun. Five original
  packet claims prove at full size and seven at the small model with fresh
  full-size simulation. `packet-audit01/result.json` records no unresolved claim.
- Physical commands and all class measurements are in
  [the physical report](../../../spec/usb-physical-validation.md).
  `usb_seal.py --verify build/plan03/usb-closure/physical-size03-receipt02.json`:
  `PASS sealed physical evidence unchanged`. Independent review verifies all
  478 bound files; receipt remains `failed-validation` for boundary/physical
  qualification, not a CI or signoff pass.
- Focused tooling checks:
  `python -m unittest discover -s hw/ip/usb -p test_evidence.py`: **16 tests, OK**;
  `python -m unittest tools.timing.test_usb_qualification tools.timing.test_timing`:
  **29 tests, OK**;
  `python -m unittest discover -s tools/physical -p 'test_usb*.py'`:
  **14 tests, OK**;
  `python -m unittest discover -s hw/ip/usb/formal -p test_sampling.py`:
  **2 tests, OK**;
  `python tools/check_structure.py --include-untracked`: **exit 0**.
  No USB aggregate or CI tier rerun in this follow-up.
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
- `python tools/ci.py --tier fast --output build/plan03/fast01` at clean
  `2504a318de0931087963b37ff8b6381cf38dc6be`: **failed (partial tier run)**,
  measured monotonic wall time **2864.272 seconds**. Last output:
  `FAILED T19 USB; inspect result.json for every unresolved obligation`.
  Every preceding command passed; later core emission/timing/lockstep/formal
  commands were not reached. The frozen source inventory is in `result.json`.
  Existing deferrals: T14 BUS-FAIR-M0/M1/M2 and BRIDGE-RETURN-DATA;
  T17 WRITE-COVER/CORRECT, READ-COVER/CORRUPT/CORRECT and
  RECOVER-COVER/CORRUPT/CORRECT. All twelve remain explicitly unproved.
  USB passed all 23 simulations in eight suites, resume equivalence, the
  focused formal suite, real packet covers/faults and byte CDC. Pre-enable
  equivalence failed historical compilation; engine/wrapper timing consequently
  blocked on missing D58 evidence. EP0 timing separately blocked on retained
  sampling and exception qualification. Packet-controls-only correctly remains
  unresolved for positive proofs; CI supplies no audited packet manifest.
  Standalone SIE is diagnostic-only. The complete USB child receipt is
  `build/plan03/fast01/fast/usb/result.json`.
- `python hw/ip/usb/evidence.py --manifest build/t19/occupancy-evidence-manifest.json --output build/plan03/usb-evidence-audit01`:
  **failed**, `Incomplete or stale full-size source binding`. The read-only
  packet audit and SIE binding pass; packet inventory is five full-size and
  seven small-model proofs. No closed proof was rerun. Current full-size
  simulation evidence must be authenticated before that combined inventory
  can pass; archived receipts were not amended.
- `python hw/ip/usb/formal/preenable_equivalence.py --after build/plan03/fast01/fast/usb/emit --regmap build/plan03/fast01/fast/usb/regmap/usb_regs.json --output build/plan03/preenable-fixture-fix01`:
  **PASS** at `2504a31` plus the receipt-hashed fixture repair:
  `PASS D58 engine/wrapper relational equivalence and phase/consumer faults`.
  Both correct cases prove; early, late and off-enable-consumer faults fail
  as intended in both blocks, and the real-wire consumer fault is rejected.
  Fresh candidate emission and exact pinned baseline HDL hashes match.
  `python tools/check_structure.py --include-untracked` and
  `git -c core.safecrlf=false diff --check` also pass after the repair.
  Fast CI was not rerun: the separate T19 qualification blockers remain.
- Full CI: not run in this task.
- `python hw/top/reference/formal/check_inactive.py --output build/plan03/adc-retirement-formal`:
  PASS at `5d47869` plus retirement changes: five remaining assertions proved
  unbounded with ABC PDR, cover reached, and all three retained actual enable
  faults rejected at their expected identities. Zero assumptions; original
  caps/depth unchanged. Measured times are in the SoC formal ledger.
- `python dv/soc/check_production.py --output build/plan03/adc-retirement`:
  PASS at `5d47869` plus receipt-hashed retirement changes: 77 tests across
  24 suites, no failures/skips/cancellations/pending tests; four complete top
  emissions and minimal-I0 compilation pass. Measured runner-monotonic time:
  simulation 1287.52 seconds, complete runner 1347.68 seconds (sbt separately
  reports 1427 seconds for simulation).
  `python scratch/plan03_compare_retirement.py` confirms exactly the five approved
  runtime test-name removals, with no other differences. Independent review
  recomputed this comparison and checked all current source hashes against the
  frozen receipt before accepting retirement.

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
After B2 passed, D74 explicitly retired the ADC integration test inherited by
SocIoSpec, SocPwmSpec, SocPinmuxSpec and SocWatchdogSpec, plus the ADC-only pad
fault in SocInactiveSpec. Measured remaining runtime inventory: 77 tests in
the same 24 suites, exactly matching 82 − 5. The ADC directory's
AdcSpec, AdcRawSpec and AdcSampleStateSpec and its ADC-specific proofs/timing
were also retired. The pure software conversion tests remain. The pre-deletion
file/test inventory is `build/plan03/adc-retirement-inventory.json`.

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
accept CI or B3–B6. The same independent reviewer separately accepted the ADC
retirement after checking the actual source/test delta, proof receipt and
frozen runtime evidence.
The reviewer also accepted the B3 fixture repair and blocked handoff after
independently recomputing all proof source/emission hashes and checking both
induction proofs and every fault result. This does not accept PLAN03 or CI.

## Open issues

B4 production measurements/budget and review, B5 debt register/triage and B6
reconciliation/T32–T38 briefs remain. T20 is open. No new peripheral block work
or full CI has run. B3's fast pass retains twelve explicit T14/T17 deferrals
and the existing bounded proof scopes; it does not close whole-chip signoff.

USB qualification is scoped: the optional partial-header/new-SETUP diagnostic
is unresolved; standalone USB internal timing and the two-way bus fixture use
separate placements. Analog metastability, pad/board electrical behavior,
reset pulse/glitch characterization, upstream source-control sequencing and
whole-chip physical validation remain tape-out obligations. See the
[sampling report](../../../spec/usb-sampling-proof.md) and
[physical report](../../../spec/usb-physical-validation.md). Raw asynchronous
STA diagnostics remain visible under the exact-pin D77 qualification.
