# T41 remaining cancellation boundaries

D106 is approved for DMI only. User approval2026-11-25 records the additional
bus-bridge exception and preserved BIST pin abort as D107; implementation and
qualification remain pending. This records the complete follow-up audit of the
non-USB reset-source families in the committed T41 inventory.

## Bus timeout needs immediate cancellation too

The main-to-AON bridge and the debug leaf use the same BusBridge. Its current
transport epoch includes `!producer.abort`. On timeout the source returns one
error and cancels queued requests before the destination can issue them. The
target may drain work already offered/granted; reset is not rollback. These are
distinct cases in [the bus contract](bus.md) and BridgeTarget.

A stopped destination creates this trace:

1. A source request is accepted and queued; destination has not asserted its
   external `target.req` for that request.
2. Source times out while destination is stopped and reports the error.
3. Destination resumes. A synchronized abort has not arrived yet, so an old FIFO
   head can become a new downstream write after the timeout.

The existing asynchronous link quarantine prevents step 3. Merely synchronizing
abort changes the existing no-late-dispatch contract. It is the same class of
issue as DMI, but D106 deliberately does not authorize a general exception.

Measured diagnostic on baseline `e4279f8` plus the test/default-equivalent hook:

```text
python tools/env/run.py run -- python tools/sbt.py "hw/testOnly deadhorse.bus_bridge.BridgeCancelSpec"
```

PASS: two tests, measured ScalaTest runner13.469s and sbt26s. A destination-phase
sweep observes public ports, distinguishes requests already offered before
timeout from queued/unissued work, and checks that the latter is never dispatched.
The negative control inserts the shared synchronizer into abort propagation and
must fail the specific late-dispatch assertion. The positive uses the production
bridge generator with its existing diagnostic limit32; production limit131072
is unchanged. This is a cancellation diagnostic, not full bridge acceptance,
full-width timing, or an exhaustive architecture proof. Existing formal claims
and their deferred status remain unchanged.

## Approved authorization (D107)

Extend D103's asynchronous-control exception to **BusBridge timeout/abort
quarantine only**, for both production instances. Preserve immediate suppression
of queued old requests, acknowledge FIFO/state flushing before reopening, and
retain exactly-once drainage of work already offered/granted. Use the shared CDC
implementation, minimize and inventory asynchronous event/valid state, and keep
bank initialization synchronous where possible. No timeout, assertion, clock
assumption, ownership rule, region or peripheral behavior changes.

Explicitly retain the **existing BIST external-pin abort capture/quarantine**
when debug or BIST already holds aggregate warm reset. It is a capture of an
existing warm source, not a new logical reset cause: BIST must still survive
ndmreset but abort on the external pin. A pin pulse cannot be replaced by an
ordinary sampled level or inferred from a new warm edge that never occurs.
Do not apply the GPIO input's pulse-width assumption to reset. Acknowledged
functional clearing of both agents/results precedes readmission. No new BIST
retention behavior is proposed.

The DM remains cold-only under D106; USB and analog interfaces remain unchanged.
This approval would not permit arbitrary additional reset cohorts or bank-reset
trees. All asynchronous controls and physical CDC/RDC obligations stay visible.

## Complete source-family disposition

| Family | Required treatment / decision status |
| --- | --- |
| Cold, warm, causes, watchdogs, PWM and client/service reset | D103 centralized releases; existing cause/event capture retained; performance watchdog joins warm |
| DMI hard-clear | D106 approved immediate quarantine plus acknowledged flush |
| BusBridge timeout/abort, toAon and debug leaf | Additional immediate-quarantine exception proposed above; no delayed dispatch contract change |
| BIST external-pin abort | Preserve selective source-event capture/quarantine as explicitly described above; accepted BIST survives other warm sources |
| Oscillator OFF / source qualification | Flush and acknowledge source/gate/configuration state while source clocks still run, then lower OSC_EN; keep gate closed through fresh startup qualification. No extra asynchronous protocol exception established |
| Bootstrap / internal warm while debug holds reset | Cold-owned clock management keeps running, functionally invalidates epochs and requalifies before application release |
| Lite HOLD and debug teardown | Drain, synchronously initialize all affected state, acknowledge before C3 writes/start; clock halt alone is insufficient |
| Ordinary mailbox/UART/GPIO configuration and direction permit | Centralized cold/warm resets and acknowledged functional clearing |
| USB wrapper/slot/engine | Existing unchanged T19 exception; no implicit new watchdog reset source |
| GPIO edge and pin/POR cause acquisition | Existing asynchronous input-event capture remains explicitly inventoried; not falsely counted as eliminated reset pins |

Independent review of these families found no further unavoidable protocol
exception. This is an architectural audit, not a proof that implementation or
physical checks cannot reveal another issue. The earlier DMI-only review did not
close the BusBridge abort boundary; this audit closes that planning omission.

## Approval boundary

T41 says to ask before retaining controls beyond the approved reset structure
or changing other behavior. D106 is not silently broadened. D107 resolves this approval boundary; do not claim the
four-cohort implementation, warm ROM, measurements or task complete.
