# T24 Limited GPIO output alternate functions

## Goal

User-assigned continued RTL on 2026-11-21 under D39/D69. Implement the
remaining limited pin mux on main, without CI. Preserve dedicated interfaces
and prior SoC profiles; no physical pad assignment or architecture freeze.

## Read first

AGENTS.md; plans 03, 06, 07, 11–16; D39/D69; bus/SoC and register-map specs;
T21–T23 reports; GPIO, timer, PWM and shared register/reset contracts. Skills:
task execution, clocked Chisel, regmap authoring, reference testing, formal
properties/timeout triage and GF180 timing.

## Scope

Three existing GPIO output pads each select disconnected, their existing GPIO
output, same-index timer compare, or same-index PWM. This is an output-only
logical alternate-function table. GPIO input/wake continues to observe its own
pad; timer capture inputs, dedicated timer/PWM outputs, serial, clocks, reset
and JTAG routing remain unchanged. No general crossbar or new CDC. The logical
table is provisional until G1, with all approved interfaces still coexisting.

Use unused GPIO-window space at offset 0x200 for a generated 256-byte owner-
checked register block, main clock/main-service reset. Reset disconnects all
outputs. Registered output data/enables add one main edge of latency while
stable; a selection change inserts a full disabled sample interval before the
new source can drive. Firmware switches functions only when an interrupted
waveform is acceptable. Core/AON reset preserves the selection and outputs;
main-service/cold/warm reset asynchronously disables them.

Independent contract review before RTL. Add an opt-in profile extending the
current functional DMA profile; existing profiles and tests stay intact. The
open T23 range proof is inherited, not waived or a new RTL dependency.

## May change

This brief/index and own STATUS row/log; hw/ip/pinmux; directly necessary
top/config/map bindings/tests; focused dv/soc preparation/verification;
block/top/spec/ledger/report docs. Preserve unrelated local work. No vendor,
core, USB, DMA engine or peripheral-engine changes.

## Acceptance

- Reviewed contract, generated register map, clocked implementation and real
  SoC GPIO/timer/PWM bindings; no replacement of dedicated physical functions.
- Independent cycle-model tests for every selection and source-enable value,
  rapid changes, registered latency, reset, byte masks, denied origins and
  decode errors; actual RTL fault rejected by the same oracle.
- Unbounded selection/disable/reset safety properties with reachable covers
  and actual fault controls; no new assumptions beyond stated digital inputs
  and initial reset; existing 120-second formal cap/triage rules.
- SoC MMIO/pin/input/wake/independent-reset tests; existing focused regressions,
  whole-top 8/9MHz stub/real-USB emissions and source-bound GF180 timing/area
  with existing limits. No CI.
- Frozen sources, independent source/evidence review, factual report.

## Stop conditions

No physical pin reallocation, input-route invention, added peripheral breadth,
clock-source choice, reset-domain change, exception or relaxed check. Stop for
an unapproved architecture conflict or genuine impasse after focused review.
