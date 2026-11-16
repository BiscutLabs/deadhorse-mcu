# Missing T11 clock-gate dependency

Status: shared-wrapper scope approved by the user, 2026-11-15; implementation,
scoped checks and independent review complete. The proposal below records the
original dependency; see the implemented [contract](../../lib/CLOCK-GATE.md).

T11 rule 5 requires the project's Chisel gating wrapper, rather than Ibex's
`prim` cell. Inspection of all Chisel sources and hardware paths finds no such
wrapper. `hw/lib/` currently contains register-bus, register-block and smoke
example modules. The only clock-gate sources are immutable Ibex reference
primitives, whose generic implementation contains a transparent-low latch.

The existing T11 shared-library allowance covers interface bundles, not a new
clock-gate implementation. AGENTS.md requires approval before exceeding the
brief's May change list. No new wrapper or alternate clock implementation has
been introduced before that approval; the missing dependency is now resolved.

## Proposed scope

Add the shared Chisel clock-gate wrapper under `hw/lib/`, plus its verification
and necessary target bindings. ASIC implementation uses the already selected
GF180 integrated clock-gating cell. Simulation/formal must model its enable
capture faithfully, and FPGA substitution remains inside the wrapper. Do not
replace it with an arbitrary combinational clock AND, a rising-edge enable
register, an ungated clock, or vendor CPU RTL.

Keep Ibex's existing registered busy control and debug/interrupt wake inputs,
test-enable bypass and reset behavior. Verify the wrapper separately, then
prove top integration with gating enables matched, as T11 requires. Retain all
timing, electrical, retirement, sleep/wake and negative-control obligations.
Cell-level glitch freedom remains a physical-cell property, not a claim from
zero-delay RTL simulation.

This fills an implementation dependency; it does not propose a new sleep mode,
clock architecture, ISA feature or replacement performance core. The faithful
`IbexCore` baseline is independently verified; registered execution integration
and whole-candidate acceptance remain incomplete.
