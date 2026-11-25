# T40 DMA circular receive for UART RX

## Goal and ordering

D102 (user-approved 2026-11-24): DMA circular receive, UART RX only,
reload from shadow. Extend the existing T23 DMA after PLAN05's design
changes and Phase 2 qualification; do not interrupt or change PLAN05 work
in flight. Reconcile against the resulting production top, endpoint table
and measured area budget before implementation. Coordinate with T36 if its
Phase 3 changes share the SoC binding. No new peripheral or DMA architecture.

This brief schedules implementation; its creation does not start RTL work.
If PLAN05 is still open, use a separate `codex/` branch and keep changes
within the scope below. D92-D101 record PLAN05; D102 is the subsequent
circular-receive decision and supersedes none of them.

Continuous variable-length UART streams need receive buffers without
fixed-count restart gaps. At the assumed 420 kbaud, 8-N-1 link rate, the
estimated time to fill an empty 8-byte RX FIFO is
`8 * 10 / 420000 = 190.476 us`; this is not a measured software deadline.
Pairing two channels per UART would need six channels for three UARTs,
versus the existing four. No application-specific radio/GPS protocol enters
hardware. CPU interrupt overhead must be measured if quoted.

## Read first

AGENTS.md; plan README, STATUS, 03, 07, 08, 10, 11-16; PLAN05 contracts
and report when landed; T23 brief/report; docs/ledger/dma-formal.md;
docs/spec/bus.md and soc.md; hw/top/reference/soc.yaml and its generated
endpoint table; hw/ip/dma/README.md, dma.regmap.yaml, RTL, tests and formal
harnesses; UART request/POP and shared register-generator contracts.

Skills: deadhorse-task-execution, clocked-chisel-block-design,
regmap-authoring, reference-model-testing, chisel-formal-properties,
gf180-synth-timing-check and formal-timeout-triage.

## May change

hw/ip/dma; its directly required production SoC binding/map and focused
integration tests; DMA driver/example under sw/; register/map generation
inputs and generated build outputs; own spec, README, ledger, task report,
STATUS/index/decision and chip area-budget documentation. Generated C/Scala
maps remain under build/ and are not committed. No vendor edits, unrelated
IP changes, new endpoint, ownership change or PLAN05 refactoring.

## Hardware contract

1. Add a per-channel `circular` bit. The inspected baseline uses only
   endpoint bits 4:0 at offsets 0x40..0x4c; bit 5 is free and is the proposed
   location, reset zero. Confirm availability after PLAN05, keep the selector
   field unchanged, update dma.regmap.yaml and regenerate C/Scala maps. Use
   an existing free field before adding a register.
2. START allows circular only on UART RX and count >= 2. The endpoint
   generator in hw/top/reference/check_soc_map.py enumerates UART0, UART1,
   UART2, each TX then RX: the confirmed baseline RX selectors are **1, 3,
   5** (TX 0, 2, 4; SPI 6, 7; waveform destinations 8..16). Reconfirm from
   the validated post-PLAN05 table, including the merged timer destinations;
   do not infer RX merely from odd selector numbers. Invalid combinations
   set config-error like existing invalid STARTs. Memory span, alignment,
   duplicate-endpoint and ownership validation remain unchanged.
3. On the successfully completed item that reduces remaining to zero,
   reload current and remaining from the channel's shadow address/count
   and continue. Do not produce done in circular mode. Run until ABORT or
   fault; no second stored copy of base/count. Narrow reload/compare widths
   naturally where existing range checks already establish bounds.
4. While a circular channel is busy, reject shadow writes to address,
   count, endpoint and circular: ignore the write and set config-error.
   The whole endpoint/circular register write is rejected together. Preserve
   non-circular write behavior. Specify and test START/write and terminal
   item/write collisions so no accepted active transfer sees a changed
   reload source. Writes after completed abort are accepted as before.
5. Add per-channel half and wrap events after existing fields: proposed
   half bits 19:16, wrap bits 23:20 in events at 0x0c, W1C, reset zero;
   matching irq_enable bits at 0x10. Preserve existing event bit positions
   and W1C collision semantics. Half occurs on the item making remaining
   equal to floor(count/2), once per lap, including odd counts. Wrap occurs
   on each actual reload. Sticky status may coalesce events until cleared;
   verify the underlying event pulses and clear between laps when testing
   repeated status notifications. Non-circular channels generate neither.
6. ABORT stops at an item boundary, including the wrap item, with existing
   drain semantics. Abort/fault termination takes priority over starting a
   new lap: no reload and hence no wrap when termination suppresses reload.
   A successfully completed half item still reports half. Faults stop as
   before; failed items must not be counted as successfully received bytes.
   Review terminal-event collisions before RTL, retaining original behavior
   for non-circular operation.
7. current remains the coherent, single-register firmware write-position
   read. Define its publication point relative to committed SRAM writes,
   UART POP and lap reload; software must never see an unwritten byte as
   available. A running ring exposes a modulo-buffer position, not a lap
   count. Preserve stopped/faulted current semantics and document them.
8. No hardware overrun detector, software read pointer in hardware, circular
   TX/SPI/PWM/memory-to-memory mode, or extra descriptor storage. Existing
   non-circular contracts, round-robin fairness, clock holds, resets,
   ownership and endpoint table remain unchanged.

## Software

Add a small driver under sw/ that starts a ring given channel, UART, buffer
and length; returns bytes available since a saved software read position;
and advances that read position after consumption. Use the coherent current
snapshot and existing DMA/SRAM ordering rules. Validate UART and length,
handle split-at-end reads, and document start/abort/fault handling.

