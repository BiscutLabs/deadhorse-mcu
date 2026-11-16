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


### Focused assertion partitions

`riscv_formal.py --checks jalr --split-assertions --prove-window --timeout 120`
keeps the original startup-window model and checks each original assertion in a
separate job. Other assertions are removed only from that job, never assumed.
The exact assertion union, unchanged model content, hashes and short timeout are
validated; jobs stop at the first unresolved result. The existing instruction
cover and injected RTL fault must still pass before instruction acceptance.
PDR here proves only the configured startup-window checker, not unbounded ISA
correctness. Explicitly omitted instructions remain unverified by that run.

Yosys's generated setundef cell names are renamed reversibly before JSON reload
to avoid automatic-ID collisions. No cell connections, values, parameters,
assumptions, clock stimulus or properties change. Both snapshots and the mapping
are recorded under the requested build output.

### Targeted JALR address invariant

Run the proof jobs and their required companion audit together:

```sh
python3 dv/core/riscv_formal.py --target candidate --candidate build/t13/exponent/candidate --checks jalr --jalr-address-invariant --timeout 120 --output build/t13/jalr-address-strengthened
python3 dv/core/audit_jalr_invariant.py --output build/t13/jalr-address-strengthened
```

The Chisel predicate checks reported rs1 against instruction bits 19:15 for every
nonreset, valid JALR retirement with nonzero encoded rs1. There is no condition on
reported trap. Free-input SAT proves exact activation/violation correspondence
to the pinned checker, including the enable of its instruction-selection assumption.
The audit must reject a wrong-opcode monitor and find active cover/fault traces;
a raw proof-job receipt alone is not acceptance evidence.

The independent lemma removes only the checker's forced-JALR assumption and its
other properties. Production cells and original reset/clock assumptions remain
identical. A separate job checks the original address assertion with every original
assumption retained and the lemma present as an assertion, never an assumption.
This proves one obligation; it does not grant aggregate JALR or ISA acceptance.

`check_jalr_strengthened.py --lemma build/t13/jalr-address-strengthened --output
build/t13/jalr-complete-strengthened` authenticates that evidence and runs the
complete original JALR assertion inventory with the helper retained. The original
covers and a real reported-destination-bit fault remain required. Jobs stop at
the first unresolved result, retaining the short timeout and original depth.

### Targeted JALR return-value invariant

```sh
python3 dv/core/check_jalr_link.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-link-v2
```

This focused continuation authenticates the frozen original checker and checks
all valid, nonreset, 32-bit JALR retirements. The encoded destination selects
zero for x0 or the retired PC plus four modulo 2^32. There is no reported-trap
or nonzero-rs1 condition. Free-input SAT compares both the exact original
activation and violation predicates, including the removed instruction-selection
assumption's enable. Changing the monitor's increment to eight must be rejected.

The independent proof retains the original reset/clock environment and removes
only checker properties and forced instruction selection. On success the runner
requires separate active x0/nonzero-destination covers and a nonzero-destination
fault witness from an actual reported-output bit mutation. It then checks the
original destination-value assertion with the helper retained as an assertion
and every original assumption unchanged. The run stops on the first unresolved
job; no stage is optional and no aggregate ISA pass is granted.

### Target-PC proof and immutable audit receipts

```sh
python3 dv/core/check_jalr_target.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-target
```

The predicate compares reported next PC with the normalized source plus a signed
12-bit offset, wrapping to RV32 and clearing bit0. Normalization follows the full
checker: encoded rs1=x0 substitutes zero before the instruction model. Exact
free-input guard/violation qualification and a zero-extension fault precede the
sequential proof. Required covers exercise x0, an odd sum and a negative offset;
the real output fault changes PC bit1 for a nonzero encoded source. No trap guard,
new assumption or changed cap is introduced. Fail-fast leaves later roles unrun
if an earlier role is unresolved.

JALR consumers now use `jalr_receipts.snapshot_baseline_audit` to authenticate
and copy existing audit evidence without rewriting the shared baseline. Historical
receipts affected by the old shared-audit overwrite retain their original bytes;
`input-relocations.json` records exact original hashes and immutable snapshots.
Use the recorded snapshot when rechecking a relocated input. A missing exact
hash match is a provenance failure; never update the expected hash to accept it.
The task report records executed-source snapshots for metadata-only runner edits;
these do not imply rerunning historical sequential proofs.

### JALR redirect transport

```sh
python3 dv/core/check_jalr_transport.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-transport-v2
python3 dv/core/audit_jalr_transport.py --output build/t13/jalr-transport-v2
```

Observation-only ghost state captures the masked first-phase redirect target and
original instruction/PC. At retirement, capture existence/identity and next-PC
transport are assertions. Pre-edge capture data feeds the next RVFI observation
stage, whose validity is overwritten each cycle. No trap or capture-valid guard
hides an obligation. Clock/reset are bound to the actual production RVFI state.
The companion audit requires exact source/witness hashes and rejects a wrong
retirement opcode through independent SAT qualification. A real reported-PC
bit1 fault and active retirement cover are mandatory. This proof does not
establish the rs1-plus-immediate arithmetic correspondence or aggregate ISA.


