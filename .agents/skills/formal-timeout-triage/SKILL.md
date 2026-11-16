---
name: "formal-timeout-triage"
description: "Use when a formal check on a Deadhorse MCU block or core times out, runs for minutes without a result, or before choosing proof depth, engines or abstractions for a large design such as the performance core."
---

# Formal timeout triage (Deadhorse)

A timeout says the model is too hard as posed. It says nothing about the
design and is rarely fixed by waiting. Work down the ladder below in order,
measure at each step, and stop at the budget. Do not build new proof
machinery before the cheap steps are exhausted.

Status: first version. The ladder is standard practice; the repo-specific
commands have not all been run here. Where a real run contradicts this file,
report it so the skill can be corrected.

## Rules

1. Never rerun an unchanged check hoping for a different result.
2. Never add an assumption, delete an assertion, or narrow a property to get
   a result. Splitting into cases is allowed only when the cases are shown to
   cover everything.
3. A timeout is recorded as *unresolved*, never as a pass and never as a
   failure of the design.
4. Changing a bound, a time limit or an acceptance label is a decision for
   the user. Propose it once as a general rule, not per instruction.
5. Budget: at most one attempt per rung, and at most three rungs, per
   property. Then stop and report with the measurement table below.
6. Writing more than two new proof scripts for one property needs the
   user's approval first. Say what they would prove and what they cost.

## Step 0: measure before changing anything (15 minutes)

Record these for the timed-out job and put them in the report:

| Measurement | How |
| --- | --- |
| Model size | Yosys `stat` on the prepared model: flip-flop bits, cells, memories |
| Depth requested, and the step the solver reached | The engine log prints the step it is checking |
| Growth curve | Run the same job at a quarter and half of the depth; record the times |
| Smallest depth at which the cover is reachable | Run the cover alone, increasing depth |
| What is in the model that the property does not need | Arithmetic units, memories, register files, counters |

Read the result:

- Time roughly doubles or worse with each depth step: the bound is too deep
  for this model. Go to rung 2 and rung 3.
- The solver stalls at one step regardless of depth: hard logic at that
  point, usually arithmetic. Go to rung 3 or rung 5.
- Even a shallow depth is slow: the model is too big. Go to rung 3.

## The ladder

### Rung 1: engine portfolio (changes nothing about the proof)

List several engines in the `[engines]` section; SymbiYosys runs them in
parallel and takes the first result. Use every suitable engine in the pinned
environment, for example a BTOR model checker, two different SMT solvers and
ABC. Engines differ by orders of magnitude on the same model: in T11 one
engine passed a check on which another timed out at 600 seconds. Record
which engine won.

### Rung 2: right-size the bound

A bounded check from reset costs more than linearly in depth times model
size. Do not give every property the window that the slowest operation
needs.

- For each property or instruction class, the window is the smallest depth
  at which its cover is reachable, plus a fixed margin stated in the plan.
- Long-latency operations (iterative multiply, divide, floating point) get
  their own longer window and their own checks.
- This changes acceptance, so it needs approval as a rule (rule 4). Record
  the window per class in the ledger.

### Rung 3: sound over-approximation (cutpoints)

Replace logic the property does not depend on with unconstrained values. If
the property holds when that logic may produce anything, it holds for the
real logic. No assumption is added, so a pass carries over.

- Free the **data** outputs of units not under check: multiplier, divider
  and floating-point results, performance counters, unrelated CSR read data.
  For an instruction check on a load or an add, arithmetic results of other
  instructions only reach it as register values, which the checker takes as
  given.
- Keep control real: valid, ready, stall and done signals stay as they are,
  unless replaced by a protocol model whose behaviours are proved to include
  the real unit's.
- Large memories and register files: free the read data where the property
  does not depend on stored values, or keep one symbolic entry.
- A failure on the abstraction may be spurious. Replay the trace on the real
  design. If it does not reproduce, put back the piece that mattered; do not
  add an assumption.
- **Covers and negative controls must run on the real model.** A cover that
  is reachable only because a value was freed proves nothing.
- Label the result *abstracted*, and list each cutpoint in the ledger.

### Rung 4: exact case split

Split on a condition of the inputs or the instruction (for example aligned
and misaligned address, or trap and no trap) and check each case. The cases
must cover everything: show it by a trivially true disjunction in the
report. Splitting the set of assertions also helps, but only if unrelated
logic is then removed from each model (`opt_clean` after deleting the other
assertions); otherwise the model is the same size.

### Rung 5: separate arithmetic

If the hard part is a multiplier, divider or floating-point datapath, do
not bit-blast it. Use the decision D44 pattern: an integration check with
the arithmetic abstracted on both sides, an integer-arithmetic lemma for the
algebra, and seeded simulation with injected faults.

### Rung 6: induction with helper invariants (needs approval)

Replace a deep bounded check from reset with a short induction from any
state, strengthened by invariants that are each proved. This is real proof
engineering: it can take days and produce many scripts. Ask first (rule 6),
state the invariants you expect to need, and time-box it.

### Rung 7: more time, once

Only if the growth curve from step 0 predicts completion. State the
predicted time, run once with that limit plus a margin, and record it as a
diagnostic unless the user has approved the limit.

## What to report when the budget is spent

- The step 0 table.
- Each rung tried: what changed, the result, the time, the winning engine.
- The smallest change that would be expected to work, and whether it needs
  a decision (a bound, a limit, an abstraction label, or rung 6).
- The property's status: *unresolved*, with the evidence that does exist
  (simulation, lockstep, covers, faults).

Then stop and continue with other authorized work.

## Design choices that keep proofs tractable

- Every multi-cycle unit has a start and done handshake, so it can be cut
  out of other proofs (rung 3).
- Added latency deepens every bounded proof that includes it. When a timing
  fix adds cycles, expect the proof windows to grow and plan the per-class
  windows at the same time.
- Keep wide datapaths and control in separate modules so control can be
  proved without the datapath.

## Signs you are off track

| Sign | Do instead |
| --- | --- |
| The same check has timed out three times | Stop; write the step 0 table |
| Each attempt adds a new script, monitor or audit for one property | Stop; this is rung 6 and needs approval |
| The time limit was shortened and then treated as fixed | State where the limit came from; compare with the limit earlier results used |
| One depth is used for every instruction | Rung 2 |
| Only one engine has been tried | Rung 1 |
| The report for one task is longer than the design it verifies | Summarize; move evidence to receipts under `build/` |
