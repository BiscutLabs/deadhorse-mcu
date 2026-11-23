# Debug proof scopes

Run through the pinned environment. Receipts and counterexamples stay under
`build/t32/`; the task report identifies the exact commands and snapshots.
No receipt from an older source snapshot establishes final T32 acceptance.

| Runner | Claim and environment | Scope limit |
| --- | --- | --- |
| `check.py` | SBA stable payload, route ownership, one response and cancellation; DM memory origin/selected-hart checks. Initial reset, arbitrary subsequent reset/inputs. | SBA `targetQuiet` is an external contract, not a proof of system composition. |
| `transport.py` | Actual shared request/response FIFOs with independent TCK/main clocks and reset epochs. One outstanding DTM request and one DM response per accepted request are modeled structurally. | Digital sampling only; no metastability or liveness claim with stopped clocks. |
| `epoch.py` | Actual SBA, routing helper, main/AON BusFabric, BusBridge, DirectionPermit and drain credit, with production timeout values. One legal delayed/error echo endpoint. | Single-master retained path, not complete production arbitration or retained-memory contents. Unresolved until all properties, covers and fault controls close. |
| `command.py` | Actual adopted two-hart command controller: captured selection, stable ownership, cancellation/reset priority and per-hart status clearing. Initial POR only; arbitrary later inputs. | Sampled single-clock `dm_mem` proof, not complete CSR/transport composition. |
| `tap_equiv.py` | Pristine and extracted TAP/DTM equivalence at the original CDC seam, with pre-cut pin/alias/polarity audit and concrete TDI fault. | Both TCK edges and asynchronous reset retained; does not equate the original CDC to its shared replacement. |

## TAP reference preparation

The production import intentionally omits upstream CDC implementation files.
The frontend equivalence runner needs pinned reference checkouts only to elaborate
the original CDC declaration before removing that instance. Prepare these once,
from the repository root in the pinned environment, using fresh destinations:

```sh
git clone https://github.com/pulp-platform/riscv-dbg.git build/t32/riscv-dbg
git -C build/t32/riscv-dbg checkout --detach 643607e19df3435cfd77cc56143e2637f5900a6e
git clone https://github.com/pulp-platform/common_cells.git build/t32/common_cells
git -C build/t32/common_cells checkout --detach b5ec8905ed7828655155b0ae971023adf793c600
python hw/vendor/riscv_dbg/prepare.py
python hw/ip/debug/formal/tap_equiv.py --output build/t32/tap-equivalence-fresh
```

The runner verifies commit IDs and every consumed reference file against its git
blob, normalizing only CRLF. It also checks original and applied production files
against the vendor lock. No checkout source is imported into production.
Existing checkout directories must be verified, not overwritten. Output must be
a new directory under `build/`. `tap-equivalence06` is the independently accepted
run: its fault is an edge-aware arbitrary-input witness, including variable
testmode, rather than a constrained normal-JTAG setup/hold trace.

## Reset composition

The default-disabled vendor extension has a separate reproducible check:

```sh
python hw/ip/debug/formal/vendor_equiv.py --output build/t32/vendor-equivalence-fresh
```

It verifies the locked pristine sources and patches, materializes the candidate
only under `build/`, and compares against pinned `dm_mem` with its two identical
reset branches regrouped. The regrouping moves disjoint assignments without
changing their event or reset condition. This is sampled `async2sync`
equivalence with the extension disabled; enabled-extension properties and the
replacement transport are checked separately. It does not claim analog reset
or CDC equivalence.

The composed harness assumes only initial POR. Clock levels, later POR, service
resets, offered payload/mask, endpoint delay/error and other busy/permit inputs
are unconstrained. The producer has one outstanding DM request; the endpoint
responds at most once to an accepted beat. There is no fairness assumption and
no assumption that quiet means globally empty.

Epoch claims cover: one SBA response, current-request read data, local reset
cancellation before result commit, bridge remote-reset cancellation before its
result commit, error propagation, source dispatch/payload, transport-ticket
dispatch/payload, and downstream fabric dispatch/payload. Both production
`SocDrainCredit` assertions and both `DebugSba` assertions remain enabled.
The fabric monitor records its committed registered grant and preceding offered
payload: a transport flush can withdraw req after capture but before grant.
An already committed write may finish once after cancellation; cancellation
does not roll back side effects. A reset after a result was committed cannot
retroactively invalidate that result.

