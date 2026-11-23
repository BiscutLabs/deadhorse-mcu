# T32 debug formal evidence

Working tree on `9b80375109826e41d28cae95b1b80c653bfc34ff`; final T32
acceptance is open. Commands below use `python tools/env/run.py run --`.
The [task report](../plan/tasks/reports/T32.md) records the broader checks.
Assumptions and scope are in [the formal README](../../hw/ip/debug/formal/README.md).

## User-directed deferral, 2026-11-23

The user deferred the remaining T32 epoch read-data proof to prioritize timing
(D80). It remains unproved; existing assertions, assumptions, caps, receipts
and fault controls are unchanged. No further composition attempt is authorized
or run by this timing-only follow-up. Deferral does not establish the claim.

## SBA retained-path reset composition

Concrete model: actual DebugSba/routing, single-master main and AON BusFabric,
BusBridge and shared CDC, DirectionPermit, SocDrainCredit and a legal delayed
echo target. Production timeout parameters are retained. POR is initially
asserted; subsequent reset, clocks and inputs are arbitrary. The single-request
DM producer and legal endpoint are structurally modeled; no fairness or quiet
emptiness assumption is added. This is not full production arbitration.

`python hw/ip/debug/formal/epoch.py --output build/t32/epoch05` preserves the
first corrected-model attempt. All jobs hit their unchanged 120-second cap;
none is accepted as passing. Prior epoch03/04 counterexamples found a monitor
error followed by the real registered-grant drain-accounting defect, now fixed.

`python scratch/t32_epoch_triage.py` ran step-0 diagnostics and the engine
portfolio; its exact executed source is preserved in
`build/t32/epoch-triage01/runner.py`. `python scratch/t32_epoch_triage.py partition`
made an exact disjoint split: all original assertions are discharged by the
control group or the one end-to-end data assertion, with no helper assumptions.
Its producer is preserved in `build/t32/epoch-partition01/runner.py`.

| Claim/check | Result | Measured evidence |
| --- | --- | --- |
| Control, cancellation, source/target dispatch/payload and embedded SBA/credit assertions (15) | Proved, unbounded engine portfolio | `epoch-partition01/control.json`: 45.993748 s |
| End-to-end current-request read data (1) | Unresolved | Concrete whole-model and split-data jobs reach the 120 s cap |
| Full original assertion set, depths 24/48 | Bounded only | `epoch-triage01/growth24.json`, `growth48.json`; not a proof |
| All eight reset-race covers | Covered within 96 steps | Concrete BTOR witnesses in `epoch-partition01/covers96`, measured 8.160461 s |
| Corrupted read data | Fault rejected by intended data assertion | `epoch-partition01/fault-data.json`, measured 7.497882 s |
| Lost cancellation error bit | Fault rejected by data/error-propagation assertions | `epoch-triage01/fault-stale.json`, measured 96.910324 s |
| Restore faulty req-and-grant drain accounting | Concrete nested credit assertion fails | `epoch-triage01/fault-credit`, measured 48.566508 s; generic identity parser missed the nested name, independently audited offline |

The independent audit at `epoch-partition01/independent-review.json` verifies
exact model hashes, the disjoint assertion inventory, control proof and all
cover identities. The depth-48 BTOR summary incorrectly lists all covers as
unreached; its concrete witness identities establish seven of eight. Only the
successful SBA-completion cover was absent at that diagnostic depth.

The final permitted rung, `python scratch/t32_epoch_triage.py abstract`, frees
only `f.elapsed[17:0]`, `targetFabric.elapsed[7:0]` and
`bridge.producer.age[17:0]` before clock conversion. Every concrete trace is
included by choosing those values equal to its counters. No fairness/expiry
premise is added; FSM, handshake, reset and data remain. This safety
over-approximation also times out (`epoch-abstract01/data/status`); an induction
counterexample is not a reachable failure. No more data-proof attempts are
authorized by the current triage budget.

Step-0 measured model statistics (`yosys -Q -p 'read_rtlil
build/t32/epoch05/correct/model/design_prep.il; stat'`): 1,407 cells,
209 `$ff` cells and 177 `$anyinit` cells after clock conversion, 15,918 wire
bits, 16 assertions and one initial-reset assumption. Cell counts are not
flip-flop-bit counts. Growth/cover depths and times are retained in the JSON
receipts. The remaining data cone contains both real CDC memories and the
epoch-associated payload/response registers; control assertions alone do not
establish their relational invariant.

Smallest proposed further proof work: an independently proved, reset-qualified
data/ownership invariant at the intervening fabric/FIFO boundaries, bound to
the identical emitted model before use. This would be a new lemma attempt;
the present ledger does not assume it or claim closure.

## Adopted command ownership and reset priority

