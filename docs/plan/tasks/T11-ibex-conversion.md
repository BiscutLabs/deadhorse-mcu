# T11 Equivalence-checked Ibex conversion to Chisel

## Goal

Convert the pinned Ibex reference (T10) to clocked Chisel as RV32IMC with no
functional change, and prove each module and the whole core equivalent to the
reference. The author may be any agent or model: acceptance rests on the
checks, not on who wrote the code. No F extension here (T12/T13).

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [T10-ibex-reference.md](T10-ibex-reference.md) and its report
- [../10-decisions-and-risks.md](../10-decisions-and-risks.md), D2/D16/D17
- [../12-formal-verification.md](../12-formal-verification.md)
- [../14-timing-design-rules.md](../14-timing-design-rules.md)

## Inputs and readiness

Requires T10 complete and T09 for timing. Read the reference from
`hw/vendor/ibex_ref/`; never edit it.

## May change

`hw/ip/perf_core/`, shared interface bundles under `hw/lib/`, build and CI
registration, `dv/core/` module maps and exclusions, core design notes, the
formal ledger, report and own status line. No handwritten SystemVerilog, no
SoC integration, no ISA change.

## Rules for the conversion

1. **One Chisel module per reference module,** with the same ports. Keep
   register names so state can be matched; where emitted names differ,
   record the mapping in `dv/core/module_map.json`.
2. **No improvements in this task.** Do not restructure, retime, re-encode
   state or change reset behaviour. Record ideas in the design notes for T13
   or later. A cleaner design that fails equivalence is a failed task.
3. **Convert leaf modules first,** then their parents. Each module is merged
   only with its equivalence result. Substitute converted modules into the
   reference hierarchy one at a time so failures localize.
4. Keep Apache 2.0 notices on converted files and state in each header that
   it is a translation of the named reference file and commit.
5. Clock gating follows the project's Chisel gating wrapper, not the
   `prim` cell. Record that single intended difference and prove equivalence
   with gating enables matched.

## Deliverables

- Chisel core under `hw/ip/perf_core/` emitting SystemVerilog under `build/`.
- A per-module results table: proved, bounded with depth and reason, or
  excluded with reason. The exclusion list needs review before completion.
- Whole-core equivalence result, riscv-formal on the converted core, lockstep
  on the architectural tests and on the T02 workload binary.
- T09 timing and area for the converted core next to the reference's, same
  library, corner and constraints.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"
python3 dv/core/equiv.py --all-modules --candidate build/emit/perf_core --output build/t11/equiv
python3 dv/core/equiv.py --top --candidate build/emit/perf_core --output build/t11/equiv_top
python3 dv/core/riscv_formal.py --target candidate --output build/t11/rvf
python3 dv/core/lockstep.py --candidate build/emit/perf_core --suite arch,flight --output build/t11/lockstep
python3 tools/ci.py
```

Completion requires every non-excluded module proved or bounded with a
recorded reason, the top level proved or bounded likewise, riscv-formal no
worse than the reference's T10 result, and zero lockstep mismatches.

## Fallback

If the conversion cannot reach equivalence, the reference can be integrated
unmodified behind a BlackBox (D16 permits vendor RTL). That is a decision for
the user, not for the implementing agent. Stop and report.

## Stop and ask

A module cannot be proved or bounded after localizing the difference; the
reference appears to have a bug (report it, do not fix it in the conversion);
equivalence only passes with an assumption not in the reference's own
constraints; timing misses the T09 budget.
