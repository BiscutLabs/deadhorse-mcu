# T14 verification ledger

Updated 2026-11-17; T14 active acceptance passed with the four user-approved deferrals. Base commit
`b4680a4529ad629fc4e3577ee42fa83e45e6943d` plus uncommitted T14 changes;
receipt hashes identify each tested source. Commands use
`python tools/env/run.py run --`. No arithmetic abstraction is used.

**User decision, 2026-11-17:** abandon current proof attempts and revisit later.
Exactly three bus arbitration-wait assertions and one bridge return-data
assertion are **deferred, unproved**. Keep the properties and evidence; do not
retry them or develop helper proofs without a new instruction. This supersedes
the pending helper-proof approval request and does not defer other obligations.

| Configuration / obligations | Kind and current result | Engine / witness depth | Receipt |
| --- | --- | --- | --- |
| CDC depth-two FIFOs, widths 32/33/72: capacity, order/data, stable head, reset flush and retained pending; Gray transitions and two-edge reset release | **Proved** at each listed configuration; covers reached, actual data/Gray/early-release faults rejected; 21 jobs, measured 98.945 s | ABC PDR; covers 48 | `build/t14/cdc-final/result.json` and `cdc-32/`, `cdc-33/`, `cdc-72/` |
| Bus, three masters/two regions, 128-cycle limits: response/target credit, owner/data/decode, bounded completion and quarantine | **31 protocol assertions proved**, exact partition of unchanged 34-assertion model, measured 10.218 s | ABC PDR; original ten covers to depth 144 reached; actual response fault rejected | `build/t14/bus-formal-03/`, `bus-partition-01/result.json` |
| Same bus: three arbitration fairness assertions | **Deferred, unproved (user decision)**: original PDR and portfolio timed out; all three exact partitions timed out at 120-second cap; no reachable design counterexample | ABC PDR / suprove / Yices portfolio; diagnostic BMC only | `build/t14/bus-triage-01/`, `bus-partition-01/` |
| Bridge, watchdog **32**: source dispatch (three), target dispatch (two), control including wake/cancel (eight) | **13 assertions proved** in exact partition of corrected 14-assertion model; return-data assertion deferred/unproved; active aggregate accepted under explicit exception | suprove source partition 20.280 s; PDR target 0.871 s and control 3.094 s | `build/t14/bridge-formal-05/`, `bridge-triage-02/` |
| Same bridge: return-data equality (one) | **Deferred, unproved (user decision)**: exact partition timed out in 121.348 s; intended actual data-path fault found at BMC step 38; six covers reached | PDR cap 120 s; covers depth 128, all reached by step 78 | `build/t14/bridge-formal-05/`, `bridge-triage-02/` |
| Production bridge watchdog **131072**, bus timing configuration limits **128/131080** | **Not formally qualified by the shorter configurations above**; timing qualification is separate | No universal-parameter proof claimed | `hw/ip/bus/formal/TIMING.md` |
| Direction permit and AON arbiter: exclusivity, four-phase release, eligible-edge progress and fairness | **Proved** in final receipt; covers and two actual faults pass; measured 43.023 s; independent acceptance review complete | ABC PDR; depth recorded per job | `build/t14/direction-final/result.json` |
| Mailbox endpoint, owners 0/1: complete bus/register contract, staging, exact command pulses, IRQ, overflow/underflow/peer-reset events, set-over-clear | **Nine assertions proved per owner**, eleven covers each, actual read-data fault rejected; measured 58.930 s | ABC PDR; covers 64 | `build/t14/mailbox-final/result.json` |
| Complete mailbox ordering/wake | Endpoint guarantees plus proved 32-bit CDC queue; actual top wiring checked by simulation and independently reviewed; **no independent unbounded top-wiring proof claimed** | Composition, not an additional complete-top solver result | `hw/ip/mailbox/formal/README.md` |

Final gate `python3 tools/ci.py --tier fast --output build/t14/ci-fast-final-01`
passed **29 jobs in measured 1185.432 s**, status **pass_with_deferrals**. Full tier
was **not run**. Its T14 subprocesses reran 16 simulation tests across seven
suites, all active formal obligations/covers/fault controls (260.125 s), and
15 timing configurations (70.779 s). Fresh formal receipts live under
`build/t14/ci-fast-final-01/fast/bus-formal/`; the rows above retain the prior
triage provenance and identical configuration scope.

