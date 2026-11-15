# Ibex reference only

This directory is the golden comparison source for T10/T11, **not production
IP**. The chip must contain the equivalence-checked Chisel conversion. The
[comparison tools](../../../dv/core/README.md) describe the checks and limits.

Ibex: upstream tag `v2.1.0`, commit
`38c070939183cc10940b66c8e9e04eeca6b65470`, from
<https://github.com/lowRISC/ibex>. Apache-2.0 notices and the original LICENSE
are retained. The bundled lowRISC primitive provenance is recorded in
`vendor/lowrisc_ip.lock.hjson`. Only upstream technology-neutral primitives and
their upstream simulation wrappers are selected; the generic clock-gating
primitive contains an upstream reference-only latch.

The `riscv-formal/` subtree comes from
<https://github.com/YosysHQ/riscv-formal> at
`c992aa61fdfe0846c5ed90324c596202a1c69b76`, with its permissive COPYING retained.
No upstream verification result is inherited.

`ibex_ref.lock.json` records every imported file's original path, upstream and
SHA-256, the ordered flat compile list, include directories and defines.
Local `.gitattributes` disables text conversion so Windows checkouts preserve
the pinned upstream bytes too.
Run `python3 hw/vendor/ibex_ref/verify_lock.py` in the pinned environment.
`dv/core/import_reference.py` is a byte-preserving importer from the two pinned
checkouts below `build/t10/upstream/`; it refuses to overwrite changed files.

The fixed top-level parameter set is in
[config.json](../../../dv/core/config.json): RV32IMC, flop register file,
multicycle fast M, no cache/PMP/security, debug trigger and RVFI enabled.
Upstream machine/user-mode capabilities are retained; intended software tests
run in machine mode. No Chisel core is implemented by this import.

The approved, hash-guarded [analysis adaptation](../../../dv/core/ADAPTATIONS.md)
removes only the unused declaration initializer at `rtl/ibex_top.sv:540` from
generated copies. Both frontend routes elaborate those copies. The untouched
original is also run in retirement comparison. No global initialization
suppression is used. See the [T10 report](../../../docs/plan/tasks/reports/T10.md)
for current completion and review status.
