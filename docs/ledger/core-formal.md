# Core reference formal ledger

## T11 final focused acceptance, 2026-11-15

Final-source configured proofs, faithful core/top proofs and all fault controls
pass. `python tools/env/run.py run -- python3 dv/core/revision_equiv.py --before
build/t11/ci-before-csr-fix/registered --after build/t11/csrfinal1/candidate
--output build/t11/csrfinal1/revision_equiv_final` proves unbounded exact
whole-top equality of all 246 states, outputs, resets, clocks and enables with
no assumptions or normalizations; output/reset/next-state/gained-reset faults
are rejected. Source/manifest hashes bind the before revision to the completed
70-partition registered ISA run. Independent review verified every underlying
job and the binding. Prior ISA/integration evidence is transported through this
exact proof, not reported as rerun. Current architectural/flight comparisons,
58 simulations and critical timing checks pass; full CI was stopped under the
user's explicit focused-verification instruction. Full details, limitations
and hashes are in [T11 report](../plan/tasks/reports/T11.md).

The following sections are historical checkpoints, with their original scope.

## T11 continuation: repaired leaves and prefetch hierarchy

The final checkpoint driver run uses `--emitted build/t11/checkpoint/emit
--output build/t11/checkpoint/formal` and passes all eleven configured checks,
including the restored faithful multiplier MAC. The first full local gate
found that newly recorded Chisel aliases displaced reference names during
reference self-comparison. `state_equiv.named_pairs` now considers both
spellings while still rejecting ambiguity and unmatched state. All state,
reset, clock, next-state and product-operand obligations remain. A behavioral
regression covers original/translated/ambiguous cases; fifteen core harness
tests and reference/candidate multdiv plus reference RF self-checks pass.
Fresh independent review reproduced the fix under
`build/t11/checkpoint_review/state_names/`. The first gate failure is preserved
at `build/t11/ci-first-failure.json`; it is not reclassified as a pass.

Measured at base `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus working
changes. All commands use `python tools/env/run.py run --`.
`python3 hw/ip/perf_core/formal/check_leaves.py --emitted
build/t11/counter11/emit --output build/t11/counter11/formal` passed the then
registered CSR/counter/ALU/register-file/compressed-decoder/FIFO cases. Each
rejects applicable output, reset-value, next-state and gained-reset faults.
Counter11 preserves staged parallel-prefix carries; independent review proved
widths 1, 5, 17, 33, 63 and 64 in both update-output modes with three faults each
under `build/t11/review/counter11/`. These extra parameter runs were performed
by the reviewer, not the primary agent.

`python3 dv/core/equiv.py --module ibex_prefetch_buffer --candidate
build/t11/prefetch2/emit/prefetch_buffer/ibex_prefetch_buffer.sv --replace
ibex_fetch_fifo=build/t11/prefetch2/emit/prefetch_buffer/ibex_fetch_fifo.sv
--self-check --output build/t11/prefetch2/formal` passed unbounded named-state
induction with four fault controls rejected. Independent review reproduced it.
The incremental helper rejects unused replacements and both top-check routes;
it records effective child source/hash and is explicitly verification-only.

`python3 dv/core/equiv.py --module ibex_multdiv_fast --candidate
build/t11/multdiv2/emit/multdiv_fast/ibex_multdiv_fast.sv --self-check --output
build/t11/multdiv2/formal` passed six-state induction and one structural signed
multiply congruence, with output/reset/next-state/sign faults rejected. The
parallel MAC addition trial in `multdiv3` also passes these same obligations.
No multiply was expanded for SAT and no environmental assumption was added.
The first translation's reversed unpacked-array packing failed equivalence;
correcting element zero to the high word resolved the translation defect.
The reference was not changed. These proofs do not claim timing closure or
whole-core acceptance.

## T11 counter repair and faithful ALU

Measured at `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus uncommitted
T11 changes. `python tools/env/run.py run -- python3
hw/ip/perf_core/formal/check_leaves.py --emitted build/t11/repair6/emit
--output build/t11/repair6/formal` passed all configurations in the initial
leaf table below, each with output, reset-value and next-state faults rejected.
No state or assumptions changed in the authorized combinational counter repair.
Independent review also proved partial widths 1, 5, 17, 33 and 63 in both
update-output modes with the same controls; its evidence is under
`build/t11/review/repair6_final/`.

