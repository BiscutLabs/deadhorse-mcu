# Core reference formal ledger

## T13 acceptance deferred for S1, 2026-11-17

User-approved S1 measurement dependency exception; T13 remains incomplete.
Formal timeouts are deferred/unproved, with their original assertions,
assumptions and bounds preserved. No further long sweep is authorized by this
exception. See the [acceptance inventory](../plan/tasks/reports/T13.md#deferred-acceptance-for-s1).

| Obligation | Current status | Scope retained |
| --- | --- | --- |
| Repaired faithful-F integration, original 28 assertions, depth 160 | Deferred, unresolved timeout | Diagnostic depth 40/80 bounded arithmetic-abstracted results, concrete covers and fault controls do not prove depth 160 |
| Complete repaired faithful-F configured ISA sweep | Deferred, unrun | Earlier three focused instruction checks preceded the repair |
| Complete changed-core no-F/refinement | Deferred, not established | Local compressed-decode/CSR proofs and unchanged-module equivalence retain only their stated scope |
| Standard full CI tier | Unrun | Not a proof result or a passing gate |

Independent read-only audit found current candidate source hashes match the
bus-error repair and the prior non-formal receipt's core/FPU inputs. No proof
was rerun for this reconciliation. Counterexamples require investigation;
they are not covered by a timeout deferral.

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


## T13 checkpoint: F integration (2026-11-15)

Measured on `11c72b3` plus the T13 working tree, pinned environment. Commands
and receipts are detailed in [T13 report](../plan/tasks/reports/T13.md).

- `check_float_integration.py --fpu-contract --prove`: all 28 safety properties
  proved unbounded by ABC PDR, with only initial reset constrained. Exact
  production/monitor and T12/integrated-FPU bindings pass. Real commit fault
  rejected; eight covers witnessed in the abstract protocol model. No arithmetic,
  deadline, full-ISA or RVFI proof is implied.
- `equiv.py --unchanged-since t11-baseline`: 12 untouched active modules proved
  against the rebuilt tagged baseline, with fault controls. The division-only
  specialization receives a live division-sign fault when no multiplier exists;
  the original multiply-sign fault remains for modules containing a product.
- `check_no_f.py`: compressed decoder conditional equality outside exactly the
  four added F compressed classes. CSR induction retains 22 legacy states and
  proves both added registers reset/stay zero with no F commit and FS-preserving
  effective mstatus writes. Only misa.F read bit is normalized. Three faults
  rejected by actual SAT counterexamples. IF conditional composition remains open; core/ID exact cycle equivalence is
  inapplicable after the approved latency changes.
- Critical `jalr,lw,c_add` instruction bounds at depth144/check64 timed out at
  120 seconds without counterexamples. A single JALR PDR startup-window trial
  also timed out. These are unresolved, not passes; cover/fault stages did not
  complete. No long sweep, changed assertion or longer timeout.

T13 is incomplete; no whole-task CI/acceptance or commit/push is claimed.


### Approved critical-ISA partitioning continuation (2026-11-15)

Measured by `python tools/env/run.py run -- python3 dv/core/riscv_formal.py
--target candidate --candidate build/t13/exponent/candidate --checks jalr
--split-assertions --prove-window --timeout 120 --output build/t13/rvf-jalr-split`
on `11c72b3` plus the recorded working-tree model hashes: six of 33 assertion
partitions pass; partition 06, `rvfi_insn_check.sv:171` (nonzero spec_rs1_addr must
match rs1_addr), times out without a counterexample. No subsequent assertions,
retirement covers or RTL faults run. This is not an aggregate ISA pass.

All model content except unselected assertions is preserved exactly. No peer
assertion becomes an assumption. Complete inventory accounting, unchanged
startup model/depth144/check64/120-second cap, and mandatory final cover/fault
gates remain. Only generated setundef cell keys are renamed reversibly to avoid
a Yosys JSON-reload naming collision. Raw/stabilized hashes and the mapping are
recorded. Independent review audited the seven executed models and configurations.
41 core Python tests and repository structure check pass in this continuation.


### Approved JALR address invariant (2026-11-15)

Measured on `11c72b3` plus the authenticated working-tree inputs using
`riscv_formal.py --target candidate --candidate build/t13/exponent/candidate
--checks jalr --jalr-address-invariant --timeout 120 --output
build/t13/jalr-address-strengthened`, followed by the required
`audit_jalr_invariant.py --output build/t13/jalr-address-strengthened`:

- All-retirement source-address invariant: **unbounded PDR PASS**, 5.450122 s.
- Exact original source-address assertion plus helper assertion: **PASS**,
  4.613703 s; original depth144/check64 startup-window semantics preserved.
- Active retirement cover: PASS, 1.674053 s; actual RVFI address-bit fault:
  rejected, 1.718116 s. Witnesses show expected1/reported1 versus expected1/reported0.
- Free-input combinational qualification proves the same guard and violation
  predicate as the pinned checker. Wrong monitor opcode0x67->0x66 is rejected
  with a SAT counterexample. No reported-trap guard is added.

The independent lemma retains original reset==$initstate and alternating-clock
initialization assumptions, removes only the checker instruction-selection
assumption, and preserves production cells exactly. It never assumes another
assertion. The original partition preserves every original assumption and its
selected assertion, adding the independently proved helper as an assertion.
Independent review cleared both models and witnesses. The required companion
audit verifies input hashes and active witnesses before accepting this scoped
evidence. This is not aggregate JALR/ISA acceptance; T13 remains incomplete.

A single complete-JALR attempt via `check_jalr_strengthened.py --lemma
build/t13/jalr-address-strengthened --output build/t13/jalr-complete-strengthened`
retains all 33 original assertions, covers, assumptions and production cells,
plus the helper assertion. **TIMEOUT** at the unchanged 120-second cap, measured
command duration 121.181980 s including shutdown, with no counterexample. No
aggregate proof or individual result is inferred from internal solver progress.
Fail-fast prevented the original cover/destination-fault stages. No further
proof retry or ISA sweep followed. Forty-seven Python harness tests and structure
check passed; full T13 acceptance remains incomplete.


### Approved JALR return-value continuation (2026-11-16)

Measured on `11c72b3` plus authenticated working-tree inputs by
`python3 dv/core/check_jalr_link.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-link-v2` in the pinned environment:

- Independent all-retirement link-value invariant: **unbounded PDR PASS**,
  87.135088 s under the original reset/clock wrapper environment.
- Exact original `rvfi_insn_check.sv:177` plus helper assertion: **PASS**,
  76.110678 s; original depth144/check64 startup-window semantics retained.
- x0/nonzero-destination active covers: **PASS**, 2.015849 / 2.105153 s.
- Actual reported-output bit fault, enabled only for nonzero destination:
  **rejected**, 2.226163 s, with an active nonzero-destination VCD witness.
- Free-input activation/violation and instruction-assumption-enable SAT checks:
  **PASS**; monitor PC+4 -> PC+8 mutation **rejected** with a SAT counterexample.

The predicate uses encoded rd, RV32 wrapping addition and no reported-trap or
nonzero-rs1 restriction. Every surviving original production/environment cell
is unchanged; the independent lemma removes only checker properties and forced
instruction selection. The original assertion job retains all original
assumptions and adds the helper as an assertion, never an assumption. Independent
review inspected model preservation, completed proof statuses and actual witnesses.
Every job kept the 120-second cap; no complete-checker retry or ISA sweep ran.
The initial width-sensitive negative-fixture failure stopped before any
sequential proof and is retained in `build/t13/jalr-link`; it was corrected by
validating Yosys's optimized constant width and updating the mutation width
consistently. Fifty-two Python harness tests and structure check pass.

The next-PC obligation and other T13 acceptance work remain open; these scoped
passes do not constitute aggregate JALR/ISA or task acceptance.


### Focused JALR target-PC continuation (2026-11-16)

Measured on `11c72b3` plus recorded working-tree inputs by
`python3 dv/core/check_jalr_target.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-target`: **TIMEOUT**, no counterexample, unchanged
120-second cap; command wall time 121.221777 s including shutdown. Fail-fast
prevents the x0/odd-sum/negative-offset covers, actual PC-bit fault and original
line178-plus-helper job. None is reported as passed or waived. No further proof
retry or ISA sweep ran.

Free-input exact guard/violation qualification passes (0.029262 s measured);
zero-extension in place of the signed immediate is rejected (0.026530 s measured)
with a SAT counterexample. The monitor includes the full checker's encoded-x0
source normalization, wrapping32-bit add and bit-zero clearing, with no actual
trap guard or peer assumption. The original production and reset/clock
assumptions are preserved exactly. Sixty Python harness tests pass.

Independent review also exposed mutable shared audit metadata. Prior raw result
files/statuses remain unchanged. Their old audit and executed-script inputs are
recovered/archived only with exact matches to the originally recorded SHA256,
then reauthenticated through `input-relocations.json`. The link proof, earlier
complete-JALR timeout and current target timeout all reauthenticate; no sequential
proof is rerun. New consumers verify and snapshot existing audit evidence in
their own output directory, leaving the shared baseline audit untouched. See
T13 report for exact repair commands and the historical/source provenance limit.


### JALR redirect transport continuation (2026-11-16)

Measured on `11c72b3` plus authenticated working-tree inputs with
`python3 dv/core/check_jalr_transport.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-transport-v2` and required companion
`python3 dv/core/audit_jalr_transport.py --output build/t13/jalr-transport-v2`:

- **Unbounded PDR PASS**, 14.200172 s: qualified first-phase redirect capture,
  required capture validity and instruction/PC identity at retirement, then
  matching staged RVFI target. Original production clock/reset/environment.
- **Cover PASS**, 1.758349 s: actual redirect capture survives the link phase
  and is reported by RVFI after retirement.
- **Actual reported-PC bit1 fault rejected**, 1.953078 s, with an active witness
  showing expected0x20/reported0x22 after capture and retirement.
- Exact free-input external retirement activation **PASS**; wrong opcode0x66
  in the monitor **rejected** with a SAT counterexample.

Original production cells/ports/netnames are preserved, with observation-only
clocked ghost state added. Required capture validity/event ordering is asserted,
never assumed or used to suppress retirement checks. Cap120/depth144 unchanged.
The initial preparation stopped before proving on a generated state-name mismatch;
actual RVFI output-Q binding now validates its real clock/reset and reset value.
Sixty-three Python harness tests pass. This establishes transport only; target
arithmetic, complete ISA and T13 acceptance remain unresolved.


### JALR capture/source continuation (2026-11-16)

Measured on `11c72b3` plus authenticated working-tree inputs with
`python3 dv/core/check_jalr_capture.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-capture`, then the same runner with
`--resume-from build/t13/jalr-capture --output build/t13/jalr-capture-resumed`:

- **Unbounded PDR PASS**, 28.087467 s: normalized capture-source correspondence
  through retirement/RVFI, jointly with redirect transport.
- **x0 cover PASS**, 1.807055 s; **rs1=rd cover PASS**, 1.804066 s.
- **Actual RVFI source-bit fault rejected**, 1.920735 s, expected0/reported1.
- **Capture arithmetic TIMEOUT**, unchanged120-second cap, wall121.357526 s,
  no counterexample; later arithmetic covers/fault unrun, not waived.

The initial source-only witness omitted unused arithmetic signals. The repaired
parser reuses byte-identical completed jobs after validating archived executed
source, all old hashes/configurations/statuses, and the actual trace. Original
raw receipt is unchanged. Independent review clears the reuse/source witnesses.
`python3 dv/core/audit_jalr_capture.py --output build/t13/jalr-capture-resumed`
passes the source-only audit and wrong-opcode guard negative; it explicitly
preserves aggregate unresolved/arithmeticTIMEOUT. No new assumptions or trap
guard. Sixty-six Python harness tests pass. ISA and T13 acceptance remain open.


Further diagnostic, measured on the same base/protected source set:
`python3 dv/core/check_jalr_request.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-request` yields **saved-request alignment TIMEOUT** at
unchanged120-second cap (wall122.057978 s), without counterexample. It asserts
response valid, saved ALU kind/ADD/first-cycle and both saved operands under the
original capture guard. Exact production model and assumptions are unchanged.
Later alignment covers/fault and local ADD proof/cover/fault are unrun; external
activation SAT qualification alone is not a proof or negative-control clearance.
Independent review clears code/model, not proof acceptance. Sixty-eight harness
tests and structure check pass; further solver attempts stopped.


### Exact alignment-conjunct diagnostic (2026-11-16)

Measured on `11c72b3` plus authenticated inputs by
`python3 dv/core/split_jalr_alignment.py --baseline build/t13/jalr-request
--output build/t13/jalr-alignment-split`: response-valid **unbounded PDR PASS**
(3.962384 s); ALU-kind **TIMEOUT** at unchanged120-second cap
(wall 121.125216 s), without counterexample. Remaining four conjuncts unrun.
This is partial diagnostic evidence; original covers/faults and local ADD/ISA
acceptance are unresolved. No peer assertions assumed. All six conjuncts retain
the original guard/enable and exact production/environment. Free-Boolean SAT
proves equivalence; omitting the immediate conjunct is rejected with an active
witness where that conjunct alone is false. Independent review verifies models,
protected hashes, statuses and negative witness. Seventy-one Python tests and
structure check pass. No production RTL change or widened time budget.


### Accepted execute-request tracking (2026-11-16)

Measured on `11c72b3` plus authenticated inputs by
`python3 dv/core/check_jalr_ownership.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-ownership`, resumed after parser repair with
`--resume-from build/t13/jalr-ownership --output build/t13/jalr-ownership-resumed`:
accepted JALR kind **unbounded PDR PASS** (3.948244 s), actual saved kind/phase
retention **unbounded PDR PASS** (4.052221 s), retained JALR kind **unbounded PDR
PASS** (3.881496 s). Capture instruction/PC identity **TIMEOUT**, cap120 s,
wall121.319890 s, no counterexample; later ownership covers/fault unrun.

Issue/retention covers and actual input/saved-kind faults pass. Required companion
`python3 dv/core/audit_jalr_ownership.py --output build/t13/jalr-ownership-resumed`
rejects wrong-opcode activation and an actual accepted-input-kind corruption
observed later in retained state (1.515339 s for the fault job). Audit acceptance
is explicitly limited to completed control components. No extra assumptions.
Every request is tagged; actual consume/reset clears validity. Original parser
incorrectly required unused ownerJalr in the retention-fault trace. Exact archived
executed source, immutable raw receipt and byte-identical model/config checks
allow reuse without rerunning completed proofs. Seventy-four harness tests and
structure check pass. Full identity/arithmetic/ISA/task acceptance remains open.

Independent review cleared the scoped control components and delayed fault
witness. The hardened auditor additionally authenticates the actual identity
status file. It passes with `--audit-output build/t13/jalr-ownership-control-audit`,
retaining identityTIMEOUT and aggregate unresolved. Old executed auditor bytes
are archived with their recorded hash; historical audit/positive proofs are
unchanged. Only short negative qualifications reran after that auditor change.


### Exact capture ownership flag split (2026-11-16)

Measured on `11c72b3` plus protected inputs with
`python3 dv/core/split_jalr_ownership.py --baseline build/t13/jalr-ownership-resumed
--output build/t13/jalr-ownership-split`: capture owner-valid **unbounded PDR
PASS** (6.300894 s); owner-JALR **TIMEOUT** at unchanged120-second cap
(wall 121.409461 s), no counterexample. Remaining owner-first/instruction/PC
partitions unrun. Positive subsets remain diagnostic, with covers/faults and
aggregate identity/ISA outstanding; no ALU-kind composition is claimed.

All five conditions preserve original capture/enable and exact production/ghost
state/environment. Free-Boolean equivalence passes and omitted-PC negative is
rejected with an active witness. Independent review clears transformation/tests;
seventy-seven harness tests and structure pass. The tag-only timeout persists
without wide identity equality in the predicate; no further cosmetic split or
longer retry was run.

Final independent review authenticates the five-way partition's protected hashes
and final statuses. Read-only inspection finds no established stale-response bug.
Next proposed diagnostic: ID phase/tag stability across outstanding integer
execution, using actual IF instruction-write rather than its registered pulse.
Qualified FPU protocol abstraction may reduce a dominant FPU cone only after
concrete-port-trace inclusion and every model restriction are justified. Neither
proposal is an executed proof or an arithmetic/ISA acceptance change.


### Transition-local execute phase stability (2026-11-16)

Measured on `11c72b3` plus protected inputs using
`python3 dv/core/check_phase_stability.py --baseline build/t13/jalr-address-strengthened
--output build/t13/phase-stability`: unbounded PDR **PASS** for no instruction
write while holding (10.610338 s), no ID clear (7.818669 s), and full tag stability
across the holding edge (12.955898 s). All active covers and actual production
write/clear/phase faults pass. Companion `audit_phase_stability.py --output
build/t13/phase-stability` verifies hashes/witnesses and wrong-opcode guard
negative. Independent review clears these scoped results. No new assumptions.

`strengthen_jalr_ownership.py --phase build/t13/phase-stability --owner
build/t13/jalr-ownership-resumed --output build/t13/jalr-ownership-strengthened`
proves inherited-monitor named-state equivalence (SAT0.064738 s) and rejects a
tag-binding negative, but capture=>ownerJALR plus the three asserted phase
invariants **TIMEOUT** at120 s (wall121.178246 s), without counterexample.
Target covers/fault and wider ownership/arithmetic/ISA remain pending. Positive
phase proofs are not promoted to aggregate acceptance. Eighty-one harness tests
and structure check pass; no further global retry or increased timeout.

Final independent review verifies monitor state correspondence, exact full-model
preservation and the strengthened timeout hashes/status. Recommended next method:
small base/step/final SAT induction over exact ghost transitions and already-proved
phase/retention guarantees, including accept/consume exclusion. Theorems must use
explicit implication antecedents, not add assumptions to the production checker;
actual binding, mutation negatives and capture fault/cover evidence remain
required. No compositional result is claimed from this proposed method.


### Exact ownership composition (2026-11-16)

`python3 dv/core/compose_jalr_ownership.py --output
build/t13/ownership-composition-confirmed` passes reset-base, one-step induction
and final implication using authenticated monitor transition/reset equations.
All three mutation negatives reject. This composes phase stability, retention
and capture-valid guarantees into full ownership identity; it neither changes
production assumptions nor establishes arithmetic or aggregate ISA acceptance.
Independent review clears the composition, its exact transition/reset binding
and qualified premise chain. Measured results are on `ac45fd4` plus protected
working-tree inputs; exact runtimes and hashes are in the generated receipt.

`qualify_owner_valid.py --split build/t13/jalr-ownership-split --owner
build/t13/jalr-ownership-resumed --output build/t13/owner-valid-qualified`
passes active capture cover (measured1.745269 s), ghost-valid sensitivity
negative (1.722141 s) and actual production PC-bit ownership negative
(1.742066 s). Independent review verifies all protected hashes, statuses and
active witnesses and clears only this qualification scope. Eighty-eight harness
tests pass in the pinned environment; prior timeout receipts remain unresolved.


### Saved kind/phase, ADD and operand components (2026-11-16)

On `ac45fd4` plus authenticated working-tree inputs, root commands
`compose_jalr_request_kind.py --ownership build/t13/ownership-composition-confirmed
--output build/t13/request-kind-confirmed` and `audit_request_kind.py --output
build/t13/request-kind-confirmed` pass exact implication, two wrong-conclusion
negatives, active capture and actual kind/first register faults. Independent
review clears this scoped alignment result.

`induct_jalr_execute.py --output build/t13/jalr-execute-induction-confirmed`
passes exact production reset/step/final SAT implications with dispatch-state
invariants, all negatives, overflow/odd-result cover and actual adder bit fault.
Independent review clears the saved-input ADD response equation only. The
full-core attempt in `build/t13/jalr-execute-only` remains TIMEOUT at120 s.

`check_jalr_operands.py --output build/t13/jalr-operands` proves accepted Op/A/B
classification (measured5.500861 s) and payload retention, each with active cover
and actual incoming/saved-field fault. Direct source stability TIMEOUT at120 s
(measured121.2943 s wall), no counterexample; no later source roles ran.
`audit_jalr_operands.py --output build/t13/jalr-operands-audit` authenticates
complete dependencies, preserves timeout and proves20-state inherited Phase
monitor equivalence plus binding negative. Independent review clears only
issue/retention. Source, full operand alignment and aggregate ISA remain open.


### Conditional IF equivalence (2026-11-16)

Root `python3 hw/ip/perf_core/formal/check_if_no_f.py --output
build/t13/if-conditional-confirmed` passes full baseline-interface conditional
named-state induction, unconditional actual integrated-candidate binding,
decoder-input equality and binding/output/transition/reset negatives. Independent
review clears the local result. Formal-only standalone emission retains the
baseline ALU-copy output pruned from the integrated candidate; no original
baseline output obligation is dropped. Profile specialization of disabled
features is checked by unconditional integrated binding.

The hypothesis excludes the four compressed F raw encoding classes even on
invalid, stalled or error payloads, at each comparison. It is not an unrestricted
whole-core no-F-program theorem. The SAT transfer witness is one-step
nonvacuity, not a reset-reachable cover. Measured proof metadata and source hashes
are in the generated receipt on `ac45fd4` plus protected working-tree inputs.


### FPU protocol qualification finding (2026-11-16)

Independent review identified that the old formal protocol model shares the
arbitrary invalid response payload with the next valid completion payload.
Exact all-port trace inclusion is not established by that model or its previous
28-safety receipt. Those raw results remain unchanged and apply to the old
model only. A new model with separate arbitrary payload inputs, exact concrete
transition inclusion, and a rerun of the same safety assertions is required
before it supports ISA abstraction. This is a formal-model qualification gap,
not an observed production RTL failure. No acceptance assertion is removed.


### Operand and JALR target closure (2026-11-16)

Root commands `compose_jalr_operands.py --source
build/t13/rf-source-composition-confirmed --output build/t13/operand-composition-confirmed`
and `compose_jalr_target.py --arithmetic build/t13/operand-composition-confirmed
--output build/t13/jalr-target-composition-confirmed` pass. Independent review
clears exact reset/transition/final implications, inherited state bindings,
all premise receipts, original line178 activation/violation qualification and
all mutation/active-witness checks. Arithmetic uses signed immediate, wrapping
addition, encoded-x0 normalization and bit0 clearing; no trap guard is added.

The actual response-valid negative requires premature pcSet+pcMux controls;
the earlier pcSet-only ineffective mutation remains recorded. Full-model covers
exercise zero source, odd sums and negative immediates; real saved operand,
execute-target and RVFI-PC faults are rejected. The normalized RF source proof
is independently cleared through actual RF controls and exact RF transitions.
The historical direct/full-model timeouts remain unchanged. This closes original
next-PC line178, not yet the complete original assertion inventory or other ISA
instructions. Measured timings/hashes on `ac45fd4` plus working-tree inputs are
in the generated receipts. 104 harness tests pass in the pinned environment.


### Widened FPU trace inclusion (2026-11-16)

`python3 dv/core/qualify_fpu_protocol_wide.py --output
build/t13/fpu-protocol-wide-confirmed` passes five exact SAT implications and
five mutation negatives. Independent review clears constructive all-port trace
inclusion: abstract pending/valid/response match concrete state, finish uses
concrete valid-D, completion payload uses response-D, invalid payload uses
current response. All other concrete arithmetic state is free; control/reset
invariants and cleared history are established by base/step, not assumed.
The original payload coupling is rejected by a concrete SAT witness.

Pre-use fingerprints and post-stage checks close a reviewed preparation race;
old executed runner and raw receipts are preserved. This new formal-only model
has no production RTL effect and claims no arithmetic/deadline proof. The same
28 integration assertions/eight model covers and remaining critical ISA checks
still need qualified replacement runs. Original ISA covers remain concrete.


### Complete original JALR checker (2026-11-16)

`build/t13/jalr-original-complete/result.json` records a complete disjoint union
of all 33 original assertions: six authenticated original partitions, three
address/link/target obligations, 22 remaining original assertions, and two
qualified destination/trap obligations. Independent review clears all 824
protected inputs, exact wrapper/model metadata correspondence, original guards
and environment, and the concrete original cover and real PC-bit fault.

The earlier 24-assertion attempt remains TIMEOUT. The new 22-assertion group has
its own positive proof and actual memory-mask negative; destination and trap
have separate all-retirement proofs tied to original lines176/198. The full
checker fault is `FAIL` with a converted counterexample (expected PC0, observed2),
not a timeout, despite cleanup making measured wall time slightly above120 s.
The configured cap remains120 s. This closes JALR only; other critical ISA checks
and the final focused gate remain open.


### Widened-model integration qualification (2026-11-16)

The same 28 safety assertions pass unbounded on `FpuProtocolModelWide`, with
eight abstract-model covers and the actual commit-on-squash negative detected.
`build/t13/integration-production-binding/result.json` freshly binds the
concrete instrumentation projection to production across 271 states, with
output/reset/transition/clock negatives. Independent review clears both receipts;
abstract covers are not concrete execution coverage. Measurements and exact
commands are recorded in the T13 report against `ac45fd4` plus protected inputs.

One widened critical LW run reaches the unchanged 120-second cap without a
counterexample (`build/t13/critical-wide/result.json`). It is unresolved; its
fail-fast runner did not execute C.ADD or concrete qualification. No bound,
assertion, assumption or acceptance requirement changed.


### Bounded critical-ISA scheduling refinements (2026-11-16)

Native `btormc --checkall` preserves the exact model and ORs the original bad
predicates. Its LW attempt remains TIMEOUT. One subsequent exact two-group
partition preserves all 33 original assertions and every non-assertion model
object, with no peer assumptions. The 11-assertion control/register group passes
at depth 144; the 22-assertion memory/trap group times out at the unchanged
120-second cap, without a counterexample. Concrete qualification and C.ADD do
not run after this fail-fast result. No aggregate acceptance is claimed.

Receipts: `build/t13/critical-checkall/result.json` and
`build/t13/critical-two-part/result.json`. Measured process times on `ac45fd4`
plus authenticated working-tree inputs are 122.010 seconds for the native
query, then 91.625 and 121.234 seconds for the two partitions; timeout process
times include cleanup. All retain check cycle 64/depth 144. The T13 report gives
the commands and independent-review scope. No further solver cascade is queued.


### User-directed timeout triage and CI (2026-11-16)

Source baseline `ecc5d7e` plus recorded working-tree hashes. Performance was
measured before new proof jobs using `dv/core/performance.py`; architectural
comparisons passed and an independent reviewer recomputed cycle statistics.
The T13 report records the simulation/frequency table.

`python3 dv/core/formal_triage.py --stage step0` completed in measured 110.900 s.
Concrete checked nontrapping retirement first covers at cycle 12 for LW and 11
for C.ADD; every earlier check cycle was tested and unreachable. Both original
jobs reached frame 127 at requested depth 144/check 64. Quarter (36) and half (72)
depths precede check activation and are timing diagnostics only. Prepared models
have 6,923/6,960 cells respectively, 5,711 FF bits and no memory cells. A reviewed
metadata correction includes 145 `$ff` bits and excludes the configured maximum
bound from progress; raw receipt and exact executed runner remain preserved.
All 263 Step 0 input fingerprints were independently checked.

The unchanged concrete portfolio uses btormc, SMTBMC/Yices, SMTBMC/Z3 and
ABC/bmc3, capped at 600 seconds per job. LW passed bounded at depth 144/check 64
in measured 584.257 s (Yices); its concrete cover and both actual result-bit fault
controls passed qualification. C.ADD timed out in measured 601.855 s including
cleanup, at frame 127, without a counterexample. Timeout remains unresolved.
Parser-only native VCD scope repairs reused completed identical jobs, never
reran them; executed sources and interrupted receipts are preserved.

Rung 2 timed out for C.ADD in measured 601.472 s, at unchanged depth 144/check 64. Exact
32-bit data cutpoints, independently checked against the prepared netlist:

- `wrapper.core.u_ibex_core.ex_block_i.clocked_execute.multiplier.result_o`
- `wrapper.core.u_ibex_core.floatExecution.fpu.io_rsp_bits_result`

All handshake/control signals remain real. The divider remains concrete because
its result aliases internal recurrence that influences completion control; the
shared execution result also carries ALU data and must not be cut for C.ADD.
This retains more real data behavior than the authorized abstraction. Positive
results with these cuts are labelled **bounded, abstracted**; concrete covers
and both concrete fault controls are required. No induction is authorized.

Final rung: `python3 dv/core/formal_triage.py --stage window --cutpoints
build/t13/feedback/triage/data-cutpoints.json` passes. C.ADD uses check cycle 19
(minimum concrete cover 11 + 8), depth 54; btormc wins in measured 71.281 s.
Concrete cover passes in 5.500 s; ordinary and nonzero-destination result-bit
faults are rejected in 7.414 s and 6.758 s. Status: **bounded, abstracted** with
exactly the two cutpoints above, and **fewer preceding histories**. Original
144-step C.ADD remains unresolved. LW retains its concrete check 64/depth 144
result without another solver run. M/divide/float windows remain unchanged.
Receipts: `build/t13/feedback/triage/{portfolio,cutpoints,window}/result.json`.
Both-property triage is complete; no further rungs or induction are queued.

Fast tier passes all 21 commands in measured 475.113 s. Full tier was executed,
not waived: 51 commands passed, then registered no-F timing failed at
25.335854 ns against the unchanged 24.960000 ns allowance. Its measured
3217.428 s is **partial elapsed time to failure**, not complete full-suite time.
The critical mapped path is controller-run state to mcycle counter bit 59;
26 later commands were unrun, including registered and F-integrated ISA sweeps.
The faithful configured ISA sweep passed at depth 40, retaining ALTOPS and
zero-divisor-only classifications. T13 remains blocked. Independent review
verified both gate receipts, all 922 frozen source hashes, and the timing failure.
Receipts: `build/t13/feedback/ci-fast-registered/result.json` and
`build/t13/feedback/ci-full/result.json`. No RTL or timing-limit repair was made.

## T13 faithful F continuation (2026-11-16)

Base `d8683936` plus recorded working-tree hashes. [Report](../plan/tasks/reports/T13-faithful-f.md).
`build/t13/faithful-f/qualified/unchanged/result.json`: 12 unchanged modules
proved with rejected faults. Changed integration remains a separate obligation.
`isa-focused/result.json`: ADDI/LW/C.ADD **bounded**, depth 40/check 12,
concrete covers and result faults, no cutpoints, measured 69.410 s total;
all other instructions omitted from this focused invocation.
`fpu-wide/result.json`: existing five all-port inclusion roles proved and
five controls rejected for this candidate. Normal integration uses that
qualified protocol, not a concrete arithmetic proof.
`integration/result.json`: production binding proved, binding faults rejected,
but normal integration assertion 15 fails at bound 10. Unsolicited data error
coincides with FP acceptance; next cycle load-fault cause-save and cancellation
overlap pending ownership. No FP/flag/integer commit in the relevant cycles.
Next recorded state also asserts reset; cancellation-only recovery and concrete
replay are unrun. Independent review confirms hashes and trace interpretation.
No induction extension, new bus assumption or weakened assertion was introduced.
Fault/cover integration roles were not reached; do not claim integration safety.

Fast tier **failed (partial tier run)**, measured 426.823 s to stop; 15 commands passed, failed at integrated-timing. Full tier **not run this continuation**.

## T13 bus-error repair (2026-11-16)

User-requested fix qualifies data responses by prior bus grants, for F-enabled
profiles only. No inherited LSU change or new environmental assumption.
Original unsolicited-response simulation fails before repair and passes after;
real aligned/split load/store errors, backpressure and reset regression pass.
Bound production monitor equivalence and all binding controls pass.
Original 28 integration assertions: depth160/120s **unresolved**, timeout at
step93; one unchanged-model portfolio also times out. Diagnostic depths40/80
pass (25.428/94.154s), **bounded, abstracted**, not replacement acceptance.
Only the existing qualified wide FPU protocol is substituted; no new cutpoint.
All eight **concrete** covers pass (earliest bounds5,9,10,13) and original
commit-on-cancel fault is rejected on the concrete model. No induction extension
or timeout increase. Prepared size3110cells/2240state bits/no memories.
Receipts under `build/t13/bus-error/{integration,diagnostics,concrete-fault}`.
Only emitted ibex_core changes against the preceding faithful-F candidate;
other source and extra-source hashes remain identical. Prior unchanged-module
proofs are not claimed as new runs. Selected full lockstep suites pass freshly.
Fast tier **PASS**, all 26 commands, measured 824.220 s (13m 44s), including 14 RTL tests. **Full tier not run.**
See [repair report](../plan/tasks/reports/T13-bus-error.md) for commands and independent review.

## T39 focused simulation regression — 2026-11-24

D89 simulation evidence only; no new proof or inherited proof closure.
At code `fa21f70fafb9b9bf48cdfc2f97b5ce0a17ff496f`, freshly emitted faithful
floating core passes `python dv/core/lockstep.py --candidate
build/t39/faithful-inputs01/candidate --isa rv32imfc --suite arch,flight-float
--output build/t39/faithful-lockstep01`: measured 51 pinned RV32UI/UM/UC cases,
six project FP-mode cases, 21,776 architectural-case and 191,201 flight
retirements. Eight checker trace faults are rejected; these are not RTL faults.
Production fixed/hard-float before/after-wake and two-hart OpenOCD regressions
also pass. The [report](../plan/tasks/reports/T39.md) records exact commands,
source binding, full fast-tier status and limitations: standalone debug
parameters, incomplete direct FCSR observation, historical flight checksum
references and independent test clocks for OpenOCD. Broad ISA/ISS qualification
and all previously unresolved T13/T32 proof obligations remain open.
