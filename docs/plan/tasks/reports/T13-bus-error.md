# T13: response ownership fix

## Outcome

The unsolicited bus-error defect is fixed and independently reviewed; T13 remains blocked on complete acceptance, including the unresolved depth-160 integration check.

F-enabled cores now accept data responses only for previously granted bus
beats. Real load/store faults remain visible. Integer-only cores and the
equivalence-proved LSU are unchanged. No property, assumption or timing limit
was relaxed. Fast tier **PASS**, all 26 commands, measured 824.220 s (13m 44s), including 14 RTL tests. **Full tier not run.**

## What changed

- `IbexCore.scala`: two-bit outstanding-beat counter in the existing core
  clock/reset domain. It counts actual grants and owned responses, supports
  both split beats, and ignores an unowned response even when a new request
  is granted that cycle. Both LSU response-valid and bus-error are qualified.
  A concurrent owned response/grant preserves the count. Only reset clears it.
- `FloatCoreSpec.scala`: queued delayed responses and port-level regressions
  for unsolicited errors during FP execution, before/on grant, error without
  response-valid, aligned/split accesses, faults on either beat, and reset
  with both split beats outstanding. Both F profiles run the same tests.
- Core README documents the bus contract. No new formal monitor or induction
  machinery was added; diagnostics call the existing emit/prepare/job helpers.

Research: the pinned [Ibex protocol](https://github.com/lowRISC/ibex/blob/38c070939183cc10940b66c8e9e04eeca6b65470/doc/03_reference/load_store_unit.rst)
returns one in-order response per granted request, at least one cycle later.
The inherited LSU relies on that contract. An ID-stage "expecting response"
signal alone is insufficient because an instruction can be waiting for grant.
The hardening therefore uses actual bus grants, without adding assumptions.

## Checks run

Base commit `d868393695ac9d12948669d6fefb71d1e961a7da` plus uncommitted T13
integration and this fix. Commands use `python tools/env/run.py run --`.

- Before RTL repair: `python3 tools/sbt.py 'hw/testOnly deadhorse.perf_core.FaithfulFloatCoreSpec -- -z "unsolicited bus errors"'` failed at the unchanged 6000-cycle progress limit. This concrete behavioral replay is the negative control; repeated unsolicited errors prevent FP completion. It is not claimed to be a cycle-exact replay of the earlier formal witness.
- After repair: `python3 tools/sbt.py 'hw/testOnly deadhorse.perf_core.FaithfulFloatCoreSpec deadhorse.perf_core.FloatCoreSpec -- -z "bus"' 'hw/runMain deadhorse.perf_core.EmitFaithfulFloatCore build/t13/bus-error/emit'`: four bus tests passed, emission passed.
- `python3 hw/ip/perf_core/formal/package_candidate.py --float --top build/t13/bus-error/emit/model --leaves build/t13/faithful-f/ci-fast/fast/leaves --core build/t13/faithful-f/ci-fast/fast/core --output build/t13/bus-error/candidate`: packaged faithful F candidate.
- `python3 dv/core/lockstep.py --candidate build/t13/bus-error/candidate --isa rv32imfc --suite arch,random,flight-float --output build/t13/bus-error/lockstep`: PASS selected suites, including 191201 flight-float retirements.
- `python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/bus-error/emit/asic --operating-point main-9mhz --output build/t13/bus-error/timing`: PASS 65.726219 ns / 66.666667 ns, electrical violations zero.
- `python3 hw/ip/perf_core/formal/check_float_integration.py --faithful --emitted build/t13/bus-error/emit/asic --wide-qualification build/t13/faithful-f/qualified/fpu-wide --output build/t13/bus-error/integration`: production binding PROVED with rejected controls; original depth-160 normal role TIMEOUT at step 93, no counterexample. Existing qualified wide-FPU evidence is authenticated against byte-identical FPU sources; no arithmetic proof is claimed.
- `python3 scratch/bus_error_diagnostics.py`: existing helpers run quarter/half-depth diagnostics, original concrete covers and one engine portfolio; results below. The scratch runner is protected in the diagnostic input inventory. No new per-instruction monitor, assertion or assumption.
- Concrete original commit-on-cancel fault: existing `check_float_integration_wide.history_and_fault` and `formal_triage.job`, using the bound production model with no cutpoints, depth 48/120 s. Rejected in measured 1.548 s with a VCD witness. Exact solver command/configuration/input hashes: `build/t13/bus-error/concrete-fault/`.


- `python3 tools/ci.py --tier fast --output build/t13/bus-error/ci-fast`: PASS fast tier, all 26 commands. Registered F default timing also passes, 24.947506 ns / 24.960000 ns. Both profiles' random lockstep and local no-F checks pass. No previous gate was removed or bypassed.
- After the gate, independent review strengthened only the reset test stimulus: withhold stale responses through boot, then inject them while the restarted load awaits grant. `python3 tools/sbt.py 'hw/testOnly deadhorse.perf_core.FaithfulFloatCoreSpec deadhorse.perf_core.FloatCoreSpec -- -z "owned bus responses"'`: two tests passed. This focused rerun verifies the final test-only change; the full fast tier was not repeated. No RTL or checker changed after the passing gate.
- Independent review verified the RTL/protocol boundary, actual proof/model/timing hashes, diagnostic classifications, fault witnesses and final report. The original false-trap/progress failure is fixed; full integration acceptance is not claimed.

## Numbers

All values below are **measured** from the commands/receipts above except
derived margins. GF180 timing uses pinned Yosys 0.71+34/OpenSTA 3.2.0,
7t5v0 SS/125C/3.0V, ideal clocks, mapped pre-layout without routed/SRAM signoff.
Cell area: **839962.5472 um2**. Derived timing margin:
66.666667 - 65.726219 = **0.940448 ns**. Timing differences include synthesis
mapping changes; do not attribute the whole area/delay difference to two flops.

| Formal timeout measurement | Result |
| --- | --- |
| Prepared model | 3110 cells; 2240 state bits (30 `$ff` + 2210 `$anyinit`); no memories |
| Original bound / limit / reached | 160 / 120 s / 93; TIMEOUT |
| Quarter depth 40 | PASS, 25.428 s; diagnostic bound only |
| Half depth 80 | PASS, 94.154 s; diagnostic bound only |
| Concrete covers | All eight PASS, 1.713 s; first reached at bounds 5, 9, 10, 13 |
| Single portfolio rung, unchanged depth 160/120 s | TIMEOUT, 121.599 s; no winning engine |

The portfolio used btormc, SMTBMC/Yices, SMTBMC/Z3 and ABC bmc3. No second
attempt, larger timeout, shorter acceptance window, extra cutpoint or induction
was tried. Original assertions remain unresolved at depth 160; the lower-depth
passes do not replace that requirement. Concrete cover minima by property index:
0:9, 1:13, 2:13, 3:9, 4:10, 5:10, 6:5, 7:5. The model retains integer execution,
LSU and controller logic while replacing only FPU behavior with the previously
qualified wide protocol. The measured runtime increase with depth gives no basis for an unchanged retry.

## Deviations from the brief

This is the user-requested bus-error repair, not full T13 completion. Existing
counterexample and timing failures remain historical receipts. New timing is
a fresh measurement, not a relaxed constraint. Full tier/complete ISA sweep
was not run; no performance-cycle remeasurement is claimed for this revision.

## Open issues

The required depth-160 integration result remains unresolved. Further changes
to its acceptance bound, abstraction or induction approach need a separate
decision. Full T13 acceptance and production-profile adoption remain open.
