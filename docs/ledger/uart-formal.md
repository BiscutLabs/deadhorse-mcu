# T15 UART formal ledger

Measured 2026-11-17 at base `172d4f1d2279bb5cc5c621685ad94923bfd15282`
plus the T15 source hashes in `build/t15/check/result.json`. Reproduce using
`python tools/env/run.py run -- python3 hw/ip/uart/check.py --output build/t15/check-new`.
The aggregate emits fresh models and invokes `python3 hw/ip/uart/formal/check.py
--json build/t15/check-new/regmap/uart_regs.json --output build/t15/check-new/formal`.
Current receipts are `build/t15/check/formal/result.json` and its named job logs.

| Property | Result / engine | Configuration | Measured correct-job seconds |
| --- | --- | --- | ---: |
| Complete helper sum equals unsigned addition | Proved, ABC PDR | Arbitrary pair of 16-bit operands, all 17 result bits; configured depth 4, unbounded engine | 0.316107 |
| Configured TX frame, response accounting, enable and hold | Bounded, BTOR btormc | 160 edges; FIFO 2, increment 8192, normal polarity, scripted configuration, arbitrary accepted byte | 52.045300 |
| Sticky AON wake, settled capture, request equality | Proved, ABC PDR | Arbitrary digital inputs/reset; configured depth 24, unbounded engine | 0.315592 |
| Denied accesses return errors/zero and preserve observable disabled state | Proved, ABC PDR | Owner 0, all denied tags 1..7, FIFO 2, arbitrary requests/addresses/data/strobes; configured depth 32, unbounded engine | 0.916231 |

All covers reached concrete witnesses; all faults were rejected with concrete
counterexample traces. Cover/fault jobs use BTOR btormc at the configured depths.

| Role | Cover(s) | Fault | Measured cover / fault seconds |
| --- | --- | --- | ---: |
| phase | Carry-out at 65535 + 1 | Flip sum bit zero | 0.316372 / 0.316216 |
| frame | Completed A5 frame; busy midpoint | Invert the production TX register update | 1.567761 / 0.415574 |
| wake | Pending after disarm; capture with clear | Invert the production sticky-state update | 0.365906 / 0.315708 |
| denied | Error response; error response with request offered | Bypass the production owner comparison | 0.415385 / 0.415502 |

No T15 formal job timed out or was deferred in this run. Each solver invocation
retains the existing 120-second cap. An unbounded result is limited to the
listed claim/configuration; TX is never described as unbounded.

## Assumptions and limits

- Reset is initially low, subsequently arbitrary. The HF input is the shared
  domain's qualified reset; physical distribution/recovery/removal is excluded.
- Frame stimulus is the specified legal write sequence. Its byte is captured
  on grant. This does not cover arbitrary firmware, RX, all rates, inversion,
  or FIFO depths eight/sixteen; independent pin/queue simulation covers those
  sampled configurations separately.
- Denial maps input tag zero to one, covering exactly all denied tags against
  owner zero. It does not assume an internal signal. It does not prove active
  ownership transfer; the external controller must drain/block work first.
- Wake's capture assertion requires reset warm-up and four consecutive
  armed/active samples. Sticky retention is conditional on no clear; capture
  wins clear. Synchronizers are digital only: no metastability/MTBF, analog
  clock startup or whole-system sleep guarantee follows.
- The helper-sum proof is not a proof of byte-pipeline temporal retiming.
  Independent arithmetic review checked all legal increments and both initial
  seeds against closed-form bit boundaries; public-pin simulation and the
  bounded configured-frame check provide separate RTL evidence.

Independent review found no blocking harness, fault-control or gate issue.
Initial `build/t15/formal-initial` stopped at a wake corrupt-model assertion-count
error before solving; it remains failed evidence, not an accepted negative
control. Successful fresh model/fault results above replace that attempt.
