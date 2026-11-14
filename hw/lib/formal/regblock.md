# Register-block formal contract

`RegBlockFormal` generates port-only temporal properties from validated JSON.
It checks all stored-field reset values, preservation and software updates per
bit, hardware set/write priority, read snapshots (including live read-only
fields and reserved bits), command pulse/data, response uniqueness and stability,
and transaction-wide suppression on address/partial-command errors. It observes
no private DUT state. The conjunction is one safety property per fixture.

Assumptions: initial `reset_n=0`, then unconstrained; the harness history monitor
starts at zero and its RTL next value is always one. `checking` exposes that
monitor, so sampled history is defined. No restrictions on
addresses, masks, data, request stability, backpressure or hardware inputs.
Each transition is one rising clock edge. Async reset is checked after a sampled
reset by formal; edge-free reset assertion is tested separately in simulation.
No analog reset recovery/removal or GF180 timing claim is made.

Both format fixtures require unbounded proofs: induction through native CIRCT
BTOR2/BtorMC and PDR through emitted SystemVerilog/SymbiYosys ABC. The native induction search limit is
12 steps (assumed sufficient for the response and one-step history); exhausting
it without induction success is a failure, never a proof. Each route must reject
three deliberate DUT faults: reversed byte strobes, inverted stored reset bit,
and corrupted read data. SymbiYosys SMTBMC/Z3 additionally requires witnesses for every
cover: successful read, partial non-error write, partial-command error, stalled
response, simultaneous hardware/software write, error response, reset while
pending. The last cover observes reset assertion with a previously pending
response: asynchronous reset has already cleared current `rsp_valid`.
Covers/counterexamples are bounded witnesses, not unbounded results.

The native adapter inserts the monitor's initial zero, renumbering BTOR2
references without changing DUT transitions. It also adds an initialized-true
`pastGood` observer, whose next value is `pastGood && !originalBad`, and queries
`pastGood && originalBad`. This detects exactly the first failure on each trace;
existence of a counterexample is unchanged. BtorMC's init-free recheck then has
the preceding safety hypothesis needed for induction. There are no additional
input assumptions. Adapter regressions exercise actual solver outcomes for
first, delayed, repeated and absent failures. Asserted strengthening properties
also check ready/valid complementarity and the startup/history relationship;
neither is assumed.

Run `python3 hw/lib/formal/regblock_proof.py`. Fresh run directories under
`build/t05/formal/` contain a machine-readable proof ledger: command, engine,
kind, result, runtime, commit and input hashes. The T05 report records the durable
summary within its allowed paths; no generated ledger is committed.
