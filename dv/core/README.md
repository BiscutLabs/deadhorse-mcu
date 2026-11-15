# Reference comparison tools

Verification only. No core implementation or production primitive is introduced.
Use every command through `python tools/env/run.py run --` (the pinned Linux
container); output paths must be below `build/`.

## Inputs and the compatibility record

The byte-exact Ibex and riscv-formal pins, licences and source list are in
[the reference directory](../../hw/vendor/ibex_ref/README.md). Every top
parameter is explicit in [config.json](config.json). The existing container's
QEMU package is pinned again in [iss.json](iss.json); no new simulator install
is needed. [ADAPTATIONS.md](ADAPTATIONS.md) records the approved removal of
one unused initializer from generated analysis copies, including bug-triage
and reversal instructions. Original vendor sources remain unchanged.

`common.py build/t10/frontends` elaborates with slang and converts with sv2v,
then elaborates the converted result with Verilator. Verilator's diagnostic
warnings remain in logs; this is elaboration, not a claim of warning-free lint.
The native Yosys Verilog parser cannot resolve this reference's RVFI hierarchical
references, so it is not the sv2v elaboration backend. Slang is the formal route.

## Equivalence

`equiv.py --module ibex_alu --candidate build/candidate.sv --output build/equiv`
compares a named module. `--all-modules` enumerates every Ibex RTL module in
the immutable source lock (including inactive implementation alternatives);
`--top` checks the whole pinned core. `--candidate` also accepts a directory.
Without a candidate, both sides elaborate the reference independently.
Standalone modules use their reference defaults; the top uses every parameter
in `config.json`. Receipts distinguish these configurations.

The checker matches named state, including fields within packed vectors,
then proves every next-state, clock, enable, reset/load and output function
equal for arbitrary corresponding state and inputs. State cell kinds,
parameters, reset presence and initialization must match. An unmatched
register is a failure. `module_map.json` records reference-to-candidate wire
names by module; `@cell:<reference cell>` can identify a multiply operator
whose result has no named alias. No exclusion mechanism is implemented.

This is a one-step inductive correspondence, not a bounded startup check.
Matched uninitialized registers represent corresponding arbitrary initial
states: it does not claim two physical chips power up identically. Equal
initialization/reset behavior establishes the base relation; equal transitions
preserve it. Clock-gate/latch behavior is compared digitally, with no analog
glitch or timing claim. Tool failures and unsupported state cells fail closed.

Multiply results become shared symbolic inputs only after retaining proof
obligations for every operand and matching width/signedness. No multiply is
bit-blasted. `--self-check` requires an output fault for every module and
state/reset faults where applicable; the full sweep also requires gained-reset
and fast-multiplier sign-extension faults. Results say `proved` only after
the complete correspondence and SAT obligations pass. These self-checks
qualify the harness, not an unwritten Chisel conversion.

The arbitrary-state relation is deliberately strict. A diagnostic Yosys
Verilog round-trip differed at ID-FSM next state when multiple decode choices
violated an upstream `unique case` premise, despite passing smoke simulation.
Its proof remains failed. Do not add an assumption or ignore that obligation
to accept a candidate. A separate fixed-parameter fixture preserving the
reference body passed the unchanged top proof. T11 must match the reference
function or explicitly establish any stronger invariant needed by a proof.

## Retirement comparison

`lockstep.py --self-check --output build/t10/lockstep` builds the directed
[program](program.S), runs the original immutable reference and adapted
analysis copy with Verilator, and compares every RVFI retirement against both
the reference and QEMU. `--candidate build/candidate.sv` replaces `ibex_top`
with a compatible candidate. Directory candidates supply every locked Ibex
module under `rtl/` or at the directory root, with one file per module.
Missing/ambiguous files fail; there is no silent fallback to reference core
modules. Immutable package definitions and verification primitives remain
shared. Source hashes and the exact initializer adaptation are recorded.

Parameterized candidates receive the pinned SV parameter overrides. Fixed
emissions (including ordinary Chisel output) instead supply `candidate.json`
with `schema: 1`, `kind: "fixed"`, the exact `parameters` object from
`config.json`, and `source_sha256` mapping every locked `rtl/ibex_*.sv` module
except the package to its emitted source hash. Only after checking the complete
hash set and declared configuration does the harness omit candidate `-G` and
BlackBox parameters. Golden-reference overrides are unchanged. The declaration
is provenance, not a correctness assumption: equivalence and instruction checks
must still establish behavior. Mismatched configuration or missing/bad hashes fail.

The program
exercises integer arithmetic, M operations and corner cases, loads/stores,
branches/jumps, compressed instructions and `mscratch`. This is a directed
smoke test, not an architectural compliance suite or flight-workload run.

`lockstep.py --candidate build/t10/reference_copy --suite arch,flight --output
build/t10/lockstep_suites` runs the additional suites. `arch` uses every
RV32UI/RV32UM/RV32UC test from the [pinned source subset](arch/README.md).
Test bodies and scalar macros are unchanged; the local startup/pass/fail
environment uses Ibex's reset vector. Instruction comparison reads the evolving
independent memory image, keeping self-modifying-code and misaligned tests active.

