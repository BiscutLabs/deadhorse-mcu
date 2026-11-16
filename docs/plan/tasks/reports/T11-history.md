# T11 historical checkpoints

This archive preserves the chronological investigation record, including failed and superseded runs. Statements of pending work describe their checkpoint only; the current acceptance status is in [T11.md](T11.md).

# T11 report

## Outcome

T11 remains incomplete: shared clock gating and the faithful core/top baseline are verified; registered execution passes architectural/workload comparisons but integrated timing and final verification remain open.

## What changed

- `hw/ip/perf_core/`: handwritten Chisel CSR/counter/ALU/register-file/compressed-decoder/fetch-FIFO/prefetch/multiplier-divider modules, emitters, independent arithmetic/register-array/counter/CSR simulation models and a parameterized leaf equivalence driver. Every translated source attributes the pinned Ibex commit and Apache-2.0 license.
- The approved counter repair changes only combinational increment logic. With no update output it uses independent 8-bit carry-select slices; with the update output it uses 4-bit slices and preserved parallel-prefix stages. Chisel `addAttribute` keeps selected combinational intermediates. There are no new registers, latency, resets or clocks. Earlier grouping attempts are historical evidence, not the current implementation.
- ALU translation covers pinned RV32BNone only, retains every operator encoding's observable behavior, and packs unused intermediate array ports as 64-bit vectors. Other RV32B configurations fail elaboration.
- `dv/core/equiv.py`: explicit parameters for reference-only leaf elaboration; output mutation now uses the existing driven-inverter/alias-safe mechanism for the ALU too. The old ALU-only constant-port mutation could be ignored by JSON wire aliasing in emitted candidates. That failed self-check remains recorded, not counted as a pass. No proof obligation was removed.
- `dv/core/module_map.json`: explicit optional shadow-register and register-file word name maps.
- `dv/core/state_equiv.py`: translated spellings supplement original names so reference self-comparison still works. Both spellings identifying different state elements is rejected as ambiguous. The full local gate exposed the original exclusive-alias defect; its failed receipt is retained, a behavioral regression covers original/translated/ambiguous cases, and reference RF/multdiv self-checks pass after the correction. State/reset/clock/product obligations are unchanged.
- `tools/timing/`: stateless combinational timing via a virtual clock, identical library/load/slew/budget, and required rejection of sequential cells in both Python and STA. Existing sequential timing checks remain. A Chisel XOR fixture, unit boundary tests and actual wrong-mode controls qualify the new mode.
- README, formal/timing ledgers and own STATUS row/log document the decisions and results. Vendor files, timing constraints, briefs and decisions remain unchanged. No complete core exists.
- The timing flow now uses an explicit combinational ABC mapping script with buffering and cell sizing, no retiming. Final STA still uses the pinned library, input slew, output load and budget. ABC's driver and delay target are mapping heuristics, separately recorded in receipts. Actual max-capacitance/max-slew reports are required, and violations fail the gate. A real electrical-only overload, missing/duplicate report tests and CLI violation counts cover the added rejection path.
- FIFO and prefetch address increment repairs preserve resetless address/data state and all cycles. Prefetch equivalence checks both the parent-only substitution and the all-Chisel parent/child hierarchy. The new verification-only `--replace` route rejects top use and inactive children and records child hashes; full-core production checks still require a manifest. Independent review found the initial missing guards; both were fixed and regression-tested.
- Multiplier/divider preserves one signed 17-by-17 multiplication for structural congruence. The initial unpacked-array word-order translation defect failed equivalence and was corrected to match the reference; the reference was unchanged. Its MAC-prefix experiment passed equivalence/model tests but worsened timing, so the faithful MAC was restored. Both experiments remain recorded.

## Checks run

Base commit `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus uncommitted T11 changes. Each command below ran in this repair session using prefix `python tools/env/run.py run --`.

| Command after prefix | Observed result / last output |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/repair6/emit" "hw/testOnly deadhorse.perf_core.*"` | Exit 0; `Tests: succeeded 5, failed 0, canceled 0, ignored 0, pending 0`; `All tests passed.` |
| `python3 hw/ip/perf_core/formal/check_leaves.py --emitted build/t11/repair6/emit --output build/t11/repair6/formal` | Exit 0; `PASS configured leaf equivalence and negative controls` |
| `python3 tools/timing/check.py --top ibex_counter --source build/t11/repair6/emit/mcycle/ibex_counter.sv --clock clk_i --output build/t11/repair6/timing_mcycle` | Exit 0; `PASS ibex_counter: 17.448200 ns, budget 24.960000 ns` |
| `python3 tools/timing/check.py --top ibex_counter --source build/t11/repair6/emit/minstret/ibex_counter.sv --clock clk_i --output build/t11/repair6/timing_minstret` | Exit 0; `PASS ibex_counter: 21.172373 ns, budget 24.960000 ns` |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/alu1/emit"` | Exit 0; successful emission |
| `python3 dv/core/equiv.py --module ibex_alu --candidate build/t11/alu1/emit/alu/ibex_alu.sv --self-check --output build/t11/alu1/formal_fixed_fault` | Exit 0; candidate `PROVED`, output fault `FAILED`; final `PASS equivalence: all selected modules proved; requested negative controls rejected` |
| `python3 dv/core/equiv.py --self-check --output build/t11/alu1/reference_fault_check` | Exit 0; reference `PROVED`, output fault `FAILED`; same final PASS |
| `python3 tools/timing/check.py --top ibex_alu --source build/t11/alu1/emit/alu/ibex_alu.sv --combinational --output build/t11/alu1/timing` | Exit 1; `FAIL ibex_alu: 62.401089 ns, budget 24.960000 ns` |
| `python3 tools/timing/check.py --self-test --output build/t11/timing_mode_validation_final` | Exit 0; Hello, CombTiming, both RegBlock fixtures pass; existing elapsed-time negative fails; final `PASS timing self-test: valid path accepted; real over-budget path rejected` |
| `python3 -m unittest tools.timing.test_timing -v` | Exit 0; `Ran 8 tests`; `OK` |
| `python3 -m unittest discover -s dv/core -p test_*.py -v` | Exit 0; `Ran 12 tests`; `OK` |
| `python3 tools/check_structure.py --include-untracked` | Exit 0, no issues |

`git diff --check` passed. Every configured CSR/counter proof rejects output, reset-value and next-state mutations. The simulation checker rejects a deliberately corrupt counter output. The stateless timing self-test rejects a register-containing design through the Python boundary checker and independently through direct STA invocation; no missing-clock check is bypassed.

Independent reviewer `t11_readiness_review` reproduced both final counter timing passes and all configured proofs, verified fresh emission bytes, and proved ten additional counter cases (widths 1, 5, 17, 33, 63 with both update-output settings) with all negative controls. Evidence is under `build/t11/review/repair6_final/`. The reviewer found no issue with the grouping or combinational keep annotations.

The same reviewer reproduced ALU equivalence/fault rejection, byte-identical fresh emission and the 62.401089 ns timing failure under `build/t11/review/alu1/`. Actual CLI and direct STA wrong-mode tests rejected counter registers. The ALU path is real, not a timing-mode error.

All-module/whole-core candidate equivalence, full candidate riscv-formal, architectural/flight candidate lockstep and full-core timing have not yet run for T11: no whole core exists. The first local `python3 tools/ci.py` run failed on the new exclusive state-alias defect in reference multdiv self-comparison (`build/t11/ci-first-failure.json`). The defect is corrected and the full gate rerun finished exit 0 with final PASS (`build/t11/ci-final.json`), before the iterative redesign. Later edits require fresh final verification. No earlier T10 result counts as T11 acceptance. No commit or push has been made.

After the latest approval, the primary agent ran the following additional commands with the same environment prefix and base commit:

