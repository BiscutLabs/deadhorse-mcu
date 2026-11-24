# Oscillator and reset formal evidence

PLAN04, measured with the pinned environment on `2c33976` plus receipt-hashed
working-tree sources. These are partial component results, not full production
clock/reset composition acceptance. No CI tier is implied.

| Claim | Command (prefix `python tools/env/run.py run -- python`) | Result and assumptions | Negative control |
| --- | --- | --- | --- |
| Digital reset selection, minimum AON release and frozen AON strap | `hw/ip/osc_ctrl/formal/reset_check.py --output build/plan04/reset-formal01` | Three unbounded ABC PDR jobs. Both static D84 bypass choices checked; reset/strap jobs start with pin reset, then reset/selection inputs arbitrary. Both AON inputs share one proof clock. Separate POR initial-state job assumes no initialized state or pin-reset pulse. Covers both AON strap positions in both modes. | Cold reset bypass, changing frozen strap and premature release, each in normal/bypass modes, rejected. |
| AON policy safety | `hw/ip/osc_ctrl/formal/check.py --policy-only --output build/plan04/formal-policy03` | Unbounded ABC PDR; only initial reset constrained. Policy inputs/source reports otherwise arbitrary. Broad source seal predates the later counter repair; historical policy evidence until frozen refresh. | Lost wake, refused/early gate, ignored hold and reset-low OSC_EN rejected. |
| Stability-counter timing repair | `hw/ip/osc_ctrl/formal/stability_equivalence.py --output build/plan04/stability-equivalence03` | Unbounded ABC PDR comparison with original arithmetic; all output cycles equal for arbitrary count/request/reset/OSC_EN after initial reset. Stable cover reached. | Wrong decrement rejected. |
| Divider source-edge pulse widths and progress | `hw/ip/osc_ctrl/formal/divider_check.py --output build/plan04/divider-formal03` | Six assertions proved by ABC PDR. Monitor-only initial reset; DUT initial phase/reset arbitrary. Qualified high phases are three source edges, reset can extend low, and sustained reset release requires continuing divide-by-six operation. Both covers reached. | Wrong production terminal predicate rejected. |

Every solver job retains the 120-second cap. Receipt files contain measured
per-job wall times, model/source hashes and artifact hashes. Reset, stability
and divider results received independent review; policy requires a final seal
refresh. The first divider run stopped on a checker assertion-count guard
(two monitor-init constraints, not one); no solver result was claimed. The
second divider run proved pulse widths; the third strengthened it with progress
to exclude a stuck-output implementation. No timeout was rerun unchanged.

Additional intermediate results, measured on the same base commit with each
receipt's source hashes (not a frozen acceptance snapshot):

| Command (same prefix) | Result | Limits |
| --- | --- | --- |
| `hw/ip/osc_ctrl/formal/composition_check.py --output build/plan04/composition02` | Historical, before command/completion FIFOs: actual policy/source/ICG freshness ABC PDR PASS, 1.27 s; early authorization and stale epoch faults rejected; all three covers reached. | Initial reset only, independent arbitrary clocks and local/policy demands. Does not qualify current negative controls or shutdown closure. |
| `hw/ip/osc_ctrl/formal/clock_contracts_check.py --output build/plan04/clock-contracts01` | Actual local gate acknowledgement PDR PASS, 0.27 s; shared-FIFO count delivery/hold PDR PASS, 0.77 s. Gate, data and premature-stable faults rejected; covers reached. | Aggregate unresolved: full-width minimum count assertion timed out. Later independent-input oracle correction requires refreshed delivery evidence. |
| `sby -d build/plan04/count-edges-portfolio01 build/plan04/count-edges-portfolio01.sby` | Same prepared count assertion, Yices/Z3 portfolio: TIMEOUT, 121 s wall time, unchanged 120 s solver cap. | Failed induction state is not established reachable; no reachable design counterexample was produced. |

The full-width count assertion remains **unresolved**. Step-0 triage:

| Measurement | Measured evidence |
| --- | --- |
| Prepared model | 238 cells, 153 `$ff` bits plus 149 `$anyinit` bits after `clk2fflogic`, no RAM; `yosys -s build/plan04/count-edges-stat.ys` |
| Initial engine | ABC PDR, unbounded; 121.20 s wall time at 120 s cap |
| Alternate engine | Yices/Z3 induction with depth 128, same assertion/model; timeout. Yices base case reached step 67 at 91 s; Z3 reached step 56 at 94 s. |
| Witness | Count zero and count nine stable covers reached by BTOR, longest witness 62 global steps; 0.77 s total cover job. This is not a worst-case latency bound. |
| Growth / unnecessary state | Single-run logs retained; no unchanged quarter/half reruns. Wide countdown and independent elapsed counter dominate; divider and gate logic outside the assertion cone are removed by `opt_clean`. |
| Next proposal | Prove accepted-count/remaining-count/elapsed-edge invariants, then discharge the unchanged assertion. Focused 30-minute rung-6 attempt requested; awaiting approval. No extra assumption or solver-cap change proposed. |

