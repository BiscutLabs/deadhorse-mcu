# T10 Selected Chisel core and FPU

## Goal

Implement the approved Ibex reimplementation in clocked Chisel with full
RV32IMFC, area-focused multicycle FPU and selective HardFloat reuse. This is
the design prerequisite for S1, not an alternative-core evaluation.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../03-architecture.md](../03-architecture.md)
- [../10-decisions-and-risks.md](../10-decisions-and-risks.md), D2/D19/D20
- [../12-formal-verification.md](../12-formal-verification.md)
- [../13-test-environment.md](../13-test-environment.md)
- [../14-timing-design-rules.md](../14-timing-design-rules.md)

## Inputs and readiness

Requires T07/T09. Before RTL, record exact Ibex architectural reference and
HardFloat source revisions/licences and reference-model/tool support. Those
pins are not supplied by this planning discussion; resolving them is the first
task step, not permission to substitute a SystemVerilog CPU. Obtain a reviewable
core/FPU contract and verification matrix before implementing instructions.

## May change

`hw/ip/perf_core/`, `hw/ip/fpu/`, selective pinned `hw/vendor/hardfloat/`,
related shared interface bundles, build/CI registration, independent tests and
ISA vectors under `dv/`, core design notes, ledger and report. No SoC integration,
new handwritten SystemVerilog, neural IP, alternative core bakeoff or changed ISA.

## Deliverables and steps

1. Preserve upstream licence/provenance. Specify memory interface, interrupts,
   exceptions, machine-mode/vectored interrupts, CSRs, debug, RVFI, FPU issue/retirement and clock-gating contracts.
2. Implement I/M/C and full F: fused operations, divide/sqrt, comparisons,
   conversion, moves/classification, rounding modes, fcsr/flags, special values
   and subnormals. No D. Trap and interrupt behavior during multicycle operations
   must be precise; no partially committed architectural state.
3. Reuse selected HardFloat components through pinned Chisel-compatible sources;
   no full single-cycle datapath by default. State area/timing improvement
   hypotheses, but claim benefits only with same-configuration evidence.
4. Independent ISA/reference comparison, FPU bit-level reference tests including
   rounding/flags, random and directed sequences, debug/interrupt/reset tests.
   Properties beside RTL, negative control per proof, explicit assumptions.
5. Add CI and T09 timing integration. S1 measures throughput/area of this selected
   implementation; no requirement to implement another core for comparison.

## Acceptance checks

Proposed test interfaces, **not run by PLAN01**:

```sh
python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"
python3 tools/sbt.py "hw/testOnly deadhorse.fpu.*"
python3 dv/core/check.py --output build/t10
python3 tools/ci.py
```

`dv/core/check.py` must fail on ISA/reference mismatch, missing full-F coverage,
or a negative control not detected; report actual formal depth/proof status,
RVFI coverage and unsupported checks. Integer riscv-formal alone does not
verify F. Publish GF180 timing evidence through T09 and actual tool commands.

## Stop and ask

Required correctness/timing tests fail; reusable source requires incompatible
licence or non-Chisel integration; selected architecture cannot meet constraints.
Do not drop F, flush subnormals, weaken tests or switch cores to close the task.