`python hw/ip/debug/formal/command.py --output build/t32/command03` passes on
the current uncommitted T32 source. The actual patched `dm_mem` uses the
production parameters (two harts, 32-bit bus/access, base 0x10000 and enabled
hart-reset extension). All input payloads/control are arbitrary; only initial
POR is assumed. This is sampled single-clock safety, not a whole-DM/CDC proof.

The six assertions prove captured command selection, stable owner while busy,
reset cancellation, reset priority over simultaneous status writes, and cleared
halted/resuming status for the reset hart. The upstream parameter assertion is
also retained. ABC PDR proves the correct model; concrete BTOR witnesses reject
a wrong-hart selector and a lost reset connection. All six covers are reachable,
including both owners, changed live selection during a command, reset with a
same-edge completion write, reset during acceptance and reset of the other hart.
Exact measured runtimes and model hashes are in `command03/result.json`.

`command01` was a frontend assertion-inventory error (the upstream parameter
assertion was counted incorrectly). `command02` proved the positive model but
the initial wrong-hart fault reached reset priority before command selection;
its intended-identity check correctly rejected the receipt. The fault is now
restricted to non-reset selection cycles, with no assumption added and no
positive property changed. Independent review is pending.

The final refinement, `python hw/ip/debug/formal/command.py --output
build/t32/command05`, retains those claims and adds other-hart survival: an
active command cannot disappear without its own completion or reset. A new
cross-reset fault ties either hart's reset to both inputs and fails exactly
that property. Seven controller assertions plus the upstream parameter
assertion prove; all six original covers and all three faults qualify.
Measured proof/fault/fault/fault/cover wall times are
0.415308/0.415036/0.415036/0.415405/0.465209 seconds. The independent audit at
`command05/independent-review.json` accepts this scope and verifies source,
vendor, emitted-model and artifact identities. Complete DM CSR/status binding,
TAP extraction and the epoch read-data claim remain separate obligations.

## TAP extraction and full-DM binding

`python hw/ip/debug/formal/tap_equiv.py --output build/t32/tap-equivalence06`
passes: measured 389 cells prove through `equiv_simple`, with zero additional
induction cells. `clk2fflogic` retains both TCK edges and asynchronous reset.
Before cutting, the runner verifies all original CDC seam pins, extracted port
aliases and inverted clear. Exact identity buffers are collapsed with driver/cycle
checks. The negative inverts actual TDI loads and has a concrete depth-24 SAT
counterexample beginning in reset. This is an edge-aware arbitrary-input witness
(testmode varies), not a normal-JTAG setup/hold qualification. Independent review
accepts frontend/extraction equivalence, explicitly excluding old/new CDC equivalence.
Proof and review receipts bind source/tool/artifact hashes. Reference preparation
is documented in `hw/ip/debug/formal/README.md`.

Earlier TAP attempts are preserved: reference line endings/dependencies/frontend
option diagnostics, then an insufficient cut-boundary/clock-model qualification
in `tap-equivalence04`, and identity-buffer graph diagnosis in `05`. Only `06`
is accepted. No failed induction is counted as a qualified fault.

`python tools/sbt.py 'hw/testOnly deadhorse.debug.DebugModuleSpec'` passes two
directed tests on the actual adopted full DM: reset/status/acknowledgment priority,
selected-command ownership and a lost-reset connection fault. Measured sbt time
22 seconds; accepted source/binary/log review in `dm-unit04/independent-review.json`.
The fixture suppresses only the constant-range warning required by the production
two-hart parameterization. This complements the command-controller proof and actual
OpenOCD production-TAP tests; it is not an asynchronous composition proof.

`python dv/soc/debug/check.py --output build/t32/debug03` passes all nine positive
scenarios and the missing-halt fault, measured wall time 665.169853 seconds.
Fresh correct/fault emission includes active assertions. Independent review binds
the frozen source snapshot, emitted HDL, drivers, binaries and probe receipts.
The separate end-to-end epoch read-data assertion remains unresolved.

## Refreshed transport qualification

`python hw/ip/debug/formal/transport.py --output build/t32/transport02` passes
on the current sources. The runner now seals source/tool/emission/artifact hashes,
checks the intended request-data and stale-response fault identities, checks all
four concrete covers and rejects source changes during proof. No claim, assumption,
engine, depth or cap changed. Independent review verifies the actual solver source
copies and accepts the unbounded proof plus both faults and covers. This supersedes
transport01's incomplete receipt metadata; it does not close retained SBA epoch data.

The refreshed USB sampling source binding is distinct from JTAG proof work:
`python scratch/t32_usb_rebind.py` freshly emits production/observer HDL, verifies
byte identity, and replays the original canonical and selected proof models exactly.
Original proof jobs are reused, not rerun. The only changed upstream input is the
OpenOCD-expanded environment lock. New sibling receipts preserve the immutable
originals and archived runners. `usb-rebind02/independent-review.json` accepts the
binding. Fresh witness simulation passes; full-size and strict collector qualification
are recorded separately and are not implied by model identity.

