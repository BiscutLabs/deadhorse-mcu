# T10 multiplication timeout investigation

Investigation date: 2026-11-14. Base commit:
`7b4a65f620d52cd10f0a32bb9767e9c55eb2315c`, plus uncommitted T10 changes.
All executable checks use the pinned container through
`python tools/env/run.py run --`.

## Assessment

The available evidence favors arithmetic solver complexity over a multiplier
RTL bug. This is an inference, not a proof that the core is correct. No
positive multiplication proof or counterexample has been obtained. A
separate ISS trace-boundary bug was reproduced and fixed; it does not explain
the formal timeout because the formal driver does not use the ISS checker.

The normal formal gate retains its 600-second limit, all inputs and upstream
assertions, the 40-global-step horizon and selected retirement at core cycle
12. Those horizon/cycle values are assumed coverage choices. No arithmetic
abstraction or constrained operand subset has been promoted to acceptance.

## Evidence

- Extended-time experiment: `sby -f -d build/t10/diagnosis/mul-long
  build/t10/diagnosis/mul-long.sby` returned **TIMEOUT**, no counterexample,
  with the diagnostic limit raised from 600 to 1,800 seconds. SBY measured
  1,801 seconds including termination. Byte comparison confirmed the config
  changed only that timeout; receipt is
  `build/t10/diagnosis/long-config-comparison.json`. The ordinary acceptance
  limit stays 600 seconds. Process samples show ABC accumulating CPU time
  while the log remains at the first result-equality bound; this was not a
  launcher waiting on I/O. Guest elapsed-time counters and UTC log timestamps
  diverged during this run, so the reported duration is SBY's measured
  elapsed time, not a subtraction of UTC headers. The cause of that clock
  discrepancy was not investigated.
- The corrected CI run timed out on MUL, MULH and MULHSU. The solver produced
  neither a counterexample nor a successful result. The timeout is a failure
  to establish the property, not evidence of an incorrect product.
- An alternate BTORMC diagnostic discharged preceding checks and stalled at
  upstream `rvfi_insn_check.sv`'s destination-result equality assertion
  (`spec_rd_wdata == rd_wdata`). Its model/log are under `build/t10/mul-btor/`.
  Independent review verified the bad-property mapping. This localizes the
  difficulty but does not prove that assertion.
- Source/netlist review found the configured fast multiplier and signedness
  match the four instruction models. The core uses signed partial products;
  the checker uses a direct full-width product. Review found no carry,
  extension, operand-capture or RVFI result-routing discrepancy.
- Measured by `python3 dv/core/mul_diagnose.py --output
  build/t10/diagnosis/stress`: **4,420 operand pairs**, **17,680 products** and
  **40,122 retirements** passed original/adapted/QEMU comparison and the
  independent Python arithmetic oracle. The fixture contains the Cartesian
  product of 18 explicit edge values and 4,096 pseudorandom pairs, seed
  `0xDEAD0010`. All 36 injected result-bit faults were rejected. Receipt:
  `build/t10/diagnosis/stress/result.json`. These measured results cover the
  finite fixture, not all operands or execution histories.
- Measured by `python3 scratch/t10/mul_controls.py`: all four multiplication
  partitions have reachable upstream covers and reject the deliberately
  flipped RVFI result bit. Logs/configurations and result receipt are under
  `build/t10/diagnosis/controls/`. This diagnostic reuses the existing CI
  wrapper and unchanged assertion, horizon and timeout. Covers and negative
  controls establish that the check is exercised; they do not establish the
  positive arithmetic result. Independent review found these first fault
  witnesses wrote x0: they specifically demonstrate RVFI zero-register data
  checking, not a nonzero destination's arithmetic result.
- A stronger diagnostic emits `ReferenceFormal` in `fault-nonzero` mode,
  flipping the RVFI result bit only when its destination is nonzero. This
  adds no assumptions and leaves ordinary positive/fault modes unchanged.
  Measured by `python3 scratch/t10/nonzero_controls.py`: all four instruction
  checks reject this fault at the upstream result-equality assertion; each
  run takes approximately 9-10 seconds. Receipts/witnesses are under
  `build/t10/diagnosis/nonzero-controls/`. These are negative controls, not
  proofs of the unmodified multiplier. Independent review confirmed all
  four witnesses write x16 and fail the intended result assertion.
- `python3 scratch/t10/remaining_partitions.py` reruns the 20 non-multiply
  partitions that CI had not started, using the existing wrapper and original
  bounds/assertions/timeout. Measured: every bounded check and cover PASS,
  every fault FAIL. Combined with CI's 46 completed partitions, all 66
  non-multiply partitions have bounded/cover/fault evidence at the selected
  startup check cycle. The original full gate still failed; these diagnostics
  do not cover normal long-latency division/remainder or the broader ISA
  obligations excluded by the harness contract. Receipts are under
  `build/t10/diagnosis/remaining/`.

