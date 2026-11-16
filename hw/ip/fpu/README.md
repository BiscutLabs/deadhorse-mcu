# Standalone single-precision FPU

T12 standalone implementation; core integration belongs to T13. Runs entirely
in `clk_main`, with asynchronous reset assertion and externally synchronized
release. No clock generation, domain crossings, architectural registers or CSRs.

`req` and `rsp` are Decoupled interfaces. A request contains `op`, IEEE binary32
operands `a/b/c`, and a resolved `rm` (0 RNE, 1 RTZ, 2 RDN, 3 RUP, 4 RMM).
Integer operands/results use their ordinary 32-bit representation. T13 resolves
dynamic rounding and rejects reserved instruction encodings. This block returns
canonical NaN with NV for unsupported operation or rounding encodings.

One transaction may be outstanding, including a held response. Ready, response
valid, result, flags and busy are registered. Request fields are captured only
on acceptance. `busy` remains asserted until response consumption or cancellation;
backpressure may therefore hold busy indefinitely. The computation completion
bound applies to response presentation, independently of response ready.

Synchronous `cancel` takes priority over acceptance and response consumption;
neither handshake commits on a cancel edge even when valid/ready were high.
It invalidates the current computation and any held response, resets iterative
control and clears visible result/flags. A new request can start the next cycle.
Reset has the same visible effect: ready=1, busy=0, valid=0, result=flags=0.
Payload registers are overwritten before use; cancellation is not secure erasure.

The implementation shares the fused datapath for ADD/SUB/MUL and all four FMA
forms. Multiplication is serial, with one significand bit per cycle. Division
and square root share HardFloat's iterative raw engine. All floating-point
arithmetic and integer-to-float conversions share the final rounding unit.
Arithmetic uses gradual underflow, tininess after rounding, canonical NaNs and
flags in RISC-V order NV/DZ/OF/UF/NX. Moves and sign injection preserve NaN payloads.
MIN/MAX return the numeric operand for one NaN, canonical NaN for two, and raise
NV for any signaling NaN; opposite zero signs choose -0 for MIN and +0 for MAX.

Cycle contract, from acceptance to response presentation: min/max/comparisons
4 cycles; sign/class/moves 3 cycles; float-to-integer 6 cycles; integer-to-float 8 cycles; fused datapath
38 cycles; DIV at most 58 cycles; SQRT at most 56 cycles. These are synchronous
cycle counts, checked by simulation and control formal, not silicon timing
measurements. Unsupported encodings return in 2 cycles. Response backpressure
does not alter result or flags.

GF180 measurements required staging FMA alignment/normalization, rounding,
and integer conversions. The divider uses a registered trial and commits one
quotient/remainder bit every two cycles. Internal arithmetic stages continuously settle while
the controller holds their inputs constant; the controller waits for the
documented stage count before capture. They are not independently decoupled
pipelines. Timing adaptations are patches on the pinned sources, applied only
under `build/vendor/hardfloat/`. The wide increments and serial multiplier use
the locally proved prefix adder. Emission preserves named values so the prefix
adder keep attributes survive lowering and mapping. No multicycle timing
exceptions are used.

See [formal/README.md](formal/README.md) for proof scope and assumptions, and
[../../../dv/fpu/README.md](../../../dv/fpu/README.md) for reference tests.

The measured mapped area is 217,553.1008 um^2 and the worst path is
24.402643 ns with zero electrical violations, from `hw/ip/fpu/check_timing.py`
on base commit `3dfa92e` plus the T12 working tree. See the T12 report and
`build/t12/timing/result.json` for provenance. These are pre-layout results.
There is no numerical standalone FPU area ceiling in T12; mapped area feeds
the later S1 chip budget. The unchanged timing limit is 24.96 ns at GF180
SS/125 C/3.0 V (assumed 41.6 ns clock times 60%).
