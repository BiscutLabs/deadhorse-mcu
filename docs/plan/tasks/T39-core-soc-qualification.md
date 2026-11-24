# T39 Production-core and integrated-SoC qualification

## Goal, inputs and readiness

Establish fresh, reproducible simulation and architectural-test evidence for
both production cores, separately and inside the single `DeadhorseSoc`, before
T38 physical integration. Work on main. D88 authorizes this brief and plan
placement; implementation starts only when assigned. All acceptance below is
**unverified**. A passing campaign is scoped functional qualification, not a
proof of all executions, official certification or tape-out signoff.

Use the implemented T13 performance core/FPU, T25 lite core and T20/T32–T34
production integration. Their open proof obligations are inputs to this task,
not circular prerequisites that must first be proved. Do not reopen core
selection, substitute the reference Ibex into production, or create feature
profiles. T35 SRAM macros and T36 production ROM are not prerequisites for
this campaign: test the current memory models and documented loader/start
path, clearly naming them. Those tasks must replay the affected T39 campaign
when they replace memory or boot behavior. T37 must retain functional-mode
equivalence and replay affected tests; T38 consumes fresh evidence after these
changes, not an obsolete T39 pass.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 07, 10–16; docs/spec/soc.md and bus.md;
T10–T13, T20, T25, T32–T34 reports and their formal ledgers; T13-nonformal report;
docs/spec/soc-verification-debt.md; dv/core/README.md, dv/core/ADAPTATIONS.md,
dv/core/arch/README.md and lock.json; hw/ip/lite_core/README.md and formal/README.md;
tools/env/lock.json; existing CI tier definitions. Historical passes retain their
original source/configuration scope; do not infer present qualification from them.

Skills: deadhorse-task-execution, reference-model-testing,
chisel-formal-properties, formal-timeout-triage, clocked-chisel-block-design;
gf180-synth-timing-check and sv-to-chisel-translation if a fix changes mapped
RTL or an equivalence-qualified conversion.

## Deliverables

1. `docs/spec/core-qualification.md`: reviewed ISA/platform contracts for each
   hart, reference-model choice, trace/event semantics and coverage matrix.
2. `dv/core/qualification/manifest.yaml`: versioned test inventory, source/tool
   locks, hart/configuration identity, fixed seeds, required coverage bins,
   expected faults and per-job deadlines. New values are labeled planned or
   assumed; no count is a measurement until run. No result-dependent selection.
3. `dv/core/qualification.py`: staged standalone campaign reusing existing
   emission, provenance, architectural, differential, FPU and fault tooling.
4. `dv/soc/core/check.py`: production two-hart retirement checking and directed/
   seeded integration stress with the real digital feature set and clocks.
5. Source-bound receipts, test list before/after, coverage and minimized failures
   under `build/t39/`; no generated RTL, binaries, traces or test programs committed.
6. `docs/plan/tasks/reports/T39.md`, updated core/formal evidence ledgers and
   own STATUS entry/debt references. Explicitly separate current results,
   historical evidence, unrun checks and deferred proofs.

## Work, in order

### 1. Freeze contracts and inventory; qualify the checking tools

- Record production revision plus working-tree hashes, emitted HDL, elaboration
  parameters, firmware, memory map/latency, clocks/resets, environment image,
  compiler, simulator, ISS, generator and reference-source versions/hashes.
- Enumerate the performance hart's RV32IMFC plus implemented machine/debug
  facilities, and lite hart's RV32E plus its documented machine/debug subset.
  State ISA/privileged spec versions, supported CSRs and writable/WARL fields,
  reset vectors, interrupt/NMI availability, alignment and bus-error behavior,
  counters, WFI, fences, debug and unsupported encodings. Derive requirements
  from approved contracts/specifications; do not redefine them from observed RTL.
- List every existing core/FPU/SoC test and its scope. Retain pinned
  RV32UI/RV32UM/RV32UC tests and existing random/flight suites and fault controls.
  Classify uncovered requirements and existing formal debt separately.
- Reuse Verilator/Chisel and QEMU retirement comparison. Retain original Ibex
  comparison only for the common behavior it implements; it is not the oracle
  for F or the unrelated lite core. Qualify an independent ISS supporting the
  exact RV32E/machine subset (prefer a suitable pinned Sail or Spike model);
  an RV32I model accepting registers x16–x31 does not establish RV32E legality.
