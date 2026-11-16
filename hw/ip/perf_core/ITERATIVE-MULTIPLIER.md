# Iterative multiplier contract

User approval on 2026-11-14 permits additional multiply cycles and new state,
with arithmetic/transaction refinement replacing exact-cycle Ibex equivalence
for this changed block. The faithful `IbexMultdivFast` remains a verification
baseline. Unchanged modules retain their exact equivalence obligations. Whole
core retirement comparison, ISA checks and the 24.96 ns timing limit remain.

`IterativeMultiply` runs on the performance clock with asynchronous active-low
reset. In idle, an enabled edge captures A, B, two independent signed-mode bits
and high/low selection. Enabled edges advance the transaction. After 32 unsigned
shift/add rounds and two signed-high-word corrections, the registered result is
valid. Valid and result hold until an edge with enable and ready. An idle bubble
separates consumption and the next capture. Reset aborts any transaction and
clears all state. Inputs may change after capture. No fairness assumption is
needed for safety; completion requires 34 enabled edges after capture.

The unsigned machine uses a 33-bit addition followed by a fixed right shift;
corrections subtract captured unsigned operands modulo 2^32 from the high word.
Both corrections always execute, including unsigned and low-result operations.
All outputs depend only on registered state. No CSR or clock crossing is added.
Estimated storage: 171 bits (five 32-bit words, five count bits, three state bits,
two sign bits and one high/low bit). Area and timing require measurement.

Verification will combine emitted-RTL next-state/reset/output correspondence to
an independent mathematical transaction machine, integer induction lemmas,
port-only BigInt simulation, reset/stall/backpressure cases and deliberate faults.
Neither an integer lemma alone nor ALTOPS is an arithmetic implementation proof.