### JALR capture arithmetic and source correspondence

```sh
python3 dv/core/check_jalr_capture.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-capture
python3 dv/core/audit_jalr_capture.py --output build/t13/jalr-capture
```

Source correspondence and capture arithmetic are independent jobs. Source jobs
jointly require inherited transport, encoded-x0 normalization, staged source
validity, x0 and rs1=rd covers and an actual reported-source bit fault. Arithmetic
compares the captured execute target with the normalized source plus the signed
immediate, wrapping to32 bits and clearing bit0. Negative-offset/odd-sum covers
and an actual execute-target bit fault are required after that proof. All original
environment assumptions and short limits remain; failure stops later jobs.
The companion auditor checks completed source jobs only, including exact input
and trace hashes and a wrong-opcode guard negative. Its source-only PASS cannot
change an arithmetic timeout or unresolved aggregate status.

`--resume-from` supports the recorded witness-parser repair: the prior runner
must be archived as `check_jalr_capture.executed.py` with its exact recorded hash.
All prior protected inputs must authenticate, regenerated models must be byte
identical, configurations may differ only by model path, and actual status files
and witnesses must revalidate. Never edit a raw receipt or its expected hashes
to enable reuse. The T13 report identifies the executed outputs and unresolved
arithmetic result; these components do not constitute complete ISA acceptance.


`check_jalr_request.py --baseline build/t13/jalr-address-strengthened --output
build/t13/jalr-request` further separates saved-request alignment from local ADD
response arithmetic. Both observe the exact production model with unchanged
reset/clock assumptions. Alignment asserts response validity, ALU kind, ADD,
first-cycle and both operand values under the existing capture guard; the ADD
predicate independently uses saved operands for every valid ALU/ADD response.
No alignment precondition is assumed. The recorded alignment attempt times out;
fail-fast leaves all later covers/faults and local ADD roles unrun. Code/model
review does not constitute proof acceptance or remove the original checker.


### Exact saved-request alignment partitions

```sh
python3 dv/core/split_jalr_alignment.py --baseline build/t13/jalr-request --output build/t13/jalr-alignment-split
```

This diagnostic authenticates the existing alignment proof model and extracts
its six original conjuncts: response-valid, ALU kind, ADD operation, first-cycle,
source-operand equality and signed-immediate equality. It validates their actual
net bindings and widths, and preserves the original capture guard and assertion
enable. It adds only Boolean guard gates and replaces the single assertion with
six named assertions. All production/environment cells and model interfaces
remain unchanged. Each job retains one assertion; no peer becomes an assumption.

Free-Boolean SAT proves the conjunction exactly equivalent to the old predicate;
an omitted-immediate-conjunct negative must fail. Unit tests independently
exhaust the Boolean cases and reject missing inventory, guard, operand and width
changes. All six conditions remain required, with the original short limits and
fail-fast behavior. A positive subset is diagnostic evidence only. Original
active covers, actual design faults, local ADD and full ISA acceptance remain
required; this command does not grant their acceptance.


### Accepted-request ownership monitor

`JalrOwnershipProperty` observes the actual execute ready/valid handshakes on the
same gated clock and asynchronous reset as production state. A reset-cleared
valid bit and tag record every accepted instruction, PC, phase and incoming kind.
Consumption clears validity; acceptance has priority, and simultaneous acceptance
and consumption is asserted impossible. Capture checks pre-edge ownership even
when the response is consumed that cycle. No ID-clear/new-instruction signal
suppresses or cancels a producer ownership check. Classification, retention,
retained JALR kind and capture identity are separate obligations; original
arithmetic and ISA checks remain outstanding. These are observation-only formal
registers with combinational predicates, not production RTL or timing changes.
The runner `check_jalr_ownership.py` retains the original environment and short
caps, requires active covers and actual input-kind/saved-kind/PC faults, and
stops at the first unresolved role. It does not assume any of the relations.


```sh
python3 dv/core/check_jalr_ownership.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-ownership
python3 dv/core/audit_jalr_ownership.py --output build/t13/jalr-ownership
```

The companion audit qualifies completed issue/retention/retained-kind components
only, retaining any unresolved identity status. Its additional real incoming-kind
fault must be witnessed after acceptance in retained state, independently of the
issue assertion. A wrong-opcode external activation fault is also required.
The replacement cover permits a prior different execution phase, including a
JALR link phase; do not describe it as necessarily a non-JALR instruction.
For the documented parser repair, `--resume-from` requires the prior exact runner
archive `check_jalr_ownership.executed.py`, authenticated inputs, byte-identical
models and configurations differing only by model path, plus actual statuses
and re-parsed witnesses. No original receipt or expected hash is rewritten.


### Ownership flags versus instruction/PC identity

```sh
python3 dv/core/split_jalr_ownership.py --baseline build/t13/jalr-ownership-resumed --output build/t13/jalr-ownership-split
```