`flight` uses T02's existing QEMU-crosscheck config A ELF unchanged: RV32IM
fixed point, with the existing assumed 40 scenario iterations per mode. The
full historical T02 gate still runs separately. One JAL at `0x80010080` enters
the workload's `0x80000000` entry; its retirement is compared and counted.
Loaded bytes and ELF hashes are recorded. The assumed functional fixture
budget is 50,000,000 cycles for this suite only; the original 50,000-cycle
smoke/architectural/stress deadline and 30-second QEMU timeout are unchanged.
Neither is a measured MCU performance budget.

QEMU's documented T02 MMIO re-entry can log the same load prestate twice.
Flight normalization accepts only identical full register/PC snapshots at a
RAM load immediately after an adjacent decoded T02 marker store, with store
pre/post registers unchanged. Every duplicate is recorded. Other repeats or
changed states remain visible. Ordinary completion-tail validation is unchanged.

`candidate.py --reference-copy build/t10/reference_copy` prepares byte-identical
fixtures. `candidate_check.py --output build/t10/candidate_negative` injects a
real ALU source fault into a build copy and requires a formal assertion
counterexample and a concrete retirement mismatch through both candidate
entrypoints. `--self-check` remains the directed smoke controls; combining it
with other suites is rejected explicitly. Both suites and source-fault controls
are required by the local gate.

The memory responder grants requests and returns data on the next cycle;
reset is asserted across an explicit falling edge before execution. Memory
starts with the binary followed by zeros. IRQ/debug requests and errors are
inactive. The pinned Ibex publishes its first order as one. QEMU's terminal
post-state is retained to check the last retirement. Destination and memory
effects are decoded independently from the instruction and ISS operands;
the complete ISS register state must match each RVFI write. Fault controls
include shared corruption of both hardware traces, so they exercise the ISS
path as well as reference-versus-candidate comparison.

QEMU can log repeated iterations of the final self-jump while its finisher
shuts down. The checker locates the finisher store independently in the ISS
trace, requires its post-state, and validates every remaining row as that
exact self-jump with all registers unchanged. Only those verified inert
iterations are excluded from the retirement count; arbitrary extra rows,
missing post-state and changed registers remain errors.

`mul_diagnose.py --output build/t10/diagnosis/stress` adds a deterministic
edge-case/random diagnostic for all four multiplication instructions. It
compares the original reference, adapted copy and QEMU, then checks each
product against Python arbitrary-precision arithmetic. It is simulation,
not a substitute for the unresolved multiplication formal checks. See
[the investigation](MULTIPLICATION-INVESTIGATION.md) for evidence and limits.

`div_diagnose.py --output build/t10/div_stress` is also required by the gate.
Fixed-seed edge/random pairs exercise DIV, DIVU, REM and REMU, including zero
divisors, signed overflow and truncation toward zero. Original/adapted Ibex,
QEMU and independent integer arithmetic must agree. Corrupt results must fail
the oracle and ISS comparison even when both hardware traces share the fault.
Smaller batches retain the existing deadline for iterative division.

Undefined RVFI data lanes are masked, compressed instructions use their low
halfword, and x0 write data is ignored. Upstream's extra read masks on
non-memory instructions are preserved, not silently zeroed. Standard RVFI
fields are compared; Ibex-specific extensions are outside this baseline.

## Formal contract and limits

D44 adds a verification-only `MultiplyAltop` on the reference core clock,
with asynchronous active-low reset. It captures operands/operation at
`mult_en_internal && sva_mul_fsm_idle` (ALBL) and holds them through the
unchanged fast-multiplier completion/hold logic. Only RV32MFast is supported.
The adapter asserts that live operand/operation inputs remain stable while
the operation is active; it adds no assumptions. The result is an add/sub/XOR
of registered operands, selected using captured operation metadata. Its
combinational output deliberately preserves the reference result timing;
this is verification logic, with no production area/timing claim.
The upstream RVFI properties, covers and negative controls check the adapter
in context. The full-product diagnostic remains separate and unresolved.
Integer lemmas ([equations and limits](MUL-LEMMA.md)) and real-arithmetic stress simulation complement ALTOPS;
the correspondence between those lemmas and RTL is review/simulation,
not a formal proof of the unabstracted arithmetic.

`riscv_formal.py --target reference --output build/t10/rvf` emits only a
Chisel verification adapter around the pinned Ibex BlackBox. Upstream
`rvfi_testbench`, `rvfi_insn_check` and every model in `isa_rv32imc.txt` are
unchanged. Slang reads the core/adapter; Yosys's formal Verilog frontend reads
the upstream checkers, including their `$initstate` use. No handwritten RTL
wrapper or changed upstream assertion is introduced.

Each instruction gets a separate bounded ABC check, BTOR2 retirement covers,
and a result-bit fault check when the selected retirement is reachable. A
passing bounded job without the checked-retirement covers is classified
unsupported at this bound. A tool error/timeout or reference assertion failure
fails the command. The result file records each instruction separately;
it never promotes a bounded result to an unbounded proof.

