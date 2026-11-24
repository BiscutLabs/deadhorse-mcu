# Lite-core formal evidence

T25, main `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus dirty source hashes.
Each result is limited to its receipt's source/artifact hashes. No CI.

## Contracts and proof separation

`ClockedCore` is the faithful pinned clocked adoption. Its exact named-state
equivalence checks every register/reset/init/next-state/output, with no state
exclusions or assumptions, using existing `dv/core/state_equiv.py` tooling.
Measured `build/t25/state-equivalence-first`: PASS, 31 state elements/723 bits,
three actual output/reset/next-state faults rejected. Baseline simulation is
independent ISA/bus comparison, not source-text matching.

`LiteCore` is the production extension; baseline equivalence does not qualify
it. Adapter and core-control proofs establish interface safety with arbitrary
inputs, initially asserted and then arbitrary reset, one digital clock. They
do not establish CSR, interrupt entry/return or complete instruction semantics.
No memory fairness, fixed instruction stream or restricted operand assumption.

Measured historical receipts: `formal-baseline-first/adapter` proves ten
assertions with five covers and a returned-data fault. `formal-control-first`
proves nine assertions in 1.47 s, with six covers and the held-address IRQ fault.
The control source later gained a no-op next-PC fault hook; fresh current-source
receipts are required before accepting current qualification.

## ADDI timeout triage

Measured by `formal/instructions.py` and `scratch/t25_triage.py` (both through
the pinned environment). The checker uses unmodified pinned riscv-formal
semantics, aligned physical memory lanes, explicit RVE high-register legality
and the actually accepted memory-error response. Fourteen all-cycle assertions
remain unchanged; no startup-window restriction or input assumptions beyond reset.

| Step-0 measurement | Result |
| --- | --- |
| Prepared model | 1102 cells, 100 FF cells / 1204 FF bits, no memories |
| Requested/reached | Unbounded ABC PDR, depth32 for induction/cover witnesses; PDR stalled at frame3 |
| Original result | TIMEOUT at existing120 s solver cap, no counterexample |
| BMC growth, unchanged assertions | depth8 PASS 0.566 s; depth16 PASS 1.116 s; bounded diagnostics only |
| Concrete covers | Both successful and trapping ADDI reachable first at k6 |
| Concrete negative | Actual next-PC corruption rejected by the intended PC assertion |
| Unneeded state for instruction semantics | RF storage/history and counter/control paths feeding arbitrary operand values |
| Rung1 | Same-model ABC PDR + Z3 induction portfolio, TIMEOUT at same cap; no reachable counterexample |
| Rung2 | Bound reduction cannot close this unbounded obligation; no acceptance change made |

Rung3 freed only the fifteen exact, disjoint 32-bit RF outputs,
shared across every fanout, while preserving control, operand snapshots and
response/error tracking. Independent review accepted this as a sound data
overapproximation: every original trace is still included. Concrete covers
and faults stay on the real model. A pass would establish abstracted instruction
semantics only, not RF consistency or full ISA qualification. Measured
`python scratch/t25_triage.py --cut`: **TIMEOUT**, 121.861 s wall time under
the unchanged120 s solver cap. The pre-cut inventory binds each of the fifteen
32-bit nets to its actual `$aldff` Q driver; pre/post models and config hashes
are in `build/t25/rvfi-cutpoints`. Z3 failed induction on trap/data obligations;
this is an arbitrary induction-state witness, not a reachable design failure.
No proof is claimed. Stop after original, portfolio and reviewed data-cut
attempts; do not repeat an unchanged timed-out model.

Model-phase distinction: measured `before.json` is before `async2sync`, with
916 cells/1173 FF bits; `after.json` is after conversion/cuts/cleanup, with
952 cells/722 FF bits. The step-0 1102-cell/1204-bit number is a different,
prepared concrete stage. These are not directly comparable area figures.
Independent review checked fifteen 32-bit `$anyseq` drivers, shared fanout,
all fourteen assertions, sole reset assumption and config/source/artifact hashes.

The next useful proof change is a small, separately discharged retirement
lemma tying the instruction/operation/error and saved operands to the response
that produced RVFI. It would strengthen induction without assuming the desired
claim. Helper-invariant work is rung6 and is not authorized by these timeout
results; the current sequence stops without adding one or changing RTL.

LW and other instructions were not reached by the fail-closed runner. CSR,
RF consistency, instruction-fetch correspondence and interrupt architecture
remain distinct open obligations. Directed ISA/machine/loader tests are
simulation evidence, not formal closure.

## Frozen current-source checkpoint

Measured pinned commands:

- `python hw/ip/lite_core/formal/check.py --cases adapter control --output build/t25/formal-frozen`:
  PASS ten adapter and nine control assertions, all eleven covers and both
  actual fault controls. Positive wall times 0.416 s and 1.267 s. Sole initial
  reset restriction, otherwise arbitrary digital inputs/reset; no data cuts.
- `python hw/ip/lite_core/formal/state_equivalence.py --output build/t25/state-equivalence-frozen`:
  PASS all 31 baseline state elements and public outputs, no assumptions or
  exclusions, 0.153 s; output/reset-value/next-state faults rejected.
- `python dv/soc/check_lite.py --output build/t25/frozen01`: PASS 28 simulation
  tests in nine suites, provenance/map/structure and four complete top emissions.

Independent review verified current source/artifact inventories: control 44/237,
baseline 47/53, functional 1131/604, and identical real-hart/start/reset/ownership
bindings in all four top profiles. Current-source mapped timing also passes;
see the timing ledger. This clears the limited RTL/functional/control checkpoint,
not architectural or physical acceptance. The ADDI obligation above remains
unresolved. No CI, commit or push.

## PLAN03 focused debt attempt — 2026-11-22

Measured by `python tools/env/run.py run -- python dv/soc/plan03_debt.py --case lite --output build/plan03/debt01/lite`.
Unbounded solver PASS indices: [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]; unresolved: [4].
Fresh concrete models match all historical variants. Original assertions,
assumptions, depths and120-second caps remain. No helper or unchanged retry.
Exact per-assertion times, model sizes, fault limitations, historical evidence
audits and next scoped work are in [the debt report](../spec/soc-verification-debt.md).
Indices6 and9–12 are trivial ADDI memory predicates, not ISA coverage.

## T39 focused simulation regression — 2026-11-24

D89 simulation evidence only; no new proof or original assertion discharge.
At code `fa21f70fafb9b9bf48cdfc2f97b5ce0a17ff496f`, the exact `tools/sbt.py
hw/testOnly` command in the [report](../plan/tasks/reports/T39.md) passes
measured 29 cases: LiteBaseline 3, LiteHart 4, LiteMachine 3, LiteDebug 3,
SocLite 2, SocBootRelease 2 and SocClockReset 12, with no failed/skipped cases.
Fresh XML/source receipts are in `build/t39/focused01/result.json`.
Existing corruption/START/release-binding controls remain. Loader/boot fixtures
retain their USB-stub/external-clock diagnostic scope; SocClockReset uses the
production clock/reset wrapper with behavioral analog models. Lite IRQ oracle
alignment still follows the DUT boundary. New external RV32E ISS qualification,
full ISA/machine proof and all prior unresolved obligations remain open.