- Integrate a pinned compatible `riscv-arch-test` release and its reference/
  target configuration, adapting only the documented test environment and
  target interface. No changed upstream expected results or test bodies.
  Check ELF sections, stack and signature buffers against each real hart's
  memory/ownership limits before execution. Use supported generator partitioning
  without dropping cases; do not enlarge production memories or silently run an
  oversized integrated test only in a standalone fixture.
  Unsupported optional features may be not-applicable only by the frozen
  contract; a required unsupported generator/model feature is an open blocker.
- Evaluate pinned `riscv-dv` for supported random generation; reuse existing
  deterministic generators where they cover the contract. A new UVM simulator
  stack is not required by default. Establish tool/ISA compatibility with small
  positive and intentionally wrong cases before a long campaign. Pin additions
  in the repository environment; no ad-hoc host installation or vendor edits.
  New project harness RTL remains clocked Chisel. Any adopted SystemVerilog
  stays under locked vendor rules; emitted/generated HDL belongs in build/.
- Obtain independent review of the contracts, applicability decisions, ISS
  adapters and manifest before accepting results. Report missing tool support
  without silently dropping the affected hart, extension or test.

### 2. Fresh standalone baseline and architectural coverage

Run the existing applicable suites on freshly emitted production cores, not
only historical analysis variants. Preserve their assertions and deadlines.
Then run all applicable tests from the pinned architectural suite for each
declared hart configuration. Provide source-test-to-executed-result accounting;
an empty suite, missing case, timeout, unreviewed exclusion or mismatch fails.

Required coverage categories (expand into enumerated bins in the manifest):

| Category | Required cases |
| --- | --- |
| Integer/RV32E | Every supported instruction, register source/destination and alias class, x0, signed/unsigned extrema, shifts/immediates, branches both ways, jumps and dependencies; lite high-register encodings rejected as specified |
| Multiply/divide | All supported M operations, sign combinations, high/low products, zero, signed overflow, divide-by-zero, destination/source overlap and dependent consumers; lite unsupported M follows its illegal-instruction contract |
| Compressed/fetch | Every supported C form, halfword/word boundaries, cross-word fetch and branch redirects, illegal/reserved encodings; lite alignment and unsupported C traps |
| Memory | All widths/byte lanes and sign extensions, aligned/misaligned contract, first/second split-transfer errors where applicable, memory boundaries, stalls, denied accesses and instruction/data consistency |
| Floating point | All supported F operations, conversions/comparisons/moves/classification, static/dynamic rounding, legal rounding modes, flags and fcsr, zeros/infinities/subnormals/NaNs, overflow/underflow/inexact/invalid/divide-by-zero, fused-versus-unfused cases and dependency chains |
| Machine behavior | Every implemented CSR/access type, read-only/WARL/reserved behavior, illegal instructions, ecall/ebreak, trap PC/cause/value, interrupt entry/return/masking/pending, WFI/wake and counter semantics |
| Debug/reset | Halt/resume, approved per-hart register access, performance single-step, halt-on-reset, reset during fetch/load/store and multicycle operations, no stale retirement or duplicate side effects |

Reference matching covers PC/instruction, integer/FP architectural effects,
memory address/data/masks, trap/interrupt state and defined CSR effects.
Check x0 and register-file state, not just the reported destination. Use
verification-only observation or validated architectural readback to expose
state that retirement traces omit. Verify observer noninterference; no core
behavior change to make tracing easier. FCSR probes must not hide hazards or
interrupt races: compare direct effects where available and retain explicit
coverage gaps where probes cannot establish them. Do not treat QEMU text
traces as independently observing flags they do not contain.

Distinguish mandatory architectural values from implementation latitude or
unspecified fields in the selected ISA/platform contract. For each affected
field, use an independently reviewed permitted-value set or the fixed documented
implementation behavior (for example WARL legalization or a trap-value field).
Require exact equality wherever the specification/contract defines it, including
required FP encodings and flags. Do not demand an ISS's arbitrary choice for
unspecified data, mask whole CSR/trap/FP records, or derive permitted values from
the DUT result. Preserve existing checks; a changed comparison rule needs an
explicit specification justification and independent review.

### 3. Seeded differential stress and checker fault controls

Run deterministic mixed-instruction programs for both harts. New campaign
minimums are **planned workload requirements, not measured coverage**: seeds
0–31, each contributing at least 1024 matched non-padding instruction
retirements per hart at standalone and integrated levels. Fixed loops, startup,
signature extraction and padding do not satisfy that count. Partition programs
to respect existing per-job caps; retain all pre-existing seeds and workloads.
Measure unique generated instruction/operand combinations to detect duplicate
streams. Seed count never substitutes for required coverage bins.

