# Focused core and SoC regression scope

D89 narrows [T39](../plan/tasks/T39-core-soc-qualification.md) to existing,
unchanged regression tests. Results and exact commands belong in the
[T39 report](../plan/tasks/reports/T39.md); this document defines their scope,
not a proof or architectural-certification claim.

## What is checked

| Target | Existing evidence required by this campaign | Interpretation |
| --- | --- | --- |
| Faithful Chisel performance core/FPU | Fast core/FPU tests, existing pinned RV32UI/UM/UC, F and hard-float lockstep, fast random smoke | Standalone pipeline regressions; original Ibex only covers common behavior, QEMU covers the supported comparison fields |
| Lite RV32E core | Baseline, hart, machine and debug suites, existing seeds and actual fault controls | Existing project specification models; no new external RV32E ISS qualification |
| Loader and boot release | SocLiteSpec and SocBootReleaseSpec | Diagnostic USB-stub/peripheral-test or external-clock configurations; not complete production-clock evidence |
| Production clock/reset top | Complete SocClockResetSpec | Real integrated digital top with behavioral analog models; boot straps, reset/debug-reset and existing sleep/wake cases |
| Two-hart JTAG | Existing OpenOCD positive scenarios and missing-halt fault | Actual production digital/TAP assembly under independently driven test clocks; not the production oscillator/reset wrapper |
| Production flight workloads | Existing fixed and hard-float workloads before/after UART oscillator-off wake | Fresh DUT execution and checksums, passive performance retirement trace, unchanged cycle comparisons |

Production remains the single `DeadhorseSoc`; no feature profile, memory-size
change, source substitution or clock/reset policy change is introduced.
Named existing diagnostic configurations retain their narrower scope.

## Reference and observation limits

- Standalone faithful-core emission uses its historical default debug addresses;
  those differ from production. The production debug binding has a separate
  OpenOCD regression. Do not relabel the standalone configuration as an exact
  production-parameter equivalence result.
- QEMU text traces do not directly expose all FCSR effects. Existing explicit
  probes and FPU tests retain their scope; this campaign adds no new complete
  FP/CSR architectural-state observer.
- Lite machine tests use the DUT's interrupt-boundary indication when advancing
  their project oracle. Their directed IRQ/WFI checks remain useful but do not
  independently establish legal interrupt timing for every execution.
- The production flight runner authenticates freshly rebuilt workload bytes
  against existing target-QEMU checksum receipts. The DUT runs are fresh; the
  target-QEMU reference run is historical. Neither checksum equality nor
  before/after-wake timing equality is whole-program instruction lockstep.
- Current SRAM/ROM models, loader and bootstrap firmware are named test inputs.
  These results do not qualify T35 SRAM macros or T36 production boot firmware.
- Behavioral analog models and two-state digital simulation do not qualify
  physical POR/oscillator operation, metastability, PVT, or routed timing.

## Explicitly deferred broader qualification

New architectural-suite/generator adoption, a qualified independent RV32E ISS,
independent IRQ alignment, production two-hart ISS lockstep, complete state
observation, the new large seeded campaign, exhaustive coverage and expanded
RTL/common-mode fault campaigns are outside D89's finite scope. All inherited
unbounded proofs and their original owners remain recorded in STATUS/ledgers.
Existing fast-tier formal jobs still run; no unchanged deferred-proof retry
or new assumption is introduced.

Preflight research found that some upstream architectural cases cannot execute
within the production lite program aperture even when individually partitioned.
The approved response was to narrow the campaign significantly, not to enlarge
memory, alter upstream tests, or count a standalone result as an integrated pass.
No researched Sail/ACT/RISCV-DV source is adopted as an acceptance input here.

## Freshness and replay

Fast CI and the selected regressions qualify a frozen revision plus working
source hashes under the pinned environment. Post-run documentation publication
is checked separately and does not change the tested code. Any RTL, test, tool
or firmware-source fix requires affected replay and fresh final fast CI.
T35/T36/T37 replay affected cases after their changes. T38 consumes the current
scoped evidence with these limits; a T39 pass is not an integration-stage exit
or tape-out signoff. The full-tier disposition must remain explicit.