## Arithmetic-only isolation

`python3 scratch/t10/arithmetic_identity.py` asks pinned Boolector to refute
a known unsigned low-product identity, independently of any CPU state:
for `a = al + 2^h * ah`, `b = bl + 2^h * bh`, and word width `2h`,

```text
a*b mod 2^(2h) = (al*bl + 2^h*(al*bh + ah*bl)) mod 2^(2h)
```

The omitted high-by-high term is a multiple of the modulus. The SMT operands
remain arbitrary; only the width varies. Independent review checked the
identity and reproduced the small-width result. Measured results from
`build/t10/diagnosis/identity/result.json`:

| Word width | Correct identity | Injected low-bit inversion |
| --- | --- | --- |
| 8 | UNSAT, 0.324 s: exhaustive identity check | SAT, 0.006 s |
| 16 | TIMEOUT at the diagnostic 120 s limit | SAT, 0.008 s |
| 32 | TIMEOUT at the diagnostic 120 s limit | SAT, 0.011 s |

This demonstrates arithmetic solver difficulty without the core/harness.
It is not an Ibex proof, does not cover signed/high products, and gives no
completion-time bound for the core's ABC run. The short diagnostic limits
are separate from the unchanged acceptance limit.

## Trace-boundary defect

The expanded fixture reproduced an ISS trace with multiple executions of
the final inert `j .`. QEMU's asynchronous finisher shutdown can emit more
than one such state. The checker previously expected exactly one post-state
and rejected otherwise correct traces for a retirement-count mismatch.

`lockstep.py` now independently locates the ISS finisher store and validates
every subsequent state: the next instruction must be a self-jump, its PC
must remain fixed, and all registers must remain unchanged. The first
post-state is retained to validate the final store. All earlier retirement,
PC, instruction, register and memory comparisons remain intact. Regression
tests reject corrupted PCs/registers, missing post-state and a non-jump tail.

## Upstream context and next step

The [riscv-formal RVFI documentation](https://yosyshq.readthedocs.io/projects/riscv-formal/en/latest/rvfi.html#alternative-arithmetic-operations)
explicitly identifies multiplication/division as difficult for hardware
model checkers. Its ALTOPS mode substitutes simpler arithmetic to check
integration behavior. ALTOPS alone would not verify the actual multiplier
and is not enabled here. The same guidance is present in the pinned
riscv-formal checkout's `docs/source/rvfi.rst`.

The [Ibex documentation for the pinned revision](../../hw/vendor/ibex_ref/doc/03_reference/rvfi.rst)
describes formal support as limited to I/C and verification as unfinished.
An RVFI port is not evidence that this M-extension proof should finish.

Recommended follow-up is a compositional proof: establish real arithmetic
correctness for the multiply unit separately, then prove its control,
operand capture and retirement integration using only guarantees already
proved. Every cutpoint obligation must be discharged against the immutable
reference, with covers and negative controls; merely assuming the expected
product is circular. Keep the current end-to-end check and report its
unresolved result until an equivalent complete proof chain is demonstrated.
This strategy is a recommendation, not an implemented or validated solver
solution, and its runtime is unknown.

Independent reviewer `t10_final_review` checked the arithmetic/RTL comparison,
stress receipts, nonzero-destination fault witnesses, all remaining partition
statuses and the evidence limits. The extra time did not establish the
missing result; it does not establish that an even longer run could never
finish. At this checkpoint T10 remained blocked, with no full local gate pass. The user subsequently
authorized committing and pushing this incomplete checkpoint for further
agent review. Generated logs and scratch diagnostics remain local and ignored.

## D44 follow-up

Commit `1b04c8af3aee8143d471394105c139ceaa7f18aa` approved the revised
acceptance: ALTOPS integration for the four multiply instructions, integer
lemmas, required stress simulation, and an unresolved non-gating raw check.
See [the current task report](../../docs/plan/tasks/reports/T10.md) for final
acceptance status and [the lemma](MUL-LEMMA.md) for its actual obligations.

The independent review's optional stronger-route feasibility attempt used a
Chisel-emitted shared symbolic memory with five read ports, 34-bit addresses
and 34-bit values. Measured by the pinned commands recorded in
`build/t10/d44/review/uf/result.json`: the unwritten memory was optimized to
zero. A dummy write port retained a declaration, but the generated unsized
array bound was truncated by both frontends into a two-entry memory; making
the generated bound explicit produced a slang range error. The source and
commands are under `scratch/d44_review/`, with logs under that build directory.
No valid full-address function reached the core/spec integration stage or a
bounded solver run. No smaller memory or fixed function was substituted.
The attempt is unresolved, not a passing stronger proof. D44's arithmetic
lemma-to-RTL review/simulation caveat therefore remains mandatory.
