# Bus properties

`BusFormal` uses the real three-master/two-region fabric with 128-cycle target
watchdogs. Its public-port oracle covers accepted and returned transaction
credits, response data/errors, exact target payload/decode, denied/unmapped
access, quarantine and continuously eligible round-robin service.

Reset starts asserted. Requesters hold requests and payloads until grant. Each
target accepts one credit, may reply with arbitrary data/error after arbitrary
delay, and may explicitly cancel; only an empty credit supplies quiescence.
Admission and ownership inputs are arbitrary. No response deadline is assumed
of the target: the fabric must enforce its own.

All 34 assertions remain in source. The active gate proves the 31 protocol
assertions; the user deferred the three 400-edge arbitration-wait assertions
on 2026-11-17. They remain unproved and are not retried. Full-model covers and
actual response-data fault controls remain required. Reviewed harness hashes
bind the exact generated property names to these three deferrals; a changed
mapping fails closed pending review. No complete bus proof is claimed.
See the [ledger](../../../../docs/ledger/bus-formal.md) for accepted active-gate
results, retained timeout receipts and configuration limits.
