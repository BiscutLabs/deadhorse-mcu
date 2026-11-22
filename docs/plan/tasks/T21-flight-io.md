# T21 GPIO, timers and retained ADC implementation

## Goal

User-assigned 2026-11-21: replace the GPIO/ADC/timer inactive interfaces with
functional clocked peripherals and explicit SoC bindings. Work on main; do
not run CI. This is implementation, not another stub-only checkpoint.

## Read first

AGENTS.md; plan 02, 03, 04, 06, 07, 11–16; T20 report and SoC pin contract;
bus and regmap specifications; shared CDC/RegBlock/BusRegAdapter contracts;
pinned T06 ClockedSpiAdc and ClockedScaling. Skills: task execution, clocked
Chisel, regmap authoring, reference testing, formal properties/timeout triage,
GF180 timing.

## Scope and contract decisions

- Three GPIOs: registered output/enables, synchronized independent inputs,
  sticky edge IRQs and AON level wake with atomic acknowledged configuration.
  No general pin crossbar or changes to dedicated pin allocations.
- Receive-only ADC: adopt the pinned clocked RISCay engine/scaler with source
  provenance. Preserve first-conversion discard and exact scaling; add the
  generated register interface, owner checks and shared input synchronization.
  A concrete external ADC part and board calibration are not qualified here.
- D68 approved: retain AON sleep-deadline timers at 0x40000000; add the
  main-clock microsecond timebase/four capture-compare channels within unused
  GPIO space. The high-resolution service holds the main clock while enabled;
  AON deadlines work with main stopped. No Q15/Q16 clock choice follows.
- Preserve the I1 stub profile and its tests; add an explicit functional I/O
  profile and integration tests. No changes to unrelated core/USB/serial RTL.

## May change

This brief/index and own STATUS row/log; new peripheral specifications,
`hw/ip/gpio/`, `hw/ip/timers/`, `hw/ip/aon_timer/`, `hw/ip/adc/`, directly required top/configuration
bindings and tests, minimal HAL definitions, provenance, emit/check tools and
formal/timing ledgers. Generated output remains in build. No vendor edits,
new CDC primitive, pad-ring implementation or unrelated peripheral work.

## Deliverables and acceptance

1. Independently reviewed register/clock/reset/ownership/wake contracts before
   RTL. Generated register maps, clocked engines and actual SoC bindings.
2. Independent pin/MMIO tests: byte strobes, owner denial, safe reset, edge/
   level behavior, timer wrap/update/capture overrun, ADC framing/scaling,
   first-result discard, interrupt routing, sleep and independent resets.
3. Formal safety/progress properties, covers and real negative controls;
   every assumption listed, bounded results distinguished from proofs. Existing
   120-second job cap and formal-timeout-triage budget; no unchanged retries.
4. Pinned GF180 source-bound timing and area, with the existing per-domain
   budget. No new timing exceptions or relaxed budgets.
5. Frozen-source focused block and SoC tests, both whole-top USB variants,
   independent source/evidence review, task report. No CI by user instruction;
   state both tiers unrun and retain inherited T20 qualifications.

## Stop conditions

Unapproved map/domain/reset changes, changed limits/assumptions, prohibited
imports or a genuine impasse after diagnosis/review. Missing final pad/clock
selection is not permission to silently invent it. Do not claim complete
chip readiness from functional digital peripheral tests.
