# Core reference formal ledger

T10 evidence, based on `7b4a65f620d52cd10f0a32bb9767e9c55eb2315c` plus the
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
