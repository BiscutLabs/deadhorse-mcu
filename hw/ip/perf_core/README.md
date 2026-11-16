# Performance core: faithful Ibex conversion

T11 converts pinned Ibex `38c070939183cc10940b66c8e9e04eeca6b65470`
to clocked Chisel before any F extension. This directory is
qualified under the user's focused-verification instruction. Faithful baseline
equivalence, registered integration/ISA evidence, current retirement comparisons
and whole-top timing pass. The final CSR repair is exactly cycle-equivalent to
the ISA-qualified registered top. The repeated full CI run was stopped at the
user's direction; see the task report for the explicit evidence and limits.

The user approved preserving inherited combinational boundaries for this
equivalence baseline. Each translated module retains its original ports,
cycle behavior and reset. This exception does not waive timing budgets,
authorize retiming, or extend to new SoC boundaries. The approved supporting
scope includes candidate isolation, gated-clock timing, a separately identified
reference benchmark and core entries in the timing ledger. Reference RTL
remains forbidden in production.

The user subsequently approved equivalent combinational repairs for measured
T11 timing failures after retaining each faithful baseline proof. Named state,
ports, resets, cycle behavior, limits and verification obligations stay fixed.

## Initial leaves

`IbexCsr` preserves the write-enabled register and optional inverted shadow.
`clk_i` is rising-edge; active-low `rst_ni` asynchronously restores
`ResetValue` (the shadow restores its complement). `rd_data_o` is the register
value. The optional combinational `rd_error_o` compares the shadow; without
a shadow it is constant zero. Width, reset value and shadow mode are Scala
constructor parameters.

`IbexCounter` preserves the asynchronous zero reset, write priority (high-half
write before low-half write before increment), and truncated counter width.
`counter_val_o` is the zero-extended register value; `counter_val_upd_o` is
the inherited combinational increment when enabled by `ProvideValUpd`, otherwise
zero. Counter width and update-output mode are constructor parameters.

Both leaves use the main domain; no new clock or crossing is introduced.
They have no memory-mapped interface of their own. Under qualified buffered/sized
mapping, the approved same-state counter repair passes GF180 timing: measured
21.831022 ns for mcycle and 19.555578 ns for minstret, against the assumed
24.96 ns budget. It retains independent local increment slices and, where the
raw increment is exposed, preserved parallel-prefix carry stages. `keep` attributes
apply only to combinational wires; no state, latency or timing constraint changes.
Exact commands, corner, areas, failed attempts and independent review are in
the [T11 report](../../../docs/plan/tasks/reports/T11.md). No whole-core area
estimate is claimed from these leaves.

Formal obligations and evidence are described in [formal/README.md](formal/README.md).

## ALU baseline

`IbexAlu(RV32B = 0)` translates the pinned no-bitmanip configuration, including
the observable behavior of otherwise unused operator encodings. It preserves
the 33-bit operand/34-bit sum multdiv interface and comparison flags. It is an inherited combinational leaf,
covered by the approved boundary exception. Its two-word intermediate ports
are flattened to 64-bit vectors; in this configuration the input is unused and
the outputs are zero. Other RV32B configurations are rejected at elaboration.
The ALU passes exhaustive combinational equivalence and output-fault rejection.
The faithful baseline measured 62.401089 ns under the original area-only mapper.
The authorized repair uses parallel short-slice sums, zero-sum checks and
shifts. It passes equivalence and independent integer-model simulation. With
qualified combinational buffering/sizing, measured timing is 23.850603 ns
against the unchanged assumed 24.96 ns limit, with zero reported electrical
violations. Final STA constraints are unchanged; the mapping recipe and its
driver heuristic are recorded separately. Historical failed measurements are
retained. This is pre-layout evidence, not full-core timing signoff.

## Flop register-file baseline

`IbexRegisterFile` preserves the pinned non-secure, full-register configuration:
asynchronous active-low reset to `WordZeroVal`, rising-edge writes, two
combinational read ports, and hard-wired register zero. The optional dummy
register-zero behavior is retained as a constructor parameter. Security-check
and RV32E alternatives are rejected at elaboration. No memory macro replaces
the flops. Inherited read outputs are covered by the approved combinational
boundary exception. Formal state correspondence explicitly names each word.
The default configuration passes named-state induction with output/reset/next-state
negative controls and an independent array-model simulation covering both reads,
x0, edge-only writes, hold and asynchronous reset.

## Compressed decoder

