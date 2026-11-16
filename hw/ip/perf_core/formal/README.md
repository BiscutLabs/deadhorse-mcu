# T11 conversion properties

The primary property is equality of every output and named next-state,
reset, clock and enable function to the pinned reference. It is checked by
`dv/core/equiv.py`, with state correspondence in `dv/core/module_map.json`.
There are no new environmental assumptions. Equal named arbitrary state is
the induction relation; it is not a physical power-up guarantee.

Run each leaf with `--module`, its emitted `--candidate` file and
`--self-check`. Output, reset-value and next-state negative controls must be
rejected where applicable. An implementation is not qualified until the
result and negative controls have been observed. Whole-core acceptance and
the D44 arithmetic qualifications remain required by T11.

`check_leaves.py` checks the emitted configurations with explicit reference
parameters. The prefetch parent is checked with its emitted Chisel FIFO via
`--replace`; every requested child must occur in the elaborated hierarchy.
This incremental route records child source hashes and cannot be used for
`ibex_top` or all-module acceptance, which still requires the production manifest.

The multiplier/divider comparison preserves one signed 17-by-17 product on
both sides. Operand equalities are obligations; its symbolic result is shared
only after those obligations are included. Output, reset, next-state and
multiply-sign faults must fail. Ascending unpacked `[0:1]` intermediate arrays
flatten with element zero in the high word; packed write-enable bit zero still
controls element zero. This is checked at every port by equivalence.

## Current module results

