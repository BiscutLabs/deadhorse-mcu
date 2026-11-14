# T13 F integration and core improvements

## Goal

Integrate the T12 FPU into the converted core (T11) to give RV32IMFC, then
apply any justified improvements. From this task on the core intentionally
differs from the Ibex reference, so equivalence no longer applies to changed
modules and other checks carry the proof.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [T11-ibex-conversion.md](T11-ibex-conversion.md), [T12-fpu.md](T12-fpu.md) and their reports
- [../10-decisions-and-risks.md](../10-decisions-and-risks.md), D2/D19/D20
- [../12-formal-verification.md](../12-formal-verification.md)

## Inputs and readiness

Requires T11 and T12 complete. Tag the T11 result first: it is the
equivalence-proved baseline that every later change is compared against.

## May change

`hw/ip/perf_core/`, `hw/ip/fpu/` interface glue, `dv/core/`, build and CI
registration, core design notes, formal ledger, report and own status line.

## Steps and deliverables

1. **F integration,** as its own change set: decoder (including compressed
   forms the selected ISA string requires), 32-entry float register file,
   `fcsr`/`frm`/`fflags`, `mstatus.FS` with dirty tracking, `misa`, illegal
   instruction when FS is off or the rounding mode is invalid, pipeline stall
   during multicycle operations, and RVFI extended to report float state.
2. Interrupts, debug entry and traps during a multicycle operation must be
   precise: cancel the FPU and commit nothing, or finish and commit all.
3. **Unchanged modules stay proved.** Rerun `equiv.py` on every module T13
   did not touch. For changed modules, prove equivalence to the T11 baseline
   under the assumption "no F instruction and FS off" where that holds.
4. Lockstep against the pinned simulator with F enabled: architectural
   tests for I, M, C and F, seeded random instruction streams mixing float
   and integer with interrupts, and a hard-float build of the flight loop.
5. riscv-formal on the integer, compressed and CSR checks. Record which F
   checks the pinned riscv-formal supports; lockstep and T12 vectors carry
   whatever it does not. Integer riscv-formal alone does not verify F.
6. **Improvements,** each as a separate change after F passes: one
   hypothesis, one measured before/after through T09, and the full check set
   rerun. Drop any improvement that does not measure better.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"
python3 dv/core/equiv.py --unchanged-since t11-baseline --candidate build/emit/perf_core --output build/t13/equiv
python3 dv/core/lockstep.py --candidate build/emit/perf_core --isa rv32imfc --suite arch,random,flight-float --output build/t13/lockstep
python3 dv/core/riscv_formal.py --target candidate --output build/t13/rvf
python3 tools/ci.py
```

Report formal depth and status honestly, F coverage achieved, and T09 timing
and area. S1 then measures this core.

## Stop and ask

Lockstep mismatches that are not explained by a documented simulator
difference; imprecise trap behaviour; timing misses the budget. Do not drop
F, flush subnormals, weaken tests or switch cores to close the task.