`IbexCompressedDecoder` preserves all compressed expansion and illegal-encoding
outputs, including pass-through bits on unsupported encodings. Its clock, reset
and valid pins are retained; as in the reference synthesis view they do not
gate the combinational outputs. It introduces no state or latency.

## Fetch path

`IbexDecoder` retains the pinned RV32IMC/no-bitmanip/no-branch-target-ALU
configuration and rejects unsupported constructor settings. It preserves
illegal-encoding outputs and the independence of its two instruction inputs.
Exhaustive combinational equivalence covers every input combination; tests
independently encode ordinary and M instructions, immediates and compressed
error containment, with a corrupted-result negative control.

`IbexLoadStoreUnit` retains the non-ECC 32-bit bus, ten state elements,
alignment/byte lanes, split transfers, grant/response handling, PMP/bus errors
and failing-address retention. Named-state induction checks arbitrary inputs
and illegal FSM values, with output/reset/next-state faults. Its independent
byte-memory simulation covers aligned/split loads and stores, sign extension,
delayed grants/replies and first/second bus errors. PMP errors, midtransaction
reset, simultaneous second grant/first reply and performance outputs are covered
by equivalence rather than explicit simulation scenarios. Both new modules
passed fresh independent review; commands and measurements are in the report.

`IbexFetchFifo` retains packed validity, per-word data/error registers and the
halfword instruction address. With `ResetAll=false`, the address/data/error
flops deliberately have no reset, while validity resets asynchronously. It
preserves bypass, compressed/unaligned instruction assembly, clear, backpressure
and error-plus-two behavior. The approved address increment repair uses local
parallel slices without changing state.

`IbexPrefetchBuffer` retains two outstanding-request/discard bits, request hold,
branch flush and both fetch/stored addresses. It instantiates the converted
FIFO. Its approved increment repair computes the advance before request
selection. Both modules pass named-state equivalence and timing; the prefetch
proof explicitly replaces the reference child with the emitted Chisel child.

## Multiply/divide

`IbexIfStage` instantiates the translated prefetch buffer/FIFO and compressed
decoder, preserving the pinned non-cache, non-predicting fetch interface and
unreset payload flops. Its proof matches 24 state elements, including child
state; flattened inactive cache-array ports are tieoffs. Byte-program simulation
checks mixed compressed/word alignment, backpressure and boot, jump, exception,
debug, MRET and DRET targets. Bus/PMP errors and arbitrary live redirects are
covered by equivalence rather than separate simulation scenarios.

`IbexController` preserves the pinned no-writeback-stage FSM, interrupt/debug
priorities, exception reporting, WFI and wake behavior. Packed IRQ fields are
software/timer/external/fast from high to low; packed cause fields are internal
interrupt/external interrupt/five-bit cause. Ten state elements match under
unbounded induction without environmental assumptions. Focused tests exercise
boot, interrupts while stalled, debug priority, DRET, sleep/wake and exceptions.

`IbexWbStage` implements the selected combinational bypass, including the
masked OR when both write enables are asserted, retirement/error qualification
and all inactive-stage tieoffs. Exhaustive equivalence and independent stimulus
testing cover this boundary. These three blocks passed fresh agent reviews;
they do not establish whole-core acceptance.

`IbexCsRegisters` is translated for one debug trigger, zero optional
performance counters, and disabled PMP/cache/security options. It reuses the
translated CSR/counter leaves on `clk_i` with active-low asynchronous reset;
retains machine/user privilege, trap/NMI stack, debug state, interrupt enables,
cycle/retirement counters and the reference CSR access rules. Parent proof,
tests and timing pass with independent review. Its explicitly approved analysis
copy preserves procedural priority for conflicting selectors; see
[CSR-PRIORITY-INVESTIGATION.md](CSR-PRIORITY-INVESTIGATION.md). Inactive PMP array
ports are flattened tieoffs. The approved faithful baseline retains the
reference combinational read/write paths.

`IbexMultdivFast(RV32M=2)` retains the multicycle multiplier and iterative
divider states, enables, intermediate registers' external interface and
backpressure behavior. Structural equivalence preserves the signed 17-by-17
product and rejects a sign-extension fault. Independent integer-model simulation
covers multiply high/low, signed/unsigned division/remainder, zero, overflow,
enable stalls and result backpressure. Intermediate word zero occupies the
high flattened word, matching the reference's ascending unpacked array.

