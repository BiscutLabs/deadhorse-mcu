# Clock-domain bus bridge (T14)

Status: implemented; active checks accepted with explicit proof deferral. One transaction at a time through shared
depth-two request/response CDC FIFOs. See [bus contract](../../../docs/spec/bus.md).
Source and target clocks are independent. Each external reset asserts
asynchronously and releases through `ResetRelease`; either reset flushes FIFO
transport. Surviving source bookkeeping is outside the transport flush reset.

`offer` comes from the local fabric's registered waiting level, before admission.
`permitRequest` is held for a fair `DirectionPermit` grant. `admit` lets that
fabric select this bridge. Blocked offers consume no local bus slot. The
source-clock `clockRequest` level must feed ungated AON wake logic through the
shared synchronizer when not already in AON; it precedes grant and remains
asserted through completion/recovery. Never connect it only to a stopped clock.
`targetClockHold` is the target-domain registered drain/recovery demand. The AON
controller must also collect it through the shared synchronizer when necessary;
it preserves orphan drainage if the source itself is held in reset/stopped.

Production source/target endpoints are separate single-clock modules for timing
and focused properties. Their request and response payload boundaries are
registered. FIFO consumers have no combinational ready chain.

Timeout/peer reset produces one source error and an acknowledged transport abort
before permit release. Target reset starts quarantined. `quiescent` acknowledges
that no old endpoint response or effect can remain; destination reset alone is
not sufficient for independently reset endpoints. Already granted orphan work
drains. Quarantined requests return error without issuing downstream work.
There is no automatic replay of a write with uncertain outcome.

T41/D107 transport now uses one shared `CdcEpoch` for request and response.
Timeout/peer-reset quarantine still blocks admission asynchronously; FIFO
pointer/head/synchronizer banks initialize synchronously on their existing
domain clocks. Both clocks must acknowledge initialization before reopening.
Source release and target flush retain clock demand until this handshake closes;
the endpoint's existing orphan credits and quiescence checks remain separate.
This change does not yet consolidate the production cold/warm reset distribution.

`DirectionPermit` is AON-resident, round-robin between the two directions. Its
transport control resets when either domain resets, independently of retained
AON application state. Requesters use four-phase request/permit release; a
released request must observe permit low before reacquiring.

All external outputs are registered. Synchronizer/FIFO payload path constraints
and MTBF remain physical integration obligations. At diagnostic watchdog 32,
13 of 14 assertions proved, including wake/cancel and dispatch; end-to-end
return-data equality is user-deferred and unproved. Production watchdog 131072
has directed source-endpoint simulation (exact expiry, final-edge priority,
reset/recovery and retained wake), but no full-bridge unbounded parameter proof. See the [ledger](../../../docs/ledger/bus-formal.md) for scope
and the [timing notes](../bus/formal/TIMING.md) for measured component costs;
the original combined 0.05 mm2 area figure was an assumption.
