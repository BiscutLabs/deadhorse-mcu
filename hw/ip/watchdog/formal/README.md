# T26 formal contracts

`check.py` emits the production channel or output-disable components and
fails closed on missing assertion/assumption counts or an unrelated negative
control failure. All jobs retain the existing 120-second solver cap. It never
runs CI. Generated models and receipts are under `build/t26/`.

| Job | Claims | Assumptions | Negative control |
| --- | --- | --- | --- |
| channel | Sticky cause; saturating expiry count; expiry asserts reset/cause; exact four-interval hold; active iff remaining nonzero; countdown within captured period; warning matches remaining threshold; expiry disarms; legal feed reloads captured period; otherwise countdown decreases; START while active reports error; valid START captures period | POR and service reset initially asserted, then both arbitrary; arbitrary commands/settings on one AON sample clock | Accept early feed; shorten hold; reset retained state with service reset |
| break | Permit cannot be revoked except reset; local readiness requires upstream epoch readiness and an observed local idle; only STOP after both guards can acknowledge a channel | Reset initially asserted, then arbitrary; idle, epochReady and STOP unconstrained | Force all permit bits high on acknowledgment |
| pad | Output enable/value exactly match the registered selected source and disabled handover interval; watchdog suppresses PWM bank while retaining other banks | Normal reset initially asserted, then arbitrary; watchdog reset and all selections/data arbitrary | Bypass the PWM bank's watchdog reset |

The break job adds no assumption that epochReady is truthful. The whole SoC
binds it to SocLocalMemory.epochReady, whose reset/drain contract is exercised
with an actual retained STOP transaction in SocWatchdogEpochSpec. Formal local
proofs alone are not a proof of that composition. Stopped-clock asynchronous
assertion is tested in simulation; analog RDC/recovery/removal is separate.

The channel's original Yices induction/basecase attempt and the subsequent
ABC/Yices/suprove portfolio timed out. All channel assertions remain. Covers
and the actual early-feed, shortened-hold and lost-retention faults qualified,
but the positive channel job is **unresolved**, not proved. No unchanged
timed-out job is rerun by the frozen focused check: it runs break/pad only.
Channel diagnosis and the step-0 table are in
[watchdog formal ledger](../../../../docs/ledger/watchdog-formal.md).