The faithful baseline timing fails. It measured 52.541870 ns;
the discarded parallel MAC trial measured 55.642658 ns. Both exceed the unchanged
24.96 ns limit despite zero electrical violations. The subsequent explicit user approval permits the iterative replacement described
in [ITERATIVE-MULTIPLIER.md](ITERATIVE-MULTIPLIER.md). It captures operands and
uses 32 one-bit multiply rounds plus two signed corrections. Functional proofs and independent review pass. Under the final alias-aware
flow, standalone timing passes but integrated-multdiv timing fails at
25.093014 ns against 24.96 ns; see the task report for measured receipts.
The faithful default remains available for structural equivalence.


## Execution stage

`IbexCore` is the faithful, unretimed two-stage RV32IMC core baseline, with all
active children translated to Chisel, debug trigger enabled and RVFI available
through the `WithRVFI` constructor setting. The latter is enabled for every
comparison; it is disabled for physical measurement and the bound
production-control formal monitor. The
complete baseline passes named-state induction against the approved analysis
model, fault controls and independent review. `CoreSpec` checks retirement
against a small architectural interpreter with delayed byte-memory interfaces,
including signed/unsigned M operations, zero divisors, misaligned accesses,
branching, CSR reads/writes and an EBREAK trap. A corrupted-retirement control
must fail. This finite directed test does not establish comprehensive interrupt,
debug, compressed-instruction or bus-error coverage.

Core proof: `formal/check_core.py`; emitter: `deadhorse.perf_core.EmitCore`.
The top wrapper and authenticated candidate manifest now exist. The approved
shared clock gate has separate ASIC-cell and verification bindings; see
[clock-gate contract](../../lib/CLOCK-GATE.md). Baseline whole-top induction,
all active module checks and architectural/flight retirement comparisons pass.
Registered integration and ISA evidence carry forward through the exact
whole-top revision proof for the final CSR repair; current retirement checks
pass separately. Baseline cycle equivalence alone does not establish the
registered profile's correctness.

`IbexIdStage` implements the faithful pinned two-stage ID boundary,
with the translated decoder and controller, same-cycle operand/control outputs,
two asynchronous-reset intermediate words and the reference multicycle/branch
tracking state. Writeback forwarding, branch predictor, separate branch-target
ALU and security options are disabled. No additional clock or CDC is introduced.
Behavioral tests and mapped timing pass. The original baseline proof fails on
conflicting instruction copies; a single-qualifier source-priority analysis
normalization is approved and passes independent review and the mandatory
configured proof gate. See
[ID-PRIORITY-INVESTIGATION.md](ID-PRIORITY-INVESTIGATION.md).
The later approved registered execution integration must retain this baseline
and separately verify changed completion timing and instruction retirement.

`IbexExBlock` retains the pinned RV32MFast/RV32BNone/BranchTargetALU=false
interface. The faithful parent is proved with both children replaced by Chisel.
The approved same-cycle repair optionally computes fixed divider arithmetic
before state selection and removes ALU result dependencies that the parent's
mult/div result mux makes unobservable. Original ALU data is retained when
neither mult/div select is asserted; no enable-implies-select assumption is
introduced. These child variants are proved at the EX boundary, not claimed
equivalent as isolated arbitrary-input leaves. ALU comparison and adder outputs
remain fully observable and unchanged. No extra divider state or cycles are added.
This unregistered parent remains a comparison and diagnostic target. The
registered replacement passes its separate whole-top timing check; leaf passes
alone do not establish whole-core timing.

All implemented production-profile block timings are gated by `check_timing.py`;
faithful failed multiply timing remains recorded as baseline evidence, while the
explicitly approved iterative implementation is the production-profile target.
The subsequent registered-execution approval supersedes the integrated
unregistered multdiv/EX timing target. `ClockedExecute` captures one operation,
registers ALU and multiply results, and divides each divider transition into
issue/compute/advance phases. See [EXECUTION-TIMING.md](EXECUTION-TIMING.md) for
its interface, latency, formal composition and retained diagnostic profile.
The local gate runs the block and whole-core checks as well as all original
reference and reference-copy comparison-harness checks. `EmitTop` retains the
faithful baseline; `EmitRegisteredCore` emits the registered comparison model
and the ASIC `DeadhorsePerfCore` hierarchy. The latter includes the register
file and actual clock gate and is measured by `check_top_timing.py`.
The registered profile has its own bounded integration checks, abstracted ISA
classification and architectural/flight retirement comparisons. The baseline
cycle-equivalence proof is not substituted for those obligations. Consult
the task report and sole status tracker for current acceptance completion.
