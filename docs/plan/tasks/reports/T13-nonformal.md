# T13: full non-formal validation

## Outcome

Requested non-formal validation passed all 54 jobs; T13 remains blocked on outstanding acceptance, including the unresolved depth-160 integration check.

Measured runtime: **2387.400 s (39m 47s)**. **259 Python unit tests and 71 RTL tests across 20 suites passed**, with no RTL tests skipped, cancelled or pending. Both F-enabled profiles passed architectural, random and hard-float flight lockstep. Standalone FPU simulation passed all **184,380 result/flags vectors**, plus **12,000 QEMU special-value cases**.

**Formal was not run**, including environment solver probes. Neither the standard fast tier nor the standard full tier ran: this was the full non-formal inventory derived from the full tier, not full CI acceptance. The pinned Ibex reference timing benchmark still exceeds the old 24 MHz budget; its driver records that measurement without failing the test job. Candidate timing checks passed.

## What changed

- `tools/env/check.py`: explicit `DEADHORSE_NO_FORMAL=1` omits only the two environment solver probes and records that omission. Default probes and failure conditions are unchanged; version, artifact and compiler checks remain active. This switch does not disable hardware formal commands.
- `tools/env/test_env.py`: mocked tests verify explicit omission makes no solver calls and the default still rejects incorrect solver results.
- `tools/env/README.md`: documents the switch's limited scope.
- This report, T13 summary and STATUS record the validation. No RTL, vendor source, assertion, assumption, timing budget or production profile changed.

The existing full-tier command inventory and mixed FPU/candidate drivers were inspected to select their simulation components. Two scratch adapters retain the existing real ALU source-fault and clock-gate falling-edge fault simulations while omitting their formal companions. Independent review checked this selection, the default-preserving environment change, and final receipts.

## Checks run

Base commit **`a9447dc`**, plus the three environment files above. The receipt authenticates 929 source files and the runner; source equality was checked before every job and at completion. Documentation updates follow the run.

```text
python tools/env/run.py build
  -> PASS; immutable image sha256:b3ac4142f7fcce199808d0fc360103a2d9f204238807cdc1ab873eb704ee7864
python tools/env/run.py run -- python3 scratch/run_full_nonformal.py
  -> PASS full non-formal suite; formal not run
```

Exact commands, per-job durations, exclusions and source hashes are in `build/t13/full-nonformal/result.json`; each job has its numbered log beside it. The three scratch runners and their hashes are archived under `build/t13/full-nonformal/runner-sources/`. Previous fixed-path T12 evidence was preserved under `previous-t12/` before generating fresh evidence.

| Check group | Result / final output |
| --- | --- |
| Environment, structure, vendor lock, compile, emission and candidate packaging | PASS; 337 pinned Ibex files unchanged; solver controls explicitly not run |
| Python unit suites | PASS: 68 tools, 141 core, 7 FPU receipt, 19 register-map, 3 parser-only, 21 historical flight tests |
| `python3 tools/sbt.py hw/test` | PASS: 71 tests / 20 suites; zero failed, cancelled, ignored or pending |
| Timing flow self-test, clock gate, 19 implemented blocks | PASS unchanged checks |
| Faithful and registered integer `dv/core/lockstep.py --suite arch,flight` | Each PASS: 16,172 architectural + 283,490 flight retirements; reference-copy run also passes |
| Both F profiles `dv/core/lockstep.py --isa rv32imfc --suite arch,random,flight-float` | PASS rounding-mode programs, two random seeds and 191,201 flight-float retirements per profile |
| `dv/core/mul_diagnose.py` | PASS 17,680 products, 40,122 retirements, 36 faults rejected |
| `dv/core/div_diagnose.py` | PASS 17,680 operations, 41,110 retirements, 280 faults rejected |
| `bash sw/flight/loop-measurement/check.sh` | PASS historical summary unchanged; four exact QEMU matches |
| `dv/fpu/iss.py`, `dv/fpu/sim.py`, existing checker controls | PASS 12,000 QEMU cases; 184,380 result/flags/backpressure vectors; positive accepted and eight negatives rejected |
| Lockstep self-check and concrete candidate/clock-gate implementation faults | PASS real faults rejected in simulation |
| `dv/core/reference_timing.py` | Measurement completed; strict reference timing **FAIL**, as detailed below; benchmark driver exits zero by design |

## Numbers

Delays, runtimes and test counts are **measured** by the commands in the authenticated inventory at the commit and working-tree snapshot above. Unchanged timing budgets and characterization conditions are **assumed configuration inputs** from `phys/gf180-ws-1x1/block-timing.json`, with the named operating-point override where applicable. Timing uses pinned Yosys 0.71+34 / OpenSTA 3.2.0, GF180 7t5v0 SS/125C/3.0V, ideal clocks and mapped pre-layout cells. These are not routed-chip signoff results. Each listed timing result has zero electrical violations. The reference benchmark uses the existing approved analysis adaptation (unused initializer removal, RVFI disabled) and qualified GF180 clock-gate binding; vendored files remain untouched.

| Timing target | Delay / unchanged budget (ns) | Result |
| --- | ---: | --- |
| Faithful F, named 9 MHz trial | 65.726219 / 66.666667 | PASS |
| Registered F, default operating point | 24.947506 / 24.960000 | PASS |
| Registered integer, default operating point | 24.734173 / 24.960000 | PASS |
| Standalone FPU | 24.421045 / 24.960000 | PASS |
| Pinned Ibex reference benchmark | 61.667374 / 24.960000 | FAIL measurement; not a candidate gate |

The fresh registered-integer timing pass does not erase the earlier failed mapping receipt. No limit was changed to obtain it.

## Deviations from the brief

The user explicitly requested the full test suite **without formal**. Formal solvers, proofs, bounded ISA sweeps and mixed-driver formal children were excluded and itemized; parser/receipt fixture tests, synthesis and timing were retained. Repeated identical commands and smoke subsets were covered by their full equivalents. Full-T13 acceptance and a standard CI-tier pass are not claimed.

## Open issues

- The original depth-160 integration check remains unresolved; no formal evidence was refreshed or promoted by this run.
- Production clock/profile adoption and the other T13 acceptance obligations remain open. Passing simulation does not establish unbounded correctness or the flight-loop deadline.
- The reference benchmark exceeds its old default timing budget. All tested candidate timing gates pass at their stated operating points.
