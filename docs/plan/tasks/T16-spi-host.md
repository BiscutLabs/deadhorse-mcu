# T16: SPI host peripheral

## Goal

Implement the approved SPI controller for timestamped IMU acquisition: modes
0/3, two chip selects, FIFOs, checked ownership, IRQ/DMA request interfaces
and retained sleep support. User assigned T16 after T15; core optimization
remains deferred. This is standalone IP, not DMA, sensor firmware or SoC wiring.

## Read first

AGENTS.md; plan 02 requirements, 03 architecture, 04 carryover, 06 power/reset,
07 peripherals, 11 structure, 12 formal, 13 testing, 14 timing and 15 skills;
T14/T15 reports; `docs/spec/bus.md`, `docs/spec/regmap-format.md`, and the
T16 contract `docs/spec/spi-host.md` (write/review before RTL).

Skills: deadhorse-task-execution, regmap-authoring, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage. Existing user direction to defer formal timeouts and
continue peripheral work applies; retain all obligations and label unproved.

## Inputs and readiness

T05/T07/T09/T14/T15 are available. Reuse RegBlock, BusRegAdapter, LocalBus,
CdcSync and qualified reset conventions. RISCay's receive-only ADC player is
a separate retained block, not a general SPI host (plan 04); no Coldfoot source
is imported. T13/S1 are not prerequisites of standalone peripheral work.

## May change

This brief, task index and own STATUS row/log; `docs/spec/spi-host.md`;
`hw/ip/spi_host/` including register map, RTL, tests, formal and check scripts;
build/CI registration and directly relevant gate tests;
`docs/ledger/spi-formal.md`, timing ledger and `tasks/reports/T16.md`.
No core, FPU, vendor, historical firmware or earlier S1/T13 changes.

## Deliverables

1. Reviewed contract and generated register map. Bounded full-duplex byte
   transfers with continuous chip select, modes 0/3, two active-low chip selects,
   programmable rate, TX/RX FIFOs, sticky errors and masked IRQs.
2. Owner checking for every bus access; DMA uses the same checked bus and
   registered request levels. No DMA engine, hidden bypass or new access type.
3. Accepted transactions complete during sleep; selectable admission while
   the core sleeps, retained queues, registered clock demand/quiescence.
   Shared CDC for MISO; capture an integration-supplied same-domain timestamp
   at accepted acquisition start. No new timer, DRDY policy or clock domain.
4. Independent pin-level SPI device/queue tests for both modes and CS outputs,
   arbitrary bytes, repeated transfers, minimum/maximum FIFO sizes and divider,
   RX/TX errors, byte strobes, ownership, reset/config/sleep races, IRQ/DMA
   and timestamps. Real negative controls must be rejected.
5. Measure a command + dummy + 14-byte payload transaction under 150 us at
   assumed HF clocks 9/12/24 MHz, and demonstrate 4 MHz SCLK at 24 MHz.
   Digital edge counts do not qualify pads, oscillator tolerance or board delays.
6. Scoped formal safety/frame properties, covers, actual faults and explicit
   assumptions. One bounded-budget attempt; timeouts remain deferred/unproved;
   counterexamples/tool failures require diagnosis, never silent suppression.
7. Default T09 GF180 SS timing/area including generated register interface;
   preserve 24.96 ns limit. Record measured pre-layout area; invent no area cap.
8. Register aggregate checks in both CI tiers, run fast CI, obtain independent
   review, write report/ledgers, commit and push after active checks pass.

## Acceptance

Commands to implement and run in the pinned environment:

```sh
python3 hw/ip/spi_host/check.py --output build/t16/check
python3 tools/ci.py --tier fast --output build/t16/ci-fast
```

Aggregate includes register generation, independent simulations, scoped formal
with covers/fault controls, and source-bound GF180 timing. Fast CI retains all
earlier active checks and approved explicit deferrals. Full CI/ISA sweep is not
required for this standalone peripheral continuation; report it unrun.

## Stop conditions

Stop for an architectural/contract change, weakened acceptance, prohibited
import, or genuine impasse after diagnosis and independent review. Routine
implementation/tooling fixes remain authorized. Do not relax the rate, deadline,
ownership/reset behavior or timing budget to close the task.
