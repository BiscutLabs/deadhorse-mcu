# FPU formal contracts

`FpuFormal.scala` extends the actual production class. Before abstraction,
the checker removes only monitors and proves exact named-state equivalence to
the separately emitted production FPU. Missing properties, cutpoints, witnesses,
or expected fault failures fail the check.

The unbounded ABC PDR proof checks request capture, one outstanding transaction,
registered ready/busy/valid consistency, held response stability, cancellation
including divider abort, per-operation completion bounds, and stable inputs and
capture timing for FMA postprocessing and final rounding. There is no assumption of response-ready,
stable unaccepted request fields, legal opcodes, or legal rounding encodings.

One environmental assumption: reset is asserted in the initial formal cycle.
Reset is unrestricted thereafter. The clock is the model checker's synchronous
step; analog reset recovery/removal and metastability are outside this proof.

Arithmetic is **abstracted**, using fresh unconstrained values at selected
combinational arithmetic nets. Sequential outputs/aliases, state machines,
counter updates, register enables, valid/ready and cancellation remain intact.
The exact cutpoints, retained aliases and source hashes are recorded under
`build/t12/formal/*/abstraction.json`. This proves the control contracts even
with arbitrary arithmetic results; it does not prove floating-point arithmetic.

Operation/held-response covers use one concrete request with legal rounding,
fixed operands and a held response, searched at the terminal frame. Protocol
covers use special-case division over 14 frames, with valid/ready/cancel left
unconstrained. This window includes response presentation, a held cycle and
consumption after the staged divider; it is not an operation deadline.
A separate cover group exercises normal DIV and SQRT with fixed 1.0/2.0
operands and a held response through a 64-frame witness window.
These stimulus restrictions apply only to witness search, never the safety
proof. Every cover is required. Negative controls introduce a response after
cancel, change a held result, and prevent the multiplier counter from advancing.
The stalled-counter fault uses a concrete request to find its counterexample.

`FpuAddFormal.scala` separately proves exact modular addition at all five used
widths against ordinary addition, with a dropped carry-in fault at each width.
`dv/fpu/arithmetic.py` proves the serial-multiply integer recurrence and rejects
a faulty recurrence at every step. Base case: P0=B. Inductive invariant:
Pk=floor(B/2^k)+A*(B mod 2^k)*2^(24-k). Thus P24=A*B. The intermediate addition
requires 49 bits before shifting into 48 bits. The three 17-bit addition chunks
carry into the next chunk; their concatenation is (product+addend) mod 2^49.
The prefix-adder proof validates the changed divider subtraction. Each unsigned
trial operand is at most 27 bits, so its difference lies strictly between
-2^27 and 2^27 and fits the chosen signed 28-bit result without losing a sign
or carry. The next-iteration term is captured alongside the updated remainder
and quotient. The remaining
divider algorithm is pinned HardFloat reuse, reference-tested here rather than
claimed as a new arithmetic proof.
