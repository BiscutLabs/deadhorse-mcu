# T13: faithful-pipeline F integration checkpoint

> Historical checkpoint. The [bus-error repair](T13-bus-error.md) fixes the unsolicited-response defect and passes both timing checks and the fast tier. Depth-160 integration remains unresolved; the earlier failures below are preserved.

## Outcome

Blocked: the faithful F candidate passes simulation and focused ISA checks, but fails an integration assertion and the 9 MHz timing budget; it is not accepted as production.

**Current evidence:** 12 unchanged modules proved equivalent with rejected faults;
ADDI/LW/C.ADD bounded at depth 40/check cycle 12 with concrete covers and fault
rejection; full selected architectural/random/flight-float simulation passed.
The wide FPU protocol is independently qualified, but integration safety fails
at bound 10. No integrated safety pass, complete ISA sweep or full-tier pass is
claimed. No assertion, assumption, deadline or timing allowance was relaxed.

| Final candidate measurement | Result |
| --- | ---: |
| Mapped delay / allowance, 9 MHz | 67.791702 / 66.666667 ns: FAIL |
| Mapped cell area | 838720.064 um2 (0.838720064 mm2) |
| Fixed-point loop, mean / worst cycles | 3879.792 / 4350 |
| Hard-float loop, mean / worst cycles | 12338.667 / 14233 |
| Fixed-point loop at 9 MHz, derived mean / worst | 431.088 / 483.333 us |
| Hard-float loop at 9 MHz, derived mean / worst | 1370.963 / 1581.444 us |

Fast tier **failed (partial tier run)**, measured 426.823 s to stop; 15 commands passed, failed at integrated-timing. Full tier **not run this continuation**.

### Counterexample requiring resolution

The normal integration check fails property 15 (`assert__chisel3_builtin_21`),
which forbids exception/debug CSR save/restore while an FP request is pending.
The trace accepts FP instruction `0xf0000043` at PC `0x84`; an unsolicited
`data_rvalid_i && data_err_i` is present in the same acceptance cycle and causes load-access-fault exception entry.
`csr_save_cause_o`, cancellation and the still-set pending monitor coincide.
No data request is outstanding anywhere in the trace. No integer write, FP
write, FP commit or FCSR commit occurs at the acceptance/cancellation/trap
cycles. The next recorded state is clear with reset asserted; cancellation-only recovery has not been replayed.

This is a counterexample to the stated property with unconstrained bus inputs.
It does **not** establish a partial FP architectural commit. It does not depend
on a floating result or completion choice; independent review infers the same
control sequence is possible in the concrete model, but a concrete replay has
not been run. Implementation changes and further proof attempts stopped on
this result. Do not hide it with a bus assumption or a weakened assertion.

## What changed

- `IbexCore.scala`, `IbexIdStage.scala`, `FloatExecution.scala`: reuse the
  existing FPU, float registers and CSRs on the faithful ID multicycle path.
  FP arithmetic/FSW stage operands for one cycle; integer operations retain
  faithful timing. Illegal F encodings cannot issue memory requests, write
  integer registers or increment retired-instruction counts.
- `EmitFaithfulFloatCore.scala`, candidate packaging/authentication and
  lockstep/performance drivers add the distinct `rv32imfc-faithful-v1` profile.
  Existing integer-only and registered profiles remain available.
- Existing F-core behavioral tests also run against the faithful profile;
  illegal-F tests cover memory issue, integer writes, trap values and minstret.
- The existing integration monitor is adapted to faithful handshakes, with
  fresh production binding and qualified wide-FPU substitution. Concrete
  controls are configured, but were not reached after normal-role failure.
  Frozen source/receipt hashes are revalidated throughout the checker.
- Fast/full CI registers the new candidate in addition to the existing checks.
  The fast tier includes faithful timing; a failing candidate is not omitted.

## Checks run

All commands below use `python tools/env/run.py run --` and base commit
`d868393695ac9d12948669d6fefb71d1e961a7da` plus the recorded working-tree hashes.
Final candidate and evidence root: `build/t13/faithful-f/qualified/`.