This exact diagnostic splits the existing capture predicate into owner-valid,
owner-JALR, owner-first, instruction equality and PC equality. All five remain
mandatory; every job retains the original capture guard and environment, with
no peer assumptions. Free-Boolean SAT checks the complete conjunction and an
omitted-PC negative must fail. The original producer/monitor cells and state
remain byte-identical; only the assertion and added Boolean guard gates differ.
Passing flags alone do not establish full identity, operand or ISA acceptance.
Any later kind-composition argument must authenticate shared state/bindings and
proved prerequisites, including capture's reset guard; none is assumed in the
production checker. Active covers and real faults remain required.


### Outstanding execute phase stability

`PhaseStabilityProperty` observes the exact combinational IF instruction write
pulse and ID clear, plus clocked one-edge instruction/PC/phase history. Holding
means a newly accepted or already owned integer request with no actual consume,
outside reset. Separate assertions prohibit IF replacement and ID clear while
holding, and require instruction, PC, valid, first-phase, compressed and dummy
tags to remain equal across a holding edge. Reset clears history validity;
consumption allows normal phase advance. No event or stability relation is
assumed, and ID clear does not silently cancel producer ownership. Observation
registers use the production clock/reset and are formal-only; combinational
predicates do not change production timing. Active covers and actual production
write/clear/phase faults are required before scoped acceptance.


```sh
python3 dv/core/check_phase_stability.py --baseline build/t13/jalr-address-strengthened --output build/t13/phase-stability
python3 dv/core/audit_phase_stability.py --output build/t13/phase-stability
python3 dv/core/strengthen_jalr_ownership.py --phase build/t13/phase-stability --owner build/t13/jalr-ownership-resumed --output build/t13/jalr-ownership-strengthened
```

The strengthening runner authenticates phase proof/audit inputs and projects the
inherited monitor to the original ownership interface. Named-state induction
checks reset, clock, transition and output semantics; a tag-output fault must be
rejected. It then adds only assertions for no-write, no-clear and owner-JALR to
the existing step-check model. No proven helper becomes an assumption. A positive
job still requires active target cover/fault qualification and full composition;
the recorded attempt remains a timeout, not an accepted ownership result.


### Exact ownership composition

`compose_jalr_ownership.py --output build/t13/ownership-composition-confirmed`
uses the authenticated emitted phase monitor, its exact asynchronous reset
values and next-state D pins. Three SAT implications establish the reset base,
preserve full owner identity across a transition, and derive the original
capture ownership predicate. Explicit antecedents refer to independently proved
phase stability, retention and capture-valid guarantees. All premises must be
qualified and their hashes/statuses verified; no assumptions enter production.
Each implication has a deliberate mutation negative. The composition concerns
control ownership only; arithmetic and ISA acceptance remain separate.

`qualify_owner_valid.py --split build/t13/jalr-ownership-split --owner
build/t13/jalr-ownership-resumed --output build/t13/owner-valid-qualified`
adds an active capture witness, a labeled ghost-state sensitivity fault and an
actual production IF-PC fault against the full ownership predicate. Ghost
mutation rejection is not presented as a production fault or standalone proof.


### T13 acceptance composition and focused gate

The final JALR aggregate is `aggregate_jalr_inventory.py`: it requires the exact
original assertion inventory, qualified component proofs, concrete execution
coverage and an actual RVFI fault. Ownership, source stability and arithmetic
components alone are not instruction acceptance. Failed earlier global attempts
remain diagnostic records rather than being relabeled passing.

`qualify_fpu_protocol_wide.py` establishes concrete all-port trace inclusion for
independent invalid and completion payload choices. `check_float_integration_wide.py`
rechecks the original safety assertions on that model;
`bind_float_integration.py` separately authenticates the concrete production
binding. Abstract-model covers are distinguished from concrete ISA coverage.

`check_critical_isa_wide.py` keeps the original bounded LW/C.ADD checks and uses
the qualified abstraction only for safety. Concrete retirement covers and an
actual RVFI-output fault remain mandatory. `check_critical_isa_checkall.py`
changes only the pinned solver's query grouping: native `--checkall` checks the
OR of all bad predicates, with unchanged model, assumptions, depth and timeout.
It authenticates the prior model, pinned help and actual executed command.
`check_critical_isa_two_part.py` makes exactly two complementary assertion
partitions without changing other model objects or assuming peer assertions.
Both groups, concrete coverage and the actual fault must pass before instruction
acceptance; it never fabricates a full-model solver PASS from partial progress.
A timeout from any runner is unresolved.

Run the focused gate through `python3 tools/ci.py --scope t13`; default full CI
is unchanged. The focused gate requires the authenticated prior evidence tree,
current emission identity and fresh tests. It is not a clean full-repository
CI run, and refuses missing, changed or unresolved prerequisites. Keep sources
stable throughout a gate run. The task report identifies the current accepted
receipts and any remaining obligations.