Candidate invocation is explicit: `riscv_formal.py --target candidate
--candidate build/t10/reference_copy --output build/t10/rvf_candidate`.
It uses the same bounds, checkers, ALTOPS qualification and fault checks.
Losing reference-supported retirement coverage fails candidate mode. Both
reference and candidate runs record measured total wall seconds.

A non-reference multiplier needs hash-bound `formal_adapter.json`: schema 1,
with `multiply_altops.source_sha256` and `multiply_altops.signals`. The latter
maps `mult_en_internal`, `sva_mul_fsm_idle` and `mult_valid` to scalar candidate
nets, validated by unoptimized tool elaboration. The result needs one continuous
driver. Its original RHS is preserved; emitted Chisel selects real division
or abstract multiplication. Exact wiring, reversal and hashes are recorded.
Capture/stability assertions and both fault controls remain active. Metadata
does not prove a conversion: T11 still requires state/operand/control
equivalence. Bad hashes, missing nets or unsupported driver shapes fail.

The four multiply partitions alone define `RISCV_FORMAL_ALTOPS` in the
generated reference and upstream checker. Their status is exactly
`bounded, arithmetic abstracted (ALTOPS)`; non-multiply partitions retain
their previous checker. Each multiply partition requires a nonzero-destination
result fault and an independently corrupted captured-operand fault to fail.
`mul_lemma.py --output build/t10/mul_lemma` proves integer product expansion,
accumulator ranges and universal low/high carry identities, with satisfiable
domains and negative controls. It invokes pinned Z3; it does not prove RTL
equivalence. `mul_diagnose.py` is now also required by local CI.

`riscv_formal.py --target reference --unabstracted-multiply --output
build/t10/raw-diagnostic` retains the original full-product checks, at the
unchanged limit. It is not called by CI. An explicit arithmetic timeout is
`unresolved (arithmetic)`; an assertion failure or tool error remains failed.
The optional shared-function attempt could not preserve its required symbolic
memory through the pinned frontends. No stronger integration result is claimed.

The baseline is **assumed** to use a 40-global-step horizon and select the
retirement at core cycle 12, following upstream's single-check-cycle harness.
This checks that selected retirement after an arbitrary startup instruction
sequence; it does not prove every retirement in the horizon. Long operations
that cannot retire at that cycle are not covered. These limits are explicit
baseline coverage choices, not production latency budgets.

All environment assumptions and fixed inputs:

- Upstream assumes reset equals `$initstate`; its checker is disabled during
  startup reset. The external root clock alternates low/high for the bounded
  horizon. `clk2fflogic` preserves the upstream reference clock gates.
- Test enable is high to hold the top clock gate open. Fetch is enabled,
  boot address is `0x80000000`, hart ID is zero. Interrupts, debug requests,
  bus errors and scrambling inputs are inactive; scan reset is inactive.
- Instruction/data grants follow requests; response-valid is registered one
  cycle later. Data words are symbolic and registered. They are not constrained
  to a consistent memory, so this is instruction semantics, not memory causality.
- The upstream checker assumes the selected instruction model is valid at
  its check cycle. This is instruction partition selection, not an assumption
  about its result. All four upstream cover conditions must be reached before
  reporting that partition as bounded and exercised.
- All addresses are executable/readable/writable under the upstream default
  PMA model. Compressed ISA support is enabled. Memory uses effective addresses
  and low byte lanes; `RISCV_FORMAL_ALIGNED_MEM` is not defined.

CSR semantics, IRQ/debug entry, liveness, memory causality, all operation
latencies and an unbounded ISA proof remain unsupported. No area estimate
applies to this verification-only wrapper; it is excluded from chip sources.
Results and failed-tool diagnostics live under the requested output directory.

DIV, DIVU, REM and REMU are classified `bounded, divisor-zero early-finish path
only at check cycle 12`. Cover-witness inspection confirms `MD_IDLE -> MD_FINISH`
with a zero divisor and data-independent timing disabled. Normal iterative
division is not qualified by those covers. Stress supplies finite arithmetic
evidence; no division ALTOPS split or longer formal bound is introduced.

## Production isolation

`isolation.py` checks production source/configuration inputs, original hashes,
adapted hashes and reference provenance. It rejects the vendor directory,
the verification adapter, T10 output paths, and the reserved comparison tops
`ibex_top`/`rvfi_wrapper` in emitted RTL. A production Chisel top must use its
own name; equivalence adapters can retain the reference comparison name.
CI runs positive/negative isolation controls, including converted and renamed
reference output after frontend emission. This is an accidental-inclusion
guard, not a security boundary against deliberately rewritten reference code.

The physical timing ingress hook calls the same guard before mapping;
its scope is approved by the revised T10 brief. Isolation self-tests exercise
the real timing entrypoint and copied emitted ALTOPS helpers as well as the
vendor inputs. Timing budgets and checks are unchanged.
T11 reference-only area comparison will need a separately identified benchmark
route; it must not admit reference RTL into a production build.
