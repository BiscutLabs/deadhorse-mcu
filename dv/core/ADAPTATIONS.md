# Reference analysis adaptations

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