Inject legal reproducible memory grant/response delays, errors, interrupt
events, branch/operand hazards and long-latency operations. Derive new-job
deadlines from the declared program/service/clock bounds before running them;
record them in the reviewed manifest, not after a timeout. Do not increase
existing bounds, change unsupported behavior or introduce fairness assumptions
to make results pass. Ordinary and fault/error streams have explicit completion
or trap expectations; a hanging simulator is not a passed test.

Compare at architectural retirement/event boundaries, not equal wall-clock
cycles. Independently generated interrupt requests and bus stimulus must reach
both DUT and oracle under a reviewed event contract; do not align the ISS by
arbitrarily copying a DUT trap decision. Legitimately variable interrupt
boundaries must be checked against a specification-derived allowed set, with
latency checked separately. CSR counters/WFI/debug and nondeterministic MMIO
need explicit modeling, not blanket ignored fields or trace filtering.

Negative controls must reject at least: wrong integer result, x0 write, wrong
PC/branch, missing/duplicate retirement, wrong memory lane/address/data,
incorrect trap/CSR result, incorrect F result and flags, stale post-reset
response, and a broken checker/trace input. Include actual temporary RTL faults
in emitted build copies, not just edited traces. Include common-mode corruption
of hardware traces to demonstrate independence of the ISS path. Match the
intended failure identity; compile errors and unrelated failures do not count.
Production sources remain fault-free.

### 4. Both harts in the production SoC

- Use `DeadhorseSoc`, real USB and existing debug/clock/reset/peripheral binding.
  Analog behavioral substitutes are allowed and explicitly labeled; core,
  fabric and memory-path substitutes are not acceptance targets. Standalone
  CPU fixtures remain useful diagnostics only. Preserve both retirement streams
  with hart and reset-epoch identity; no unexpected missing trace is tolerated.
- Load programs through the current authorized loader/debug/boot paths. Reuse
  present bootstrap firmware; do not implement T36 or bypass loader/ownership
  protections. Reset and initialization assumptions are explicit; uninitialized
  RAM cannot silently become an all-zero hardware guarantee.
- Execute the applicable architectural programs inside the SoC as well as the
  integrated seeded campaign. Map every standalone required test to an integrated
  result; environment adaptation must preserve test semantics. No fallback to
  standalone signatures for a failing production run.
- Run both harts concurrently with mailbox/bridge traffic, permitted shared
  memory accesses, DMA contention, XIP fetch and mixed peripheral traffic.
  Use independent transaction/memory models. A DUT write or loaded value may
  update the oracle only after its address/value/order is validated; do not let
  DUT behavior manufacture its own expected answer. Check legal inter-hart
  ordering and synchronization without assuming a stronger memory model.
- Directed cases cross every applicable hazard with normal completion, a
  pending interrupt and reset/cancellation: fetch stalls, outstanding loads/
  stores, integer multiply/divide and FPU ownership/response, main/AON bridge
  work and DMA. Check reset cancellation and committed-side-effect semantics
  from the existing contracts, not an invented rollback rule.
- Exercise both watchdog reset scopes, performance debug halt/step, lite debug
  halt/resume, sleep/wake, main-clock stop/restart and retained-state behavior.
  Event injection uses existing SoC pins/interfaces or reviewed test-only
  stimulus boundaries, not forced internal state. Check preserved owners,
  reset-disabled PWM outputs, no old-epoch replies and deterministic recovery.
- Replay existing fixed-point and hard-float workloads before/after wake and
  with specified contention. Report correctness, mean/worst cycles and IRQ
  latency with commands/source hashes. Preserve D75 and existing deadlines;
  do not resolve Q16 or S1 performance-floor decisions by changing a test.

### 5. Coverage, defects and finite acceptance

Create a requirement-to-test-to-result matrix for every category above and
every supported opcode/CSR/trap. Include operand classes and directed crosses
for hazards, interrupts, reset, memory response phases and both harts. Count
coverage from observed behavior/traces, not merely generated instructions.
Every mandatory bin needs a witness; unhit bins prevent completion unless the
user approves an explicit scope decision. Report RTL line/toggle/branch coverage
where supported, with denominators/exclusions; do not invent a percentage as
a correctness guarantee. Report reference/generator limitations separately.

