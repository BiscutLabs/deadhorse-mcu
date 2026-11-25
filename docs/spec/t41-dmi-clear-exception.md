# T41 DMI cancellation boundary — decision required

## Conflict

T41 requires the debug module and JTAG/DMI transport to use cold reset only,
with one ResetRelease per reached domain and no other reset trees. It also
requires preserving behavior outside the explicitly approved reset changes.
The existing debug contract cancels unaccepted DMI requests when the TAP samples
TestLogicReset/dmihardreset, even when the main clock is stopped. Ordinary
`dmireset` clears sticky error status; it is not this hard-clear operation.

The current Chisel transport implements hard-clear by resetting both FIFO
endpoints asynchronously from the registered TCK clear epoch. This is an
additional asynchronous source, distinct from cold reset. The vendor interface
patch already exposes it; no vendor change is needed to retain the function.

## Concrete distinguishing trace

1. A DMI request has reached main's FIFO output but has not been accepted.
2. Main stops. TCK samples hard-clear; no main edge occurs meanwhile.
3. Main's consumer is ready at its next edge.

The existing transport removes request-valid before that edge. A purely
synchronized functional flush cannot yet distinguish the clear trace from the
no-clear trace and can admit the old request. Additional permission handshakes
do not remove the final interval between the last synchronized authorization
and acceptance. An unaccepted old write must not become an accepted write merely
because its cancellation took longer to cross.

Measured on source baseline `74bea3c` plus the diagnostic test/hook:

```text
python tools/env/run.py run -- python tools/sbt.py "hw/testOnly deadhorse.debug.DebugTransportCancelSpec"
```

PASS: two tests, measured ScalaTest time 13.057 s, sbt time 21 s. The XML
and source-hash receipt are preserved under `build/t41/debug-cancel01/`. The first
uses the production transport and observes its public ports only. The second
inserts the shared two-stage synchronizer into the request-clear path and must
fail the same cancellation assertion; the test catches that intended failure.
It is a diagnostic negative control, not a proposed completed FIFO-flush design
or a proof that all possible architectures fail. The first compile attempt used
an invalid Clock poke API; it ran no simulations. Removing those unnecessary
pokes fixed the fixture without changing its assertion or stimulus sequence.

The existing formal oracle independently defines the same epoch boundary in
`hw/ip/debug/formal/DebugTransportFormal.scala`. That proof was inspected, not
rerun here. No assertion, clock assumption or timeout was relaxed.

## Recommended narrow exception (not approved)

Allow a DMI-transport-only asynchronous cancellation/quarantine control triggered
by cold reset or the TAP's registered hard-clear. Keep the DM, TAP protocol
state, hart debug state and ordinary cold reset distribution under their existing
cold-only reset contract. Do not introduce a new pin or vendor patch.

Implementation requirements after approval:

- Assert quarantine without waiting for main clock edges, suppressing request
  acceptance and stale response visibility at the old cancellation boundary.
- Use acknowledged synchronous clearing for FIFO pointers, pending/ownership
  state and synchronized pointer history where possible; reopen only after both
  domains agree that flushing finished. Do not retain a whole extra bank-reset
  tree merely for convenience.
- Implement the asynchronous control in the shared crossing library; inventory
  every event/valid state bit, reset/control net and release element honestly.
  Calling it a functional event must not conceal its asynchronous source or
  physical CDC/RDC obligation.
- Include pending flush in wake/clock demand, including when DM is inactive.
  Preserve accepted SBA work draining exactly once and accepted BIST continuing
  to completion; transport clearing is not rollback or BIST abort.
- Preserve the existing transport assertions and faults, add stopped-clock and
  repeated-clear cases, and retain physical qualification debt. No extra fairness
  or reset-pulse assumption is approved by this proposal.

This is a narrowly identified exception to the four-cohort/cold-only-debug
constraint, not approval to change USB, analog interfaces or warm retention.
Its implementation and measurements have not run. Alternatively, keeping the
literal cold-only transport restriction requires an explicit change to the DMI
cancellation contract; that is not recommended or implemented here.

## Why work stops here

The T41 brief says: “Ask before retaining any cohort beyond the four above”
and forbids unapproved behavior changes. Both retaining an extra asynchronous
transport control and delaying the existing cancellation boundary cross that
decision boundary. Independent review examined the vendor interface, current
formal oracle and synchronized/event-capture alternatives and confirmed the
need for this narrow decision. Inventory and diagnostic checks may be committed;
the reset consolidation must not be marked complete pending approval.
