# PWM formal scope

Run in the pinned environment:

```
python3 hw/ip/pwm/formal/check.py --output build/t22/formal-frozen
```

Use a fresh output directory for another run. The runner checks assertion and
assumption inventories, requires concrete cover/fault witnesses and verifies
the intended fault identities. It binds source and emitted-model hashes.

| Job | Unbounded claim | Actual RTL fault | Covers |
| --- | --- | --- | --- |
| channel | Counter/divider bounds, valid active/queued configuration, pin value consistent with phase, no pending update while stopped; STOP clears enable/pending/output, starts and snapshots preserve all input bits, transfer uses the saved snapshot, active settings change only on start/transfer/stop, queued settings hold until capture/stop | Invert the value written to the output flop | High and low enabled output, queued transfer, rejection, stopped output |
| dma | Mask suppresses request, event wins acknowledgement, acknowledgement clears without a replacement, pending survives without service, overrun exactly reports an unserviced repeated event | Invert request bit zero | Pending, overrun, service with replacement |
| denied | Non-owner transactions receive only error/zero-data replies; cannot enable outputs, generate IRQ or DMA requests | Bypass owner check | Error reply |

Assumptions: initial reset asserted, then arbitrary assertion/release; one
digital clock. The denied fixture maps the owner tag to a non-owner, representing
every non-owner tag. Channel settings, commands, DMA events/masks/acknowledgements
are otherwise unconstrained. No helper is assumed, no memory abstraction or
reduced-width model is used. Production channel widths are retained.

These are safety and buffered-update proofs. Exact divider/period timing and
elapsed-time progress are checked by the independent duration simulation model,
not claimed as unbounded waveform proofs. Top reset wiring is exercised by the
SoC tests, not proved by the standalone harness. Analog reset/metastability,
physical hold/RDC and pad timing are outside this scope.

The first channel PDR-only attempt timed out at the existing 120-second cap.
The timeout triage's first rung (solver portfolio) proved the identical model;
no assumption, assertion or cap changed. See the
[formal ledger](../../../../docs/ledger/pwm-formal.md) for measurements.