Measured at base `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus T11 working
changes, using `python tools/env/run.py run -- python3
hw/ip/perf_core/formal/check_leaves.py --emitted build/t11/ci/emit
--output build/t11/ci/leaves` (exit zero). All listed properties are
unbounded; all applicable negative controls were rejected. Timing evidence and
its separate status are in the task report and timing ledger.

| Module | Tested configuration | Equivalence | Negative controls |
| --- | --- | --- | --- |
| ibex_csr | Defaults; width 8/shadow/reset 0xa5 | Named-state induction | Output, reset, next-state |
| ibex_counter | Defaults; width 64, update disabled/enabled | Named-state induction | Output, reset, next-state |
| ibex_alu | RV32BNone | Exhaustive combinational | Output |
| ibex_decoder | RV32E=false, RV32MFast, RV32BNone, BranchTargetALU=false | Exhaustive combinational | Output |
| ibex_load_store_unit | MemECC=false, MemDataWidth=32 | Named-state induction | Output, reset, next-state |
| ibex_if_stage | Pinned no-cache/predictor, all three Chisel children | Named-state induction | Output, reset, next-state, gained-reset |
| ibex_controller | No WB stage/predictor/ECC | Named-state induction | Output, reset, next-state |
| ibex_wb_stage | No WB stage/dummy instructions | Exhaustive combinational | Output |
| ibex_cs_registers | DbgTriggerEn=1, MHPMCounterNum=0; other defaults | Named-state induction against approved source-priority analysis model | Output, reset, next-state |
| ibex_id_stage | Pinned two-stage, both Chisel children | Named-state induction against approved source-priority analysis model | Output, reset, next-state |
| ibex_core | DbgTriggerEn=1, pinned two-stage baseline; all active Chisel children | Named-state induction and product congruence against approved source-priority analysis model | Output, reset, next-state, gained-reset |
| ibex_register_file_ff | Default non-secure full-register configuration | Named-state induction | Output, reset, next-state |
| ibex_compressed_decoder | Fixed reference configuration | Exhaustive combinational | Output |
| ibex_fetch_fifo | NUM_REQS=2, ResetAll=false | Named-state induction | Output, reset, next-state, gained-reset |
| ibex_prefetch_buffer | ResetAll=false, emitted Chisel FIFO | Named-state induction | Output, reset, next-state, gained-reset |
| ibex_multdiv_fast | RV32MFast, faithful MAC | Named-state induction and structural product congruence | Output, reset, next-state, multiply sign |
| ibex_ex_block | Faithful and same-cycle repaired parents, both Chisel children | Named-state induction and structural product congruence | Output, reset, next-state |
| ibex_top | Faithful baseline with project clock gate and flop register file | Named-state induction and structural product congruence | Output, reset, next-state, gained-reset |

The archived all-module run at `build/t11/ci-before-csr-fix/baseline_modules`
proves all 18 active baseline modules. Final-source configured leaf/core checks
pass at `build/t11/ci/leaves` and `build/t11/ci/core_equiv`; current whole-top
proof at `build/t11/csrfinal1/baseline_top` matches 196 state elements and one
product without input assumptions.
The exact inactive set in `dv/core/candidate.py` was independently reviewed:

| Excluded module | Fixed configuration making it inactive |
| --- | --- |
| ibex_branch_predict | BranchPredictor=0 |
| ibex_dummy_instr | SecureIbex=0; DummyInstructions=0 |
| ibex_icache | ICache=0 |
| ibex_lockstep | SecureIbex=0; Lockstep=0 |
| ibex_multdiv_slow | RV32M=RV32MFast |
| ibex_pmp | PMPEnable=0 |
| ibex_register_file_fpga | RegFile=RegFileFF |
| ibex_register_file_latch | RegFile=RegFileFF |

These exclusions cannot remove an active declaration. The registered profile's
refinement, integration and retirement obligations are separate from baseline
cycle equivalence; their current status is in the task report.


## Approved iterative multiplier

See `../ITERATIVE-MULTIPLIER.md`. `check_iterative.py` proves every emitted state,
reset, clock, enable and output transition against `MultiplyModel.scala`, then
checks integer induction/width/sign/projection lemmas and six reachability
witnesses. Each state component has a fault; generic output/reset/next-state
faults remain. No symbolic input assumption is added to transition equivalence.
A transaction starts from reset/idle; physical power-up is not specified by an
empty solver assumption list. Progress requires enabled edges, safety does not
require fairness. Composition of integer lemmas with the bitvector model is
explicitly reviewed, not one automatically composed end-to-end theorem.

`check_division.py` keeps exact correspondence for selected DIV/REM with multiply
held disabled; it proves its generated reference normalization roundtrip and
rejects output, next-state and reset faults. Mixed operations are additionally
exercised through the full shared interface by `MultdivSpec`.


Execution-stage baseline: faithful parent plus both Chisel children
and same-cycle repaired parent pass exact state/output equivalence. The optional
iterative child changes multiply cycles and is covered separately; no exact
reference-cycle claim applies to that variant. The historical unregistered EX
timing failure is retained as a diagnostic; registered execution replaces that
path. All production-profile block timing results are gating in local CI.

## Registered execution replacement

The approved `ClockedExecute` replacement now passes unbounded contract/step
refinement/deadline induction, exact production-emission binding, six contract
faults and eight bounded completion witnesses. See
[EXECUTION-TIMING.md](../EXECUTION-TIMING.md) for assumptions, composition and
the retained unregistered diagnostic profile. Independent aggregate evidence:
`build/t11/registered_review/formal`, base `a532304` plus working changes.
Its full producer deadlines are asserted; no receiver fairness is assumed.
This proof does not establish whole-core instruction retirement.

Decoder/LSU rows were subsequently measured at the same base plus working
changes using `dv/core/equiv.py --module <module> --candidate <emitted.sv>
--self-check --output <directory>`. Root evidence is
`build/t11/decoder1/equiv_checked` and `build/t11/lsu1/equiv`; fresh independent
review receipts are `build/t11/decoder_review/equiv` and
`build/t11/lsu_review/equiv`. No assumptions, state cuts, or input tying were
introduced for the decoder. LSU matches all ten named state elements without
environment assumptions. Simulation limitations are listed in the block README.

IF/controller/WB rows were subsequently checked with the same command form,
at `build/t11/if1/equiv_mapped`, `build/t11/controller1/equiv` and
`build/t11/wb1/equiv`. IF explicitly substitutes all three emitted children;
its ten hierarchical name aliases only change names, not state relationships.
Fresh independent receipts are `build/t11/{if_review,controller_review,wb_review}/equiv`.
All are unbounded and assumption-free. The controller review also independently
re-emitted identical RTL. CSR evidence is `build/t11/csrbank2/leaves/cs_registers`
with fresh emission and explicit reference parameters. Approved analysis
normalization, original failure, exact hashes and independent qualification are
documented in [CSR-PRIORITY-INVESTIGATION.md](../CSR-PRIORITY-INVESTIGATION.md).
All 19 configured cases and fault controls pass at `build/t11/csrbank2/leaves`.

The ID stage proves 15 states without assumptions against the user-approved
single-qualifier priority normalization. All 20 configured cases and their
negative controls pass at `build/t11/id2/leaves`; the top reference-copy check
also passes with both approved normalizations at `build/t11/id2/top_reference_copy`.
Fresh independent review passes at `build/t11/id2/independent-review`.
The original failure for conflicting instruction copies remains recorded at
`build/t11/id1/equiv`. See
[ID-PRIORITY-INVESTIGATION.md](../ID-PRIORITY-INVESTIGATION.md).

## Faithful core baseline

`python3 hw/ip/perf_core/formal/check_core.py --emitted build/t11/core2/emit
--output build/t11/core2/equiv` proves all 163 state elements and one structurally
matched multiplier, with no environment assumptions. All four fault controls
are rejected. All thirteen active child declarations are explicitly replaced
by Chisel output and checked for reachability; no vendor CPU implementation
remains in this core proof. The existing CSR/ID analysis normalizations apply.
Independent reproduction: `build/t11/core2/independent-review/equiv`.

The core's IRQ structures retain the reference's individual field registers.
`dontTouch` preserves constant-valued RVFI registers for strict state matching;
no constant-state exemptions or proof-engine changes were added. Parent mappings
prefix already-reviewed child aliases. Chisel observation wires reproduce the
reference RVFI cross-module references without adding state.

This baseline intentionally retains original execution timing. The approved
registered execution replacement has separate integration and retirement
verification. The repeated full CI run was stopped under the user's focused
verification instruction; final-source acceptance is detailed below. The
approved project clock-gate wrapper and faithful top pass
their scoped verification. `build/t11/top1/equiv` proves 196 state elements and
one structurally matched product, with four rejected faults and no assumptions.
The all-module run covers 18 active modules; eight inactive fixed-configuration
alternatives are explicitly excluded and independently reviewed. Baseline
architectural/flight lockstep at `build/t11/top1/lockstep` records zero differences.
These measurements are from base `a532304` plus the T11 working tree.

## Registered integration

`check_integration.py --emitted <ASIC emission> --output <build path>` checks
the registered core with arbitrary memory responses, IRQ/debug inputs and
subsequent resets. Only startup reset is constrained. Its exact inventory is
21 assertions and 14 covers. Assertions include execution ownership, held
instruction/phase, side-effect qualification, reset cancellation, one issue and
completion per phase, redirect capture and blocked FIFO transfers, and cached
controller-state consistency. The scope is bounded control, not an unbounded
ISA or memory-causality proof.

Every normal/fault/cover variant removes its observation logic and proves the
remaining circuit equal to the supplied production emission. The normal binding
also runs output/reset/next-state faults. Integration negatives mutate real RF
write enable or redirect target bit 2; assertions stay unchanged. Covers include
all operation completions, nonzero divide, trap/debug/IRQ entry and consecutive
redirects. The runner requires concrete cover/failure witnesses.

`riscv_formal.py` authenticates the registered manifest and the iterative
multiplier result adapter. Reference/baseline retain depth40/check12 and their
original engine; registered execution uses depth144/check64 and pinned btormc,
with the same timeout and complete ISA partition/cover/fault requirements.
Multiply is explicitly arithmetic-abstracted; nonzero long division still lies
outside this startup window and is covered by the separate divider/execution
refinement and architectural tests. No plain arithmetic or unbounded ISA pass
is inferred from the abstracted check. Current results live in the task report.

## Final CSR repair and evidence transport

`dv/core/revision_equiv.py --before build/t11/ci-before-csr-fix/registered
--after build/t11/csrfinal1/candidate --output
build/t11/csrfinal1/revision_equiv_final` proves exact whole-top cycle equality
for all 246 named states, outputs, enables, clocks and resets, with no
assumptions or analysis normalizations. All four fault controls are rejected.
Both complete manifests and source inventories are authenticated; registered
checks cannot use baseline module views. A failed fault stage invalidates the
aggregate receipt, covered by a behavioral regression.

The before-candidate hashes identify the exact archived 70-partition ISA run.
Independent review audited that binding, every underlying ISA job and the
final revision proof. Its ISA/integration evidence therefore carries forward
across the mstatus-only equivalent repair. This is not a fresh ISA run or an
unbounded ISA theorem. Current architectural/flight lockstep and timing pass
separately. Full CI definitions remain intact; the user directed focused
verification instead of another hours-long sweep. See the T11 report.
