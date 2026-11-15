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
tools, `tools/ci.py`, the formal ledger, report and own status line. Also
the guard in `tools/timing/check.py` that rejects reference-only sources,
and nothing else in that file (step 3 requires it; added 2026-11-14).

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

## Multiply and divide: split check (D44)

Approved by the user on 2026-11-14 after the investigation in
`dv/core/MULTIPLICATION-INVESTIGATION.md`. The end-to-end riscv-formal check
of MUL, MULH, MULHSU and MULHU compares two different multiplier structures
bit by bit and does not finish. Do not raise its timeout. Replace it, for
these four instructions only, with the parts below. Every other instruction
keeps its unchanged check.

**A. Integration check, gating.** Use riscv-formal's ALTOPS mode.

1. Define `RISCV_FORMAL_ALTOPS` for the checker so its specification uses
   the alternative operations from the pinned riscv-formal instruction models.
2. Add one formal-only adaptation to the generated analysis copy, recorded
   in `dv/core/ADAPTATIONS.md` and `adaptations.json` like the existing one
   (hash, exact bytes, reversal). Under `RISCV_FORMAL_ALTOPS` it replaces the
   multiply unit's result with the same alternative operation of the operands
   the unit captured. Take the operations from the pinned models; do not
   retype constants. Valid, stall and handshake timing are untouched: the
   substituted value appears exactly when the unit reports its result.
   The vendored originals stay byte-exact.
3. This proves decode, operand selection and capture, stall timing, result
   routing and RVFI for the four instructions. It does **not** prove how
   partial products are assembled.
4. Keep the bound, check cycle, 600-second limit, covers and the
   nonzero-destination result fault. Add a second negative control that
   corrupts operand capture, and show it is caught.

**B. Arithmetic, gating.**

1. `dv/core/mul_lemma.py`: prove over integers, with a pinned solver that
   supports integer arithmetic, that the shifted sum of the reference
   multiplier's partial products equals the full product, for the signed and
   unsigned operand combinations of all four instructions. Write the
   partial-product formula from the reference multiplier source and have an
   independent reviewer check it against that source. Negative control: a
   wrong shift or sign must be refuted. Use the pinned z3.
2. Promote the existing stress run (`dv/core/mul_diagnose.py`: 4,420 operand
   pairs, 17,680 products, 36 injected faults) to a required CI check with
   its fixed seed.
3. State in the report that under route A the link between the lemma and the
   RTL rests on review and simulation, not on proof.

**C. Stronger integration check, attempt once, not gating.** Replace the
17-bit product in the analysis copy with an arbitrary function of its two
operands (for example an unconstrained read-only memory indexed by both),
rewrite the checker's specification as the same partial-product sum using
that function, and run the unchanged bound. If it completes, it also proves
the assembly and makes B.3's caveat unnecessary. Time-box it to one working
session and report the outcome either way. Promoting it to gating is a
later decision.

**D. The unabstracted end-to-end check** stays in the repository as an
on-demand diagnostic. Its status is recorded as "unresolved (arithmetic)".
It is not run in CI and is never reported as a pass.

**Recording.** In `result.json` and the ledger these four instructions carry
the status "bounded, arithmetic abstracted (ALTOPS)", never plain "bounded".

**Division and remainder.** If a check that reaches DIV, DIVU, REM or REMU
hits the same wall, first show it is a timeout with no counterexample and
that covers and faults behave. Then the same split applies without a new
decision; report it.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 hw/vendor/ibex_ref/verify_lock.py
python3 dv/core/equiv.py --self-check --output build/t10/equiv
python3 dv/core/lockstep.py --self-check --output build/t10/lockstep
python3 dv/core/riscv_formal.py --target reference --output build/t10/rvf
python3 dv/core/mul_lemma.py --output build/t10/mul_lemma
python3 dv/core/mul_diagnose.py --output build/t10/mul_stress
python3 tools/ci.py
```

Each self-check must show the reference passing and its negative control
failing. Report tool versions, the Ibex commit and the parameter set.

## Stop and ask

The reference cannot be elaborated unmodified by either front end; a needed
source has an incompatible licence; equivalence cannot be made to run on
even one module; riscv-formal fails on the unmodified reference. A solver
timeout on multiply or divide arithmetic is handled by the split check above
and is not a stop condition; a counterexample always is.
