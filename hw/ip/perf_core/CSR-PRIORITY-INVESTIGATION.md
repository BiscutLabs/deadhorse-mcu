# CSR unique-case proof mismatch

Status: explicitly approved 2026-11-15, implemented and independently qualified.
Production RTL and the vendor tree are unchanged by the normalization. T11
remains incomplete; this document retains the original diagnosis and trial.

## Finding

`IbexCsRegisters` preserves the procedural ordering in the pinned
`rtl/ibex_cs_registers.sv`: save-cause before DRET before MRET, and IF before ID
before WB for the saved PC, defaulting to ID. Both selectors use
`unique case (1'b1)` in the reference. The reference's uniqueness promise lets
synthesis remove the ID branch because its assignment equals the default.
This changes the lowered function on conflicting selectors.

Measured counterexample at base `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus
working changes, `build/t11/csrbank1/equiv/compare.log`: IF save is zero, ID and
WB saves are one; source-priority Chisel selects ID, while the optimized
reference selects WB. The failed next-state obligation is MEPC. No input
assumption was added. The failure is retained and is not a pass.

This is not evidence of an architectural Ibex defect. It exposes a difference
between procedural priority (including the unique-case diagnostic) and a
synthesis completion for inputs violating the uniqueness promise. Yosys also
documents a multi-selected `$pmux` as undefined in its simulation model;
rewriting the Chisel as a masked OR merely to match a solver completion would
not preserve the source's procedural priority.

## Concrete proposal

In a generated analysis copy only, replace the two exact occurrences of
`unique case (1'b1)` with `case (1'b1)`. Keep every branch, assignment, default,
port, state element and input combination. Do not change the pinned source,
production Chisel, library, timing constraints or fault controls.

Pinned source SHA-256:
`8f403e1faa0c11a1b1b645b704912cbad55bbdd7437241d7fb24cba743ccb9c1`.
Trial normalized SHA-256:
`6c9cadde850909c0fdc253746a256da2fdfd7cc6604de3206dd25917c24136e6`.
Reference parameters are `DbgTriggerEn=1`, `MHPMCounterNum=0`, other module
defaults. These differ from module defaults and must be explicit in receipts.

This changes the formal reference preparation. A result under this proposal
must be identified as equivalence to the priority-preserving analysis model,
not to the previous optimized reference. The original failure remains evidence.

## Trial results

Commands run through `python tools/env/run.py run --`:

- `python3 scratch/check_csrbank.py build/t11/csrbank1/emit/cs_registers/ibex_cs_registers.sv build/t11/csrbank1/equiv`
  fails the original 22-state comparison, with no environmental assumptions.
- `python3 scratch/check_csr_priority.py` passes the experimental unbounded
  22-state comparison and rejects output/reset-value/next-state faults.
  Receipt: `build/t11/csrbank1/priority_trial`. Scratch runner and generated
  analysis source are deliberately not committed or registered as acceptance.
- `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.CsRegistersSpec"`
  passes both tests, including read corruption rejection. The final rerun adds
  all 64 combinations of the outer and inner selector controls, checking absent
  and conflicting selects against procedural priority. The earlier architectural
  cases cover register write/set/clear, illegal accesses, interrupts, debug,
  trigger matching, counter carry/speculative reads, trap stack and reset.
- `python3 tools/timing/check.py --top ibex_cs_registers --source build/t11/csrbank1/emit/cs_registers/ibex_cs_registers.sv --clock clk_i --output build/t11/csrbank1/timing`
  measures **24.659073 ns**, **84921.312 um2**, zero electrical violations.
  Unchanged assumed **24.96 ns** limit, GF180 SS/125C/3.0V, mapped pre-layout
  with ideal clock and no wire delay. This does not establish formal acceptance.

An independent reviewer reproduced the experimental proof and all three faults
at `build/t11/csrbank1/priority_review`, verified the unchanged vendor lock, and
recommended presenting this exact scope for approval. They did not rerun CSR
simulation or timing. Trial `result.json` inherits the generic, misleading
"reference module defaults" label; the explicit parameters above and in the
generated `gold.ys` are authoritative for the trial, and this receipt defect
must be corrected before acceptance.

## Qualification required after approval

1. Enforce the pinned input hash and both exact locations/count; verify that
   reversing the normalization reproduces the pinned source byte for byte.
2. Record authorization, normalized hash, explicit parameters and source hashes
   in the aggregate proof receipt, including every negative control.
3. Use fresh Chisel emission and candidate elaboration rather than cached JSON.
4. Register and test the normalization for affected module/parent/top proofs;
   retain original-reference diagnostics and all existing checks.
5. Obtain independent review and rerun required gates. Whole-core conversion,
   ISA/retirement/workload checks and whole-core physical comparison remain open.

## Approved qualification results

`dv/core/csr_priority.py` and the `csr_priority` entry in `adaptations.json`
enforce both pinned hashes, the two exact lines and qualifier-only edits, then
reverse the edits byte-for-byte. `equiv.py` uses this analysis preparation only
for CSR/core/top comparisons. Translated candidate files are left unchanged;
byte-identical reference copies used to test the harness receive the same
analysis treatment. Simulation and physical tools do not use this normalization.
Elaboration receipts bind emitted source files and netlists, explicit reference
parameters, authorization, reversal and normalized identity. Fault receipts
retain the same provenance and name the deliberate mutation.

Measured at the same base plus working changes, through the pinned wrapper:

```text
python3 -m unittest discover -s dv/core -p "test_*.py" -v
Ran 17 tests; OK
python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.CsRegistersSpec" "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/csrbank2/emit"
Tests: succeeded 2, failed 0; All tests passed.
python3 hw/ip/perf_core/formal/check_leaves.py --emitted build/t11/csrbank2/emit --output build/t11/csrbank2/leaves
PASS configured leaf equivalence and negative controls
python3 tools/timing/check.py --top ibex_cs_registers --source build/t11/csrbank2/emit/cs_registers/ibex_cs_registers.sv --clock clk_i --output build/t11/csrbank2/timing
PASS ibex_cs_registers: 24.659073 ns, budget 24.960000 ns; electrical violations 0
python3 dv/core/equiv.py --top --candidate build/t10/ci/reference_copy --self-check --output build/t11/csrbank2/top_reference_copy
PASS equivalence: all selected modules proved; requested negative controls rejected
```

All 19 configured leaf cases pass; the CSR case proves 22 states under the
approved priority model, with no input assumptions and all three faults rejected.
The fresh emission reproduces the prior mapped area/delay. Independent reviewer
`csr_review` reproduced CSR proof/faults, simulation, guard tests and timing at
`build/t11/csrbank2/independent-review`, and additionally ran core/top reference
self-checks. They audited success/fault provenance and approved the scoped result
without actionable findings. These parent/top results qualify harness routes;
they do not establish whole Chisel-core correctness. The original failed
comparison remains unchanged at `build/t11/csrbank1/equiv`.
