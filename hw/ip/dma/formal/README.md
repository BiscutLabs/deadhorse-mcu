# DMA properties

`DmaFormal.scala` elaborates the production-width engine and MMIO wrapper.
The only temporal assumption is initial reset asserted; reset may assert or
release thereafter. One digital sample clock is used. Bus grants, responses,
data, errors, requests, START/ABORT and descriptors are unconstrained. There is
no eventual-service or exclusive-firmware assumption in the safety model.
The denied-access harness maps any owner tag to a non-owner, covering all
unauthorized origins. No assertion is replaced with an assumption.

Engine assertions: memory/peripheral offers are mutually exclusive; offered
origin is performance; addresses are aligned; memory offers stay inside
performance SRAM; both offered payloads remain stable until grant; each active
channel has nonzero remaining count and a valid endpoint selector.

Wrapper assertions: denied requests have the adapter's registered response
timing, error and zero data, and cannot produce DMA requests, IRQ or PWM ack.
Negative models corrupt the emitted bus origin or bypass MMIO ownership;
both must produce counterexamples for named assertions.

Production covers reach completion, error, abort, RX memory write and PWM ack;
the wrapper cover reaches a denied reply. These are reachability witnesses,
not progress proofs. Whole-transfer data integrity, event bookkeeping and
round-robin behavior use the independent simulation oracle; no unbounded
proof of these behaviors is claimed.

Initial receipt: `build/t23/formal-first/result.json`. Covers and faults pass;
the seven wrapper denial properties prove. The ten-assertion engine aggregate
reached its 120-second cap. The identical-model portfolio also timed out
(`build/t23/formal-portfolio-v2/result.json`). The 9/18-step BMC passes are
bounded evidence only. Separate jobs account for every original assertion
once (`build/t23/formal-split/result.json`); results are in the
[ledger](../../../../docs/ledger/dma-formal.md).
Nine engine assertions and all seven wrapper assertions are independently
verified unbounded proofs. Only engine memory-range remains unresolved.

The hard cone is cursor-range conservation. The failed portfolio induction
trace additionally starts with an unreachable active descriptor having an
invalid saved origin; this is not a reset-reachable bug. Any approved helper
invariants must be proved before reuse, with identical-model hashes, while
retaining all original properties and assumptions.

`check.py` runs the original full model. `triage.py` authenticates its receipt
and emitted models, records size and bounded growth, and supports the portfolio
or exact assertion partition. Never rerun unchanged timed-out jobs. Neither
script invokes CI.

## T40 circular receive

`circular.py` preserves every original finite assertion with the new circular
input tied low, then checks circular behavior through the actual register
wrapper. That wrapper receives arbitrary MMIO, owner tags, requests, grants,
responses and errors. Initial reset is asserted, then reset is arbitrary.
There is no assumed shadow stability, fairness, service deadline or memory
contents. The original non-owner harness and seven assertions remain unchanged.

The circular model has 38 assertions: selector/count/cursor conservation and
enabled SRAM-byte bounds; real shadow stability; event timing and absence of
done; an independent per-channel descriptor/lap counter compared against
current/remaining; and serialization of START against register acceptance.
Aligned SRAM word addresses can precede an unaligned ring base, so bounds
are checked on each enabled byte lane. Proof-only descriptor copies are
elided from production. Half/wrap expectations use successful observed POPs
and the independent lap state, not DUT remaining.

`build/t40/formal-final01` re-proved nine original finite assertions, bounded
the inherited range claim at 36 steps, and reached all five circular covers
(last first witness at36). Circular BMC16 passed but does not reach the wrap
witness; BMC32 and the ABC PDR/Yices portfolio reached their120-second caps.
**Circular range, underflow and exact-per-lap formal closure remain deferred.**
Three-lap simulation is stronger behavioral evidence here than the shallow
bounded pass. No assertion is reported as unbounded merely because one
portfolio engine reported some outputs proved.

The fault-only continuation uses authenticated emitted models and selects the
named faulty assertion cones; all positive assertions stay in the positive
jobs. It fixes a Yosys selection-union runner error without rerunning any
timed-out positive job. `formal_summary.py` exports step-0 model sizes and
attempted depths without running a solver. Detailed results and exact fault
coverage are in [the T40 report](../../../../docs/plan/tasks/reports/T40.md)
and [ledger](../../../../docs/ledger/dma-formal.md). No additional triage
round is authorized; a later attempt needs a separately reviewed decomposition.