Faults corrupt returned data, lose a canceled response's error bit, and restore
the lost-credit binding `req && gnt`. The latter is a real defect found by the
composed proof, not a hypothetical mutation. The corrected production binding
counts the BusFabric grant independently of the now-withdrawn req. Covers
retain the withdrawal/grant race, old active target during main reset, successful
completion, cancellation, and admission while older target work survives.

The reset experiment does not inherit T14's deferred full return-data proof or
claim its short watchdog model proves the production watchdog. `epoch.py` uses
the actual production values (main fabric 131080, bridge 131072, AON fabric 128)
and the unchanged 120-second job cap. Timeouts remain unresolved; triage must
follow the repository skill budget with no unchanged timed-out reruns.

## Production debug entry and loader ownership

```sh
python hw/ip/debug/formal/ownership.py --replay build/t32/replay02 \
  --output build/t32/ownership-fresh --roles entry loader lite perf
```

`DebugOwnership.scala` supplies input-only observers. The runner authenticates
the replay's production source inventory and hierarchy, flattens that exact
hierarchy, and binds observers by checked signal identities and widths. Removing
the observer cells must recover the original graph exactly. The selected
production control cells retain their original pins and transitions; omitted
neighbour outputs become arbitrary inputs. This is a sound overapproximation,
not an assumption about neighbour behaviour. Physical clock-gate outputs are
also arbitrary clock inputs; no analog clock or metastability claim is made.

| Role | Guarantee |
| --- | --- |
| `entry` | A pre-boot performance fetch permit requires observed debug entry; the debug-only fetch permit requires ownership. The entry observation clears with the performance reset epoch. |
| `loader` | Debug ownership cannot supply the loader's halted permission or authorize a loader write. Inhibited mutating frames cannot create START, begin new work from idle, or change idle image metadata. Already accepted writes may drain. |
| `lite` | Debug entry alone cannot clear the loader's `notStarted` state. No application retirement occurs before a START request or actual debug entry in the reset epoch. |
| `perf` | The actual performance-core instruction-request and retirement outputs remain inactive before the first normal boot permit or actual debug entry in the core-reset epoch. This does not claim full ISA correctness. |

The only initial-state assumption is cold reset asserted at the first sample;
later resets, clock levels and exposed boundary inputs are unconstrained. There
are no fairness or unproved helper assumptions. Every job retains the existing
120-second cap; cover depth is 48. Interface covers demonstrate reachability in
these isolated control models. Public-pin OpenOCD reset/halt/loader tests provide
the separately recorded production integration evidence.

Actual-DUT negative controls bypass the pre-entry fetch mux, remove the retained
loader-permission gate, ignore loader frame cancellation, clear lite
`notStarted` without START, and force a performance retirement before entry.
The runner requires concrete counterexamples at the intended observer claims;
compile failures do not qualify. Sources, graphs, bindings, cut boundaries,
mutations, property inventories and solver artifacts are recorded in each
receipt. The focused results do not discharge the separate SBA epoch read-data
obligation or physical-flow obligations.

`build/t32/ownership05/result.json` records the safety proofs and all faults.
Its original Z3 performance-cover timeout remains unresolved in that immutable
receipt. The one authorized engine-only triage rung is recorded separately in
`build/t32/ownership-perf-cover06/result.json`: the exact same model, depth and
cap with Yices/BTOR cover engines. BTOR reached both goals with concrete traces.
Together these receipts discharge the focused safety, cover and fault checks;
no timed-out job was rerun unchanged. The portfolio's exact producer and SBY
configuration are archived beside its receipt. For subsequent replay use that
winning portfolio for the performance cover job rather than retrying the
unchanged Z3 timeout. Neither receipt closes SBA read-data composition or CI.

The maintained runner now selects that qualified portfolio for performance
covers. The fresh standard invocation in `ownership06` passes all roles,
including every cover and fault, in one receipt. `ownership05` and the separate
triage receipt remain immutable history.

`DebugFifoOracle.scala` supplies the independently qualified actual bridge-FIFO
sequence helpers. `DebugEpochLinks.scala` contains **unproved candidate** stage
invariants from the scoped experiment; none is an accepted premise. Exact
recipes and limitations are archived under
`hw/top/reference/measurements/t32/evidence_replay/epoch/`. These do not replace
the original epoch assertions or make `epoch.py` an accepted aggregate.
