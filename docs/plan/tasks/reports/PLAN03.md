# PLAN03 SoC consolidation and tape-out planning

## Outcome

Done: B1–B6 deliverables, independent reviews and the frozen fast tier are complete,
with inherited proof debt and full-tier/physical qualification explicitly open.
No new peripheral RTL.

## What changed

- Decisions D72–D76 record one production top, T31 withdrawal/loader freeze,
  ADC retirement, the historical T20 loop exception and CI policy. D77 records
  the later explicitly approved USB asynchronous-boundary qualification.
- One production `DeadhorseSoc` contains the faithful RV32IMFC/shared-MAC core,
  local memory, main/AON fabrics, bridge/mailbox, three UARTs, SPI, I2C, real
  USB, GPIO, main/AON timers, generic PWM, DMA, pinmux, both watchdogs, real
  lite hart, boot release, QSPI command/XIP and the frozen I2C recovery loader.
  JTAG, clock/power and analog implementation remain. SRAM/ROM are models.
- `soc.yaml` and `docs/spec/soc.md` describe this one top; old profiles survive
  only as history. Named minimal-I0/USB-stub/CPU-stimulus test fixtures remain.
  Old profile code was deleted after tests and exact emission comparisons.
  ADC window, pins and IRQ are unassigned; ADC code/tests were deleted separately
  after B2 passed. Firmware can use general SPI/DMA for external converters.
- Approved B3 USB work closed required sampling/spacing, applied-exception and
  scoped routed/boundary qualification. No peripheral behavior/limit change.
  Physical mapping changes and exact boundary qualifications retain raw
  diagnostics and explicit whole-chip/analog limitations.
- B4 preserves qualified USB mapping within full production synthesis, binds
  certificates to actual mapped pins, audits all constraints and accounts for
  every cell. Exact executed sources are versioned under
  `hw/top/reference/measurements`; generated evidence remains in build/.
- B5 adds `dv/soc/plan03_debt.py` and a read-only evidence auditor, the complete
  STATUS debt table and per-assertion report/ledger updates. B6 reconciles
  plans02/03/04/07/09/11/16 and the task index, and writes unimplemented T32–T38
  briefs. No gate or implementation task is completed by writing a brief.

## Checks run

All commands below use `python tools/env/run.py run --` and pinned tools unless
explicitly noted. Earlier failed attempts remain in build/plan03 and git history.

| Check / command | Actual result |
| --- | --- |
| Baseline `python tools/sbt.py 'hw/testOnly deadhorse.top.*'`, base 51332b5 | `Tests: succeeded 82, failed 0`; 24 suites; `All tests passed.`; measured sbt 1100 s |
| B2 `python dv/soc/check_production.py --output build/plan03/consolidation02`, base 7999bed plus hashed changes | PASS 82 tests/24 suites, four production/stub8/9 MHz emissions and minimal-I0 compilation; measured aggregate 1454.41 s |
| Profile cleanup/final reserved-hole metadata emissions and exact comparison | All emitted HDL byte-identical to passing B2 snapshot; `build/plan03/final-b2/comparison.json` PASS |
| ADC retirement `python dv/soc/check_production.py --output build/plan03/adc-retirement` | PASS 77 tests/24 suites; exact82 minus five authorized ADC cases; no other omission/skip |
| B3 `python hw/ip/usb/check.py --output build/plan03/usb-acceptance01 --acceptance-evidence build/plan03/usb-closure/acceptance-manifest01.json` | PASS; measured 1648.642472 s |
| B3 `python tools/ci.py --tier fast --output build/plan03/fast02 --usb-evidence build/plan03/usb-closure/acceptance-manifest01.json` | `PASS fast tier active checks; 12 deferred, unproved (see receipt)`; 34 commands exit 0; measured 3637.986439 s |
| B4 production mapping/STA/certificates/exception audit/area/workloads | PASS within stated mapped/digital scope; exact commands, paths and measurements in [production report](../../../spec/soc-production-measurements.md) |
| B4 transitive source/evidence seal | Independent review verified all 3613 files in b4-seal02 and 23 tracked executed-source snapshots; subsequent report metadata distinguished from the measured snapshot |
| B5 three scoped commands and audit02 commands | Original positive aggregates remain unresolved; exact partition results below. All evidence audits PASS, no unchanged timed-out job rerun |
| `python -m unittest tools.test_formal` | 9 tests, `OK` |
| Structure and `git diff --check` | Exit0 after debt/report publication |
| Final `python tools/ci.py --tier fast --output build/plan03/fast03 --usb-evidence build/plan03/usb-closure/acceptance-manifest01.json`, base 58833fd plus hashed B5/B6 changes | `PASS fast tier active checks; 12 deferred, unproved (see receipt)`; all 34 commands exit 0; measured 3628.413506 s |

Full tier: **not run in PLAN03**. No I2/I3/I4/I5 exit is being claimed; D76
requires full CI at each of those exits. Previous failed full-tier evidence
and the unrun remainder remain explicit in the core ledger.