| Command after prefix | Observed result / last output |
| --- | --- |
| `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"` | `Tests: succeeded 8, failed 0, canceled 0, ignored 0, pending 0`; `All tests passed.` |
| `python3 tools/timing/check.py --self-test --output build/t11/timing_sized_qualified` | Exit 0; `PASS timing self-test: valid path accepted; real over-budget path rejected` |
| `python3 -m unittest tools.timing.test_timing` | `Ran 10 tests`; `OK` |
| `python3 tools/timing/check.py --top ibex_alu --source build/t11/alu9/emit/alu/ibex_alu.sv --combinational --output build/t11/alu9/timing_sized` | Exit 0; `PASS ibex_alu: 23.850603 ns, budget 24.960000 ns` |
| `python3 dv/core/equiv.py --module ibex_register_file_ff --candidate build/t11/rf1/emit/register_file/ibex_register_file_ff.sv --self-check --output build/t11/rf1/formal` | Exit 0; proof and all three fault rejections recorded |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/leaves_v2/emit"` | Exit 0; successful emission |
| `python3 tools/timing/check.py --top ibex_compressed_decoder --source build/t11/leaves_v2/emit/compressed_decoder/ibex_compressed_decoder.sv --combinational --output build/t11/leaves_v2/timing_compressed` | Exit 0; `PASS ibex_compressed_decoder: 13.134775 ns, budget 24.960000 ns; electrical violations 0` |

The independent reviewer reproduced the ALU sized result, proved its mapped gates equivalent and rejected an output fault. The reviewer also independently injected an electrical-only load fault: measured 14.941490 ns and 16 violations, correctly rejected despite meeting the delay budget. Those diagnostics are under `build/t11/review/alu9_sized`, `alu9_production_sized` and `electrical_gate`; they are distinguished from primary-agent runs. Review recommendations were incorporated into the permanent tests.

Further primary commands, with the same prefix/base commit:

| Command after prefix | Observed result / last output |
| --- | --- |
| `python3 hw/ip/perf_core/formal/check_leaves.py --emitted build/t11/counter11/emit --output build/t11/counter11/formal` | Exit 0; `PASS configured leaf equivalence and negative controls` for its then-registered nine configurations |
| `python3 dv/core/equiv.py --module ibex_fetch_fifo --candidate build/t11/fifo2/emit/fetch_fifo/ibex_fetch_fifo.sv --self-check --output build/t11/fifo2/formal` | Exit 0; unbounded proof and four rejected faults |
| `python3 dv/core/equiv.py --module ibex_prefetch_buffer --candidate build/t11/prefetch2/emit/prefetch_buffer/ibex_prefetch_buffer.sv --replace ibex_fetch_fifo=build/t11/prefetch2/emit/prefetch_buffer/ibex_fetch_fifo.sv --self-check --output build/t11/prefetch2/formal` | Exit 0; unbounded proof and four rejected faults |
| `python3 dv/core/equiv.py --module ibex_multdiv_fast --candidate build/t11/multdiv2/emit/multdiv_fast/ibex_multdiv_fast.sv --self-check --output build/t11/multdiv2/formal` | Exit 0; six matched states, one structurally matched signed product; output/reset/next-state/sign faults rejected |
| Same multiplier command with `multdiv3` paths | Exit 0; same proof obligations and faults |
| `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.MultdivSpec"` | Exit 0; `Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0`; `All tests passed.` |
| `python3 -m unittest discover -s dv/core -p test_*.py` | Exit 0; `Ran 14 tests`; `OK` |
| Same core unit command after state-alias regression | Exit 0; `Ran 15 tests`; `OK` |
| `python3 dv/core/equiv.py --module ibex_multdiv_fast --self-check --output build/t11/reference_map_recheck/multdiv` | Exit 0; reference proof and four fault rejections |
| `python3 dv/core/equiv.py --module ibex_register_file_ff --self-check --output build/t11/reference_map_recheck/register_file` | Exit 0; reference proof and three fault rejections |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/checkpoint/emit" "hw/testOnly deadhorse.perf_core.MultdivSpec"` | Exit 0; restored faithful MAC emitted; both arithmetic/model-negative tests pass |
| `python3 dv/core/equiv.py --module ibex_multdiv_fast --candidate build/t11/checkpoint/emit/multdiv_fast/ibex_multdiv_fast.sv --self-check --output build/t11/checkpoint/formal_multdiv` | Exit 0; restored faithful MAC proof and all four faults pass |

Exact additional timing commands/receipts and measured areas are in the
[timing ledger](../../../../docs/ledger/timing.md). The latest primary timing
passes are mcycle 21.831022 ns, counter11 minstret 19.555578 ns, RF 14.182172 ns,
decoder 13.134775 ns, FIFO2 19.284517 ns and prefetch2 19.029213 ns. Each has zero
electrical violations. Multdiv2 fails at 52.541870 ns, multdiv3 at 55.642658 ns,
also with zero electrical violations. Independent review reproduced the
counter/FIFO/prefetch results and proved twelve additional counter width/mode
cases under `build/t11/review/counter11`. The latest report supersedes earlier
checkpoint descriptions below without erasing their measurements.

Fresh-context reviewer `t11_checkpoint_review` found no actionable RTL or
proof-weakening issue. It independently emitted current sources, reproduced
multdiv and prefetch/FIFO proofs with all faults, and reproduced the faithful
52.541870 ns timing failure. After the full gate exposed the state-name issue,
the reviewer separately reran reference/candidate multdiv, reference RF and all
fifteen core harness tests, confirming the fix. Evidence is under
`build/t11/checkpoint_review/`; this approves the focused work, not T11 completion.

## Numbers

The following table describes the earlier repair6/ALU1 checkpoint, measured by
the commands above at the named base commit plus working changes. That checkpoint
had five configured leaf induction proofs, one exhaustive ALU proof and five
simulation tests. The ten extra partial-width proofs there were run by the reviewer.
The subsequent pre-redesign checkpoint `build/t11/current_formal` proves eleven
configurations including the Chisel prefetch hierarchy and multiplier/divider;
the local gate's observed Scala stage passes sixteen tests across the repository.
Separate current core tests comprise eight datapath/CSR/counter cases and two
multiply/divide cases. The restored faithful MAC is rechecked separately below.

| Configuration | Worst delay ns | Cell area square micrometres | Result |
| --- | ---: | ---: | --- |
| Repaired mcycle, width 64, ProvideValUpd false | 17.448200 | 10684.0384 | Pass |
| Repaired minstret, width 64, ProvideValUpd true | 21.172373 | 12664.1088 | Pass |
| Faithful RV32BNone ALU | 62.401089 | 16914.0160 | Fail |

The counter rows are register-to-register paths. The ALU input-to-output path runs from `operator_i[1]` through decode/operand selection, adder carry, zero/comparison logic and output selection to `result_o[0]`, with 34 combinational cells. No full-core area, frequency or timing result exists.

These are mapped, pre-layout results without wire delay: pinned Yosys 0.71+34, OpenSTA 3.2.0, GF180 `gf180mcu_fd_sc_mcu7t5v0`, SS/125 C/3.0 V. The assumed period remains 41.6 ns; assumed budget fraction 0.60 gives 24.96 ns. Assumed input slew is 0.5 ns, output load 0.05 pF, ideal clock and zero IO delay. Every receipt includes exact source/flow/library hashes.

Earlier candidate attempts remain in `build/t11/repair1` through `repair5`. Measured minstret failures were 49.334980, 27.871319, 30.850758 and 25.981422 ns; repair5 passed minstret at 21.172373 ns but failed mcycle at 30.953936 ns. Repair6 uses the independently verified grouping appropriate to each constant parameter mode. The previous checkpoint's direct 64-bit counter failure (41.118233 ns) is historical evidence retained in the ledger, not rerun here or relabeled as a pass.

## Deviations from the brief