The approved IDs are `T14-BUS-FAIR-M0`, `T14-BUS-FAIR-M1`,
`T14-BUS-FAIR-M2`, and `T14-BRIDGE-RETURN-DATA`. Each remains explicitly
`deferred_unproved`. Reviewed harness digests and exact assertion-name/count
partitions prevent accidental deferral of a different property. Cover jobs retain the full cover inventory;
corrupt models retain the full assertion inventory. Missing, unknown or inconsistent
success receipts fail CI; no timeout is dynamically converted to a pass.

The production 131072-cycle source watchdog passed directed simulation for
exact expiry, final-edge response priority, cancellation/reset/reuse, retained
wake, duplicate detection and actual read-path corruption rejection. This is
**simulation evidence**, not an unbounded full-bridge parameter proof. Independent
review cleared production code, mailbox composition/wiring, tests, gate policy
and current source/receipt hashes. The four deferred assertions remain unproved.

## Premises and limits

- CDC: both resets initially asserted, subsequently arbitrary; observer history
  initialized to zero; ideal digital sampling. Clocks are independently
  unconstrained and may stop; eventual service requires local edges.
- Bus: initially asserted reset, request/payload held until grant. Target model
  accepts one credit, permits arbitrary delayed/error data, and can cancel;
  quiescence means no old response remains. Original receipt restrictions and
  current explicit target model are retained with emitted harnesses.
- Bridge: source, target and endpoint resets initially asserted; stable
  ungranted requests; target credit model with arbitrary delayed/error reply or
  explicit cancellation; permit retained until request release. The corrected
  monitor composition preserves the original functional obligations. It uses a
  32-cycle watchdog; production-default parameter qualification remains open.
- Direction permit: external resets initially asserted; four-phase requester
  models with arbitrary demand/completion and independent clocks. Wall-time
  service requires continuing clocks and completion by the current owner.
- Mailbox endpoint: initial reset only; bus/FIFO-side inputs otherwise arbitrary.
  The shared FIFO separately proves accepted-message accounting, ordering,
  reset flushing and sender wake. Review/simulation of actual connecting wires
  is distinct from a formal proof of those wires.
- No model qualifies analog metastability, Gray-bus skew, payload settling,
  reset recovery/removal, clock-controller integration or routed physical timing.

## T42 local grant, 2026-11-25

D108 replaces only production toAon's obsolete direction arbitration; the bridge,
shared CDC/FIFO and reset machinery are unchanged. Command (pinned environment):
`python hw/ip/bus_bridge/formal/local_permit_proof.py --output build/t42/local-proof01`,
mainf534b34 plus receipt-hashed sources. Two actual-primitive assertions proved
unbounded with ABC PDR: output equals last main-edge request and output is low
under reset, the latter observed from an independent clock outside the resetting
domain. Measured positive wall0.316023s. Only initial reset is assumed; later
reset/request/clocks arbitrary. Stuck request, extra-cycle and reset-high faults
each fail; grant/revoke/regrant covers pass. Existing120s cap, depth64 covers;
no timeout or new abstraction. See [report](../plan/tasks/reports/T42.md).

This does not discharge the inherited return-data/FIFO/production composition
or physical debt below. Relevant bridge/SoC reset, ownership and exact-once
simulation passes, including real transport faults; it is not a substitute for
the missing unbounded composition proof. No aggregate CI ran.

## Timeout triage and retained failures

The report's Step 0 table records model sizes, original solver frames,
quarter/half-depth growth and earliest covers. Bus rung 1 encountered an AVY
process crash; its corrected portfolio without AVY timed out. Rung 4 split all
34 assertions exactly: 31 proved, three fairness properties unresolved. No
assertion or assumption was changed during triage. Proposed bus rung-6
helper-invariant/composition work has not begun and is now deferred by the user.

Bridge Step 0: 795 cells, 1828 state bits, no memories; quarter-depth 32 BMC
passed in 3.923 s, half-depth 64 timed out in 121.762 s. The unchanged portfolio
timed out. Exact partitions retain all 14 assertions; 13 have passed and the
return-data partition timed out in 121.348 s. BMC observations are **bounded diagnostics**,
not substituted acceptance. An induction-step failure from arbitrary states is
not a reachable design counterexample.

Earlier `bridge-formal-02`/`bridge-safety-01` failures exposed proof-monitor
ticket-collision/composition defects; `bridge-formal-03` failed compilation
during repair. They do not establish a production RTL bug. Earlier vacuous CDC
runs and smaller bus configurations are superseded evidence, never aggregate
passes. Final independent review and all active fast-tier checks passed; the four
explicit deferrals and configuration/physical limits remain open.