For each failure preserve source hashes, seed, ELF/binary, stimuli, waveform,
DUT/reference traces and first divergence. Minimize without removing the
triggering behavior. Classify RTL defect, harness/reference defect, unsupported
contract or resource timeout. Make the smallest authorized fix, add a permanent
regression, independently review it and rerun affected checks. Any production
RTL change requires fresh affected equivalence/formal checks and GF180 timing/
area at unchanged limits; re-run the final affected campaign on the fixed top.
No optimization, map/ISA change, limit relaxation or hidden expected-fail.

Do not retry unchanged known-timeout formal jobs. Existing D44 arithmetic and
D80/D86/D87 deferral scopes remain explicit. New tractable proof obligations
from actual fixes follow formal-timeout-triage with original caps; stop at its
budget and report unresolved results. T39 simulation cannot discharge T13,
T25, T32 or T33 unbounded claims. If a required new proof cannot close, seek a
specific acceptance decision; do not extend old task-specific waivers silently.

## Acceptance commands and publication (all unverified)

The following new command interfaces are deliverables to implement, not
existing tools or successful runs. All run under `python tools/env/run.py run --`.
Stage receipts must seal inputs, outputs, commands, tool identity and exact case
lists. Final audit fails closed on changed sources, missing/empty cases,
unexpected exclusions, unreachable required bins or absent fault evidence.

```sh
python dv/core/qualification.py --stage inventory --output build/t39/inventory
python dv/core/qualification.py --stage baseline --output build/t39/baseline
python dv/core/qualification.py --stage architectural --output build/t39/architectural
python dv/core/qualification.py --stage random --output build/t39/random
python dv/core/qualification.py --stage faults --output build/t39/faults
python dv/soc/core/check.py --output build/t39/soc
python dv/core/qualification.py --stage audit --evidence build/t39 --output build/t39/acceptance
```

The common manifest is the sole scope definition. Individual stages are
diagnostics until the aggregate authenticates all required stages for both
harts/configurations. On source changes rerun affected stages; reuse is allowed
only with identical authenticated dependencies and independent review, never
by relabeling an old pass. Freeze before final acceptance.

D76 applies to T39 execution: run fast CI before new implementation and on the
final snapshot, retaining every inherited deferral. T33/T34's scoped no-CI
exceptions do not automatically extend to this task. The full tier is required
if claiming an integration-stage exit; T39 alone does not close I2–I5. Otherwise
report full-tier status explicitly. Any user-approved change to this policy
must be recorded before applying it. The present brief-writing task runs only
documentation checks and does not start any campaign or CI tier.

Acceptance requires independent review of ISA/platform applicability, oracle/
event alignment, coverage/fault evidence, fixes and final source identity; then
the report, own STATUS update, logical commits and push to main. Completion
means all active T39 tests and coverage obligations pass, not that the whole
MCU or inherited proof debt is signed off.

## May change

`dv/core`, `dv/soc/core`, affected core/SoC Chisel test harnesses, verification-only
observation ports, `sw/tests` test firmware, pinned test/ISS/generator adapters
and environment locks, own specs/ledgers/report and scoped CI registration.
Small defect fixes in existing performance/lite core, FPU or SoC integration
are allowed under AGENTS.md only to restore the approved contract, with a
reproducing regression and independent review. No new peripheral, SRAM/ROM
realization, architectural feature, clock/reset policy or production profile.
Upstream code remains pinned and unmodified except through approved patches.

## Stop conditions

Stop the affected acceptance sequence and report for an ISA/platform conflict,
unavailable independent oracle for a required feature, tool/license incompatibility,
unexplained trace suppression or missing observer state, a fix needing an
architecture/ABI/ownership/reset decision, timing/area/deadline failure not
repairable within scope, or a proposed test/coverage/assumption reduction.
Preserve failure evidence and continue independent authorized diagnosis; do
not call a mismatch a formal timeout or a missing test a pass. Exhausted proof
budget remains unresolved and cannot be converted into simulation proof.

## Reference choices

Local pinned tests and adapters above are the starting point.
[RISC-V architectural tests](https://github.com/riscv/riscv-arch-test) provide
architectural test infrastructure; passing them does not replace processor
verification. [RISCV-DV](https://github.com/chipsalliance/riscv-dv) is a candidate
for randomized instruction generation/reference comparison, subject to the
pinned-tool feasibility check. No latest-branch download is an acceptance input.
