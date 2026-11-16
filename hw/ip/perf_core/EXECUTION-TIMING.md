# Registered execution contract

The approved iterative multiplier is implemented and functionally verified.
Historical pre-registered measurements at base `a532304` plus working changes
are in `build/t11/approved_checkpoint/timing`: standalone multiply 23.659555 ns,
combined multdiv 25.093014 ns and execution stage 25.975801 ns. The last two
fail the unchanged 24.96 ns budget. Equivalent combinational repairs and bounded
mapper trials are recorded in the T11 report; this is not a proof that every
possible same-cycle implementation must fail.

Approved by the user on 2026-11-15: registered execution boundaries and the
necessary pipeline-control changes, including extra ordinary ALU and divide/
remainder cycles. This extends the preceding multiplier-only approval.

Under that approval, execution captures an operation, registers its result
and holds completion until accepted. Division consumes a registered ALU
response before advancing its arithmetic state. Integration must preserve operand
capture, enable stalls, reset cancellation, precise exceptions, interrupt/debug
ordering, register writeback and RVFI retirement. No architectural effect may be
published before its instruction completes. The exact number of new cycles is
an implementation result to measure, not an approved performance waiver.

Changed blocks require transaction/refinement proofs, live completion covers,
negative controls and integer-reference simulation; unaffected blocks retain
exact equivalence. Whole-core comparisons use retirement traces against pinned
Ibex and QEMU. Candidate formal horizons must explicitly cover the new latency;
the existing reference horizons/results remain unchanged. ALTOPS classifications
and the independent arithmetic obligations remain visible. Clock period, corner,
load, electrical checks, area accounting and flight-loop acceptance do not change.


## ClockedExecute interface

Single outstanding request/response in the performance clock domain. Request
fields: kind (0=ALU,1=MUL,2=DIV,3=REM), 32-bit A/B, 7-bit pinned ALU opcode,
two operand signed-mode bits, multiply high/low selection, ALU first-cycle flag
and data-independent timing flag. Request ready depends only on idle state;
requests are sampled on valid/ready edges while reset is released. Inputs may
change after acceptance. Response valid/result hold until ready. A bubble
separates response consumption and next acceptance. No external clock-enable
input is introduced; backpressure is handled at the response boundary.

Ordinary ALU operands are captured at acceptance, then result/adder/comparison
are registered. Division repeats issue (register MD operands), compute (register
ALU sum/equality), advance (step divider and both IMD registers together). The
faithful divider is reused with multiplication disabled. A separate verified
IterativeMultiply handles MUL. All children and control use the same clock and
asynchronous active-low reset; reset cancels the entire transaction. No new CDC.
Response adder/comparison are defined as zero for MUL/DIV/REM.

Derived progress bounds after the acceptance edge: ALU 1 edge; MUL 36 edges
(child capture +34 computation +collection); DIV/REM at most 111 edges (37 gated
divider transitions * 3 phases), including 6 edges for allowed zero-divisor early
completion. These are design-derived bounds to verify, not measured performance.
No register write, exception, interrupt/debug effect or RVFI event is committed
by this block; its parent must order them at response retirement.

## Verification boundary

`formal/ClockedExecuteFormal.scala` asserts capture, operation dispatch,
exactly one outstanding request, stable backpressured response, reset
cancellation, result routing, divider-step refinement and producer deadlines.
The divider reference has independent intermediate registers and an ordinary
combinational sum; it advances only on the implementation's advance phase.
`formal/check_execute.py` adds asserted internal divider-state correspondence
and age/phase/counter invariants to the elaborated JSON. They are proved with
the contract, never assumed. The normal proof permits arbitrary requests,
operands, response readiness and subsequent resets. Only startup reset is
constrained; a formal-only history register is initialized false then set true.

The runner requires an exact property inventory with no hidden assumptions.
It strips verification-only cones and proves the remaining design exactly
equivalent to the supplied production emission, including reset and all named
state. This binding also runs deliberate output/next-state faults. Contract
faults corrupt capture, result, hold, reset, dispatch and registered divider
feedback. Cover witnesses retain all operation completions, held response,
constant-time zero division and nonzero signed DIV/REM. Cover-only stimulus
uses one request, fixed A, B in {0,1} and no subsequent reset to reduce search;
these constraints never apply to the safety/refinement/deadline proof.

