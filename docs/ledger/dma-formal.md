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

## T40 circular UART receive — 2026-11-25

Measured commands, on `10a142c` plus receipt-hashed sources, prefixed with
`python tools/env/run.py run --`:

- `python hw/ip/dma/formal/circular.py --output build/t40/formal-final01`:
  original finite claims replayed, circular growth/portfolio capped; then
  a negative-job Yosys selection-union error stopped the runner before solving.
- `python hw/ip/dma/formal/circular.py --faults-from build/t40/formal-final01
  --output build/t40/formal-faults-final01`: only authenticated emitted fault
  models, corrected exact-cone selection. No positive timeout rerun.
- `python hw/ip/dma/formal/check.py --cases denied --output
  build/t40/formal-denied-final01`: seven original denial assertions proved,
  cover and owner-bypass fault passed their expected outcomes.
- `python hw/ip/dma/formal_summary.py --base build/t40/formal-final01`:
  read-only Yosys model inventory and log summary, no solver retry.

| Original finite property | Job | Current result | Engine | Measured wall seconds |
| --- | --- | --- | --- | ---: |
| Request exclusivity | finite-0 | Proved | ABC PDR | 2.268 |
| Origin | finite-1 | Proved | ABC PDR | 2.318 |
| Alignment | finite-2 | Proved | ABC PDR | 2.270 |
| SRAM range | finite-3 | Bounded36; unbounded debt unchanged | BTOR | 92.898 |
| Memory offer stability | finite-4 | Proved | ABC PDR | 2.369 |
| Peripheral offer stability | finite-5 | Proved | ABC PDR | 2.419 |
| Channel0 count/selector | finite-6 | Proved | ABC PDR | 2.269 |
| Channel1 count/selector | finite-7 | Proved | ABC PDR | 2.269 |
| Channel2 count/selector | finite-8 | Proved | ABC PDR | 2.270 |
| Channel3 count/selector | finite-9 | Proved | ABC PDR | 2.269 |
| Seven non-owner wrapper assertions | denied/correct | Proved | ABC PDR | 2.219 |

The new circular model has38 assertions, including an independent POP-driven
lap counter and descriptor snapshot. Assumptions: initial reset asserted,
thereafter arbitrary, one digital sample clock. All bus replies and MMIO are
arbitrary; no fairness, response deadline, shadow-stability or invariant is
assumed. Original finite inputs have circular tied low, exactly their old
domain. Denied accesses retain the complete non-owner mapping.

| Circular step-0/triage measurement | Measured result |
| --- | --- |
| Prepared positive model | 2,354 cells; 1,490 sequential bits including formal `$ff` state; no RAM |
| BMC16 growth | PASS bounded, 3.722s; checks through index15, before the first wrap witness |
| BMC32 growth | TIMEOUT, 121.261s; last attempted index28, not all properties discharged there |
| Portfolio | ABC PDR + Yices induction, TIMEOUT121.665s; no aggregate proof |
| Cover model | 1,789 cells, 927 sequential bits; all five covers in14.099s |
| First cover bounds | Abort18, busy config-error19, odd-count half27, wrap36, wrap with a competing channel36 |
| Extraneous/contributing cones | No data RAM. Four-channel MMIO, arbitration, wide cursor/range arithmetic and checker history share logic |

The earlier decoding-only model (`formal-ring01`,34 assertions) timed out at
BMC64. Review added independent lap state before accepting event accounting.
The 16-step pass is **not** closure of range/underflow/exact-per-lap claims:
it does not reach a wrap. These claims remain deferred with real three-lap
simulation and fault controls. A Yices induction-state failure is not a
reset-reachable counterexample; the positive bounded jobs found no such bug.
No second triage round was run. Next useful work is a separately reviewed
partition of per-channel conservation and shared bus-retirement properties,
not another unchanged timeout. No helper may be assumed without proof.

Fault results and the complete scoped test inventory are in
[T40](../plan/tasks/reports/T40.md). Neither aggregate CI tier ran.
