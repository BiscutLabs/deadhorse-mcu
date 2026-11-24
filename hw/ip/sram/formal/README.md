# SRAM formal evidence

T35/D90 uses the existing 120-second solver cap. A timeout is deferred and
unproved; neither aggregate CI tier runs for this task. Simulation is separate
evidence, not a substitute proof.

Run in the pinned environment:

```sh
python hw/ip/sram/formal/check.py --output build/t35/formal-new
python hw/ip/sram/formal/ownership.py --output build/t35/ownership-new
```

Do not rerun an unchanged timed-out job. The current receipts are
`build/t35/formal02/result.json` and `build/t35/ownership04/result.json`.

| Property | Model and assumptions | Evidence / limitation |
| --- | --- | --- |
| Byte-lane/address/control pins | Actual ASIC word wrapper, arbitrary inputs; initial reset only | Unbounded ABC PDR pass, 20 assertions; wrong-lane fault rejected; both covers reached. This checks macro inputs, not physical Q behavior or whole-SoC banking |
| Read data and latency | Full 1024-word digital model; arbitrary initial RAM; symbolic observer address constant per reset epoch, never constraining DUT inputs | Four assertions unresolved at 120 s; full/partial-byte covers reached. No macro-model equivalence or full-size proof claimed |
| March operation coverage and exclusivity | Eight-word production generator, arbitrary read data/run/permission, initial reset only | Unbounded PDR pass, six assertions; early-completion fault rejected, good/bad completion covered. Full 4096/768-word traversal is separately simulated |
| Destructive-test ownership | Full-size manager and agents with actual shared reset/synchronizer/FIFO, arbitrary independent clocks and read data, common cold/pin reset initially asserted | Two covers and missing-reset-hold fault pass; unbounded PDR attempt times out. Memory data is outside this control claim; production mux/CDC/RDC composition remains unproved |

The initial ownership assertion incorrectly required the delayed reset ACK to
remain true continuously. `ownership03` preserves its counterexample: the ACK
can briefly contain an earlier release while the acquired hold keeps both actual
service resets asserted. Independent review approved checking those actual
resets instead. Entry still requires the ACK. Functional logic and all existing
assertions outside the new T35 block are unchanged. Earlier `ownership01/02`
are tooling failures (multiclock lowering and hierarchical fault-name parsing),
not solver passes.

All results assume ideal digital sampling. They do not qualify metastability,
analog SRAM behavior, physical retention, placement, power rails or reset trees.
The result receipts retain exact sources, emitted model hashes, commands,
engines, witness artifacts and timings. Full-size array/mask/operation-oracle,
JTAG ownership and fault-status tests are described in the task report.

## Timeout triage

Only one solver attempt on each final positive formulation is spent. The user
requested deferral instead of extensive timeout work; no portfolio, reduced
bound, extra assumption or timed extension was used. Quarter/half-depth growth
runs are therefore not run; the existing basecase log supplies the observed
growth. See the T35 report for prepared-model sizes and measured times.

Data induction needs a proved relationship between the symbolic byte observer
and the actual RAM entry, rather than an arbitrary unreachable induction state.
Ownership needs a separate proved control lemma for remote release/FIFO
completion before combining the full-size counters. These are proposed next
proof steps, not assumed facts or permission to expand the campaign.