The caller must keep up and poll/consume before an entire lap goes unseen:
equal modulo positions cannot distinguish empty from an overwritten full
lap. Neither the API nor the example may claim loss detection or unlimited
buffering. State the ring-size/byte-rate service interval as an estimate.
Provide a small once-per-loop variable-length frame example and driver
tests, including position wrap. No CRSF/GPS parser is required.

## Scoped verification and acceptance (all unverified)

D102 applies the user's D91-style scoped policy to this task: **no aggregate
fast/full CI and no unrelated IP suites**. Run all existing DMA tests and
proof obligations with assertions unchanged, plus the focused checks below.
Prior timeout receipts remain visible; do not rerun an identical timed-out
job or call a timeout a pass. Bounded evidence is acceptable when clearly
labelled with depth and coverage; unresolved unbounded claims remain debt.
No other assertion, assumption, limit, tolerance or solver cap changes.

- [ ] DmaEngineSpec: at least three laps with exact byte placement; exact
  half and wrap items each lap for even and odd counts (including count 2);
  mid-lap and wrap-item ABORT; busy shadow writes rejected and writes after
  abort accepted; circular TX, both SPI directions, waveform/PWM selectors,
  and counts 0/1 rejected; circular traffic does not starve other channels.
- [ ] Preserve all existing DMA cases, reset/error/ownership checks and
  assertions. Use an independent transaction/ring model with stalls; check
  W1C, START/write collisions and coherent cursor publication. Inventory
  before/after cases so none is silently lost during PLAN05 reconciliation.
- [ ] Production SoC UART loopback receives at least three laps while the
  performance CPU executes a busy loop. Firmware consumes using current;
  compare every byte to an independent transmitted sequence and show no
  loss when firmware meets the documented service interval.
- [ ] Negative controls must be caught: reload to wrong address; half one
  item off; done incorrectly fired in circular mode; busy shadow write
  incorrectly accepted. Identify the failing test/property for each.
- [ ] Formal: circular transfer addresses remain in [base, base+span), never
  cross its end; half/wrap pulses occur exactly once per completed lap;
  remaining never underflows. Distinguish aborted/faulted partial laps,
  sticky status and event pulses. Include covers reaching wrap, odd-count
  half, abort and contention; no new fairness/environment assumption.
- [ ] Use formal-timeout-triage once within its existing budget and per-job
  caps (existing DMA jobs use 120 s). Step-0 table and per-job time, engine,
  depth, model/source hashes, assumptions, covers and faults are mandatory
  for any deferral. No unchanged timeout reruns; stop before a second triage
  round. Never assume an unproved helper to close the inherited range claim.
- [ ] Driver/example checks and independent review of contract, RTL,
  formal evidence, software ordering, area and timing pass. Freeze sources
  for final scoped replay; retain all deferred items in STATUS/report.

Existing entry points, prefix each with `python tools/env/run.py run --`:

```
python hw/top/reference/check_soc_map.py
python dv/soc/prepare_dma.py
python tools/sbt.py "hw/testOnly deadhorse.dma.* deadhorse.top.SocDmaSpec"
python hw/ip/dma/formal/check.py --output build/t40/formal
python hw/ip/dma/check_timing.py --output build/t40/timing-after
python tools/check_structure.py --include-untracked
```

These are starting interfaces, not passing results. Reconcile preparation
with the post-PLAN05 production map without reverting it. Add the circular
SoC case to SocDmaSpec (or a named focused suite explicitly run in the
receipt). Select only justified fresh formal jobs after inspecting historical
timeouts; document their exact command rather than invoking an unchanged
aggregate timeout. Driver/example and fault-runner commands are deliverables
to document. Do not use the broad historical check_dma aggregate to launch
unrelated IP suites.

## Area and timing acceptance (unverified)

- [ ] Before editing RTL, synthesize the post-PLAN05 DMA baseline with
  `python hw/ip/dma/check_timing.py --output build/t40/timing-before` in the
  pinned environment. Repeat after on identical tools, library corner,
  constraints and top. Measure the complete four-channel DMA including
  register decode/events, not just the transfer-engine submodule. Report
  area, flop count, worst path by class and start/end, command wall time,
  commit/source hashes and electrical/hold/reset qualifications. Existing
  timing limits remain; do not loosen the baseline's 9 MHz screen to 8 MHz.
- [ ] Added mapped standard-cell area across all four channels is at most
  **0.010 mm2**. If exceeded, stop and report the breakdown before any
  recovery optimization. Compare matching fresh before/after measurements,
  not the historical T23 rounded area.
- [ ] Update the chip budget/headroom using post-PLAN05 measurements,
  including any changed scan allowance and physical overhead. The temporary
  reserve in plan08 uses the qualified PLAN05 Phase2 budget; it is not a final chip-fit
  measurement. No memory growth or area-ceiling relaxation is authorized.

Historical context only: T23 measured DMA area 159020.288 um2
(0.159020288 mm2), worst path 43.368591 ns, using
`python hw/ip/dma/check_timing.py --output build/t23/timing-first` on
`72bcfac` plus receipt-hashed local sources. See the T23 report; not rerun
when this brief was written and not the T40 baseline.

## Report, publication and stop conditions

Write docs/plan/tasks/reports/T40.md with Outcome, What changed, Checks run,
Numbers, Deviations from the brief and Open issues. Include D102, the final
contract, endpoint/register evidence, before/after area/flops/timing,
command wall times, all test/proof/fault results and deferrals. State both
CI tiers were not run under this task-specific policy. Independent review
and required scoped checks precede commit/push. Do not mark implementation
done or tick stage gates from this planning work or from bounded evidence.

Stop and ask if the area cap is exceeded, any non-circular contract would
change, shadow-write locking needs extra storage (including a second base/count),
or proof work requires more than one triage round. Preserve the failing
evidence and do not recover area by changing another block's contract.
