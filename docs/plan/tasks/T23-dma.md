# T23 Basic DMA controller and SoC binding

## Goal

User-assigned continuation of RTL on 2026-11-21 after T22, under D25/D69.
Implement basic bounded DMA for existing UART/SPI and PWM request interfaces,
with actual performance-SRAM and peripheral bindings. Work on main; no CI.

## Read first

AGENTS.md; plans 03, 06, 07, 11–16; D25/D43/D69; bus and SoC specifications;
UART/SPI/PWM register and request contracts; T20/T22 reports; local SRAM
arbitration and shared RegBlock/BusRegAdapter/ResetRelease. Skills: task
execution, clocked Chisel, regmap authoring, reference testing, formal
properties/timeout triage and GF180 timing.

## Scope

Four programmable channels share a single transfer engine. Each channel binds
one existing peripheral request, a checked memory range and a finite count.
UART/SPI use packed bytes; PWM uses words plus its ordinary buffered-update
command. Single-item bursts, round-robin service, no linked descriptors, no
application-specific protocol. The new profile preserves existing profiles.

Prepare and independently review the detailed contract before RTL. The initial
integration admits performance-owned DMA only into performance SRAM and the
explicit UART/SPI/PWM endpoints. Origin is assigned by hardware, never by a
software-writable tag. Existing endpoint permissions and memory checks remain.
Core-only reset preserves DMA; main-service/whole-chip reset cancels it together
with its memory/peripheral fabric. No new CDC or clock-source selection.

## May change

This brief/index and own STATUS row/log; hw/ip/dma; directly required reference
top/configuration/map/local-memory bindings and tests; focused dv/soc firmware
and runners; block/spec/ledger/report documentation. Preserve unrelated work,
existing tests, numeric limits and prior profile behavior. No vendor edits.

## Acceptance

- Generated register contract and clocked implementation, including checked
  ranges/ownership, finite-count completion/error IRQ, abort/drain semantics,
  stable requests through grant, and no duplicate transfers.
- Independent transaction/data model with randomized stalls, byte lanes,
  errors, abort/reset and deliberate faults; actual UART/SPI/PWM integrations.
- Production-width safety formal properties, covers and actual faulty RTL
  controls. State assumptions and bounded/proved scope; existing 120-second
  job cap and timeout-triage budget.
- Local-memory tests establish unchanged no-DMA timing/behavior and bounded
  arbitration while DMA competes; retained core-reset and endpoint permissions.
- Fresh GF180 block timing/area with existing limits, focused frozen regression
  and whole-SoC emissions for the unchanged 8/9 MHz choices and USB variants.
- Independent source/evidence review, task report. Neither CI tier runs.

## Stop conditions

Do not relax checks/latency budgets, expose other private memory, introduce
unapproved reset/clock/pin changes, or claim physical/complete-SoC acceptance.
If required memory arbitration cannot preserve the existing no-DMA behavior or
timing limits, report the measured path/result before restructuring further.
