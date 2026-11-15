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

The proposed physical timing ingress hook calls the same guard before mapping;
its explicit scope approval is pending. Timing budgets and checks are unchanged.
T11 reference-only area comparison will need a separately identified benchmark
route; it must not admit reference RTL into a production build.
