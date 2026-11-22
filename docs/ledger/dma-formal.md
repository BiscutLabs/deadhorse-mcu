# T23 DMA formal evidence

## 2026-11-21 production-width safety

Measured on uncommitted `main` at `72bcfac`; source/model/artifact SHA-256
manifests in the receipts below identify the exact snapshot. Commands use
`python tools/env/run.py run -- <command>`. No CI ran.

- `python3 hw/ip/dma/formal/check.py --output build/t23/formal-first`:
  engine aggregate TIMEOUT; wrapper denial proof PASS; both faulty RTL models
  rejected; all engine/wrapper covers reached.
- `python3 hw/ip/dma/formal/triage.py --baseline build/t23/formal-first --output build/t23/formal-portfolio-v2`:
  BMC depths 9/18 PASS (bounded), identical-model portfolio TIMEOUT.
- `python3 hw/ip/dma/formal/triage.py --baseline build/t23/formal-first --output build/t23/formal-split --split`:
  nine separate engine assertions proved; memory range remains unresolved.
  Other assertions are removed only from each individual job, never assumed;
  the disjoint partition accounts for all ten original assertions exactly once.

| Original property | Job | Result | Engine | Measured wall seconds |
| --- | --- | --- | --- | ---: |
| Memory/peripheral requests exclusive | property-0 | Proved | ABC PDR | 1.569 |
| Offered origin is performance | property-1 | Proved | ABC PDR | 1.569 |
| Offered address aligned | property-2 | Proved | ABC PDR | 1.418 |
| Memory offer within performance SRAM | property-3 | Unresolved | ABC PDR | 121.112 |
| Memory offer stable until grant | property-4 | Proved | ABC PDR | 1.619 |
| Peripheral offer stable until grant | property-5 | Proved | ABC PDR | 1.769 |
| Active channel0 has count and valid selector | property-6 | Proved | ABC PDR | 1.669 |
| Active channel1 has count and valid selector | property-7 | Proved | ABC PDR | 1.669 |
| Active channel2 has count and valid selector | property-8 | Proved | ABC PDR | 1.618 |
| Active channel3 has count and valid selector | property-9 | Proved | ABC PDR | 1.769 |
| Denied reply timing, error, zero data; no memory/peripheral request, IRQ or PWM ack | denied/correct (seven assertions) | Proved | ABC PDR | 1.567 |

Assumptions: initial reset asserted, thereafter arbitrary; one digital main
clock. Denied harness maps tags to the complete set of non-owners. Bus inputs
and descriptor controls are unconstrained. No liveness, FIFO-ownership or
internal-invariant assumptions. Tests follow the separate software concurrency
contract, but that contract is not assumed by these safety proofs.

Actual origin corruption fails the offered-origin assertion; bypassed MMIO
ownership fails denied-access assertions. Measured production-model first cover
bounds: abort4, error6, RX store7, completion9, PWM ack18. These are reachability
witnesses, not proofs of progress under arbitrary stalling inputs.

### Timeout triage

| Step-0 measurement | Measured result / interpretation |
| --- | --- |
| Prepared aggregate model | 551 sequential bits, 948 cells, no memories; `triage.py` Yosys stat/export |
| Requested depth / solver progress | depth36; original PDR reached frame20, reported nine proved outputs, aggregate TIMEOUT at120-second cap |
| Growth diagnostics | BMC9: 1.168 s; BMC18: 5.125 s; both PASS bounded only |
| Cover reachability | First bounds above; longest relevant witness18 |
| Unnecessary logic | No RAM; payload/PWM data cones disappear for most split checks. Range still couples 32-bit cursor and 16-bit remaining count. |

Tried two triage rungs: unchanged-model portfolio (Yices induction, suprove,
ABC PDR; 121.155 s TIMEOUT), then exact assertion partition. The SMT induction
failure is origin preservation from unreachable arbitrary active state with
invalid saved origins, not a reset-reachable counterexample. The unresolved
PDR output is the memory-range property, not the origin property.

Next proposed change, subject to the skill's rung-6 approval: prove widened
`cursor + remaining * stride <= SRAM end`, lower bound, saved owner/alignment,
and selected/offer consistency; then discharge the unchanged original property.
Do not assume an unproved helper. Preserve the cap and source/model-hash checks.
No further unchanged timeout retry is authorized. An initial triage metadata
reader failed before starting a solver because SymbiYosys `design.json` is JNY;
the corrected script exports normal Yosys JSON from the prepared RTLIL.

## PLAN03 focused debt attempt — 2026-11-22

Measured by `python tools/env/run.py run -- python dv/soc/plan03_debt.py --case dma --output build/plan03/debt01/dma`.
Unbounded solver PASS indices: []; unresolved: [3].
Fresh concrete models match all historical variants. Original assertions,
assumptions, depths and120-second caps remain. No helper or unchanged retry.
Exact per-assertion times, model sizes, fault limitations, historical evidence
audits and next scoped work are in [the debt report](../spec/soc-verification-debt.md).