This is a protocol and step-refinement proof, not a direct SMT proof of full
integer multiplication or division. Arithmetic composes the separately proved
ALU/divider translations, iterative-multiplier model/lemmas and independent
integer-reference simulation. Whole-core instruction-retirement equivalence,
precise exceptions and interrupt/debug ordering remain integration obligations.

`check_timing.py` defaults to the approved registered production profile.
The earlier unregistered integrated multdiv/EX experiments remain available
with `--profile pre-registered`, retaining the same limits and failing exit
status. Their historical failures are retained; they are superseded designs.
All faithful baseline equivalence checks remain in the local gate.

## Core integration contract (in progress)

The separately selected `RegisteredExecution` configuration preserves the
faithful default for exact comparison. ID issues one execution request per
virtual instruction phase and holds operands until its registered response.
Only that response permits phase advancement, branch/jump redirection, CSR
updates or register writeback. Taken branches use comparison and target phases;
jumps use target and link phases. Loads/stores consume an address response,
then wait for the unchanged LSU protocol. The LSU's split-access increment
remains a separate fixed +4 path and must be included in parent timing.

Illegal/fetch-fault instructions issue no operation. Controller system actions
are delayed until the execution phase is ready; interrupts/debug retain the
controller's instruction-boundary ordering. Reset cancels both ID and execution.
No response may survive its instruction or be consumed twice. All existing
baseline checks remain mandatory. Retimed integration requires its own protocol
properties, reset/exception/debug tests and architectural retirement comparison;
the cycle-identical baseline proof does not establish those results.

Integrated timing exposed an instruction/CSR/controller/fetch control path.
The registered profile now stages CSR request fields, then captures legality
before dispatching execution. These qualification cycles prevent a stale CSR
address or legality result from permitting an instruction effect. Raw system
instruction flags persist through controller FLUSH; only DECODE-to-FLUSH is
qualified by phase completion, so MRET/DRET/WFI survive response consumption.
The faithful configuration is unchanged. Further whole-core timing and proof
qualification remain open; no pass is inferred from standalone block timing.

The registered IF profile also captures the fully selected redirect target and
valid bit before the prefetch increment/queue. Raw or pending redirect blocks
new FIFO-to-ID transfers and FIFO pop; raw redirect suppresses only new fetch
requests, preserving an existing request awaiting grant. The existing prefetch
discard machinery handles old responses when the delayed redirect applies.
Consecutive redirects apply in order. Reset clears pending-valid. Existing ID
valid is still controlled by the original controller clear, so a JAL/JALR
retains its instruction through its link phase. This adds a redirect cycle,
not an ISA change; exact-cycle baseline emission keeps this option disabled.

Three registered controller predicates cache the next-state decode for the
same cycle as the binary FSM. Integration formal asserts their consistency;
they introduce no instruction latency. Counter writes use their own exact
machine-address privilege qualification and own read-modify-write value,
avoiding unrelated CSR address/decode paths. Faithful leaf equivalence remains
mandatory for these combinational repairs.

The integration monitor now includes 21 assertions and 14 covers: the original
control obligations plus redirect valid/target capture, blocked fetch transfers,
and cached-controller consistency. A second real mutation flips target bit 2
after capture, affecting the prefetch consumer; the expected-target assertion
is unchanged. It is checked alongside the early RF-write fault. The contract
remains bounded control verification, not an unbounded whole-ISA proof.

Production whole-top timing uses `check_top_timing.py` on the emitted ASIC
hierarchy, including the register file and actual ICG. The identical numeric
flow benchmarks the locked reference separately through
`dv/core/reference_timing.py`; reference-only receipts cannot serve production
acceptance. Root and gated branches use the established ideal pre-CTS clock
convention, every sequential clock is checked by identity, and ICG enable
setup/hold and RG/IG data paths are included. Physical clock propagation at the
qualified cell load is separately checked; no placement or CTS signoff implied.