The first freshness cover attempt timed out with Z3; changing only to the
BTOR/Yices cover portfolio reached every witness. Its unbounded positive PDR
proof was already passing. Receipt hashes preserve the exact models, commands
and artifacts. The final checker must refresh these after source freeze.

Still open: complete policy/source/ICG shutdown composition, minimum full-width
stability count, final formal aggregation and physical
clock/RDC qualification. Production wake/retention simulations now pass.
The default block checker deliberately rejects full acceptance while these
composition checks are absent. Shared-primitive proofs and focused simulations
do not silently discharge those obligations.

`composition_check.py --closure --output build/plan04/closure-composition01`
rejected the false-closure fault, then found a positive counterexample at global
step 120 (ABC PDR, approximately 3 s measured). A delayed closed report from a
previous stop can be accepted after reopening. The exact trace includes live
idle transitions not yet bound to production, so it is not claimed as a
production firmware failure. Independent review nevertheless identified that
`closurePending` does not authenticate the current close transaction. A stable,
serialized close/acknowledge/reopen/acknowledge protocol was selected and
implemented as the local repair below. The original assertion and arbitrary-clock model remain.

The repair uses shared command/completion FIFOs with one command outstanding;
source closure stays latched until an explicit open, and busy/late-demand closes
are rejected. Cancellation keeps the original immediate RUN/peripheral-service
behavior. The corrected source and boundary tests pass; the old gate-reset-only
mutation is now contained by the FIFO reset. Its positive containment regression
is retained, and a direct final-enable bypass still fails the unchanged
`EARLY_EPOCH_CLOCK` check. No non-failing mutation is reported as rejected.

Post-repair shutdown triage stopped at its three-rung budget:

| Attempt / command (pinned Python prefix above unless `sby`) | Measured result |
| --- | --- |
| `composition_check.py --closure --output build/plan04/closure-composition02` | Bad-ACK fault search PDR timed out at 120 s; no positive result. |
| `composition_check.py --closure --output build/plan04/closure-composition03` | BTOR/Yices fault portfolio rejected bad ACK; positive PDR timed out at 120 s. |
| `scratch/plan04_closure_portfolio.py` | Rung 1: identical positive model, Yices/Z3 portfolio, TIMEOUT at 120 s; induction failure is not a reachable counterexample. |
| `composition_check.py --closure --abstract-startup --output build/plan04/closure-composition04` | Added explicit registered-hold safety assertion. Real bad-ACK fault fails the intended gate-low assertion in 77.86 s; ignore-source-hold fault unresolved at 121.27 s wall time. No fault qualification claimed for it. |
| `scratch/plan04_closure_portfolio.py abstract` | Rung 3: positive-only startup cutpoints, PDR TIMEOUT at 120 s; exact cutpoint names/widths audited. |
| `scratch/plan04_closure_portfolio.py split` | Rung 4, final allowed rung: one assertion per job with `opt_clean`. Fresh qualification and OSC_EN on each actual new main edge PASS unbounded; gate-low during OFF and no stranded registered main hold both TIMEOUT at 120 s. Aggregate unresolved. |

Step-0 data, measured with `scratch/plan04_closure_portfolio.py stats`:

| Model | Cells | `$ff` bits | `$anyinit` bits | RAM |
| --- | ---: | ---: | ---: | ---: |
| Full three-assertion model | 909 | 278 | 265 | 0 |
| Startup-cut four-assertion model | 863 | 230 | 216 | 0 |
| Each remaining isolated shutdown assertion | 854 | 227 | 216 | 0 |

All jobs keep the 120-second solver cap. The full PDR log reached frame 155;
the alternate Yices base case exceeded step 125 while Z3 reached step 52.
Single-run logs preserve growth data; no unchanged quarter/half reruns were
made. Current real-model covers have **not** run because the fault search stopped
the aggregate. Historical pre-repair covers do not qualify this implementation.

The positive abstraction replaces exactly `boundary.counter.stable` (1 bit),
`policy.elapsed`, `policy.delay` and `policy.timeout` (16 bits each) with
unconstrained values; gate/CDC/control/hold/reset logic remains real. These
choices include all original traces, add no assumptions, and prove neither the
startup duration nor minimum source count. The independent count proof remains
unresolved above. Exact identities/widths are recorded in
`build/plan04/closure-abstract01-audit.json`; the two passing split results are
labelled **abstracted safety proofs**, not full acceptance.

