# T27 Raw ADC acquisition and firmware conversion

## Goal

Continue the user-assigned RTL on main under D69/D71, without CI. Implement raw
acquisition and firmware conversion, retiring scaled_sample at offset0x14
under the user's2026-11-21 approval. Every other register offset is unchanged.

## Read first

AGENTS; plans04/07/11–15, D69, STATUS and PLAN02; T21 report; ADC README,
adoption manifest, RTL, register map, tests/formal; SoC ADC binding/tests.
Skills: task execution, clocked Chisel, register maps, reference testing,
formal properties and GF180 timing.

## Deliverables and order

1. Independently reviewed raw acquisition contract. Keep the adopted serial
   frame, shared CDC/pad wrapper requirements and reset/first-frame discard.
   A raw variant bypasses board-unit scaling; completion is a registered
   pulse after the frame. Document its different completion latency.
2. Raw production wrapper and generated register map; accesses to0x14 error.
   Publish raw sample, sequence and events atomically. Keep legacy arithmetic
   reference/checks outside the production hardware. No new clock, pin or
   ownership policy. Update ABI consumers/tests to the approved raw contract.
3. Generic firmware conversion helper using explicit parameters, checked
   denominator and wide arithmetic, with documented wrapping semantics.
   Independent exhaustive raw-code tests and arithmetic boundary/fault tests.
4. Independent serial tests, reset/discard/cadence cases and actual RTL
   negative control. Control/data properties, covers and negative controls,
   preserving the existing120-second cap. Keep historical scaler checks.
5. Fresh focused evidence and raw/legacy engine timing comparison under
   the existing conservative main-9MHz screen, independent review and report.
   Neither CI tier runs. Physical ADC qualification remains open.
6. Qualify raw production MMIO, READ_ACK/result collisions, continuous
   scheduling and service resets; production publication/owner properties
   with negative controls. Fresh full-wrapper timing and four complete
   watchdog-profile tops at8/9MHz with stub/real USB. Freeze the focused
   tests, firmware and receipts, then independently review the migration.

## May change

This brief/index and own STATUS row/log; hw/ip/adc engine, focused tests,
properties/runners and contracts; sw/hal ADC helper/tests; own ledger/report.
Production register map, narrow SoC bindings/preparation/tests and contracts
may change under D71. Preserve inherited local work and historical receipts.

## Stop conditions

Report failed checks without relaxing them. No unrelated proof retries,
oscillator choice, ADC part qualification or physical signoff. D71 authorizes
only the specified ADC ABI retirement; no other peripheral ABI changes.
