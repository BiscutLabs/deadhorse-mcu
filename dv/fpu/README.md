# Standalone FPU verification

Run in the pinned environment:

```
python3 dv/fpu/check.py --output build/t12
python3 tools/ci.py --scope fpu
```

The focused local gate runs repository/tool checks plus T12 acceptance. The
default full gate retains all existing checks and includes T12. A scoped pass
is not a full-gate pass. No processor integration or whole-core ISA sweep is
part of the focused command.

`tools/env/fpu.lock.json` pins every reference source blob from Berkeley
TestFloat and SoftFloat. Missing sources are fetched at the pinned commit;
verification normally runs offline from `build/t12/upstream/`. SoftFloat is
rebuilt with the RISCV specialization on each reference preparation, preventing
stale objects from another specialization. Both upstream packages are BSD-3-Clause.

`vectors.py` uses an explicitly sampled 256-vector prefix of TestFloat's seeded
infinite stream for every operation/rounding-mode pair, plus a directed corner
cross-product and independent seeded random binary32 bit patterns. Native
TestFloat result/flag vectors are cross-checked against the SoftFloat adapter.
FMA sign variants and RISC-V-specific operations use TestFloat inputs with the
adapter's expected results. This is sampled coverage, not exhaustive TestFloat.

`iss.py` compares special-value behavior against the pinned QEMU package from
`dv/core/iss.json`, including canonical NaNs, signaling flags, signed-zero
min/max, comparisons, fused signs and integer saturation. No host floating-point
arithmetic supplies expected results.

The compiled RTL simulator checks both result and every flag, captures request
operands, imposes per-operation cycle limits, and exercises response backpressure.
Every operation/rounding-mode pair is mandatory. Checker controls require
rejection of missing operations/modes, malformed inputs and incorrect results
or flags. ScalaTest adds per-phase reset/cancel with immediate replacement
DIV/SQRT, invalid encodings, and real result/flag mutations for every operation.

Formal control (explicitly arithmetic abstracted), exact prefix addition,
the separate multiplier recurrence argument, and unchanged T09 GF180 timing
complete acceptance. Receipts and emitted RTL remain under `build/t12/`.
