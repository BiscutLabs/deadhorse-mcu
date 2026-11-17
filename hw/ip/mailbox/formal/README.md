# Mailbox endpoint formal contract

Run inside the pinned environment:

```sh
python3 hw/ip/mailbox/formal/mailbox_proof.py --output build/t14/mailbox-formal
```

The runner generates the mailbox register JSON from its YAML, elaborates the
actual `MailboxEndpoint` plus its actual `BusRegAdapter` and `RegBlock`, and uses
the shared T14 driver. Each job retains the current 120-second ceiling. Normal
and fault jobs use ABC PDR; cover jobs use SMTBMC/Z3 to depth 64. Source hashes,
commands, status and elapsed times are recorded beside the evidence. A fresh
output directory is required. A solver timeout or missing witness is not a pass.

## Properties and assumptions

The only initial-state premise is `reset_n=0` initially. Reset and every bus and
FIFO-side input are subsequently arbitrary. There are no payload-stability,
FIFO-status, ownership, or clock-progress assumptions. This is a single-clock
endpoint proof at full data/address widths and the default base. Both actual
owner parameters, AON 0 and main 1, are proved independently with their own
cover and injected-fault jobs.

The nine assertions check only public ports:

- Exactly one response for every accepted request, no unsolicited response,
  and at most one outstanding request. Rejected window/origin accesses respond
  one edge after acceptance; generated-register transactions respond three
  edges after acceptance. Those latencies are measured in sampling edges and
  include the registered adapter.
- Correct response errors and read values for every address, byte enable,
  origin and write datum. Unmapped/misaligned and partial staging writes error;
  zero-strobe writes have no effect. Writes and errors return zero.
- PUSH and POP occur exactly once for each corresponding successful command,
  two sampling edges after acceptance, and never for other accesses.
- TX data equals the most recent complete staging write, including initial
  zero and preservation after partial/unauthorized writes.
- IRQ always follows the receive head-valid input.

An independent three-bit event oracle is read through the software bus. It
requires overflow on PUSH without space or link readiness, underflow on POP
without a valid head or link readiness, and peer-reset on loss of an initialized
link. Flags persist until their written W1C bit is cleared; simultaneous set
wins. The read checker also samples status and receive data at register
acceptance, so arbitrary changes of those external inputs cannot hide a stale
or corrupted bus read.

The eleven covers include successful PUSH, full PUSH, empty POP, PUSH during
recovery, simultaneous flag set/clear, software reads of each asserted event,
both adapter/register error paths, and POP with IRQ asserted. The fault variant
overrides the production endpoint's `readHead` hook to invert bit zero of the
actual receive-data path; it must produce a concrete failing trace.

## Composition and limits

The endpoint does not store the message queue. Its public `txPush/txData` and
`rxPop` drive the shared `CdcFifo`; input `txReady` and `rxValid/rxData` come from
that FIFO. The separately qualified `CdcFifo(width=32, depth=2)` proof is required
for accepted-message capacity, ordering, exactly-once consumption, data
preservation, stable receive head, reset flushing, and retained sender wake.
Endpoint pulse/data properties supply the FIFO's bus-to-command boundary;
the FIFO's queue properties supply the reverse boundary for endpoint reads.
The FIFO proof accepts arbitrary push/pop/data inputs, so composition adds no
unchecked handshake premise. Read-only accesses do not generate POP.

The actual `Mailbox` top wires each endpoint's TX to one FIFO's write side and
its RX to the opposite FIFO's read side; IRQ is the endpoint IRQ and wakePeer
is that TX FIFO's writePending. Review of those wires and the dual-clock top
simulation remain required. This harness alone is not an independent formal
proof of top-level wiring, a stopped-clock reset pulse, synchronizer analog
behavior, or physical clock-controller wake completion. Short peer reset is
retained by the FIFO's per-clock reset release; endpoint proof checks the
resulting sampled link drop. Do not describe endpoint results alone as an
unbounded proof of the complete dual-clock mailbox.
