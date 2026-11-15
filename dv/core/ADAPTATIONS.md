# Reference analysis adaptations

## D44-multiply-altops

User-approved D44, 2026-11-14. Enabled only for the four multiplication
integration partitions, never simulation/equivalence/production. The pinned
`ibex_multdiv_fast.sv` hash and exact assignment are in `adaptations.json`.
`altops.py` replaces that assignment in a generated copy, under
`RISCV_FORMAL_ALTOPS`, with the output of Chisel-emitted `MultiplyAltop`.
Without the define, the exact original assignment remains. No vendor file
is edited. Per-build `adaptation.json` records exact original/replacement
bytes and source/emitted hashes; a hash or match-count discrepancy is fatal.

New arithmetic/state/assertion logic is Chisel. The Python adapter generates
only instance wiring and the approved result-net substitution. Masks and
add/sub choices are extracted from the hash-verified pinned upstream models,
not duplicated constants. Only configured RV32MFast is supported. Capture is
at the first accepted ALBL cycle; the real fast unit uses live operands at
subsequent stages. Additional assertions check those live operands and
operation metadata remain stable. Formal emission inlines verification
layers and the Yosys script requires all four added assertion cells.

Original state transitions, intermediate arithmetic, valid, stall, ready,
and divide result selection are preserved. The captured ALTOPS value replaces
only the multiply result. The core's upstream RVFI model sees the matching
ALTOPS operation. Negative runs either flip a nonzero destination's result
or corrupt captured operand A; a clean shadow operand keeps the stability
monitor independent in the operand-fault run. The integer arithmetic lemma
and real-arithmetic simulation remain separate acceptance obligations.

Reversal: `riscv_formal.py --target reference --unabstracted-multiply --output
build/t10/raw-diagnostic` uses the original multiply source and checker.
Its timeout remains 600 seconds; it is a non-gating diagnostic. A timeout is
unresolved, a counterexample is failed, and a tool error is never a proof.
Re-audit on changes to the reference, configuration, checker or emitter.

## T10-unused-scramble-initializer

User-approved exception to T10's unmodified-analysis requirement, 2026-11-14.
The immutable upstream reference remains Ibex v2.1.0 at
`38c070939183cc10940b66c8e9e04eeca6b65470`.

The declaration of `unused_scramble_inputs` at original `rtl/ibex_top.sv:540–542`
initializes an unused variable from live inputs. Pinned slang rejects that
initialization. This appears intended to consume disabled scrambling inputs
for lint; the identifier has no consumers and the expression has no side
effects. Independent review confirmed that inspection. This is a reason to
expect unchanged observable behavior, not a claim of formal equivalence.

The build removes precisely this declaration from a generated copy. It does
not remove the adjacent constant assignments, any functional initialization,
any assertion or any port. Vendor files are never modified. The source hash
and exact removed bytes are pinned in [adaptations.json](adaptations.json);
hash/count mismatches fail closed. Each build writes an adaptation receipt
with original and adapted hashes. No global `--ignore-initial` flag is used.

If a later bug involves startup, scrambling-disabled configuration or tool
differences, reproduce with the original file and compare with the recorded
adapted hash. The original failing logs are `build/t10/frontends/slang.log`.
Reversal is to omit this single adaptation; the original source remains
available at the same locked path. Any reference revision change requires
fresh review rather than broadening the replacement pattern.

Regression evidence is produced by `dv/core/lockstep.py --self-check`: it runs
the immutable original and the adapted copy against the pinned ISS. This is
a directed retirement comparison, not an exhaustive equivalence proof of
the adaptation. `dv/core/test_inputs.py` separately checks that changed input
bytes, a missing declaration and multiple matches are rejected, and that
the original bytes are preserved.
