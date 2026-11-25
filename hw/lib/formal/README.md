# Hello formal contract

## T41 cancellation fence

`CdcEpochFormal.scala` checks an actual dual-clock, 8-bit/depth-two FIFO with
the production `CdcEpoch` and synchronous-flush mode. The independent queue
oracle checks capacity, overflow, phantom/data/held-head behavior, immediate
cancellation, and acknowledgement that both clocks have run since cancellation.
Only initial reset is constrained; subsequent reset/cancel, data and all clocks
are arbitrary. There is no fairness assumption or analog metastability model.
The six covers include capacity, pointer wrap, held-head delivery and reopening.
Faults remove peer acknowledgement, delay cancellation, or corrupt delivered data.
`python hw/lib/formal/epoch_proof.py --output build/t41/<fresh-directory>` uses
the existing 120-second job cap, ABC PDR safety and SMTBMC/Z3 covers. A safety
PASS is unbounded; covers are finite witnesses. This parameter instance is not
by itself a full-width transport or physical CDC signoff. T41 records the
separate full-width DMI proof and existing bridge proof limitations.

## Hello

`HelloFormal` observes only the DUT ports. It checks zero after a sampled reset
and the previous sample's byte successor while reset stays released.
Its data property uses the inverse predecessor relation and an explicit
wraparound case. The reference history does not assume anything about DUT state.

Assumptions: the initial model step has `reset_n = 0`; subsequent reset and
data inputs are unconstrained. The harness-only `checking` input is false at
step zero (history is not yet defined), then true forever. Each formal transition
represents one rising edge of the single clock. The runner applies these same
constraints using Yosys `fminit -seq reset_n 0,'z -seq checking 0,1` and an
initially-false BTOR2 monitor.
No output or internal-state assumptions are permitted. The initial reset is
required by the block contract, not an assumption added to obtain a proof.

Native CIRCT BTOR2 lowers the reset into the next-state function. Thus these
properties check sampled reset response, not assertion in the same step as a
new reset input. ChiselSim separately checks asynchronous assertion between
edges. Neither route proves analog recovery/removal
timing or a reset synchronizer. The wraparound cover requires reset release,
a previous input of 255, and a zero output, preventing an always-reset proof
from satisfying the coverage target.

Both routes must prove the correct fixture without a depth bound on the result,
reject wrong-increment and wrong-reset variants, and reach the wraparound cover.
BTOR2 uses BtorMC induction; SymbiYosys uses SMTBMC/Z3 induction. The search limit
is eight steps, sufficient for this one-register fixture; exhausting that limit
without induction success is a failure, not a proof. Cover/counterexample traces
are bounded witnesses. BTOR2's cover query negates the cover target as a bad-state
property, since BTOR2 has no cover opcode. Native CIRCT emission is preserved;
the runner only adds the documented initial-input constraint to a separate file.

Run `python3 tools/formal_smoke.py --output build/t07/formal` inside T08. Each run
uses a fresh directory and records commands, versions, hashes, elapsed times,
solver outcomes and witnesses. Missing tools, timeouts, unknown results, missing
properties or unexpected negative-control outcomes fail the command.
