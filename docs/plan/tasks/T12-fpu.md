# T12 Multicycle single-precision FPU

## Goal

Build the area-focused multicycle FPU (D19/D20) as a standalone Chisel block
with selective pinned HardFloat reuse. Ibex has no F extension, so this is
new design, not conversion. No core integration here (T13).

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../10-decisions-and-risks.md](../10-decisions-and-risks.md), D19/D20
- [../12-formal-verification.md](../12-formal-verification.md)
- [../13-test-environment.md](../13-test-environment.md)
- [../14-timing-design-rules.md](../14-timing-design-rules.md)

## Inputs and readiness

Requires T07 and T09. Independent of T10/T11 and may run in parallel. The
HardFloat revision and the reference (Berkeley TestFloat and SoftFloat)
revisions are chosen and locked as the first step.

## May change

`hw/ip/fpu/`, `hw/vendor/hardfloat/` (pinned Chisel sources with lock and
licence), `dv/fpu/`, `tools/env/` lock entries, build and CI registration,
formal ledger, report and own status line.

## Steps and deliverables

1. Write the block contract first: a request/response interface with
   operation, operands, rounding mode, result, flags, busy and a cancel input
   that leaves no partial state. State the cycle count per operation.
2. Implement all RV32F operations: add, subtract, multiply, fused
   multiply-add (all four forms), divide, square root, min/max, comparisons,
   sign injection, classify, moves, and conversions to and from signed and
   unsigned 32-bit integers. All five rounding modes, all five flags,
   subnormals, infinities and NaN handling as the RISC-V specification
   requires (canonical NaN). No double precision.
3. Share hardware between operations where it saves area. Heavy operations
   are iterative; outputs are registered (timing rules).
4. Test every operation and rounding mode against TestFloat vectors, with
   RISC-V NaN and min/max behaviour checked against the pinned simulator
   where they differ from IEEE defaults. Add directed corner cases and
   seeded random streams. One negative control per operation class.
5. Formal properties: handshake, cancel leaves no state, busy always ends
   within the stated cycle count.
6. Report area and timing through T09 against the 60% period budget.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 tools/sbt.py "hw/testOnly deadhorse.fpu.*"
python3 dv/fpu/check.py --output build/t12
python3 tools/ci.py
```

`dv/fpu/check.py` must fail on any vector mismatch in result or flags, on a
missing operation or rounding mode, and when a negative control is not caught.

## Stop and ask

A reused source needs an incompatible licence or non-Chisel integration;
vectors fail; timing or area cannot be met without dropping an operation.
Do not drop operations, flush subnormals or weaken vectors.
