# Core reference formal ledger

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
