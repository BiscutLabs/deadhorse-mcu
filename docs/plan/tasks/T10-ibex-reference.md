# T10 Ibex reference and comparison harness

## Goal

Pin one unmodified Ibex revision as the golden reference for the conversion
(D2) and build the harness that compares any candidate core against it. No
Chisel core is written in this task. The reference is never built into the chip.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../03-architecture.md](../03-architecture.md), Cores and memories
- [../10-decisions-and-risks.md](../10-decisions-and-risks.md), D2/D16/D19/D20
- [../12-formal-verification.md](../12-formal-verification.md)
- [../13-test-environment.md](../13-test-environment.md)
- [T11-ibex-conversion.md](T11-ibex-conversion.md), which consumes this harness

## Inputs and readiness

Requires T07 and T08. The Ibex revision, parameter set and instruction-set
simulator revision are **not supplied by planning**: choosing and recording
them is the first step. Commands below are interfaces to create, not run yet.

## May change

`hw/vendor/ibex_ref/` (unmodified sources, `ibex_ref.lock.json`, README,
`verify_lock.py`), `dv/core/`, `tools/env/` lock entries for new pinned
tools, `tools/ci.py`, the formal ledger, report and own status line.

## Steps and deliverables

1. Pin an Ibex commit. Export a flat, complete file list including the
   required lowRISC `prim` sources. Vendor the files unmodified, with Apache
   2.0 notices, every original path and a SHA-256 per file in the lock.
2. Fix one parameter set and record it: RV32IMC, flop register file,
   machine mode, vectored interrupts, debug, RVFI. Record every other
   parameter explicitly; none may be left at an unstated default.
3. Supply technology-neutral `prim` implementations for simulation and
   formal only. Mark the directory reference-only: the chip source lists
   and the physical flow must reject it. Add that check to CI.
4. Elaborate the reference with both pinned front ends (sv2v and slang).
5. Build `dv/core/equiv.py`: formal equivalence of one named module, or the
   whole core, between the reference and a candidate SystemVerilog file.
   Report proved, bounded (with depth) or failed. Never report bounded as proved.
6. Build `dv/core/lockstep.py`: run a program on a candidate and compare
   every retired instruction through RVFI against the reference and against
   the pinned instruction-set simulator.
7. Run riscv-formal on the reference with the fixed parameters and record
   which checks pass, are bounded or are unsupported.
8. Negative controls: a deliberately altered copy of one reference module
   must fail `equiv.py`; a deliberately wrong instruction result must fail
   `lockstep.py`. Reference against itself must pass both.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 hw/vendor/ibex_ref/verify_lock.py
python3 dv/core/equiv.py --self-check --output build/t10/equiv
python3 dv/core/lockstep.py --self-check --output build/t10/lockstep
python3 dv/core/riscv_formal.py --target reference --output build/t10/rvf
python3 tools/ci.py
```

Each self-check must show the reference passing and its negative control
failing. Report tool versions, the Ibex commit and the parameter set.

## Stop and ask

The reference cannot be elaborated unmodified by either front end; a needed
source has an incompatible licence; equivalence cannot be made to run on
even one module; riscv-formal fails on the unmodified reference.