`python tools/env/run.py run -- python3 dv/core/equiv.py --module ibex_alu
--candidate build/t11/alu1/emit/alu/ibex_alu.sv --self-check
--output build/t11/alu1/formal_fixed_fault` passed: exhaustive combinational
equivalence for RV32BNone and a rejected result-bit inverter. No input assumption
restricts operator encodings, first-cycle selection or multdiv operands. The
reference self-check also passed with the same real output mutation. The old
ALU-only constant-port mutation could be hidden by emitted JSON wire aliasing;
that self-check failed closed under `build/t11/alu1/formal/`. It was repaired
to use the existing driven-wire inverter mechanism, not excluded or weakened.

Independent review reproduced ALU proof/fault results and fresh emitted bytes.
These historical leaf results do not prove a complete processor. Subsequent
approved repairs and timing-flow qualification are recorded above and in the
[timing ledger](timing.md).

## T11 initial leaf translations

Measured at `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus uncommitted
T11 changes with `python tools/env/run.py run -- python3
hw/ip/perf_core/formal/check_leaves.py` (exit 0).

| Leaf configuration | Result | Required negative controls |
| --- | --- | --- |
| ibex_csr defaults | Proved, unbounded named-state induction | Output, reset value, next state rejected |
| ibex_counter defaults | Proved, unbounded named-state induction | Output, reset value, next state rejected |
| ibex_counter width 64, ProvideValUpd false | Proved, unbounded named-state induction | Output, reset value, next state rejected |
| ibex_counter width 64, ProvideValUpd true | Proved, unbounded named-state induction | Output, reset value, next state rejected |
| ibex_csr width 8, ShadowCopy true, ResetValue 0xa5 | Proved, unbounded named-state induction | Output, reset value, next state rejected |

The existing Yosys SAT checker compares every named state, reset/clock/enable
function and output with no added assumptions. The optional shadow register
has an explicit name map. Parameters are explicit in each configuration's
receipt under `build/t11/leaves/configurations/`. These are leaf proofs;
they do not establish a complete Chisel processor. The initial mcycle timing
failure and later authorized repair are recorded in the [timing ledger](timing.md).

## T10 harness continuation

User-assigned continuation of T10 at base commit
`730eef91f02f7ecad8092a774ef3c5efc42e0c07` plus the current harness changes.
The sections below this continuation preserve historical evidence, not the
current harness capability. No Chisel core conversion is included.

Measured by `python tools/env/run.py run -- python3 dv/core/equiv.py
--self-check --all-modules --output build/t10/equiv_all`:

| Reference module | Result | Matched state cells | Matched multiply cells | Comparison wall seconds |
| --- | --- | --- | --- | --- |
| ibex_alu | proved | 0 | 0 | 0.047 |
| ibex_branch_predict | proved | 0 | 0 | 0.034 |
| ibex_compressed_decoder | proved | 0 | 0 | 0.043 |
| ibex_controller | proved | 10 | 0 | 0.067 |
| ibex_csr | proved | 1 | 0 | 0.031 |
| ibex_cs_registers | proved | 29 | 0 | 0.197 |
| ibex_counter | proved | 1 | 0 | 0.034 |
| ibex_decoder | proved | 0 | 0 | 0.060 |
| ibex_dummy_instr | proved | 3 | 0 | 0.039 |
| ibex_ex_block | proved | 6 | 1 | 0.076 |
| ibex_wb_stage | proved | 0 | 0 | 0.034 |
| ibex_id_stage | proved | 15 | 0 | 0.126 |
| ibex_icache | proved | 75 | 0 | 0.192 |
| ibex_if_stage | proved | 24 | 0 | 0.081 |
| ibex_load_store_unit | proved | 10 | 0 | 0.067 |
| ibex_lockstep | proved | 235 | 1 | 0.564 |
| ibex_multdiv_slow | proved | 5 | 0 | 0.073 |
| ibex_multdiv_fast | proved | 6 | 1 | 0.058 |
| ibex_prefetch_buffer | proved | 14 | 0 | 0.052 |
| ibex_fetch_fifo | proved | 8 | 0 | 0.043 |
| ibex_register_file_ff | proved | 31 | 0 | 0.089 |
| ibex_register_file_fpga | proved | 32 | 0 | 0.093 |
| ibex_register_file_latch | proved | 1025 | 0 | 0.283 |
| ibex_pmp | proved | 0 | 0 | 0.094 |
| ibex_core | proved | 160 | 1 | 0.520 |
| ibex_top | proved | 196 | 1 | 0.691 |

Times cover correspondence construction and Yosys SAT, excluding elaboration.
Standalone modules use upstream defaults; `ibex_top` uses all pinned T10
parameters. Inactive alternatives are checked but are not adopted into the MCU.
The engine proves combinational obligations for outputs and, where state
exists, every transition/clock/reset/enable function under the named-state
induction relation. Reset presence, values, cell semantics and initialization
are compared. No register is excluded. Equal arbitrary uninitialized state
is the relational base case, not a guarantee of identical physical power-up
values. No environmental input assumption is added. Analog clock-gate
glitch-freedom and timing are outside this digital equivalence result.

Every module's output negative control failed. Applicable reset-value and
next-state mutations failed; gained-reset mutations and the fast multiplier's
flipped operand sign extension failed. Multiply results are symbolic only
with corresponding operand-equality obligations and matching parameters;
there is no bit-level multiplication proof. An independent reviewer also
rejected changed clock, reset polarity, initialization and unmatched-state
faults. Whole-core `--self-check --top` passed separately; a real faulted-source
top comparison failed and its aggregate receipt also says `failed`.

Measured by `python tools/env/run.py run -- python3 dv/core/riscv_formal.py
--target candidate --candidate build/t10/reference_copy --output build/t10/rvf_candidate`:
the byte-identical candidate passes the same instruction checks, covers and
fault controls as the reference; command wall time is 560.859 seconds.
Multiply remains **bounded, arithmetic abstracted (ALTOPS)**. DIV, DIVU, REM
and REMU now say **bounded, divisor-zero early-finish path only at check cycle
12**. All other partitions retain bounded status. Depth 40, selected cycle 12
and the 600-second per-job limit are unchanged assumptions. Candidate mode
fails if reference-supported retirement coverage is lost.

Independent inspection of the existing division covers confirms zero divisors
and `MD_IDLE -> MD_FINISH`, bypassing normal iteration. Witness inspection
commands and receipts are under `build/t10/harness_review/division/`. DIV/DIVU
produce all ones; REM/REMU preserve the dividend, subject to x0 discard.
This is coverage classification, not a new proof of normal divide latency.

`python tools/env/run.py run -- python3 dv/core/div_diagnose.py --output
build/t10/div_stress` measured 4,420 operand pairs, 17,680 real divide/remainder
operations, 41,110 retirements and 280 rejected faults. The fixture's assumed
seed is `0xDEAD0011`; zero divisors, signed overflow and sign combinations are
included. Original/adapted RTL, QEMU and independent integer arithmetic agree.
This required gate is finite simulation, not formal division proof. No D44
division abstraction or changed formal timeout is introduced.

`python tools/env/run.py run -- python3 dv/core/lockstep.py --candidate
build/t10/reference_copy --suite arch,flight --output build/t10/lockstep_suites`
measured 16,172 architectural and 283,490 flight retirements with zero mismatches.
Architecture inputs are pinned riscv-tests RV32UI/M/C bodies. Flight uses the
existing T02 QEMU config A binary plus one checked bootstrap JAL; its assumed
40 iterations per mode are unchanged. The separate full historical T02 gate
remains required. The flight-only functional fixture assumes a 50,000,000-cycle
ceiling; existing smoke/stress deadlines and the QEMU timeout remain unchanged.
The two measured QEMU post-MMIO duplicate prestates were independently audited;
strict normalization and negative mutations are documented in the harness.

`python tools/env/run.py run -- python3 dv/core/candidate_check.py --output
build/t10/candidate_negative` passed: an actual ALU source fault produced a
formal counterexample and concrete retirement mismatch through candidate paths.
Independent generic candidate-ALTOPS testing used a comment-only changed
multiplier with hash-bound metadata: MULH bounded PASS, cover PASS, capture
fault FAIL at upstream result equality with nonzero destination; wrong hash
and missing net rejected. It retains the same assumptions/bounds as D44.
Receipts: `build/t10/harness_review/generic_altops/`.

Independent fixed-configuration qualification ran
`python tools/env/run.py run -- python3 build/t10/harness_review/fixed_localparams/review.py`.
Measured: top equivalence proved with the same state relation, 98 smoke
retirements agreed and six faults were rejected; an empty-parameter Chisel
formal BlackBox emitted and compiled. The audited fixture mechanically fixed
25 parameter declarations, preserving the original body except the approved
initializer removal. Wrong configuration and incomplete/corrupt hash sets
were rejected. No Chisel conversion or full fixed-emission ISA sweep is claimed.

Earlier exploratory fixed fixtures serialized through Yosys failed the top
proof at `id_stage_i.id_fsm_q` next-state data under simultaneous decode
selections violating the source's `unique case` premise. Simulation passed,
but those proof failures remain failures under
`build/t10/harness_review/fixed/`. Neither state nor outputs were excluded,
and no assumption was added. The later parameter-table-only fixture avoids
that unrelated serialization change; the failed candidates are not acceptance
evidence. This illustrates the strict all-arbitrary-state correspondence.

The full local gate, `python tools/env/run.py run -- python3 tools/ci.py`,
passed with every recorded command exiting 0. Measured wall time was
1,876.380 seconds; reference and candidate riscv-formal commands took
560.853 and 563.269 seconds respectively (`build/ci/result.json`).
Final acceptance and independent review are recorded in the T10 report.

Historical pre-D44 T10 evidence, based on `7b4a65f620d52cd10f0a32bb9767e9c55eb2315c` plus the
uncommitted T10 changes. Command prefix for all entries:
`python tools/env/run.py run --`.

## Combinational equivalence

`python3 dv/core/equiv.py --self-check --output build/t10/equiv`

| Property | Kind | Engine | Assumptions | Runtime | Negative control |
| --- | --- | --- | --- | --- | --- |
| Every output of the pinned default `ibex_alu` equals the identical reference for all inputs | Proved, exhaustive combinational SAT | Yosys 0.71+34 SAT | None | Measured 0.211 seconds for the SAT command | Generated candidate `result_o[0]` forced low; SAT counterexample found |

This validates the comparison mechanism and baseline. It does not prove a
Chisel conversion, sequential module or whole core. The runtime comes from
`build/t10/equiv/result.json`; elaboration is excluded from that figure.

## Upstream instruction checks

The corrected asynchronous-responder run invoked by `python3 tools/ci.py`
used `python3 dv/core/riscv_formal.py --target reference --output build/t10/ci/rvf`.
It failed closed on multiplication solver timeouts. The duplicate standalone
run was stopped to avoid competing for solver resources. Earlier
synchronous-responder runs are excluded from acceptance evidence.

Measured classifications from the CI result and per-job logs:

| Instruction models | Result | Runtime evidence |
| --- | --- | --- |
| `add addi and andi auipc beq bge bgeu blt bltu bne`; all compressed models listed below; `div divu jal jalr lb lbu lh lhu lui lw` | 46 partitions bounded at the selected check cycle, covers PASS, result-bit faults FAIL | Per-job logged wall times: BMC 5–13 s, cover 3–6 s, fault 7–12 s |
| `mul mulh mulhsu` | Inconclusive: TIMEOUT, no proof/counterexample | Unchanged 600 s solver limit; MUL logged 601 s including handling |
| `mulhu` | Stopped after earlier timeout; no result | No completed run |
| `or ori rem remu sb sh sll slli slt slti sltiu sltu sra srai srl srli sub sw xor xori` | Not started after failure | No run |

The bounded compressed models are `c_add c_addi c_addi16sp c_addi4spn c_and
c_andi c_beqz c_bnez c_j c_jal c_jalr c_jr c_li c_lui c_lw c_lwsp c_mv c_or
c_slli c_srai c_srli c_sub c_sw c_swsp c_xor`. Results are bounded and exercised
only under the contract below; in particular a division cover at this early
cycle does not qualify all normal division latencies.

ABC `bmc3` checks the upstream instruction assertions; pinned BTORMC checks
all upstream cover conditions. Each completed partition's fault flips one
RVFI result bit in the verification adapter, leaving the reference and checker
unchanged. Logs/witnesses are under `build/t10/ci/rvf/<instruction>/`.
Runtime ranges are measured from SBY's per-job elapsed-wall-time lines; they
are not whole-run elapsed time. The exact model/checker pins and tool versions
are in the report.

The baseline coverage parameters are **assumed**: 40 global steps with an
alternating root clock and one checked retirement at core cycle 12. This is
a bounded startup-window check of that selected retirement, not an unbounded
proof or a check of every retirement in the window. Each instruction model
must have its upstream covers and result-bit fault witness before it is
reported as bounded and exercised. Tool failures remain unsuccessful.

The complete assumptions, fixed inputs, memory protocol, unsupported classes
and parameter set are documented in [the harness contract](../../dv/core/README.md).
Pins and observed tool identities are in [the T10 report](../plan/tasks/reports/T10.md).

## Multiplication investigation

The follow-up diagnostics do not promote any multiplication partition to
bounded/proved or change the unsuccessful CI result. The normal solver limit,
inputs, assertions and selected retirement remain unchanged.

`sby -f -d build/t10/diagnosis/mul-long build/t10/diagnosis/mul-long.sby`
changed only the diagnostic timeout from 600 to 1,800 seconds. Result:
**TIMEOUT**, no counterexample, measured SBY elapsed 1,801 seconds including
termination. `long-config-comparison.json` records the exact configuration
comparison. CPU samples confirm active solver computation. The elapsed
figure is SBY's own, because guest counters and UTC headers diverged during
the run; no cause of that discrepancy is claimed. More time did not produce
the required result, and the acceptance limit is unchanged.

`python3 scratch/t10/mul_controls.py` measured cover PASS for all four
multiplication instructions and result-bit fault FAIL. Independent review
found those fault witnesses write x0, so they establish detection of invalid
RVFI zero-register data. The additional `fault-nonzero` Chisel adapter mode
only injects a fault on a nonzero destination, without new assumptions.
`python3 scratch/t10/nonzero_controls.py` measured FAIL for all four such
faults at upstream result equality (approximately 9-10 seconds each).
Positive arithmetic checks remain unresolved.

An arithmetic-only diagnostic (`python3 scratch/t10/arithmetic_identity.py`)
checks direct unsigned low multiplication against its limb expansion with
pinned Boolector. Measured: width 8 is UNSAT in 0.324 seconds; widths 16 and
32 reach the separate diagnostic 120-second limit; each injected low-bit
inversion is SAT. This known identity has no CPU/RVFI state. It supports a
solver-complexity explanation but establishes no property of Ibex.

`python3 scratch/t10/remaining_partitions.py` subsequently ran all 20
non-multiply partitions listed as not started in the original CI table.
Measured: every bounded check and cover PASS; each fault FAIL. It reused
the same CI adapter, depth, check cycle, assertions and 600-second limit.
Together with the original 46 completed jobs, this gives 66 non-multiply
partitions with bounded/cover/fault evidence. The original full gate result
is still failed; the division/remainder coverage limits still apply.

`python3 dv/core/mul_diagnose.py --output build/t10/diagnosis/stress` measured
17,680 correct products over 4,420 operand pairs in the original/adapted
reference, QEMU and an independent Python arithmetic oracle. It rejected
36 injected faults. This is directed/random simulation, not formal evidence
for all operands. The run exposed and validated a repair to the ISS shutdown
trace boundary, independently of the formal driver.

See [the investigation note](../../dv/core/MULTIPLICATION-INVESTIGATION.md)
for diagnostic artifacts, upstream guidance and the proposed compositional
proof strategy. A separate arithmetic proof cannot replace whole-core
acceptance without discharging the integration obligations too.

## D44 revised acceptance

D44 explicitly approves a different acceptance contract; this is not a
promotion of the historical raw timeouts into passes. Current evidence is
based on `1b04c8af3aee8143d471394105c139ceaa7f18aa` plus D44 working changes.
All commands below use the pinned container prefix above.

`python3 dv/core/riscv_formal.py --target reference --output build/t10/d44/rvf`
completed successfully. Measured classifications: all 66 non-multiply models
are bounded with covers and rejected result faults; all four multiply models
are **bounded, arithmetic abstracted (ALTOPS)**, with covers and rejected
nonzero-destination result and captured-operand faults. Depth/check cycle
remain the assumed 40 global steps/core cycle 12; the 600-second limit is
unchanged. Only the multiply jobs define ALTOPS. The four added live operand
and operation stability assertions are active, with no new assumptions.

| Multiply model | Kind | BMC | Cover | Result fault | Capture fault |
| --- | --- | --- | --- | --- | --- |
| MUL | Bounded, arithmetic abstracted (ALTOPS) | PASS, 28 s | PASS, 6 s | FAIL, 19 s | FAIL, 14 s |
| MULH | Bounded, arithmetic abstracted (ALTOPS) | PASS, 25 s | PASS, 4 s | FAIL, 18 s | FAIL, 16 s |
| MULHSU | Bounded, arithmetic abstracted (ALTOPS) | PASS, 27 s | PASS, 4 s | FAIL, 15 s | FAIL, 17 s |
| MULHU | Bounded, arithmetic abstracted (ALTOPS) | PASS, 23 s | PASS, 4 s | FAIL, 17 s | FAIL, 15 s |

Times are measured per-job SBY elapsed wall time from the standalone run's
logs (`runtime-summary.json`), not whole-command runtime. ABC `bmc3` checks
assertions/faults; BTORMC checks covers. The independent reviewer reran MULH
BMC and the MUL capture fault and inspected all eight fault witnesses: each
fails upstream result equality on a valid selected instruction with nonzero
destination. `scratch/t10/audit_d44.py` reclassified all 214 actual job
outcomes with the final stricter exit-code/witness parser.

`python3 dv/core/mul_lemma.py --output build/t10/d44/mul_lemma` proved the
integer product expansions, intermediate ranges and universal low/high carry
identities in pinned Z3. Measured: 26 queries returned expected SAT/UNSAT,
including satisfiable domains and rejected wrong shifts/ranges. Independent
review reproduced all results and checked [the equations](../../dv/core/MUL-LEMMA.md)
against the immutable fast-multiplier source. This is an integer argument;
its correspondence to RTL remains **review and simulation, not proof**.

`python3 dv/core/mul_diagnose.py --output build/t10/d44/mul_stress` passed:
measured 17,680 products across 4,420 operand pairs and 40,122 retirements;
36 arithmetic faults rejected. It compares original/adapted references,
QEMU and independent Python arithmetic. The fixed-seed run is now required
by CI, together with the integer lemma and ALTOPS integration.

Optional C attempted a shared arbitrary-function memory representation. The
pinned frontend route did not preserve its full address space; no valid
core/spec integration or solver result was reached. Evidence is in
`build/t10/d44/review/uf/result.json`; see the investigation note for the
specific optimization, truncation and explicit range error. Its status is
**unresolved (frontend array representation)**. No stronger proof is claimed.

The raw full-product diagnostic remains **unresolved (arithmetic)** and is
not run by CI. Long-latency division/remainder and all other stated harness
limits remain. The full `python3 tools/ci.py` run passed (observed exit 0),
including its independent invocation of all revised instruction jobs,
integer lemmas and stress simulation. The final outcome receipt is
`build/t10/d44/ci-final.json`. The current parser also successfully
reclassified all 214 CI job outcomes. This is completion under D44's revised
contract, not a raw multiply proof.


T11 approved iterative-multiply checkpoint (base a532304 plus working changes):
`hw/ip/perf_core/formal/check_iterative.py` exit 0 at
`build/t11/iterative2/formal`; unbounded emitted RTL-to-transaction-model
induction, separate integer lemmas, twelve rejected emitted faults and six
formal cover witnesses. Integer/bitvector composition remains explicitly
reviewed. Independent rerun: `build/t11/iterative_review/formal_factored`.
`check_division.py` at `build/t11/iterative2/division_final` proves selected
DIV/REM exactly, with generated reference roundtrip and output/next/reset
faults. Independent rerun: `build/t11/iterative_review/division`.
No whole-core claim. The old nested word-projection timeout remains a failed
diagnostic; equivalent factored lemmas pass without changing the 600-second limit.


Fresh-context current checkpoint review (`build/t11/iterative_checkpoint_final/`)
independently reproduces iterative model induction/lemmas/twelve faults/six
covers and repaired EX exact equivalence/three faults, with no remaining review
finding. Main CI's Scala stage passes all 21 tests (six suites); main CI final
status and physical timing remain separate obligations, not a completion claim.


Current revised local gate (`build/t11/ci-approved-checkpoint.json`) ends exit 1
on multdiv/EX timing. Before that failure, all 21 Scala tests, 13 configured
reference-equivalence cases/faults, iterative proofs/lemmas/twelve faults/six
covers, and selected-division/normalization proofs pass. Downstream reference
ISA/lockstep commands remain present but were not reached after the timing gate;
no full Chisel core acceptance or task completion is claimed.

T11 registered execution, base `a532304` plus working changes (2026-11-15):
`check_execute.py --variant normal` at `build/t11/registered_formal/prove7`
passes unbounded k-induction (12-step search), including producer deadlines,
capture/hold/reset/no-loss, and divider step refinement. Exact production
projection binds 32 state elements, with output/next-state faults. Six contract
faults rejected at `fault2-*`; all eight covers reached within depth120 at
`cover3`. Startup reset only; internal correspondence/ranking are assertions.
Arithmetic composes separately recorded leaf proofs and integer lemmas; this
is not a new direct full-product/division theorem or whole-core equivalence.
Fresh reviewer reproduced the entire aggregate at
`build/t11/registered_review/formal` and approved focused scope.

Decoder/LSU follow-up, same base plus working changes: root
`build/t11/decoder1/equiv_checked` proves every combinational input/output
without assumptions and rejects output fault; `build/t11/lsu1/equiv` proves
ten named states/reset/clocks and rejects output/reset/next-state faults.
Fresh independent repetitions at `build/t11/decoder_review/equiv` and
`build/t11/lsu_review/equiv` pass. Both focused simulation suites and their
corrupt-result controls pass; LSU simulation scope limits are in the block README.

IF/controller/WB follow-up, base `a532304` plus working changes, 2026-11-15:
`dv/core/equiv.py --module ... --self-check` at `build/t11/if1/equiv_mapped`,
`build/t11/controller1/equiv`, and `build/t11/wb1/equiv` proves all selected
outputs without environmental assumptions. IF matches 24 named states with
all translated children and rejects output/reset/next-state/gained-reset faults;
controller matches ten states and rejects output/reset/next-state faults; WB
is exhaustive combinational with an output fault. Fresh independent reviews
reproduce proofs, timing and both tests for each block at
`build/t11/{if_review,controller_review,wb_review}`. These results establish
the selected block boundaries, not whole-core retirement or timing.

CSR approved normalization, 2026-11-15, base `a532304` plus working changes:
`check_leaves.py --emitted build/t11/csrbank2/emit --output build/t11/csrbank2/leaves`
passes all 19 then-configured cases and their faults. CSR proves 22 state
elements against the explicitly approved priority-preserving analysis model,
without input assumptions; output/reset/next-state faults rejected. Exact
hash/location/reversal guards and source/netlist/parameter receipts qualify the
two-qualifier change, leaving vendor and production RTL unchanged. Root top
reference-copy proof/faults pass at `build/t11/csrbank2/top_reference_copy`.
Independent CSR/core/top proof, simulation, timing and provenance review passes
at `build/t11/csrbank2/independent-review`. The old failed model remains recorded.

ID follow-up, same base plus working changes: original unrestricted proof at
`build/t11/id1/equiv` fails on conflicting duplicate instruction inputs, where
unique-case lowering differs from procedural priority. The source-priority
trial at `build/t11/id1/priority_trial` proves 15 states without assumptions and
rejects all three faults; independent fresh elaboration at
`build/t11/id1/independent-priority` agrees. The single additional normalization
was subsequently approved explicitly. The accepted root run
`check_leaves.py --emitted build/t11/id2/emit --output build/t11/id2/leaves`
passes all 20 configured cases and their fault controls. Top reference-copy
proof/faults pass at `build/t11/id2/top_reference_copy`. Independent accepted
ID/core/top normalization review passes at `build/t11/id2/independent-review`.
The original failure remains recorded; no whole-Chisel-core pass is claimed.

Faithful Chisel core baseline, 2026-11-15, same base plus working changes:
`python3 hw/ip/perf_core/formal/check_core.py --emitted build/t11/core2/emit
--output build/t11/core2/equiv` passes unbounded named-state induction, 163
state elements, one structural multiplier, all thirteen active child declarations
replaced. No environmental assumptions; output/reset-value/next-state/gained-reset
faults rejected. Uses the explicitly approved CSR/ID priority analysis models.
Independent source review and reproduction at
`build/t11/core2/independent-review/equiv` passes. Both architectural-model
simulation and corrupted-retirement tests pass for root and independent reviewer.
This supersedes only the absence of a core baseline result: retimed production,
top, candidate ISA/workload/physical acceptance remain outstanding.

Registered integration, frozen `integrated23`, 2026-11-15, base `a532304`
plus receipt source hashes: `hw/ip/perf_core/formal/check_integration.py
--emitted build/t11/integrated23/emit/asic --variant <variant> --output <path>`
through `python tools/env/run.py run -- python3`. Normal at `protocol/normal`
passes **bounded** ABC BMC depth160 with 21 assertions; cover at
`protocol_retry/cover` reaches all 14 covers with btormc depth160. Real early
RF-write and redirect-target-bit mutations are rejected at depth40 under
`protocol_retry/{fault,redirect-fault}`. Each variant proves its stripped
instrumentation equal to the exact production core; normal binding also rejects
its correspondence faults. Only startup reset is constrained; subsequent reset,
memory responses, IRQ/debug and external RF values remain arbitrary. This is
bounded control, not unbounded ISA/memory causality. The initial fault-emission
attempt timed out waiting for the shared Scala runner; reruns retained the
600-second limit. The final local gate remains pending; registered ISA results
are recorded below.

Fresh independent baseline reproduction on the frozen source:
`python tools/env/run.py run -- python3 dv/core/equiv.py --top --candidate
build/t11/ci/baseline --self-check --output
build/t11/registered_top_review/baseline_equiv` passes unbounded named-state
induction, 196 state elements, one structurally matched multiply, no assumptions,
and all four negative controls. Approved CSR/ID analysis normalizations are
explicitly recorded. The registered-profile obligations remain separate.

Registered ISA acceptance, same frozen source and base commit, 2026-11-15:
`python tools/env/run.py run -- python3 dv/core/riscv_formal.py --target
candidate --candidate build/t11/ci/registered --output
build/t11/ci/registered_rvf` passes all 70 partitions, retirement covers and
required fault controls at depth144/check64. Measured elapsed time 13860.50
seconds. MUL remains arithmetic-abstracted (ALTOPS), with result and operand-
capture faults rejected; DIV/REM remain divisor-zero early-finish coverage.
No unbounded ISA or direct full-product proof is claimed. Full local CI is
still running.