No further shutdown proof attempt is authorized by the triage ladder. The next
candidate is a separately proved command/completion ownership and latched-source
closure invariant, then composition with the unchanged assertions. That is helper
invariant work requiring a scoped approval; a single 30-minute attempt has been
requested and has not been run. Formal/default block acceptance remains
fail-closed: `check.py --output build/plan04/formal` rejects full acceptance
before launching a solver (`formal-acceptance-status01.log`). Production wake
coverage, the 114-test SoC/oscillator suite and paired flight-loop retention
checks now pass. Frozen `build/plan04/frozen-fast02/result.json` passes all
34 fast steps with 12 pre-existing T14/T17 deferrals, measured 3886.079379 s;
it does not close these oscillator proofs. The prior fast attempt's independent
register-checker timestamp error and unchanged successful retry are preserved
in the PLAN04 report. Full-tier CI has not run; no commit/push or whole-chip
physical signoff is claimed.

## Dedicated reset causes

Measured command on `2c33976` plus the receipt-hashed working tree:

```
python tools/env/run.py run -- python hw/ip/osc_ctrl/formal/reset_causes_check.py --output build/plan04/reset-causes04
  -> normal-correct proved; bypass-correct proved
  -> six fault_rejected; normal-cover covered; bypass-cover covered; PASS
```

ABC PDR proves cold clear, valid encoding, required pin/held-brownout capture,
sticky causes and no pin/brownout cause without raw-source history. Capture
obligations begin after two AON cold-release edges; cold reset takes
priority and clears cause history. Brownout's three active edges begin after
that qualification. Measured
positive job wall times are 0.365824 s normal and 0.265190 s bypass. Six actual
input mutations fail the intended assertions; all seven covers are reached
within the existing 24-global-step search. Each job retains its 120-second cap.

Assumptions are initial raw cold reset followed by arbitrary resets and inputs,
and static D84 bypass, exhaustively checked both ways. A separate initialization
signal affects cover history only. AON/observer/pin edges are independent;
there is no frequency, fairness or held-brownout assumption. The brownout
holding interval is an assertion antecedent, not an environmental restriction.
No helper is assumed and no RAM or functional state is abstracted.

Review strengthened the original capture checks with raw-source upper bounds
and two spurious-cause faults. The initial pulse covers allowed pin release on
an AON rising edge; the final cover instead records a completed pulse while
the AON epoch is still unchanged, then reaches cause capture. Receipts 01–03
are historical intermediate evidence, not the final short-pulse witness.
Independent review checked all eight source hashes and 394 artifact hashes,
both proofs, intended fault identities and the actual sub-AON pulse waveform.
This is digital cause-recording evidence, not analog qualification or complete
clock/reset composition. The new harness/runner postdate frozen fast02;
production RTL is unchanged, but final frozen qualification must be refreshed.


## T33 local refresh and reset-demand extension

Measured on `2c33976` plus the source-hashed T33 tree:

```
python tools/env/run.py run -- python scratch/t33_local_proofs.py
  -> PASS policy; PASS divider; PASS bootstrap; PASS causes
  -> PASS reset-cell; PASS gate-emit; PASS gate-formal; PASS gate-timing
```

`build/t33/local-proofs01/result.json` records the exact underlying commands.
Policy uses `formal/check.py --policy-only --output build/t33/policy01`; divider,
reset and cause drivers write `divider01`, `bootstrap01`, and `causes01` under
`build/t33`. Their unbounded jobs, original faults and covers pass. The policy
now receives arbitrary local `forceRun` and includes it in the unchanged
shutdown-demand obligation. Initial reset is asserted; later policy inputs/reset
remain arbitrary. Existing reset/divider assumptions stay in their receipts.

The separate reset-demand extension and keyed threshold proof are recorded in
[the power/reset ledger](power-reset-formal.md). These establish policy behavior
when the synchronized request is observed; they do not assume or establish the
service-reset/configuration crossing's whole-system composition.

`reset_cell_check.py --output build/t33/reset-cell01` passes functional simulation
of the mapped production ResetBootstrap and actual unfrozen-selector mutation
against unchanged pinned GF180 cell models. Both clock-source and static bypass
choices are exercised, with pin and supply reset assertion/recovery. This is
finite functional evidence, not physical pulse-width, metastability or analog
qualification. Fresh shared gate proof and main-period timing pass using
`build/t33/gate-emit01`; the timing receipt keeps its assumed slew/load and
pre-layout scope. Measured clock propagation is 1.896664 ns and minimum enable
slack is +0.624586 ns, with no electrical violations, from the gate-timing command
listed in the batch receipt.

The exhausted minimum-count and shutdown-composition jobs were not rerun.
D86 (user, 2026-11-24) supersedes the pending helper-attempt requests with
explicit deferral for T33 closeout. They remain unproved; their original
entrypoints, assertions, assumptions and caps are retained. Local PASS results
do not close those claims. T33 task completion with exceptions is separate
from full composition, physical and I3 acceptance.
