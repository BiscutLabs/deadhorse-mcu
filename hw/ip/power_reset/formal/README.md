# T33 local power/reset properties

`python hw/ip/power_reset/formal/check.py --output build/t33/formal`
emits the real `BrownoutSelect` and `OscSequencer` with local property wrappers.
This is a local checker, **not** the complete T33 or PLAN04 acceptance aggregate.

| Job | Claims | Negative control | Reachability |
| --- | --- | --- | --- |
| selector | Only legal active settings; an exact key and legal shadow update the active bit; invalid writes report an error; reset restores the safe setting | Actual key comparator bypass | Higher setting, then return to default |
| demand | Unmaskable service-reset demand keeps the oscillator on, cancels stopping/light sleep, and starts deep-sleep recovery with the gate closed | Actual forceRun input ignored by the policy | Demand in deep OFF and STOPPING |

Positive safety uses ABC PDR, unbounded. Faults and covers use BTOR within
the existing assumed verification-resource cap of 120 seconds per job and
24-step witness search. The search depth is not a positive proof bound.
The wrapper initializes with asserted reset; after that reset and local inputs
are arbitrary. Settings retain their full production widths, and both main
and oscillator holds are arbitrary. There is no readiness/fairness assumption.
Every job has the single initial-reset assumption; there is no assumed helper.

Selector MMIO/origin/byte-enable behavior is checked separately by
`PowerResetSpec`, against the address/key/event contract and shared RegBlock
behavior. The selector proof starts at its local apply/key/shadow interface;
it does not claim that arbitrary MMIO transactions have already been proved
through the entire SoC. `OscCtrlSpec` checks service-reset transport flushing
and persistence of failed startup; the demand lemma alone is not a proof of
the source-clock counter, command/completion FIFO ownership or physical ICG.

T34 must establish the D85 analog threshold-switching guarantee. Digital
model tests establish only that the behavioral model implements that contract.
Count/shutdown composition debt remains in the oscillator formal ledger;
none of these local jobs replaces an unresolved original property.

Receipts include source and emitted-model hashes, commands, engine, wall time,
classification and intended failed property identities. Timeout stops this
runner as unresolved; it never silently reruns a timed-out formulation.