The [exact test list](../../../spec/soc-test-inventory.md) records every runtime
case before/after B2 and D74. All 24 suites remain. The five removed cases are
the ADC producer inherited by SocIoSpec/SocPwmSpec/SocPinmuxSpec/SocWatchdogSpec
and SocInactiveSpec's ADC-pad fault. ADC-only AdcSpec/AdcRawSpec/
AdcSampleStateSpec were removed with the block in separate commit 2504a31;
software conversion tests remain. Focused fixtures were rebound to production;
the GPIO oracle distinguishes masked physical output from retained raw MMIO.

Independent review checked B2 no lost tests/behavior, ADC retirement, B3
proof/physical/aggregate receipts, B4 numbers/certificates/source identity,
and B6 briefs. B5 review authenticates concrete covers/faults and exact assertion
accounting; final proof/debt review verifies every audit hash and all original claims.
Final independent audit verified all 1485 CI source hashes, 14 child-receipt
hashes and 1561 USB source/input hash entries with zero mismatches. Command
inventory, the four T14/eight T17 deferrals and qualification limits match B3.
USB's 29 simulations pass without skipped cases; standalone SIE remains an
explicit diagnostic-only failure, with integrated engine/wrapper acceptance
passing. Audit: `build/plan03/final-review/independent-fast03-audit.json`.
Only this result/outcome and STATUS completion metadata changed after the
frozen run; source and evidence identity were rechecked before publication.
Review never substitutes for required execution.

## Numbers

B4 measured at main 736ed5c with unchanged RTL, pinned Yosys/OpenSTA and GF180
SS 125 C/3.0 V; commands and detailed per-block/class/start/end tables are in
the production report. These are mapped pre-layout figures, not chip signoff.

| Quantity |8 MHz trial |9 MHz trial | Provenance / limit |
| --- | ---: | ---: | --- |
| Mapped logic area, mm2 |3.322808384 |3.3165169408 | Measured, six SRAM/ROM sockets excluded |
| Main RR worst, ns |64.830223 |65.965767 | Measured; estimated 60% budgets 75/66.666667 |
| AON RR worst, ns |63.095551 |64.042114 | Measured; assumed active 1 MHz, budget 600 ns |
| USB FF worst ordinary class, ns |13.485458 |13.485458 | Measured warning within 15 ns; certified and strict FP classes also pass |
| Fixed-point mean / worst cycles |3879.791667 /4350 |3879.791667 /4350 | Measured 120 complete loop windows each |
| Hard-float mean / worst cycles |7809.833333 /9007 |7809.833333 /9007 | Measured 120 complete loop windows each |

Estimated worst overhead versus T13 round 2: fixed 0%; hard-float 34/8973=
0.3789156%. D75 retains the historical accepted 4821-cycle observation. Real
production recovery/lite release/ROM copy executes; full loop instructions match
except RAM relocation. Target QEMU and every floating result agree, including
fused operations; this does not claim full production architectural lockstep.

Plan08 complete core budget is **estimated 12.783522307 mm2**, leaving
**estimated 0.136477693 mm2** against 12.92 mm2. It includes measured logic,
pinned SRAM footprints, estimated scan uplift and named assumed debug, control,
ROM/BIST, analog, pad and routing allowances. This narrow margin is not layout fit.

B5 measured results under unchanged 120-second caps: DMA range TIMEOUT 122.108 s
wall. ADDI has eight meaningful unbounded passes, five trivial memory claims,
and destination-data TIMEOUT 121.345 s. Watchdog proved indices [0, 3, 4, 9, 10], unresolved
indices [1, 2, 5, 6, 7, 8, 11]. Every original assertion remains accounted for; existing faults
qualify only their stated indices. Model sizes, progress, growth, covers and
exact per-job times are in [the debt report](../../../spec/soc-verification-debt.md).

## Deviations from the brief

No unapproved behavior, assertion, assumption, bound, limit or tolerance change.
The user approved focused B3 USB closure and the B4 mapping-only follow-up;
the original failed timing screen is preserved. Native uncontracted host float
checksums differed from RISC-V FMA semantics; exact pinned target ISS and
per-result trace comparison resolve the oracle mismatch without an RTL change.

B4 measurement deliverables pass, but T20 stays open for its original generated-
top composition, complete architectural and target-interface acceptance. B5
explicitly allows unresolved proof debt without blocking B6. T36 records the
autonomous lite cold-boot path as a pre-implementation contract prerequisite,
preserving exclusive SRAM ownership and the frozen recovery loader.

## Open issues

The STATUS debt table retains T13 integration/full ISA/refinement, four T14 and
eight T17 deferrals, bounded serial scopes, T19 small-model/optional diagnostic/
chip-physical limits, T20 system composition, T23 range, T25 full ISA/machine,
T26 remaining channel claims and other unproved progress/composition scopes.
New helper-invariant work needs a separate approved scope; no further sweep
is included here. Full CI, Q15/Q16 and S1's separate performance-floor decision
remain open. Mapped timing does not qualify raw IO/hold/reset/pulse diagnostics,
macro contracts, real clocks, pads, analog behavior or whole-chip physical fit.

Next implementation order after PLAN03 and passing fast CI: T32 debug and T33
clock/reset/power first in parallel; then T35 SRAM/BIST and T36 ROM; then T37
scan/test and T38 chip/pads. T34 analog interfaces/models may start any time
after PLAN03; layout/extraction is a later brief. T31 remains withdrawn.