The user first approved preserving inherited combinational boundaries and the necessary production-isolation/timing support, with unchanged budgets. After the direct counter failed, the user separately approved localized combinational increment restructuring. The latest approval extends equivalent combinational repairs to measured timing failures throughout T11 after retaining each faithful baseline proof, while preserving every register, port, reset, cycle behavior, budget and check. Additional state/latency is now explicitly approved only for the iterative multiplier; other retiming, new assumptions or relaxed limits remain separate stop conditions.

Leaf timing is checked before continuing to larger modules. The counter configurations are actually instantiated by the pinned core. Stateless ALU timing needs the virtual-clock route because this inherited combinational module has no clock port; sequential designs cannot use that route. No wrapper register was added to the core and no path was excluded.

Chisel attributes use the pinned public `addAttribute` API, documented in the [official Chisel API](https://www.chisel-lang.org/api/latest/chisel3/util/addAttribute%24.html). They preserve combinational logic only and are not timing exceptions. Failed attempts and the repaired ALU fault-injection defect are retained as diagnostic evidence.

## Open issues

The prior ALU timing blocker is resolved for the repaired leaf with the qualified mapping flow. The faithful multiplier retains its recorded timing failure; the approved iterative replacement passes standalone and integrated-multdiv timing. The execution-stage parent is now being repaired under the prior same-cycle approval. No timing budget changed. Historical area-only results can contain library electrical-limit violations and are not reclassified as clean characterized timing. New results require zero reported electrical violations and are identified by mapping-flow version. Reference/candidate comparisons must rerun both sides under this same corrected flow.

Independent bounded synthesis diagnostics (`build/t11/review/product17/`) found
an isolated signed 17-by-17 product at 44.486725 ns under the qualified recipe,
39.733932 ns with Booth lowering, and 25.083092 ns using classic ABC mapping.
The best tried full faithful block mapping was 37.148552 ns, still over 24.96 ns.
All completed trials had zero electrical violations; mapper-target-zero and
Booth/speedup tool failures remain failures. These are reviewer measurements,
not a qualified replacement flow or proof that combinational closure is impossible.
Tighter mapping targets and preserved carry intermediates did not close timing.

Decision approved by the user after these unsuccessful same-cycle trials:
permit a narrower iterative Chisel multiplier with additional multiply cycles,
retain the 24.96 ns budget, and explicitly revise the affected module's
cycle-by-cycle equivalence requirement to a reviewed arithmetic/transaction
refinement proof plus existing ISA/lockstep/fault checks. Unchanged modules
retain exact equivalence. Whole-core comparison would also need to operate at
instruction retirement boundaries rather than demand identical clock-by-clock
outputs, because extra multiply cycles propagate into processor timing.
This changes state/latency and proof obligations,
and was explicitly approved by the user. It is implemented as an optional variant while preserving the faithful baseline. No deadline, tolerance or check is silently waived.

Whole-core conversion, parent substitutions, full parameter coverage, production candidate isolation, gated-clock support, reference/candidate physical comparison and complete acceptance remain outstanding. D44 arithmetic and bounded ISA limitations are unchanged.


Approval update, 2026-11-14: the user approved the recommended iterative
multiplier redesign, extra multiply cycles and corresponding transaction/
arithmetic and retirement-level comparison contract. This supersedes the
pending-decision language above; it does not waive timing, ISA semantics,
negative controls or exact equivalence for unchanged modules. The faithful
multiplier remains a comparison target. The preceding full local CI rerun
finished exit 0 with final `PASS`; receipt `build/t11/ci-final.json`. New
iterative implementation checks are recorded separately as they complete.


### Iterative multiplier checkpoint

Measured at base `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus working changes,
using the pinned environment and unchanged slow-corner timing assumptions above:

- `python3 hw/ip/perf_core/formal/check_iterative.py --candidate build/t11/iterative2/emit/iterative_multiply/IterativeMultiply.sv --output build/t11/iterative2/formal`: exit 0; `PASS iterative multiply: emitted transition induction, all state faults and integer lemmas`. All nine state components, clocks, resets, enables and outputs compared against the independently reviewed mathematical machine; twelve emitted faults rejected and six formal witnesses covered. The integer-to-bitvector composition is reviewed explicitly, not claimed as a single end-to-end solver theorem.
- `python3 hw/ip/perf_core/formal/check_division.py --candidate build/t11/iterative2/emit/multdiv_iterative --output build/t11/iterative2/division_final`: exit 0; selected division exact proof, generated reference roundtrip and output/next-state/reset faults pass. Multiply disabled is an explicit boundary condition; mixed-operation correctness is checked separately in simulation.
- `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.IterativeMultiplySpec"`: exit 0; both tests passed, including every-phase reset/restart, captured inputs, exact enabled-step completion, backpressure and corruption rejection. Independent reviewer reproduced the same suite.
- `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.MultdivSpec"` at iterative2: exit 0; three tests passed, including faithful and iterative mixed MUL/DIV/REM integer-model comparisons and corruption rejection. The later execution-stage test is additional.
- `python3 tools/timing/check.py --top IterativeMultiply --source build/t11/iterative1/emit/iterative_multiply/IterativeMultiply.sv --clock clk_i --output build/t11/iterative1/timing`: exit 0; measured 23.659555 ns, zero electrical violations.
- `python3 tools/timing/check.py --top ibex_multdiv_fast --source build/t11/iterative2/emit/multdiv_iterative/ibex_multdiv_fast.sv --source build/t11/iterative2/emit/multdiv_iterative/IterativeMultiply.sv --clock clk_i --output build/t11/iterative2/timing`: exit 0; measured 23.376678 ns and 55393.6768 square micrometres, zero electrical violations. Both unchanged 24.96 ns budgets pass. Independent reviewer reproduced both timing results and freshly emitted matching RTL hashes.

The direct nested word-projection integer query returned unknown at its unchanged
600-second solver limit (`build/t11/iterative1/formal_complete` and independent
`build/t11/iterative_review/formal`). The replacement factors the same theorem
into checked Euclidean existence, uniqueness and digit-composition lemmas; no
input domain or property was weakened. Original failures are retained.

Division wrapper diagnostics first rejected enum/unpacked-array connections.
Normalizing the reference through generated Yosys output solves this, with an
explicit roundtrip proof. A subsequent comparison localized different unused
DFFE D inputs when enable=0; canonicalization now keeps feedback muxes
(`-nodffe -nosdff`) on both sides, preserving the strict transition checker.

Independent focused reviewer found no remaining multiplier/divider issue and
approved that scope. Evidence: `build/t11/iterative_review/`. This is not approval
for subsequent execution-stage repairs or whole-core completion. No commit/push.


### Execution-stage continuation and timing-flow correction

`IbexExBlock` faithful parent and approved same-cycle variants are proved with
Chisel ALU/multdiv children substituted. EX1 faithful proof passes; guarded
comparator EX3, local fixed divider arithmetic EX4, result-path isolation EX5,
comparison-decode EX6, narrower carry-group EX7 and bit-zero split EX8 all prove
exact parent state/output behavior with faults. The initial EX2 direct comparator
failed because arbitrary inputs allow neither mult/div select asserted; the
original-ALU fallback fixes this without an assumption. EX2 is not accepted.
Mapped timing remains failed: EX1 27.864782ns; EX3 30.251865ns; EX4 27.776594ns;
EX5 26.638506ns; EX6 25.525236ns under v1. Receipts are under build/t11/exN/.
A later alias-aware flow measures EX6 25.514265ns, EX7 25.702322ns and EX8
26.176121ns, all over 24.96ns, all with zero electrical violations.

The qualified `buffered-sized-alias-load-v2` mapper accounts conservatively for
multiple output pins sharing a net. Synthesis finds nonconstant alias groups,
uses max multiplicity times 50fF as the mapper load, and checks that ABC did not
increase multiplicity. Final STA remains 50fF per output pin. Independent STA
inspection of the new fixture confirms two ports total 100fF. Full self-test and
all eleven timing unit tests pass, independently reproduced under
`build/t11/iterative_review/alias_flow`. Existing electrical, clock, stateless,
unsupported-macro and actual over-budget negative controls are unchanged.

Concurrent sbt invocations exposed a shared class-product race (EX7 emitter
could not load IbexAlu after another emitter changed unmanagedSources). The
pinned build wrapper now holds an OS file lock throughout the child sbt lifetime;
recompilation/emission then passed. No tool version or validation was changed.
`tools/ci.py` now includes implemented-leaf proofs, iterative arithmetic and
division proofs and production-profile block timing, preserving every original
check. Full revised gate is not yet claimed passing.


Current-source checkpoint `build/t11/approved_checkpoint/emit` matches EX6 RTL
hashes; later EX7/EX8/EX9 experiments are discarded, with their results retained.
EX9's precomputed/doubled hidden ALU operands proved equivalent but mapped at
27.568184ns and did not solve integrated timing. The final alias mapper preserves
the original frontend/synthesis ordering, using the extra premap pass only to
count aliases. Its identifier is `buffered-sized-alias-load-v3`; intermediate v2
JSON reimport changed ABC traversal and therefore its numbers are historical.
Current production EX measures 25.975801ns at unchanged 24.96ns, zero electrical
violations, independently reproduced by the fresh checkpoint reviewer. Standalone
iterative multiplier returns to its reproduced 23.659555ns with this final flow.
No STA constraint or check changed. Registered execution boundaries and extra
ALU/divide cycles have been proposed to the user but are not yet approved or
implemented. Until that decision, no latency-changing EX work is started.


Final recipe/current-source timing sweep:
`python3 hw/ip/perf_core/check_timing.py --emitted build/t11/approved_checkpoint/emit --output build/t11/approved_checkpoint/timing`
returned exit 1, `FAILED T11 implemented-block timing`. Eleven blocks pass;
standalone IterativeMultiply is 23.659555ns and 29066.6432 square micrometres.
Integrated multdiv is now 25.093014ns (RR), 61603.8976 square micrometres;
EX is 25.975801ns (RO), 132306.8992 square micrometres. Both integrated results
fail 24.96ns; all thirteen measurements report zero electrical violations.
The conservative aggregate alias load is 100fF for multdiv/EX mapping, with
unchanged 50fF per output port in STA. Earlier integrated-multdiv timing passes
remain historical v1 results, not current final-flow passes. No gate is waived.


Fresh-context final checkpoint review: no remaining actionable functional,
proof-integrity, timing-load, CI-preservation or build-lock findings. Independent
checks passed eleven timing unit tests, fifteen core harness tests, repaired EX
exact equivalence and its three faults, and the complete iterative multiplier
proof/lemmas/twelve faults/six covers. Current multdiv and EX timing failures were
independently reproduced. Evidence `build/t11/iterative_checkpoint_final/`.
The reviewer explicitly withheld task-completion/commit approval because timing
and whole-core acceptance remain incomplete.

The revised local gate has observed all twenty-one Scala tests passing across
six suites, including the new execution-stage corruption control. The gate subsequently finished with the two timing failures recorded below; no final gate pass is claimed.
The active-build probe `python3 build/t11/check_sbt_lock.py` observed the exclusive
repository lock while CI ran, and the independent proof emitter subsequently
waited and completed successfully without the previous class-product race.


Final revised gate command `python tools/env/run.py run -- python3 tools/ci.py`
finished exit 1. Last lines:

```text
FAIL ibex_multdiv_fast: 25.093014 ns, budget 24.960000 ns; electrical violations 0
FAIL ibex_ex_block: 25.975801 ns, budget 24.960000 ns; electrical violations 0
FAILED T11 implemented-block timing
```

Stable receipt: `build/t11/ci-approved-checkpoint.json`. All twenty-one simulation
tests, thirteen configured faithful/repaired equivalence cases with their faults,
iterative transition/arithmetic proofs with twelve faults/six covers, selected
division and normalization proofs, existing formal smoke/register proofs and
final timing-flow self-test passed in this gate. Eleven of thirteen production-
profile timing cases pass. The original downstream T10 reference/ISA/lockstep
commands remain in CI but were not reached after its required timing failure;
the earlier pre-redesign complete CI pass is not substituted for this failed run.
All-module/whole-core Chisel acceptance still cannot run because the core is
incomplete. Final structure check and `git -c core.safecrlf=false diff --check`
pass. No commit or push was made. T11 is `[!]` pending the proposed execution-
retiming decision in `hw/ip/perf_core/EXECUTION-TIMING.md`; the question has not
been answered and no extra ALU/divide-cycle implementation has begun.


2026-11-15 approval: the user approved registered execution boundaries, extra
ALU/divide cycles and the necessary pipeline-control changes. This supersedes
the pending-decision text above. Timing, electrical, ISA, reference, workload
and negative-control requirements remain unchanged; no completion is claimed.

## Registered execution checkpoint, 2026-11-15

The approved `ClockedExecute` captures one request, registers its response and
divides each divider transition into issue/compute/advance phases. Inputs may
change immediately after acceptance. The production timing profile now uses
this replacement; `--profile pre-registered` retains the superseded integrated
prototypes and their strict failure status. All baseline proofs remain gating.

Measured at base `a532304` plus working changes, through the pinned environment:

```text
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.ClockedExecuteSpec"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.

python tools/env/run.py run -- python3 hw/ip/perf_core/formal/check_execute.py --variant normal --candidate build/t11/registered1/emit/clocked_execute --output build/t11/registered_formal/prove7
PROVED equivalence: ClockedExecute
successful proof by k-induction.
DONE (PASS, rc=0)
```

The proof command above spells out the then-default normal variant; the current
default runs all variants. Production binding proves 32 named state elements,
reset/clocks/outputs and rejects output/next-state faults. The contract has 37
emitted assertions plus asserted correspondence/progress invariants. Startup
reset is the only DUT input assumption. A 12-step induction search proves the
contract unboundedly, not merely through 12 cycles. Design-derived producer
deadlines (also proven/simulated) are ALU1, MUL36, DIV/REM111 edges, or6 for
non-constant-time zero division, independent of receiver readiness.

Six `--variant capture|result|hold|reset|dispatch|feedback` runs at
`build/t11/registered_formal/fault2-<variant>` reject their planted faults.
`--variant cover` at `build/t11/registered_formal/cover3` reaches all eight
original predicates within depth120. Witness-only constrained operands and held
responses permit terminal-frame search; no safety assertion uses that stimulus
or skips any cycle. Earlier prefix-cover attempts `cover1`/`cover2` timed out
at the unchanged limit and remain diagnostic failures. Earlier setup/induction
attempts exposed tooling and non-inductive history scheduling; the final history
is an initialized register, not a new DUT assumption. One fault run suffered a
backwards host clock jump and SBY ERROR; only its unchanged rerun is accepted.

`tools/timing/check.py --top ClockedExecute --clock clk_i`, with all four emitted
sources in `build/t11/registered1/emit/clocked_execute` and output
`build/t11/registered1/timing`, measures **23.112328 ns**, **130017.3056 um2**
mapped cell area and **zero electrical violations**. The assumed24.96ns budget,
GF180 SS/125C/3.0V corner, load/slew and qualified mapping recipe are unchanged.
This is pre-layout block evidence, not whole-core or post-layout signoff.

Fresh independent reviewer `registered_execution_review` reproduced simulation,
fresh emission/timing, production binding, induction, six contract faults and
eight covers at `build/t11/registered_review/`. Trace inspection confirmed full
division, fast-zero completion and integer results. No remaining focused review
findings; earlier request-loss and proof-binding gaps were fixed before approval.
Full local CI is running. Decoder/core translation and whole-core acceptance
remain open; no whole-task completion, commit or push is claimed.

## Decoder and load/store checkpoint, 2026-11-15

Added faithful `IbexDecoder` and `IbexLoadStoreUnit`, fixed-profile constructor
guards, focused independent instruction/byte-memory tests and mandatory leaf
proof/timing registrations. The decoder keeps its instruction copies independent
even for illegal encodings. LSU preserves ten states, all reset semantics and
arbitrary-input error/grant/response behavior. No latency or reference change.

Measured at base `a532304` plus working changes:

```text
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.DecoderSpec" "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/decoder1/emit"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.
python tools/env/run.py run -- python3 dv/core/equiv.py --module ibex_decoder --candidate build/t11/decoder1/emit/decoder/ibex_decoder.sv --self-check --output build/t11/decoder1/equiv_checked
PROVED equivalence: ibex_decoder
PASS equivalence: all selected modules proved; requested negative controls rejected
python tools/env/run.py run -- python3 tools/timing/check.py --top ibex_decoder --source build/t11/decoder1/emit/decoder/ibex_decoder.sv --combinational --output build/t11/decoder1/timing
PASS ibex_decoder: 15.133662 ns, budget 24.960000 ns; electrical violations 0

python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.LoadStoreSpec" "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/lsu1/emit"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.
python tools/env/run.py run -- python3 dv/core/equiv.py --module ibex_load_store_unit --candidate build/t11/lsu1/emit/load_store_unit/ibex_load_store_unit.sv --self-check --output build/t11/lsu1/equiv
PROVED equivalence: ibex_load_store_unit
PASS equivalence: all selected modules proved; requested negative controls rejected
python tools/env/run.py run -- python3 tools/timing/check.py --top ibex_load_store_unit --source build/t11/lsu1/emit/load_store_unit/ibex_load_store_unit.sv --clock clk_i --output build/t11/lsu1/timing
PASS ibex_load_store_unit: 16.342241 ns, budget 24.960000 ns; electrical violations 0
```

Mapped areas measured by the same timing commands: decoder **8372.4928 um2**,
LSU **14874.6752 um2**, unchanged GF180 corner/load/slew and assumed budget.
Decoder exhaustive equivalence rejects output faults; LSU unbounded named-state
induction rejects output/reset/next-state faults. Fresh reviewers independently
reproduced both proofs/faults and timing at `build/t11/decoder_review` and
`build/t11/lsu_review`, with no blocking findings. Simulation negative controls
also pass. LSU simulation does not explicitly exercise PMP errors, midtransaction
reset, simultaneous second grant/first response or performance outputs; exact
arbitrary-input/reset equivalence covers those translation semantics.

The ongoing local gate's simulation stage passed all 23 tests present when it
started; the four new decoder/LSU tests passed in the focused commands above.
Later gate stages consume the new modules. This is not final whole-task CI or
whole-core acceptance, and no completion/commit/push is claimed.

## IF, controller and writeback checkpoint, 2026-11-15

Added faithful `IbexIfStage`, `IbexController`, and bypass `IbexWbStage`, their
focused behavioral suites, emitter and mandatory proof/timing registrations.
IF instantiates the translated prefetch/FIFO/decoder; ten child state aliases
record hierarchy spelling changes. No assumptions or state exclusions were added.
Measured at base `a532304` plus working changes:

```text
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.IfStageSpec"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.
python tools/env/run.py run -- python3 dv/core/equiv.py --module ibex_if_stage --candidate build/t11/if1/emit/if_stage/ibex_if_stage.sv --replace ibex_prefetch_buffer=build/t11/if1/emit/if_stage/ibex_prefetch_buffer.sv --replace ibex_fetch_fifo=build/t11/if1/emit/if_stage/ibex_fetch_fifo.sv --replace ibex_compressed_decoder=build/t11/if1/emit/if_stage/ibex_compressed_decoder.sv --self-check --output build/t11/if1/equiv_mapped
PROVED equivalence: ibex_if_stage
PASS equivalence: all selected modules proved; requested negative controls rejected
python tools/env/run.py run -- python3 tools/timing/check.py --top ibex_if_stage --source build/t11/if1/emit/if_stage/ibex_if_stage.sv --source build/t11/if1/emit/if_stage/ibex_prefetch_buffer.sv --source build/t11/if1/emit/if_stage/ibex_fetch_fifo.sv --source build/t11/if1/emit/if_stage/ibex_compressed_decoder.sv --clock clk_i --output build/t11/if1/timing
PASS ibex_if_stage: 23.411352 ns, budget 24.960000 ns; electrical violations 0

python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.ControllerSpec"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.
python tools/env/run.py run -- python3 dv/core/equiv.py --module ibex_controller --candidate build/t11/controller1/emit/controller/ibex_controller.sv --self-check --output build/t11/controller1/equiv
PROVED equivalence: ibex_controller
PASS equivalence: all selected modules proved; requested negative controls rejected
python tools/env/run.py run -- python3 tools/timing/check.py --top ibex_controller --source build/t11/controller1/emit/controller/ibex_controller.sv --clock clk_i --output build/t11/controller1/timing
PASS ibex_controller: 18.369602 ns, budget 24.960000 ns; electrical violations 0

python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.WbStageSpec"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.
python tools/env/run.py run -- python3 dv/core/equiv.py --module ibex_wb_stage --candidate build/t11/wb1/emit/wb_stage/ibex_wb_stage.sv --self-check --output build/t11/wb1/equiv
PROVED equivalence: ibex_wb_stage
PASS equivalence: all selected modules proved; requested negative controls rejected
python tools/env/run.py run -- python3 tools/timing/check.py --top ibex_wb_stage --source build/t11/wb1/emit/wb_stage/ibex_wb_stage.sv --combinational --output build/t11/wb1/timing
PASS ibex_wb_stage: 6.218218 ns, budget 24.960000 ns; electrical violations 0
```

Mapped cell areas from those commands: IF **52581.6256 um2**, controller
**7966.3808 um2**, WB **1108.576 um2**. GF180 SS/125C/3.0V, ideal clock,
no wires, assumed load/slew and **24.96 ns** budget unchanged. These are block
measurements, not post-layout or whole-core results.

IF proves all 24 named states, reset/clocks and outputs; rejects output, reset,
next-state and gained-reset controls. Controller proves ten states and rejects
output/reset/next-state controls. WB proves all combinational inputs/outputs
and rejects an output fault, including simultaneous write enables. Each focused
simulation also rejects its corrupt-result control. IF simulation uses an
independent byte-program fixture; errors/live redirects are checked by exact
equivalence rather than explicit simulation scenarios. Fresh independent
reviewers reproduced proofs, faults, timing and tests under
`build/t11/{if_review,controller_review,wb_review}` and approved each scope.
Controller review also re-emitted identical RTL. Whole T11 remains in progress.

## CSR proof-baseline decision, 2026-11-15

Added `IbexCsRegisters` using translated CSR/counter leaves, explicit pinned
configuration guards and inlining name aliases, plus `CsRegistersSpec` and
mandatory emitter/proof/timing registration. The original reference comparison
fails on conflicting save selectors because uniqueness-based synthesis drops
a source-priority branch. No assumption, exemption or passing classification
was substituted. Detailed commands, counterexample, measured timing and
reviewed analysis-copy proposal are in
[CSR-PRIORITY-INVESTIGATION.md](../../../../hw/ip/perf_core/CSR-PRIORITY-INVESTIGATION.md).

Both CSR tests pass, including all 64 outer/inner selector combinations and
the corrupt-read control. Initial block timing passes at measured 24.659073 ns,
84921.312 um2, zero electrical violations; unchanged assumed 24.96 ns limit.
The experimental priority-preserving reference copy proves 22 states without
input assumptions and rejects all three state/output faults. Independent review
reproduces that trial and recommends explicit approval before baseline adoption.
It is not an accepted T11 proof result. Approval is pending; vendor and
production RTL were not modified to match a synthesis completion.

`python tools/env/run.py run -- python3 -m unittest discover -s dv/core -p test_harness.py -v`
passes all eight harness tests. An initial dotted-module invocation failed
because the suite requires its directory on the import path; using its existing
discovery convention fixed the invocation without changing tests.

The earlier full local CI continues its reference-copy formal suite. It began
before the latest blocks/tests and cannot certify the present tree. The current
configured leaf gate includes the unresolved CSR comparison and must fail
until its baseline decision is resolved. No commit or push is authorized by
verification yet; whole T11 acceptance remains incomplete.

## Approved CSR normalization qualification, 2026-11-15

User approved the two CSR analysis-copy qualifier removals. Added
`dv/core/csr_priority.py`, pinned adaptation entry, synthetic provenance tests,
and elaboration/source/netlist/parameter receipt binding in `equiv.py`, including
fault receipts. Vendor source and production RTL remain unchanged. Fresh CSR
emission, tests, proof, timing and parent/top harness route checks pass. Exact
commands and results are in the investigation's approved-qualification section.
All 19 then-configured leaf cases/faults pass; CSR proves 22 states under the
approved model without input assumptions. Independent reviewer `csr_review`
reproduced CSR checks and core/top reference self-checks, audited all receipts,
and found no actionable issues.

The earlier `python tools/env/run.py run -- python3 tools/ci.py` run completed
with exit zero and final `PASS`. Its receipt is preserved as
`build/t11/ci-registered-decoder-lsu-checkpoint.json`. It covered the 23 tests and
15 configured leaf cases present at its respective stages, plus registered
execution, reference formal/stress and reference-copy architectural/flight
checks. It predates subsequent IF/controller/WB/CSR/ID additions and does not
certify the current tree or a Chisel whole core. No task completion is claimed.

## ID stage and remaining priority decision, 2026-11-15

Added faithful `IbexIdStage`, translated decoder/controller connections, state
name alias, `IdStageSpec`, emission and mandatory configured proof/timing cases.
Both behavioral tests and the corrupt-operand control pass. Timing measures
24.466211 ns, 29215.9168 um2, zero electrical violations under unchanged limits.
The original 15-state proof fails for conflicting instruction copies because
its unique-case lowering differs from source priority. Independent review finds
no mistake in the implicated Chisel priority path and reproduces the failure.

The single-qualifier analysis-copy trial passes unbounded proof without input
assumptions and rejects output/reset/next-state faults. An independent fresh
elaboration reproduces trial proof, tests and timing. This is a proposed
extension beyond the approved two-CSR normalization; approval is pending.
Exact commands, hashes, counterexample, alternative and review scope are in
[ID-PRIORITY-INVESTIGATION.md](../../../../hw/ip/perf_core/ID-PRIORITY-INVESTIGATION.md).
No original-reference pass or whole-core completion is claimed. Remaining
core/top sources contain no further selectors of this kind in the reviewed scan.

`python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"`
completed successfully: `Tests: succeeded 31, failed 0, canceled 0, ignored 0,
pending 0`; `All tests passed.` Measured elapsed time was 669 seconds at base
`a532304` plus working changes. No test was skipped, relaxed or marked expected-fail.

## ID normalization accepted, 2026-11-15

The user approved the single ID qualifier normalization. The hash/location/
reversal guards and receipts now apply it to ID/core/top analysis only; both
CSR and ID guards pass all 18 Python harness tests. Original failures remain
recorded. Vendor and production RTL are unchanged.

```text
python tools/env/run.py run -- python3 hw/ip/perf_core/formal/check_leaves.py --emitted build/t11/id2/emit --output build/t11/id2/leaves
PASS configured leaf equivalence and negative controls
python tools/env/run.py run -- python3 dv/core/equiv.py --top --candidate build/t10/ci/reference_copy --self-check --output build/t11/id2/top_reference_copy
PASS equivalence: all selected modules proved; requested negative controls rejected
```

All 20 configured cases pass. Independent reviewer reproduces accepted ID
proof (15 states, no assumptions, all three faults rejected), source guards,
and core/top reference self-checks at `build/t11/id2/independent-review`.
Root fresh ID timing at `build/t11/id2/timing` reproduces 24.466211 ns,
29215.9168 um2 and zero electrical violations under unchanged constraints.
This supersedes the pending ID approval above; full Chisel core integration
and acceptance remain open.

## Faithful core baseline, 2026-11-15

Added `IbexCore.scala`, `EmitCore.scala`, `CoreSpec.scala` and
`formal/check_core.py`. IF/controller provide internal observation nodes for
the parent RVFI monitor. The strict proof preserves all reference state,
including otherwise-constant RVFI flops, with no added state exceptions or
environment assumptions. Module maps prefix already-qualified child aliases.
Local CI now emits and proves this baseline, including all fault controls;
the existing `hw/test` includes its behavioral suite automatically.

Commands run by the implementing agent in the pinned environment:

```text
python tools/env/run.py run -- python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitCore build/t11/core2/emit"
[success] Total time: 11 s
python tools/env/run.py run -- python3 hw/ip/perf_core/formal/check_core.py --emitted build/t11/core2/emit --output build/t11/core2/equiv
PROVED equivalence: ibex_core
PASS faithful translated core equivalence and negative controls
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.CoreSpec"
Tests: succeeded 2, failed 0, canceled 0, ignored 0, pending 0
All tests passed.
python tools/env/run.py run -- python3 tools/check_structure.py --include-untracked
exit 0
```

Measured at base `a532304` plus working changes: 163 matched state elements,
one structural multiplier, thirteen active child replacements, zero environment
assumptions. The output/reset-value/next-state/gained-reset faults all fail as
required. Initial `core1` comparison exposed only a Chisel/slang register-field
granularity mismatch; splitting the IRQ fields and retaining constant RVFI
registers resolved it without modifying the proof harness.

Independent fresh-context reviewer `/root/core_review` checked wiring,
RVFI/interrupt/debug/reset semantics and the state maps, reproduced the core
proof and all faults at `build/t11/core2/independent-review/equiv`, and reran
both CoreSpec tests successfully. No actionable findings. Simulation is finite
directed coverage, not a replacement for remaining ISA/workload checks.

The full local CI has not been rerun after these additions. Its prior successful
checkpoint predates this core; no current-tree full-CI pass is claimed. The
core baseline retains the known unregistered execution path and is not the
timing-closed production implementation. No new whole-core area/timing number
is claimed. Registered integration, top wrapper, candidate manifest, inactive
module exclusion review, full acceptance and final review remain required.

## Missing clock-gate dependency

T11 requires the project's gating wrapper, but no Chisel clock-gate wrapper
exists anywhere in the hardware tree. Its shared-library May change allowance
covers interface bundles only. Adding a shared wrapper therefore needs scope
approval under AGENTS.md. The concrete proposal is recorded in
[CLOCK-GATE-DEPENDENCY.md](../../../../hw/ip/perf_core/CLOCK-GATE-DEPENDENCY.md):
selected GF180 ICG, matching verification and FPGA bindings, unchanged wake,
test/reset behavior and checks. Approval requested; no wrapper implemented,
no gate marked complete, no commit or push.

## Approved shared gate and top baseline, 2026-11-15

The user approved the shared-wrapper scope above. Added `ClockGate` with the
selected GF180 ICG BlackBox, an explicit reference-primitive verification
binding, and an FPGA clock-enable consumer example. There is no claim of a
complete FPGA core binding. Gate properties, phase simulation, target binding
and dedicated pre-layout clock/enable timing are independently reviewed by
`clock_gate_review`. All figures below are measured at `a532304` plus T11 changes.

```
python tools/env/run.py run -- python3 tools/sbt.py "hw/runMain deadhorse.lib.EmitClockGate build/t11/clock_gate/emit2" "hw/testOnly deadhorse.lib.ClockGateSpec"
All tests passed (4).
python tools/env/run.py run -- python3 hw/lib/formal/clock_gate_proof.py --emitted build/t11/clock_gate/emit2 --output build/t11/clock_gate/proof5
PASS; binding induction, covers, and fault controls.
python tools/env/run.py run -- python3 hw/lib/formal/clock_gate_timing.py --source build/t11/clock_gate/emit2/asic/ClockGate.sv --output build/t11/clock_gate/timing
PASS; clock delay 1.896664 ns; minimum enable setup/hold slack 0.624586 ns; zero electrical violations.
python tools/env/run.py run -- python3 dv/core/equiv.py --top --candidate build/t11/top1/candidate --self-check --output build/t11/top1/equiv
PASS equivalence: all selected modules proved; requested negative controls rejected.
python tools/env/run.py run -- python3 dv/core/equiv.py --all-modules --candidate build/t11/top1/candidate --self-check --output build/t11/top1/all_modules
PASS; 18 active modules proved; eight fixed-configuration inactive modules recorded as excluded.
python tools/env/run.py run -- python3 dv/core/lockstep.py --candidate build/t11/top1/candidate --suite arch,flight --output build/t11/top1/lockstep
PASS; 51 architectural binaries, 16172 architectural and 283490 flight retirements; zero mismatches.
```

Top induction matches 196 state elements and one product, with no assumptions;
four fault controls are rejected. `top_review` independently reproduced top
proof/faults and approved the eight inactive exclusions. Its manifest findings
(top views and schema-1 metadata smuggling) were fixed with regressions.

Added a hash-bound candidate ALTOPS contract and stable idle/ready observation
points. The first run (`top2/rvf`) failed an adapter stability assertion because
firtool had removed a constant-ready port and generated wiring became undriven.
The adapter now validates every input and output width/direction against the
exact primary source, preserving ready with `dontTouch`; it cannot inspect a
different standalone module view. New guard tests exercise 37 malformed
bindings/hash cases. `top_review` independently rejected 34 input/net/hash cases
before the output guard was added. `top3/equiv` again proves the baseline top
and rejects all faults. The complete candidate formal rerun is in progress.

## Registered core integration in progress, 2026-11-15

Added explicit registered execution selection to core/ID/EX/top and the
`EmitRegisteredCore` emitter, retaining faithful defaults and checks.
`CoreSpec` passes its original model and negative control plus the registered
core (three tests). `integrated2/smoke` passes 98 retirements against immutable
Ibex and QEMU with all six trace faults rejected. No trace fields were removed.
Trace-only adder observation preserves the reference's incidental values for
M operations and non-executing exception phases.

Early independent review found MRET/DRET/WFI flags were lost after consuming
their response; qualification was moved to the controller's DECODE transition,
preserving flags in FLUSH. Directed system tests are being qualified. Their
initial MRET/WFI test failed on both baseline and registered cores because the
test omitted setting MPP before MRET and consequently attempted MIE access in
user mode; the fixture now explicitly establishes machine-mode return.

Mapped core-only timing (RF external, no RVFI, not gated-top signoff):
`python tools/env/run.py run -- python3 scratch/t11_measure_core.py build/t11/integrated1`
measured **44.848339 ns**, **317630.0736 um2**, zero electrical violations: FAIL.
The registered legality stage (`integrated3`, same command/profile) measured
**34.839828 ns**, **319825.2736 um2**, zero electrical violations: FAIL.
Both retain the assumed 24.96 ns budget. The latter path reaches CSR state from
instruction decode; CSR request staging is now under verification. Failed
receipts are retained. Full production timing, integration formal/ISA suites,
full local CI and final independent review remain required. No commit or push.

### Further integration results

Commands run at `a532304` plus working changes:

```
python tools/env/run.py run -- python3 dv/core/riscv_formal.py --target candidate --candidate build/t11/top3/candidate --output build/t11/top3/rvf
PASS riscv-formal: bounded/covered classifications recorded at depth 40; fault rejected; no unbounded proof.
python tools/env/run.py run -- python3 dv/core/lockstep.py --candidate build/t11/integrated4/candidate --suite arch,flight --output build/t11/integrated4/lockstep
PASS lockstep suites: arch=16172, flight=283490.
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.CoreSpec deadhorse.perf_core.CoreSystemSpec"
Tests: succeeded 12, failed 0, canceled 0, ignored 0, pending 0.
All tests passed (integrated9 source snapshot).
```

The directed tests now cover MRET, WFI with timer wake, debug entry/DRET during
multiply, CSR/ordinary instructions followed by illegal CSR/ECALL/EBREAK,
split-load error followed by a handler store, and reset during multiply.
Baseline and registered configurations run the same system cases where relevant.

The integration control monitor retains 17 assertions and 12 covers, with only
startup reset constrained; `checking` is driven by an initialized history flop.
It checks pending ownership, stable instruction/phase, per-phase issue/completion,
write/CSR/LSU/redirect qualification, and absence of an executing transaction at
trap/debug state updates. Production binding strips verification cones and proves
the remaining core identical, including all ports/state. A real output-strobe
mutation publishes an RF write while execution is pending; no property is changed.
This is a bounded control subset, not unbounded ISA or memory-causality proof.

Recorded failures: `integrated7/protocol` exposed an illegal-CSR enable strobe
without an execution response (the CSR bank already blocked the illegal write);
the registered ID now suppresses that strobe. `integrated8/protocol` exposed a
stale multicycle phase after controller flush under arbitrary memory responses;
the registered ID now clears its phase on instruction clear. Assertions were
retained. `integrated9/protocol/normal` passed BMC to depth 160; the remaining
variants and current-tree production binding must still finish.

Further measured core-only timing failures, all using the same
`scratch/t11_measure_core.py build/t11/<snapshot>` command, 24.96 ns assumed
budget and zero electrical violations:

| Snapshot | Delay ns | Mapped area um2 | Finding/repair |
| --- | ---: | ---: | --- |
| integrated4 | 34.288101 | 319566.2400 | Static instruction/control classification |
| integrated5 | 33.355186 | 318130.5792 | LSU fixed +4 ripple path; parallel local increments |
| integrated6 | 32.675781 | 320183.0912 | Remaining CSR/jump decode controls staged |
| integrated8 | 28.048643 | 322334.3872 | Fetch-fault PC+2 path; equivalent parallel increment |
| integrated9 | 26.123409 | 325552.5504 | CSR address/read selection to counter state |
| integrated10 | 26.654974 | 326026.7136 | Fast IRQ priority to fetch address |

The CSR read mux now uses mutually exclusive parallel selects; configured
equivalence passed with all faults. Fast-IRQ priority is being restructured
without changing lowest-index priority. These are same-cycle repairs; baseline
module proofs remain mandatory. No timing limit, clock/load constraint or
electrical check changed. Core-only area excludes RF/top clock gating and is
not a full-chip estimate. Registered ALTOPS uses a separate hash-bound adapter
on the iterative multiplier and a longer, explicitly identified ISA window;
reference/baseline windows and their checks remain unchanged. Those candidate
runs remain in progress, so no new ISA/formal completion is claimed.

### Gated-top qualification and further repairs (in progress)

The integrated9 control runner completed: bounded depth 160, all 12 covers,
production binding and the real early-write mutation passed/rejected as required.
`check_leaves.py --emitted build/t11/integrated17/leaves --output
build/t11/integrated17/leaves_equiv` passed every configured equivalence and
negative control. The subsequent factored ID stalls passed the direct
`dv/core/equiv.py --module ibex_id_stage --candidate
build/t11/integrated18/leaves/id_stage/ibex_id_stage.sv --replace
ibex_controller=build/t11/integrated18/leaves/id_stage/ibex_controller.sv
--replace ibex_decoder=build/t11/integrated18/leaves/id_stage/ibex_decoder.sv
--self-check --output build/t11/integrated18/id_equiv` command. These commands
ran through the pinned `python tools/env/run.py run -- python3` prefix.

The first direct CSR CLI experiment used upstream default parameters instead
of the configured no-HPM profile and failed state-width correspondence. The
configured runner above passed; no state/width matching check was relaxed.

Measured at base `a532304` plus the source hashes in each receipt, same pinned
slow-corner library, constraints and mapping flow; pre-layout, ideal clocks:

| Snapshot/scope | Delay ns | Mapped area um2 | Result |
| --- | ---: | ---: | --- |
| integrated11/core-only | 29.373041 | 322187.3088 | FAIL |
| integrated12/core-only | 33.378227 | 325655.7248 | FAIL |
| integrated13/core-only | 26.471783 | 330195.3984 | FAIL |
| integrated14/gated top + RF | 26.974899 | 447599.0848 | FAIL |
| integrated15/gated top + RF | 26.687559 | 449640.6208 | FAIL |
| integrated16/gated top + RF | 26.432989 | 449767.9424 | FAIL |
| integrated17/gated top + RF | 26.241219 | 451780.9408 | FAIL |
| integrated18/gated top + RF | 27.034424 | 448813.0304 | FAIL |
| integrated19/gated top + RF | 25.994909 | 448911.8144 | FAIL |
| locked reference/gated top + RF | 61.667374 | 399653.7216 | FAIL benchmark |

All reported zero electrical violations; the unchanged assumed budget is
24.96 ns. Commands: `scratch/t11_measure_core.py build/t11/<snapshot>` for
core-only, `scratch/t11_measure_top.py build/t11/<snapshot>` for the full top,
and `dv/core/reference_timing.py --output build/t11/reference_timing` for the
reference, all through the pinned prefix. Scratch drivers call the production
`tools.timing.check.measure` function with every emitted ASIC source.
The reference runner authenticates the lock, disables observation-only RVFI,
and binds exactly its abstract gate to the same GF180 wrapper. It shares the
numeric flow but marks every receipt reference-benchmark-only. Production-role
calls still enforce isolation, including calls to the internal numeric helper.
Independent review verified identical interface, constraints, tools, mapping
scripts and loads. No reference timing pass or production acceptance is claimed.

The timing flow now admits only the characterized root-driven ICG; every
register clock must have exactly the root clock identity and rising edge.
RG/IG paths count toward the same budget, and all E/TE rise/fall setup/hold
slacks are recorded and required nonnegative. Dedicated gate propagation
qualification remains separate; this is ideal-clock pre-CTS timing, not CTS.
Independent review exposed an OpenSTA clock-query gap: merely counting clocks
and querying `all_registers -rise_clock` accepted an alien clock on the ICG
output. Explicit identity comparison fixes it. Root and reviewer each ran
`gated_self_test` in the pinned environment: normal 3.750224 ns, zero electrical
violations, and alien-clock/setup/hold faults rejected. Scope approved by the
independent gated-timing reviewer; whole-core timing still fails.

Further equivalent combinational changes: parallel redirect/sequential fetch
increments, bounded IRQ reduction groups, local counter read-modify-write
values, destination-qualified CSR write enables, and factored controller/ID
acceptance predicates. Registered CSR commit now uses its accepted execution
response directly; a qualified CSR is a single ALU phase, so unrelated LSU
completion does not drive its write enable. Current integration verification
is running. The 12 CoreSpec/CoreSystemSpec tests passed again on integrated19.

The registered ISA ABC run at depth144/check64 timed out without a witness;
that failure is retained. A pinned btormc trial on the exact same multiply
model, assumptions, depth and 600-second timeout passed (452 seconds measured).
The registered runner now uses that engine; reference/baseline retain their
original engine/windows. Full registered ISA classification remains pending.
New registered adapter malformed-contract tests and manifest-profile rejection
tests pass, addressing the independent adapter review recommendation.

Full local CI and final independent review remain required. No commit or push.

### Frozen registered-top acceptance snapshot

`integrated23` includes the registered redirect and three cached controller
state predicates, with baseline options disabled by default. The configured
leaf runner completed with every equivalence and fault control passing.
Whole-top timing now passes:

```
python tools/env/run.py run -- python3 hw/ip/perf_core/check_top_timing.py --emitted build/t11/integrated23/emit/asic --output build/t11/integrated23/top_timing
PASS DeadhorsePerfCore: 24.592239 ns, budget 24.960000 ns; electrical violations 0
```

Measured area 458891.1936 um2, minimum ICG setup/hold slack 0.704980 ns;
base `a532304` plus the receipt's source hashes. Assumptions/limits unchanged.
Earlier gated snapshots integrated20/21/22 measured 28.084654/25.499798/
25.632435 ns, areas 448363.0144/450764.5632/456079.1424 um2, all FAIL with zero
electrical violations. Firtool rejected a computed async-reset literal in the
cached-predicate helper; explicit false literals match all three reset-state
predicates and fixed emission without changing any check.

The directed system suite gained three JAL/JALR/C.J/straddled-instruction tests
with delayed grants and responses; all twelve system tests passed on the
cached-controller profile. A fresh independent review found no RTL defect but
identified missing enabled-interrupt entry/return coverage: the earlier WFI
case only woke with global MIE off. Two new finite tests enable MTIE/MIE and
interrupt a pending multiply or the taken-redirect boundary, check mepc/mcause,
clear the IRQ and return with MRET. Their run is pending; the review finding
remains open until it passes independently.

The integrated18 ISA run completed MUL/MULH/MULHSU bounded checks, covers and
both result/capture faults. It was stopped as incomplete after the registered
redirect changed the source snapshot; no full ISA acceptance inferred. The
integrated19 normal protocol check passed, but its later variant correctly
failed production binding after source edits; integrated21 was likewise stopped
as superseded. Fresh integrated23 protocol and full local CI runs are active.
No assertion, timeout, depth or acceptance partition was removed or relaxed.

Frozen integrated23 architectural/flight comparisons passed again:
`dv/core/lockstep.py --candidate build/t11/integrated23/candidate --suite
arch,flight --output build/t11/integrated23/lockstep` through the pinned prefix:
`PASS lockstep suites: arch=16172, flight=283490`. No normalization change.
The 21-assertion integration normal check passed BMC depth160 with production
binding and its binding fault controls. The later fault variant hit its unchanged
600-second emission timeout waiting behind the full local gate's shared Scala
runner; it did not run the solver. A separate retry is running with the same
timeout, preserving that failed receipt.

The full gate's `hw/test` passed all 56 then-compiled tests. Subsequently the
two added IRQ cases passed through
`python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly
deadhorse.perf_core.CoreSystemSpec -- -z enabled"`. The fresh-context reviewer
independently reran the same command, passed both cases, and resolved the IRQ
coverage finding. Scoped registered-integration source review is approved;
formal/full-CI completion is still pending. Production RTL remains frozen.

The frozen integrated23 integration set subsequently completed: normal BMC
depth160 at `protocol/normal`, early-write fault at `protocol_retry/fault`,
redirect-target fault at `protocol_retry/redirect-fault`, and all 14 covers at
`protocol_retry/cover`. Every variant passed production binding. Commands use
`hw/ip/perf_core/formal/check_integration.py --emitted
build/t11/integrated23/emit/asic --variant <variant> --output <path>` through
the pinned prefix. Last lines: `PASS integration fault: fault rejected, depth
40`, `PASS integration redirect-fault: fault rejected, depth 40`, and
`PASS integration cover: covered, depth 160`. Normal has 21 assertions and
no added environment assumptions. The earlier compiler-lock timeout remains
recorded and no timeout limit was increased. Full CI is still running.

The fresh-context registered-top reviewer also independently reproduced the
current faithful whole-top proof with `dv/core/equiv.py --top --candidate
build/t11/ci/baseline --self-check --output
build/t11/registered_top_review/baseline_equiv` through the pinned prefix.
It passed unbounded named-state induction for 196 state elements and one
structural multiplication, without assumptions, and rejected all four faults.
Approved analysis normalizations are explicit. No remaining scoped review
findings; final registered ISA/full local CI completion remains outstanding.
