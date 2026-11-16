# F integration contract (T13)

Status: blocked on critical load/compressed-add checks and the focused local gate. `t11-baseline` identifies the completed
pre-F core. Default elaboration remains that baseline; `WithF=true` selects
RV32IMFC on the registered execution profile. No double precision or optional
performance optimization is part of this first change set.

The main-domain core uses the T12 FPU with an approved, latency-preserving exponent-subtractor repair. One instruction is outstanding.
Instruction selection, floating metadata, operands and merged completion-valid
are staged before commit. CSR legality receives an additional request-settling
cycle. ID remains stalled until
the result can commit; the destination, accrued exception flags and FS dirty
state commit together. An interrupt, NMI or debug request during arithmetic
waits for that instruction to finish, then enters at the next instruction.
Reset or actual instruction squash cancels the transaction with no commit.
Control uses the existing asynchronous-assert reset and main gated clock;
there is no new clock or crossing.

All 32 floating registers are writable, including f0. Their initial payload is
unspecified while reset sets FS Off. FLW/FSW share integer address calculation
and the existing LSU, including memory faults and split access handling. FLW
never writes the integer register file. Loads and moves preserve every raw bit.
C.FLW, C.FSW, C.FLWSP and C.FSWSP expand in the fetch decoder; C.FLWSP f0 is legal.

CSRs fflags (0x001), frm (0x002), and fcsr (0x003) alias one eight-bit state.
Reserved upper bits read zero. CSR read-only forms do not write or dirty state.
FS is mstatus[14:13], reset Off; SD is derived from FS Dirty. Floating-register
writes, explicit floating CSR writes and nonzero accrued flags mark FS Dirty
only on commit. Stores, classification and moves to integer registers need not
dirty state. Trap/return processing preserves FS. misa advertises F.

Every F instruction and floating CSR access traps when FS is Off. Instructions
that carry rounding mode resolve rm=7 through frm and reject resolved modes
5/6/7; writing a reserved frm value itself remains legal. Instructions whose
funct3 is an operation selector do not interpret it as a rounding mode.

RVFI retains original instruction encoding, including compressed instructions.
Integer operands/destinations describe actual X-register effects. Separate FP
source/destination enables, addresses and raw values describe F-register effects;
f0 is never normalized away. Floating CSR and FS observations accompany retirement.

Unchanged modules retain equivalence obligations. With F enabled, the no-F,
FS-Off projection is an intended architectural refinement. Local compressed-decoder,
CSR and IF conditional proofs pass independent review. The IF proof explicitly
excludes the four compressed F encodings even on invalid, stalled or error
payloads; its active-transfer witness establishes one-step nonvacuity, not
reset-reachable execution. Core/ID exact cycle equivalence is inapplicable after
the approved latency changes. misa.F, execution latency, cycle-counter observations
and wall-clock interrupt timing differ; whole-core cycle equivalence is not claimed.
F correctness uses the pinned simulator, T12 arithmetic evidence and integration
properties with fault controls. Focused checks preserve assertions and timing
limits without repeating unrelated hours-long ISA sweeps.

Current integrated timing passes at 24.698816 ns against the unchanged 24.96 ns
budget, measured by `check_top_timing.py --emitted build/t13/exponent/emit/asic
--output build/t13/timing-exponent` on base `11c72b3` plus recorded working-tree
hashes. This is mapped, pre-layout timing. The approved prefix-adder exponent
subtraction preserves registers and cycle behavior; whole-top revision equivalence
and arithmetic fault controls pass.

All 33 original JALR assertions are accounted for through qualified assertion
partitions and exact reset/transition/implication composition. The aggregate
`build/t13/jalr-original-complete/result.json` includes original concrete execution
coverage and a detected actual RVFI PC-output fault. Independent review clears
that complete JALR result. Historical full-model timeouts remain recorded and
are not retroactively relabeled passing.

The original formal FPU model coupled invalid response payload and next completion
payload. The replacement `FpuProtocolModelWide` supplies them independently;
exact concrete all-port trace inclusion is independently proved. The same 28
integration safety assertions pass with this wider model, together with eight
abstract-model covers and a freshly checked 271-state binding to production.
The abstraction proves neither arithmetic nor finite completion latency, and its
covers are not concrete execution coverage. T12 arithmetic and concrete lockstep
provide separate evidence. No production RTL defect was inferred from the old
formal-model gap.

The remaining critical LW and C.ADD attempts reach the unchanged 120-second
cap without counterexamples. A subsequent exact two-group LW split closes
11 control/register assertions at full depth, while the 22 memory/trap assertions
still time out. Partial progress is not instruction acceptance. The focused
local gate also remains open. Overall T13 acceptance is incomplete; see the task
report and formal ledger for exact commands, authenticated receipts and scope.

Normative references: [F extension](https://docs.riscv.org/reference/isa/unpriv/f-st-ext.html)
and [machine-level status](https://docs.riscv.org/reference/isa/priv/machine.html).
