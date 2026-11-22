# T22 General-purpose PWM outputs

## Goal

Continue RTL under the user's 2026-11-21 instruction and D69: implement generic
PWM outputs in the existing reserved window/pins, on main. No CI. No application
protocol, command freshness, arming or per-device failsafe engine.

## Read first

AGENTS.md; plans 03, 06, 07, 11–16; T21 report; SoC, bus and register-map
specifications; shared RegBlock/BusRegAdapter/ResetRelease contracts; timer and
SoC I/O implementations. Skills: task execution, clocked Chisel, regmap authoring,
reference-model testing, formal properties/timeout triage and GF180 timing.

## Scope

Nine independent generic channels, matching the existing pin capacity. Each has
a 16-bit period-minus-one and divider-minus-one, 17-bit high-time, and buffered
updates. Use the existing 0x40030000 window and fast IRQ10; preserve legacy map
and pin identifiers. Add an opt-in PWM SoC configuration without changing the
existing I1/T21 profiles. Channel output and enables reset disabled.

Define and independently review the register/reset contract before RTL. A PWM
update event offers a registered level DMA request with acknowledgement and
overrun reporting. The DMA controller itself is outside this brief; no claim
of functional memory-to-PWM transfer follows from a request interface.

## May change

This brief/index and own STATUS row/log; hw/ip/pwm; directly required reference
top configuration/bindings/tests; PWM preparation/check scripts, spec/ledger
entries and task report. Preserve unrelated local work, tests, limits and
existing profiles. Generated files stay under build.

## Deliverables and acceptance

- README contract, generated register description, clocked Chisel channel and
  peripheral, SoC binding with registered pin signals, clock demand and IRQ.
- Independent cycle/pulse reference tests: periods, duty endpoints, dividers,
  buffered updates, invalid/busy requests, simultaneous events, disable/reset,
  DMA acknowledgement/overrun, byte strobes, ownership and decode errors.
- Formal safety/update properties, reachable covers and actual faulty RTL
  negative controls, with assumptions and scope stated. Existing 120-second
  formal job cap; use the timeout triage budget if needed.
- Fresh emission, GF180 timing/area with existing main-domain limits, focused
  SoC MMIO/pin/reset/IRQ tests and unchanged existing I/O regression tests.
- Freeze relevant sources, run focused checks, obtain independent review and
  write the report. Both CI tiers remain unrun by user instruction.

## Stop conditions

No clock-source, pin allocation, permission or timing-limit changes. No vendor
edits or new CDC primitive. Do not claim physical qualification, completed DMA
integration or complete SoC acceptance from these block checks.