```text
python3 tools/sbt.py 'hw/testOnly deadhorse.perf_core.FaithfulFloatCoreSpec' 'hw/runMain deadhorse.perf_core.EmitFaithfulFloatCore build/t13/faithful-f/qualified/emit'
  -> 4 tests passed; emission passed.
python3 dv/core/equiv.py --unchanged-since t11-baseline --candidate build/t13/faithful-f/qualified/candidate --output build/t13/faithful-f/qualified/unchanged
  -> PASS unchanged modules: 12 proved with fault controls; changed-module obligations remain.
python3 dv/core/qualify_fpu_protocol_wide.py --candidate build/t13/faithful-f/qualified/candidate --output build/t13/faithful-f/qualified/fpu-wide
  -> all five trace-inclusion roles proved; all five negative controls rejected.
python3 dv/core/riscv_formal.py --target candidate --candidate build/t13/faithful-f/qualified/candidate --checks addi,lw,c_add --output build/t13/faithful-f/qualified/isa-focused
  -> PASS bounded/covered classifications at depth 40; fault rejected; no unbounded proof.
python3 dv/core/lockstep.py --candidate build/t13/faithful-f/qualified/candidate --isa rv32imfc --suite arch,random,flight-float --output build/t13/faithful-f/qualified/lockstep
  -> PASS selected F lockstep suites, including 191201 flight-float retirements.
python3 dv/core/performance.py --faithful build/t13/faithful-f/baseline --faithful-floating build/t13/faithful-f/qualified/candidate --profiles faithful,faithful-f --output build/t13/faithful-f/qualified/performance
  -> PASS measured selected supported profiles; all architectural comparisons passed.
python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/faithful-f/qualified/emit/asic --operating-point main-9mhz --output build/t13/faithful-f/qualified/timing
  -> FAIL DeadhorsePerfCore: 67.791702 ns, budget 66.666667 ns; electrical violations 0.
python3 hw/ip/perf_core/formal/check_float_integration.py --faithful --emitted build/t13/faithful-f/qualified/emit/asic --wide-qualification build/t13/faithful-f/qualified/fpu-wide --output build/t13/faithful-f/qualified/integration
  -> production binding PROVED, binding faults rejected; normal role FAIL at bound 10; fault and cover roles not run.
```

Fast gate command: `python tools/env/run.py run -- python3 tools/ci.py --tier fast --output build/t13/faithful-f/ci-fast`. Fast tier **failed (partial tier run)**, measured 426.823 s to stop; 15 commands passed, failed at integrated-timing. Full tier **not run this continuation**. The 10 block tests passed. The failed gate command is the retained registered F default-clock timing check: 25.225288 ns / 24.960000 ns, electrical violations zero. Ten later commands were not run, including the fast-tier faithful profile checks; separate final-candidate receipts above remain distinct. Later unexecuted commands are not passes. Only report, status, ledger and README documentation changed after the gate; the post-report structure and diff checks pass. No commit/push was made because the verification condition was not met.

No timeout triage or new induction machinery was needed: the focused ISA jobs finished in
measured 69.410 s total, and the integration job returned a counterexample.
Independent review ran manifest (10), performance (5), and checker/graft (8)
unit tests, reviewed RTL, and checked the counterexample without another proof.
The root agent reviewed the reviewer's hash/label fixes independently.

## Numbers

Timing is **measured**, mapped pre-layout, GF180 7t5v0 SS/125C/3.0V,
Yosys 0.71+34/OpenSTA 3.2.0, ideal clocks, without routed-wire/SRAM signoff.
The unchanged 60% rule yields 66.666667 ns at 9 MHz; excess is **derived**
67.791702 - 66.666667 = 1.125035 ns. Critical path: instruction bit 4 to
integer RF bit 350. ABC optimization target remains 62500 ps.

Each performance build measures 120 complete iterations against QEMU, using
the existing ideal one-cycle memory fixture without interrupts or external I/O.
The integer-only and F-enabled faithful builds have identical fixed-point
cycle results. Time is **derived** as cycles / MHz; it is not silicon timing.

| Build | Mean / worst at 12 MHz (us) | Mean / worst at 24 MHz (us) |
| --- | ---: | ---: |
| Fixed, either faithful profile | 323.316 / 362.500 | 161.658 / 181.250 |
| Faithful F, hard-float | 1028.222 / 1186.083 | 514.111 / 593.042 |

Smoke retirement spacing (measured, both faithful profiles): MUL 3 cycles;
MULH/MULHSU/MULHU 4; DIV/REM mean 25.333, range 2-37; DIVU/REMU 37.
These are instruction retirement intervals including fetch/pipeline effects,
not isolated unit latencies or exhaustive worst-case bounds.

## Deviations from the brief

This is an explicitly scoped continuation, not T13 completion. No default
production clock/profile changed; registered profiles have not been retired.
The full ISA/full tier was not run, consistent with avoiding another long sweep.
The existing integration monitor was adapted; no new instruction-specific
monitor, induction argument or composition script was introduced.

Earlier candidate timing failures (75.550880 and 67.434258 ns) and the
direct-read emission's 64.900009 ns pass remain under `build/t13/faithful-f/`.
The latter omitted interface-preservation annotations; it is not the final
qualified emission and is not accepted in place of the final timing failure.
Early local/unchanged equivalence attempts with isolated leaf port views were
blocked; packaging actual integrated hierarchy views repaired that tooling
mismatch, following existing production-view comparison practice.

## Open issues

1. Resolve the exception/cancellation counterexample under the unchanged
   property and bus contract. First replay the control trace concretely; do
   not assume unsolicited errors away or call the current assertion proved.
2. Close final faithful-F timing at the approved trial point. No clock/budget
   relaxation or further pipeline redesign was made.
3. Hard-float flight loop misses 1 kHz at 9 MHz in the ideal fixture. Fixed
   point is fast enough in this fixture; system-level acceptance still needs
   I/O/interrupt/memory overhead and timing closure.
4. Integration concrete controls, complete ISA acceptance, final production
   adoption and full CI remain open. Keep T13 blocked.
