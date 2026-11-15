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
substitutes the named module in the locked source list, flattens both sides,
and runs an exhaustive combinational SAT miter. Candidate ports and module
name must match. The default is the reference itself. `--self-check` also
corrupts a generated netlist output and requires a real SAT counterexample.
No assumptions are applied. Sequential modules are rejected explicitly:
reset/state mapping and whole-core equivalence remain T11 work, not proofs
inherited from this ALU result. T11's proposed `--all-modules`/`--top` and
directory interfaces are not implemented by this combinational baseline.

## Retirement comparison

`lockstep.py --self-check --output build/t10/lockstep` builds the directed
[program](program.S), runs the original immutable reference and adapted
analysis copy with Verilator, and compares every RVFI retirement against both
the reference and QEMU. `--candidate build/candidate.sv` replaces `ibex_top`
with a compatible candidate; internal candidate modules must avoid duplicate
definitions of upstream modules in the remaining source list. The program
exercises integer arithmetic, M operations and corner cases, loads/stores,
branches/jumps, compressed instructions and `mscratch`. This is a directed
smoke test, not an architectural compliance suite or flight-workload run.

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