The final refreshed USB acceptance-input chain is independently accepted at
`build/t32/usb-boundary-refresh03/independent-review.json`. All packet claims,
fresh full-size simulation, sampling witnesses and runtime archive bind to the
current sources. Fresh production slot/USB connections, mapped Q types/clocks,
reset-release boundaries and CQ extrema qualify the identical composed fixture;
new hold and two-way STA pass every existing corner. Historical internal timing
and placement remain explicitly reused. The strict collectors are unchanged.
This removes stale USB evidence as a prerequisite to final fast CI; it does not
run CI or close any remaining T32 formal obligation.

## Focused T32 composition extension

The user's instruction to finish JTAG authorized the proposed focused attempt
within a 45-minute maximum. No production RTL changed during this attempt.
The unchanged 120-second cap applies to every job. The original read-data
assertion remains unresolved; the successful local work is not aggregate closure.

Measured commands and receipts:

| Check | Result |
| --- | --- |
| `python scratch/t32_epoch_lanes.py 8` | Four disjoint byte checks time out. Their conjunction equals the original word predicate; actual design widths and clocks remain unchanged. |
| `python scratch/t32_epoch_strengthened.py 1` | Bit-zero diagnostic with the already-proved original control claims times out, measured 121.883647 s including runner overhead. |
| `python scratch/t32_epoch_fifo.py` | Literal production request/response FIFO subsets prove independent sequence oracles in measured 37.493862 / 9.733381 s. Producer inputs are arbitrary, with the actual shared transport reset and both release/pointer/synchronizer cones retained. The bit-zero composed check still times out, measured 121.444968 s. |
| `python scratch/t32_epoch_fifo_fault.py` | Both actual head-flop D-bit corruptions fail the intended ordered-data assertion with concrete witnesses. Exact-name qualification corrects the generic parser's inability to read hierarchical observer identities; no solver rerun. |
| `python scratch/t32_epoch_links.py` and `t32_epoch_links_partition.py` | Candidate global-ticket stage invariants remain unproved. The first partition times out, so dependent jobs do not run. |
| `sby -d build/t32/epoch-links-global01/job build/t32/epoch-links-global01/job.sby` and `epoch-state-invariants01` | Stronger all-formal-step auxiliary predicates time out. Original assertions remain unchanged. Induction counterexamples are not reachable RTL faults. No strengthened predicate is assumed or accepted. |
| `python hw/ip/debug/formal/vendor_equiv.py --output build/t32/vendor-equivalence03` | Extension-disabled sampled equivalence passes in measured 15.463229 s; independent review accepts this limited claim. |

The exact authored recipes are archived under
`hw/top/reference/measurements/t32/evidence_replay/epoch/`; the historical paths
and prerequisites are explicit. Independent reviews authenticate component cell
subsets, observer-only attachment, port maps, initial-reset transfer, original
control configuration and the concrete negative witnesses. The historical
recipes are not a general receipt-authentication API or a closed acceptance command.

The next proposed step is a smaller accepted-payload lemma on the actual
production-timeout `BridgeSource`, using an independent local source-handshake
observer and checked instance binding. The failed global latest-debug-payload
formulation spans too many reset/ownership stages. T14's shorter timeout is not
substitutable production evidence. This further proof work has not been run.

## Production first-entry and loader permission closure

`python hw/ip/debug/formal/ownership.py --replay build/t32/replay02 --output
build/t32/ownership06 --roles entry loader lite perf` passes on the current
local T32 sources: measured counts are twelve unbounded safety claims, ten
interface covers and five rejected actual-DUT faults. The input-only observers
bind to the authenticated production graph. Exact production control cells are
retained; omitted neighbour outputs and physical gated-clock edges are arbitrary
inputs. Initial cold reset is the only assumption. No fairness is imposed.

The claims establish pre-boot debug-fetch ownership, no loader permission/write
from debug ownership, inhibited mutating-loader frame handling, preservation of
lite `notStarted`, and no actual perf instruction request or either core's
retirement before first normal boot/START or debug entry in the reset epoch.
They exclude ordinary halting of an already-running application and are not full
ISA proofs. Interface covers are not whole-SoC traces; production OpenOCD tests
supply that separate integration evidence.

The original performance-cover Z3 attempt in `ownership05` times out; the exact
same model, depth and cap passes with Yices/BTOR in `ownership-perf-cover06`.
That qualified engine selection is now in the maintained runner, and the fresh
`ownership06` aggregate passes. Earlier timeout and fault-mutation diagnostics
remain preserved. No production RTL, assertion, assumption or cap changed.
