# T13 report

## Outcome

T13 is blocked on the remaining bounded load/compressed-add acceptance and
focused local gate; the reviewed workflow update is separately committed and
pushed, and the user has explicitly requested this incomplete T13 checkpoint
be committed and pushed for their review.

## What changed

- `compose_jalr_request_kind.py`, `audit_request_kind.py`: exact ownership,
  retention and retained-kind implication establishes saved ALU kind and first
  phase, qualified by active capture and actual saved-register faults.
- `check_jalr_execute_only.py`, `induct_jalr_execute.py`: preserve the full-core
  ADD timeout and prove the original saved-input ADD response equation through
  exact production reset/D-pin induction, with dispatch-state invariants,
  overflow/odd-result cover and real response-adder fault.
- `OperandOwnershipProperty.scala`, `check_jalr_operands.py`,
  `audit_jalr_operands.py`: actual accepted Op/A/B classification and retention
  prove; a companion authenticates the complete inherited dependency inventory
  and binds the inherited phase monitor through exact named-state equivalence.
  Direct source stability times out and remains unresolved by this runner.

- `compose_jalr_ownership.py`, `test_compose_jalr_ownership.py`: exact emitted
  monitor reset/transition/final SAT implications compose qualified phase,
  retention and capture-valid guarantees into full ownership identity.
- `qualify_owner_valid.py`, `test_qualify_owner_valid.py`: active capture cover,
  explicitly labeled ghost-valid sensitivity fault, and real production PC-bit
  fault for the original full ownership predicate. Independent review clears
  these qualifications, without promoting them to an ISA result.
- Separately committed workflow update `ac45fd4`: minor fixes require targeted
  research, unchanged checks and independent review; approval is reserved for
  critical decisions. Skill validation and structure check passed. This commit
  contains only `AGENTS.md` and the task-execution skill.

- `PhaseStabilityProperty.scala`, `check_phase_stability.py`,
  `audit_phase_stability.py`, `test_phase_stability.py`: holding-edge monitor
  for actual IF instruction writes, ID clear and the full instruction/PC/phase
  tag, with actual production pulse/phase fault controls and active covers.
- `strengthen_jalr_ownership.py`, `test_strengthen_jalr_ownership.py`: reuse of
  the audited phase model with all three helpers retained as assertions, an
  inherited-monitor named-state equivalence proof and tag-binding negative,
  then one short owner-JALR proof. No production RTL or assumption changed.

- `split_jalr_ownership.py`, `test_split_jalr_ownership.py`: exact five-condition
  decomposition of capture ownership flags and instruction/PC identity, with
  full inventory, original guard/enable/environment and no peer assumptions.
  Free-Boolean equivalence and an omitted-PC negative qualify the split.

- `JalrOwnershipProperty.scala`, `check_jalr_ownership.py`,
  `audit_jalr_ownership.py`, `test_jalr_ownership.py`: clock/reset-matched ghost
  tags for every actual accepted execute request; issue classification, saved
  kind/phase retention and instruction/PC ownership assertions. Independent
  active covers and real incoming-kind, saved-kind and identity fault roles
  remain mandatory. A companion negative checks corrupted retained kind itself.
  No production RTL, timeout or environment assumption changed.

- `split_jalr_alignment.py`, `test_split_jalr_alignment.py`: exact authenticated
  decomposition of the existing six-condition alignment assertion, preserving
  guard/enable and production/environment bytes. A free-Boolean equivalence
  check and omitted-conjunct negative qualify the split; every condition is
  required and no peer assertion is assumed. Historical receipts are unchanged.

- `JalrRequestProperty.scala`, `check_jalr_request.py`,
  `test_jalr_request.py`: further separate saved-request ownership/operand
  alignment from the ADD response equation. Assertions observe actual saved
  request flop outputs in the authenticated full production model; the local
  ADD predicate uses its saved operands without assuming alignment. Code/model
  review found no changed production cells, guards or environment assumptions.

- `JalrCaptureProperty.scala`, `check_jalr_capture.py`,
  `audit_jalr_capture.py`, `test_jalr_capture.py`: normalized source capture and
  RVFI correspondence, separate capture-arithmetic predicate, active x0/alias
  witnesses, actual source-bit fault and source-only negative guard audit.
  Exact receipt/model/configuration validation permits reusing completed jobs
  after a witness-parser repair. Production RTL and proof limits are unchanged.

- `JalrTransportProperty.scala`, `check_jalr_transport.py`,
  `audit_jalr_transport.py`, `test_jalr_transport.py`: observation-only clocked
  capture of the qualified redirect target and instruction/PC identity, asserted
  capture validity at retirement, staged RVFI correspondence, actual PC-bit fault,
  active capture/retirement witness and negative guard qualification. No production
  RTL or environment assumption changed in this continuation.

- `JalrTargetProperty.scala`, `check_jalr_target.py`, `test_jalr_target.py`:
  focused jump-target predicate, exact checker qualification, sign-extension
  fault, required x0/odd-sum/negative-immediate covers and output fault. The
  sequential proof times out; later roles remain unrun, not waived.
- `jalr_receipts.py`, `test_jalr_receipts.py`: immutable per-consumer audit
  snapshots and exact historical input relocation. JALR consumer runners now
  validate/snapshot existing audit evidence without rewriting the shared audit.
  Archived executed-source bytes preserve historical receipts through this
  metadata-only harness change. No sequential proof was repeated for the repair.

- `JalrLinkProperty.scala`, `check_jalr_link.py`, `test_jalr_link.py`: targeted
  all-retirement JALR link-value monitor and proof runner, exact original guard/
  violation qualification, wrong-increment negative control, active destination
  witnesses, and synthetic model/VCD tests. Production RTL is unchanged in this
  continuation. The complete JALR checker is not retried.

- `JalrAddressProperty.scala`, `jalr_invariant.py`: all-retirement source-address
  predicate, exact pinned-checker guard qualification, unchanged production model
  graft and independently proved helper retained as an assertion in the original
  address partition. `audit_jalr_invariant.py` requires active cover/fault traces
  and rejects a wrong-opcode monitor. `check_jalr_strengthened.py` retains the
  complete original JALR checker plus helper for a single short attempt.
  `test_jalr_invariant.py` covers transformations and witness rejection.

- `hw/ip/perf_core/`: optional RV32IMFC profile, floating register file (including
  writable f0), staged decode/operand/completion controls, FPU transaction glue,
  FLW/FSW and compressed forms, floating CSRs/FS/misa.F, and floating RVFI state.
- Core qualification now accommodates registered instruction selection and CSR
  legality. Floating arithmetic and load commit use their qualified response
  paths. Integer write intent and load/store direction are staged. Unowned LSU
  responses cannot write integer registers outside a load-response phase in the
  F-enabled profile; this is not a claim of full memory-response causality.
- Return RVFI reports MRET/DRET targets instead of the still-sequential fetch PC.
  Execution already returned correctly; the independent interrupt comparison
  exposed the observation bug. The default non-F profile is unchanged in behavior.
- `FloatCoreSpec.scala`: port-driven dependencies, f0, compressed memory, CSR
  legality/aliases/rounding, destination preservation on faults, timer/NMI/debug,
  reset during division, and events immediately before the completion edge.
- `dv/core/assertion_partitions.py`: exact full-model partition validation,
  unique assertion-union accounting, before/after model/config hashes, and
  fail-fast sequential jobs. `test_assertion_partitions.py` rejects omitted or
  duplicated assertions, changed enables/assumptions/data, mixed models, unknown
  property forms and naming collisions.
- `dv/core/`: authenticated floating candidate, FP/CSR observations, independent
  QEMU comparison, architectural F fixtures, mixed seeded streams with software
  interrupts, hard-float T02 flight build, and checker fault controls.
- Formal instrumentation, a production-binding runner and a formal-only FPU
  protocol model are present. All 28 integration safety assertions now prove
  unbounded under that model; arithmetic and completion deadlines are separate
  T12 obligations. Earlier bounded attempts remain recorded as unresolved.
- Local tag `t11-baseline` points to `3dfa92ea25cea14f3fde0ee0b3f318c849815285`.
  Its source archive was rebuilt under `build/t13/t11-source/`; tag is not pushed.

The approved existing HardFloat patch now uses an exact signed prefix-adder
subtraction; upstream files remain unchanged. No S1/T14 work,
optional performance optimization, timing exception or relaxed limit is included.

## Checks run

Final focused experiment (implementing-agent run, independently reviewed; root
ran the unit tests):

```text
python3 dv/core/check_critical_isa_two_part.py --output build/t13/critical-two-part
  lw/bmc-0: PASS (11 original assertions, bounded depth 144)
  lw/bmc-1: TIMEOUT rc8 (22 original assertions; unresolved)
python3 -m unittest discover -s dv/core -p test_critical_isa_two_part.py
  Ran 2 tests in 0.001s; OK
```

Measured on `ac45fd4` plus the receipt's authenticated working-tree inputs:
first partition 91.625 seconds, second 121.234 seconds including cleanup.
Both retain depth 144/check cycle 64 and a 120-second solver cap. The original
33 assertions form an exact disjoint union; no other model object or assumption
changes, and no peer assertion becomes an assumption. Independent pre-run review
cleared the transformation and missing-member negative. The second group's
first active frame completed, but the next remained unresolved; that is not
full-depth acceptance. No counterexample appeared. Fail-fast prevented concrete
qualification and C.ADD in this invocation. No further solver retry or partition
cascade was launched, consistent with the user's instruction to avoid long
formal sweeps. The unresolved memory/trap cone is a verification blocker, not
evidence of an RTL bug or permission to weaken the check.

Final independent review authenticates all 430 receipt inputs, exact saved
partition models, the omitted-member negative and both actual solver outcomes.
It confirms the unresolved aggregate and absence of later qualification jobs.
Root's final pinned unit command `python3 -m unittest discover -s dv/core -p
test_*.py` passes all 122 tests (measured 2.584 seconds on `ac45fd4` plus current
working-tree inputs); structure and `git -c core.autocrlf=false diff --check`
also pass. These checks do not replace unresolved ISA acceptance or the gate.


Independent implementing-agent runs, audited by a separate reviewer:

```text
python3 dv/core/check_float_integration_wide.py --qualification build/t13/fpu-protocol-wide-confirmed --output build/t13/integration-wide
  normal: PASS (28 unbounded safety assertions)
  fault: FAIL (expected actual commit-on-squash fault)
  cover: PASS (eight abstract-model covers)
python3 dv/core/bind_float_integration.py --output build/t13/integration-production-binding
  positive: proved (271 production states)
  output: rejected
  reset-value: rejected (reset parameter)
  next-state: rejected
  clock: rejected
python3 dv/core/check_critical_isa_wide.py --output build/t13/critical-wide
  unresolved: lw/bmc TIMEOUT rc8; no acceptance claim
python3 dv/core/check_critical_isa_wide.py --checks c_add --output build/t13/critical-c-add-wide
  unresolved: c_add/bmc TIMEOUT rc8; no acceptance claim
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 118 tests in 2.318s; OK
python3 -m unittest discover -s tools -p test_t13_gate.py
  Ran 6 tests in 0.180s; OK
python3 tools/check_structure.py --include-untracked
  exit 0
git -c core.autocrlf=false diff --check
  exit 0
```

Measured on `ac45fd4` plus the receipts' authenticated working-tree inputs:
integration safety 8.1088 seconds, production binding 1.1901 seconds, and the
LW attempt 121.48 seconds including cleanup with the unchanged 120-second
solver cap. Independent review clears the widened-model integration proof and
its fresh concrete production binding. The LW timeout is unresolved; that
fail-fast invocation did not run C.ADD or concrete cover/fault qualification.


- `build/t13/jalr-original-complete/result.json` closes the exact original
  33-assertion inventory: six authenticated singleton partitions, source-address,
  link and target proofs, a clean 22-assertion partition, and destination-address
  and trap-agreement lemmas qualified against original lines176/198.
- All original assertion objects occur exactly once. The prior wrapper SV bytes
  match; only verified source-location attribute prefixes differ between reused
  models. No environment assumption or assertion enable changes.
- The original concrete cover passes; the actual full-checker PC-bit fault
  produces a real counterexample (`FAIL`, not `TIMEOUT`) at the unchanged
  120-second configuration. Its measured process wall time includes cleanup.
- The 22-assertion group's actual memory-mask fault is independently parsed
  against the original extra-write rules; parser-only repair preserves raw
  results and exact executed-source archives. Both metadata helpers have active
  covers and actual destination/trap output faults.
- Independent review authenticates all 824 aggregate inputs and reparses the
  concrete cover/fault witnesses. The original 24-assertion group timeout stays
  recorded and is not presented as passing.

This is complete original JALR checker acceptance through the documented proof
composition. It is not an all-instruction ISA or T13 completion claim.

The native solver scheduling refinement was researched against pinned
`btormc --help`, SBY's engine command and the [upstream implementation](https://github.com/Boolector/boolector/blob/master/src/btormcmain.c).
`--checkall` ORs all bad predicates into one query; it changes neither the model
nor the acceptance condition. Independent review cleared the option-only
transformation and the later exact complementary assertion split.

```text
python3 dv/core/check_critical_isa_checkall.py --output build/t13/critical-checkall
  unresolved: lw/bmc TIMEOUT rc8; no counterexample or acceptance claim
python3 -m unittest discover -s dv/core -p test_critical_isa_checkall.py
  Ran 2 tests; OK
```

The native scheduling trial measured 122.010 seconds including cleanup against
the unchanged 120-second cap on `ac45fd4` plus authenticated working-tree inputs.
Its first active frame completed UNSAT, but the next did not finish before the
cap; internal progress is not full-depth acceptance. All 33 assertions remained
present, and C.ADD/concrete qualification did not run in this fail-fast attempt.
The receipt and 425 protected hashes passed independent review.

The first root invocation of `python3 tools/ci.py --scope t13 --output
build/t13/gate-critical-preflight` stopped during input authentication because
`F-INTEGRATION.md` was edited after the gate captured its source snapshot.
The receipt preserves that mismatch; no fresh gate job ran and no gate pass is
claimed. The gate must be rerun after source edits settle and critical ISA
acceptance is resolved.

```text
python3 dv/core/qualify_fpu_protocol_wide.py --output build/t13/fpu-protocol-wide-confirmed
  PASS base / base-negative
  PASS control-step / control-step-negative
  PASS outputs / outputs-negative
  PASS step / step-negative
  PASS no-instant-completion / no-instant-completion-negative
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 107 tests in 2.380s
  OK
```

Root ran these through the pinned wrapper. Independent review clears exact
concrete-to-model port trace inclusion. The new formal-only
`FpuProtocolModelWide.scala` has independent invalid/completion payload choices;
its concrete witness choices establish output equality and the next-state
relation for arbitrary external requests, backpressure, cancellation and
arithmetic state. Reset/clock and no acceptance-edge completion are checked,
not assumed. A negative reproduces the old payload coupling defect. Pre-use
source fingerprints are retained and checked after every tool stage; an
initial provenance-race finding was fixed and the old executed runner archived.
The old model/checker/receipt remain unchanged. The same integration safety
assertions have since passed against the qualified model with a fresh production
binding (above); the critical ISA checks remain open.

```text
python3 dv/core/compose_jalr_operands.py --source build/t13/rf-source-composition-confirmed --output build/t13/operand-composition-confirmed
  response-cover: PASS; response-fault: FAIL (expected)
  PASS base / base-negative / step / step-negative / final / final-negative
  PASS arithmetic-implication / arithmetic-implication-negative
  alignment-zero: PASS; alignment-negative: PASS; alignment-fault: FAIL (expected)
  arithmetic-negative: PASS; arithmetic-odd: PASS; arithmetic-fault: FAIL (expected)
python3 dv/core/compose_jalr_target.py --arithmetic build/t13/operand-composition-confirmed --output build/t13/jalr-target-composition-confirmed
  PASS base / base-negative / step / step-negative / final / final-negative
  cover-zero: PASS; cover-odd: PASS; cover-negative: PASS; fault: FAIL (expected)
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 104 tests in 2.477s
  OK
```

Root ran all commands through the pinned wrapper. Independent review clears
both composition chains, including confirmed-run hashes and witnesses. Exact
capture/stage state induction establishes the unmodified JALR target predicate;
fresh activation/violation qualification ties it to the original checker line178,
with a wrong sign-extension negative. No trap or nonzero-source guard was added.
The complete original JALR assertion inventory remains a separate aggregate
obligation. Historical full-model timeouts stay recorded, not relabeled passes.

```text
python3 dv/core/check_rf_source_control.py --output build/t13/rf-source-control-confirmed
  address-prove: PASS; address-cover: PASS; address-fault: FAIL (expected)
  conflict-prove: PASS; conflict-cover: PASS; conflict-fault: FAIL (expected)
python3 dv/core/audit_rf_source_control.py --controls build/t13/rf-source-control-confirmed --output build/t13/rf-source-control-confirmed-audit
  PASS RF controls audit and exact inherited operand monitor binding
python3 dv/core/compose_rf_source_stability.py --controls build/t13/rf-source-control-confirmed --audit build/t13/rf-source-control-confirmed-audit --output build/t13/rf-source-composition-confirmed
  PASS base; PASS base-negative; PASS step; PASS step-negative
  source-cover: PASS
  source-fault: FAIL (expected)
```

Root ran the RF chain through the pinned wrapper. Actual RF address stability
and absence of a conflicting nonzero write are proved in the full production
model. Exact physical RF read muxes and word-register D cones, plus those proved
controls and phase stability, establish normalized source stability. No RF value
stability is assumed. The nonzero cover and actual source-bit fault are active.
Independent review clears the source component, exact RF transitions and
inherited predicate bindings; operand/ISA composition remains separate, and
the earlier direct-source timeout is preserved.

```text
python3 hw/ip/perf_core/formal/check_if_no_f.py --output build/t13/if-conditional-confirmed
  PASS normal
  PASS output-fault
  PASS transition-fault
  PASS reset-fault
```

Root ran this through the pinned wrapper. Independent review clears the local
IF proof: all original baseline outputs and 26 named states are compared under
an explicit raw-encoding condition. An unconditional 25-state binding checks
all surviving integrated candidate outputs against the standalone WithF profile;
the compiler-pruned unused ALU-copy output is retained in the full baseline
comparison. Disabled feature input specialization is checked against actual
integrated logic. Decoder input equality is also proved unconditionally.

Scope limits: the condition excludes C.FLW/C.FSW/C.FLWSP/C.FSWSP raw decoder
encodings at every comparison, including invalid, stalled and error payloads.
It is narrower than an unrestricted claim about a program containing no F
instructions. The active transfer SAT witness establishes one-step nonvacuity,
not reset-reachable sequential execution. This is local IF equivalence, not
whole-core latency or ISA refinement.

Additional root verification through the pinned wrapper:

```text
python3 dv/core/compose_jalr_request_kind.py --ownership build/t13/ownership-composition-confirmed --output build/t13/request-kind-confirmed
  PASS compose / kind-negative / first-negative
  capture-cover: PASS
  kind-fault: FAIL (expected)
  first-fault: FAIL (expected)
python3 dv/core/audit_request_kind.py --output build/t13/request-kind-confirmed
  PASS saved kind/first composition audit: active cover and exact real-driver faults
python3 dv/core/induct_jalr_execute.py --output build/t13/jalr-execute-induction-confirmed
  PASS base / base-negative / step / step-negative / final / final-negative
  execute-cover: PASS
  execute-fault: FAIL (expected)
python3 dv/core/check_jalr_operands.py --output build/t13/jalr-operands
  issue-prove: PASS; issue-cover: PASS; issue-fault: FAIL (expected)
  retention-prove: PASS; retention-cover: PASS; retention-fault: FAIL (expected)
  source-prove: TIMEOUT (120 s cap; no counterexample)
python3 dv/core/audit_jalr_operands.py --output build/t13/jalr-operands-audit
  PASS operand issue/retention audit and inherited exact monitor binding; source remains TIMEOUT
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 93 tests in 2.405s
  OK
```

Independent review clears kind/first composition, local ADD induction, operand
issue/retention and companion provenance/binding. The accepted operand proof
checks the actual incoming fields, including the live LSU address-increment
multiplexers; no override-low assumption was added. Source stability is being
split into actual RF read-address stability, no conflicting nonzero write, and
an exact local RF transition implication. No source result is claimed until
that premise chain closes. The separate full-core ADD timeout remains recorded
in `build/t13/jalr-execute-only` and was not retried.

Current continuation, on `ac45fd4` plus authenticated T13 working-tree inputs:

```text
python3 scratch/skill-validation/quick_validate.py .agents/skills/deadhorse-task-execution
  Skill is valid!
python3 dv/core/qualify_owner_valid.py --split build/t13/jalr-ownership-split --owner build/t13/jalr-ownership-resumed --output build/t13/owner-valid-qualified
  cover: PASS
  ghost-valid-fault: FAIL (expected mutation rejection)
  production-pc-fault: FAIL (expected mutation rejection)
python3 dv/core/compose_jalr_ownership.py --output build/t13/ownership-composition-confirmed
  PASS base
  PASS base-negative
  PASS step
  PASS step-negative
  PASS final
  PASS final-negative
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 88 tests in 2.035s
  OK
python3 tools/check_structure.py --include-untracked
  exit 0
```

All Python commands above ran through `python tools/env/run.py run --`.
The composition uses the exact monitor D pins and asynchronous reset values;
its theorem antecedents are previously proved guarantees, with no production
assumption cells added. The stronger invariant includes ownerJalr, ownerFirst,
instruction and PC equality while owned. Prior global timeout records remain
unchanged. Root confirmation results are separate from the implementing agent's
run. Independent review clears the full ownership identity composition, exact
clock/reset/transition binding, premise closure and mutation controls. No long
formal sweep was run.

Quick research: [YosysHQ IVY invariants guidance](https://yosyshq.readthedocs.io/projects/ivy/en/latest/quickstart.html#finding-useful-invariants)
recommends independently proved state/transition invariants when induction gets
stuck in unreachable states. This supports the chosen decomposition method;
it does not validate this implementation. The existing pinned Yosys is used,
without adding IVY or accepting unchecked assumptions.

Commands below run after `python tools/env/run.py run --` in the pinned Linux
image, at base `11c72b3` plus this uncommitted tree. Generated receipts remain in
`build/t13/`; they are not committed. Earlier failing snapshots are retained.

Approved targeted-invariant continuation (measured at `11c72b3` plus the
source/model hashes in `build/t13/jalr-address-strengthened/result.json`):

```text
python3 dv/core/riscv_formal.py --target candidate --candidate build/t13/exponent/candidate --checks jalr --jalr-address-invariant --timeout 120 --output build/t13/jalr-address-strengthened
  prove: PASS
  cover: PASS
  fault: FAIL                 (expected rejection)
  original-source-address: PASS
python3 dv/core/audit_jalr_invariant.py --output build/t13/jalr-address-strengthened
  PASS JALR audit: active cover/fault witnesses verified; wrong-opcode qualification rejected
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 47 tests in 1.393s
  OK
```

The independent all-retirement PDR job took **5.450122 seconds measured**; the
original source-address assertion plus helper took **4.613703 seconds measured**.
Cover and actual address-fault jobs took **1.674053 / 1.718116 seconds measured**.
The companion audit authenticates retained inputs and finds a JALR with expected
rs1=1/reported1 in the cover and expected1/reported0 after the real RVFI stage
output-bit mutation. The wrong-opcode (0x67 -> 0x66) guard also produces a SAT
counterexample. Independent review cleared the model preservation, proof,
witnesses and mandatory companion audit. These results establish the lemma and
one original assertion, not aggregate ISA acceptance. No sequential proof was
repeated just to add the companion witness/qualification audit.

The one complete-JALR retry retained all 33 original assertions plus the helper:

```text
python3 dv/core/check_jalr_strengthened.py --lemma build/t13/jalr-address-strengthened --output build/t13/jalr-complete-strengthened
  Reached TIMEOUT (120 seconds). Terminating all subprocesses.
  engine_0 did not produce any traces
  DONE (TIMEOUT, rc=8)
python3 tools/check_structure.py --include-untracked
  exit 0
```

The measured complete-JALR command duration was **121.181980 seconds**, including
shutdown overhead; the solver cap remained **120 seconds**. No counterexample or
aggregate proof was produced. Fail-fast prevented the subsequent original
retirement-cover and destination-fault jobs. No additional ISA sweep or timeout
increase was attempted. The internal solver progress count is not claimed as
individually accepted assertion results. Current model and runner received
independent review; this does not waive remaining acceptance checks.

Targeted return-value continuation on 2026-11-16, at base `11c72b3` plus
recorded working-tree hashes:

```text
python3 dv/core/check_jalr_link.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-link-v2
  JALR link prove: PASS
  JALR link cover-zero: PASS
  JALR link cover-link: PASS
  JALR link fault: FAIL       (expected rejection)
  JALR link original-link-value: PASS
```

**Measured** by that command and retained input hashes: independent all-retirement
PDR **87.135088 s**; original line177 plus helper assertion **76.110678 s**;
x0/nonzero-destination covers **2.015849 / 2.105153 s**; real output fault rejection
**2.226163 s**. Every job retained the **120-second configured cap** and **depth144**.
The original assertion result applies to the original fixed startup-window
checker; the independent lemma is unbounded under the original wrapper environment.
No complete-JALR checker retry or other ISA sweep ran in this continuation.

Positive free-input guard/violation qualification passed, and replacing the
monitor's PC+4 with PC+8 produced a SAT counterexample. Required VCD witnesses
show JALR x0 returning zero and JALR x1 returning 0x80000084 from retired
PC0x80000080. The real reported-output fault changes the nonzero result to
0x80000085; injection never constrains the positive environment. There is no
reported-trap or nonzero-rs1 guard. Encoded rd and wrapping RV32 addition match
the pinned model. Independent review checks the generated models, retained
assumptions, exact original assertion, qualification counterexample and witnesses.


```text
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 52 tests in 1.706s
  OK
python3 tools/check_structure.py --include-untracked
  exit 0
```

The initial `check_jalr_link.py --baseline build/t13/jalr-address-strengthened
--output build/t13/jalr-link` stopped in the qualification-negative fixture,
before any sequential proof: Yosys reduced the unsigned constant four to three
bits. The matcher now validates the numeric constant, operand/result widths and
signedness, then represents eight with a matching explicit width. No assertion,
limit or production signal changed. The initial output directory is retained.
A regression test covers both short and full-width constants. A missing brace
in that newly added Python test was corrected before the complete test rerun.

Target-PC continuation on 2026-11-16, measured on `11c72b3` plus recorded
working-tree inputs:

```text
python3 dv/core/check_jalr_target.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-target
  Reached TIMEOUT (120 seconds). Terminating all subprocesses.
  engine_0 did not produce any traces
  DONE (TIMEOUT, rc=8)
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 60 tests in 1.588s
  OK
```

The all-retirement target PDR command took **121.221777 seconds measured**,
including shutdown, under the unchanged **120-second configured cap**. There is
no counterexample or target proof. The three retirement covers, real PC-bit fault
and original line178-plus-helper job did not run because the first sequential
job timed out. No further proof attempts or full ISA sweep ran.
Free-input activation/violation/assumption-enable SAT qualification **passed**
(0.029262 s measured); deliberately zero-extending the signed immediate was
**rejected** with a SAT counterexample (0.026530 s measured). The full pinned
checker normalizes encoded-rs1=x0 to zero before calling its instruction model;
the monitor correctly performs that normalization on raw RVFI data. No peer
assertion is assumed, no reported-trap guard is added, and RV32 wrapping add and
bit-zero clearing match the checker.

Independent review found that rerunning the original audit overwrote shared
`audit.json`, invalidating that metadata path's hash in earlier consumers. Exact
prior bytes were recovered using preserved command timings **only when their
SHA256 matched the original recorded hash**. Original `result.json` files and
proof statuses remain byte-identical. Companion `input-relocations.json` files
point to immutable hash-matching audit and executed-source snapshots. This is
metadata reauthentication, not a new proof or changed measurement:

```text
python3 dv/core/jalr_receipts.py --receipt build/t13/jalr-link-v2 --source-snapshot build/t13/jalr-link-v2/check_jalr_link.executed.py
  PASS historical inputs reauthenticated: build/t13/jalr-link-v2
python3 dv/core/jalr_receipts.py --receipt build/t13/jalr-complete-strengthened --source-snapshot build/t13/jalr-complete-strengthened/check_jalr_strengthened.executed.py
  PASS historical inputs reauthenticated: build/t13/jalr-complete-strengthened
python3 dv/core/jalr_receipts.py --receipt build/t13/jalr-target --source-snapshot build/t13/jalr-target/check_jalr_target.executed.py
  PASS historical inputs reauthenticated: build/t13/jalr-target
python3 dv/core/jalr_receipts.py --snapshot-baseline build/t13/jalr-address-strengthened --output build/t13/audit-snapshot-check
  PASS immutable baseline audit snapshot: /work/build/t13/audit-snapshot-check/baseline-audit.json
```

Independent review verified all three relocation manifests against unchanged
raw receipt hashes and every original input digest. No scoped harness or
metadata finding remains; the target proof and task acceptance remain unresolved.

The updated runners' only changes after their recorded executions are audit
acquisition and protected snapshot paths. No claim is made that the target
sequential proof was rerun after this metadata-only change. Original executed
scripts are retained and hash-verified through the relocation manifests.

Redirect transport continuation on 2026-11-16, measured at `11c72b3` plus
protected working-tree inputs in `build/t13/jalr-transport-v2/result.json`:

```text
python3 dv/core/check_jalr_transport.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-transport-v2
  JALR transport prove: PASS
  JALR transport cover: PASS
  JALR transport fault: FAIL  (expected rejection)
python3 dv/core/audit_jalr_transport.py --output build/t13/jalr-transport-v2
  PASS transport audit: input/witness hashes valid; wrong-opcode guard rejected
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 63 tests in 1.716s
  OK
```

**Measured** command durations: unbounded PDR **14.200172 s**, active retirement
cover **1.758349 s**, actual reported-PC bit1 fault rejection **1.953078 s**.
The configured per-job cap remains **120 seconds**, cover/fault depth **144**.
The ghost monitor has the actual production RVFI clock/reset, captures only a
valid original noncompressed JALR first-phase redirect, and asserts capture
validity and instruction/PC identity at retirement. Its expected RVFI stage uses
pre-edge capture data even when capture validity clears on the retirement edge.
Every actual JALR RVFI retirement must have the staged identity/target; capture
validity and trap are never guards that suppress the check. Required event
exclusions are asserted, not assumed.

The cover captures target4, then retires with observed nextPC4 while the execute
adder has moved to the link phase, and RVFI reports4. The real output fault
captures raw0x21/masked0x20 and changes reported target0x20 to0x22, producing the
expected counterexample. Exact external retirement activation matches the pinned
checker on free inputs, and a wrong-opcode monitor is rejected by SAT. This is
transport evidence only: rs1/immediate arithmetic and aggregate ISA acceptance
remain unproved by this check.

The first preparation (`build/t13/jalr-transport`) stopped before any solver
because the generic state name differed from the emitted RVFI register name.
Binding now locates the actual RVFI output's unique state driver and validates
its clock, reset polarity and zero reset data for the emitted `$aldff` form (also
accepting a correctly configured `$adff`). No property or timeout changed. The
initial receipt remains retained. Synthetic tests check binding/reset mismatches,
state/net-attribute preservation and exact PC fault witness rejection.

| Command | Result / last output |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFloatCore build/t13/return-trace/emit" "hw/testOnly deadhorse.perf_core.FloatCoreSpec"` | PASS; `Tests: succeeded 3, failed 0`; `All tests passed.` |
| `python3 hw/ip/perf_core/formal/package_candidate.py --registered --float --top build/t13/return-trace/emit/model --leaves build/t11/ci/emit --core build/t11/ci/core --output build/emit/perf_core` | PASS; `PASS packaged Chisel candidate: rv32imfc-v1; inactive alternatives explicitly listed`. |
| `python3 dv/core/lockstep.py --candidate build/emit/perf_core --isa rv32imfc --suite arch,random,flight-float --output build/t13/lockstep-checkpoint` | PASS; `PASS F lockstep flight-float/T02-hard-float: 191201 retirements`; `PASS selected F lockstep suites`. |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitRegisteredCore build/t13/no-f-current"` | PASS; current default non-F emission. Tagged source separately rebuilt with its archived `tools/sbt.py` and `EmitRegisteredCore build/registered-emit`. |
| `python3 dv/core/revision_equiv.py --before build/t13/tagged-baseline --after build/t13/current-baseline --output build/t13/baseline-equivalence` | PASS; `PASS revision equivalence: whole top, no added assumptions, all fault controls rejected`. This proves the F-disabled profile against T11, not the F-enabled profile. |
| `python3 hw/ip/fpu/formal/check.py` | PASS; unbounded arithmetic-abstracted protocol proof, operation/protocol/division covers, cancel/hold/progress fault controls. Final output: `PASS formal progress_fault ... 'fault rejected'`. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/load-commit/emit/asic --output build/t13/timing-load-commit` | FAIL; `FAIL DeadhorsePerfCore: 25.290892 ns, budget 24.960000 ns; electrical violations 0`. The later return-trace ASIC emission has byte-identical contents for all emitted ASIC files. |
| `python3 hw/ip/perf_core/formal/check_float_integration.py --emitted build/t13/write-qualified/emit/asic --output build/t13/formal-owned-load` | Unresolved: production binding/fault controls passed, but the original arithmetic-cut integration BMC timed out at its 120-second limit. No pass at the requested depth is claimed. |
| Same integration command with `--emitted build/t13/store-qualified/emit/asic --output build/t13/formal-btor` | Unresolved with the alternative pinned engine and unchanged bound/timeout. |
| `python3 hw/ip/perf_core/formal/check_float_integration.py --fpu-contract --emitted build/t13/load-commit/emit/asic --output build/t13/formal-contract2` | Unresolved: exact integrated-FPU/T12 equivalence and instrumentation/production binding passed; compositional integration BMC still timed out at 120 seconds. Its negative-control/cover stages did not run. |
| `python3 -m unittest discover -s dv/core -p 'test_*.py' -v` | PASS; `Ran 33 tests`; `OK`. Includes narrow QEMU reentry/finisher fault controls. |
| `python3 tools/check_structure.py --include-untracked` | PASS; exit 0, rerun after the new proof and receipt tools. |
| `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"` | PASS; 51 tests across 15 suites, zero failures; `All tests passed.` |
| `python3 hw/ip/fpu/formal/check_add.py` | PASS; six widths plus exact signed exponent subtraction, eight rejected faults. |
| `python3 dv/core/revision_equiv.py --before build/emit/perf_core --after build/t13/exponent/candidate --output build/t13/exponent-equivalence` | PASS; unbounded whole-top named-state equivalence (405 state elements), no added assumptions, all four fault controls rejected. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/exponent/emit/asic --output build/t13/timing-exponent` | PASS; `24.698816 ns, budget 24.960000 ns; electrical violations 0`. |
| `python3 dv/fpu/check.py --output build/t13/fpu-revalidation` | PASS; complete T12 regression including 184380 vectors, QEMU, all protocol/fault checks and standalone timing (24.421045 ns). |
| `python3 dv/core/lockstep.py --candidate build/t13/exponent/candidate --isa rv32imfc --suite arch,random,flight-float --output build/t13/lockstep-exponent` | PASS; same architectural/random/flight retirement totals, `PASS selected F lockstep suites`. |
| `python3 -m unittest discover -s dv/core -p 'test_*.py' -v` | PASS; 36 tests, including focused formal selection rejection controls. |
| `python3 -m unittest discover -s hw/ip/fpu/formal -p test_receipt.py -v` | PASS; seven receipt authenticity/mutation regressions. |
| `python3 hw/ip/fpu/formal/check.py` (final authenticated rerun) | PASS; all seven roles, exact protected snapshot recorded. `PASS formal progress_fault ... 'fault rejected'`. |
| `python3 hw/ip/perf_core/formal/check_float_integration.py --fpu-contract --prove --emitted build/t13/exponent/emit/asic --output build/t13/formal-pdr` | PASS; all 28 safety assertions proved with ABC PDR (7 seconds wall time reported by SBY); commit fault rejected; eight abstract-model covers witnessed. No new environment assumptions. |
| `python3 dv/core/equiv.py --unchanged-since t11-baseline --candidate build/t13/exponent/candidate --output build/t13/unchanged` | PASS; 12 untouched active modules with real fault controls, rebuilt tagged baseline. |
| `python3 hw/ip/perf_core/formal/check_no_f.py --baseline build/t13/unchanged/baseline --candidate build/t13/exponent/candidate --output build/t13/no-f-local` | PASS; compressed conditional combinational equivalence, CSR conditional induction with 22 legacy states and two added zero-state invariants; three actual SAT fault counterexamples. |
| `python3 dv/core/riscv_formal.py --target candidate --candidate build/t13/exponent/candidate --checks jalr,lw,c_add --timeout 120 --output build/t13/rvf-critical` | UNRESOLVED; each normal BMC reached TIMEOUT without a counterexample. No covers/fault controls or ISA pass claimed. |
| Same ISA runner with `--checks jalr --prove-window --timeout 120 --output build/t13/rvf-jalr-pdr` | UNRESOLVED; single induction trial over the same fixed startup-window checker also reached TIMEOUT without a counterexample. Further retries stopped. |
| `python3 dv/core/riscv_formal.py --target candidate --candidate build/t13/exponent/candidate --checks jalr --split-assertions --prove-window --timeout 120 --output build/t13/rvf-jalr-split` | UNRESOLVED; six of 33 original assertions pass separately, partition 06 (`rvfi_insn_check.sv:171`) times out at 120 seconds without a counterexample. No later partitions, cover or RTL fault jobs run. |
| `python3 -m unittest discover -s dv/core -p 'test_*.py' -v` (partition continuation) | PASS; 41 tests, `OK`; five partition tests include mutation rejection. |
| `python3 tools/check_structure.py --include-untracked` (partition continuation) | PASS; exit 0. |

The original integration counterexample (`formal-check`) was an unsolicited
post-reset memory response causing inherited LSU writeback before an instruction
was valid. The new F-profile writeback guard addresses it without adding an
assumption or removing the assertion. The next counterexample (`formal-qualified`)
was a monitor-lifetime bug: it attributed pre-request errors to a later successful
FLW. Independent review confirmed this; the scoreboard now starts at LSU issue,
with owned errors winning simultaneous issue clearing. No load-failure assertion
was removed. Corrected bounded runs reached timeout without another counterexample. The final
induction run proves all 28 assertions under the authenticated protocol model.
Its eight covers are reachability witnesses in that overapproximation, not
concrete-production FPU reachability; the separate T12 covers and simulation
supply complementary concrete evidence.

Routine fixture/tool corrections: generate the existing flight parameter include;
recognize the compiler's compressed finisher; place the interrupt vector in its
own aligned section; avoid a Yosys duplicate automatic-name error from applying
`setundef` both before JSON export and again inside SBY. QEMU emits identical
non-retired snapshots after certain MMIO boundaries. Filters require the exact
marker/load or MSIP-clear/CSR-read pattern and unchanged state; mutations fail.

Remaining acceptance is not claimed: IF conditional composition,
resolved critical ISA checks, and a focused T13 local gate. The pinned instruction
checker does not support CSR/F verification; local CSR proofs, integration
properties, T12 evidence and lockstep carry those separate obligations.
The full local CI and hours-long ISA sweep were not run, per the user's instruction.

### Capture source correspondence and arithmetic (2026-11-16)

Commands use the pinned environment through `python tools/env/run.py run --`.
Measured on base `11c72b3` plus protected working-tree hashes:

```text
python3 dv/core/check_jalr_capture.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-capture
  source-prove PASS (unbounded abc pdr), 28.087467 s
  source-zero cover PASS, 1.807055 s
  ValueError: No active source-zero witness (post-processing; see below)
python3 dv/core/check_jalr_capture.py --baseline build/t13/jalr-address-strengthened --resume-from build/t13/jalr-capture --output build/t13/jalr-capture-resumed
  source-prove PASS (reused exact model/configuration)
  source-zero PASS (existing trace reparsed)
  source-alias PASS, 1.804066 s
  source-fault FAIL as required, 1.920735 s
  RuntimeError: JALR capture arithmetic-prove: TIMEOUT
  arithmetic wall time 121.357526 s; unchanged 120-second cap
python3 dv/core/audit_jalr_capture.py --output build/t13/jalr-capture-resumed
  PASS source-only audit: input/witness hashes valid; wrong-opcode guard rejected
  Aggregate remains: unresolved; arithmetic: TIMEOUT
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 66 tests; OK
```

The source proof jointly asserts inherited target transport and correspondence
between captured, encoded-x0-normalized source data and the normalized RVFI
source. Covers include encoded x0 and nonzero rs1=rd; the actual RVFI source-bit
fault is rejected with expected0/reported1. The guard-negative audit rejects
opcode0x66 in place of0x67. Original reset/clock assumptions are unchanged;
no no-trap guard, peer assumption or source-valid guard suppresses a retirement.
The arithmetic job proves neither a bounded nor an unbounded result; it emits
no counterexample. Fail-fast leaves negative-immediate/odd-sum covers and the
arithmetic fault unrun. No aggregate checker or ISA pass is claimed.

The initial post-processing parser required an unused arithmetic signal that
Yosys omitted from the source-only trace. Role-specific required fields repair
this without changing a property. The exact originally executed script is
archived under `build/t13/jalr-capture/check_jalr_capture.executed.py`, matching
its recorded SHA256; the original raw receipt is untouched. Resume authenticates
all old inputs, requires byte-identical generated models and configurations
identical except for model paths, checks actual status files and reparses
witnesses. Independent review cleared that reuse and the source witnesses.
No successful sequential proof was rerun for the parser repair. Independent
review also clears the final source-only audit, its wrong-opcode witness and
explicit preservation of the arithmetic timeout.

Independent read-only diagnosis suggests the remaining proof spans registered
execute-request ownership and arithmetic together: the response originates from
saved request operands, whereas the predicate uses the current ID/RF operand.
This is an inference about proof complexity, not an established hardware bug.
The proposed next split is request/operand/phase alignment plus an independent
ADD response equation against the saved request; both would require proved
assertions, active covers and actual faults before composition. The narrower monitors are now implemented in
`JalrRequestProperty.scala` and run by `check_jalr_request.py`; they are not
accepted as an ISA proof. The request-alignment assertion requires response
validity, ALU kind, ADD operation, first-cycle status and equality of both saved
operands under the original capture guard. No prerequisite is assumed.

The new Python synthetic binding test initially aliased its expected/actual
fixture lists, causing its intended width fault to mutate both sides. Independent
lists repair the fixture; no tested assertion was relaxed. Subsequent command
`python3 -m unittest discover -s dv/core -p test_*.py` passes all68 tests in
1.476 s measured. `python3 tools/check_structure.py --include-untracked` passes
with exit0. These are harness/structure results, not full local-gate acceptance.



Further focused command, measured on the same base and protected inputs:

```text
python3 dv/core/check_jalr_request.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-request
  RuntimeError: JALR request alignment-prove: TIMEOUT
  unchanged 120-second cap; no counterexample
```

The result receipt records wall time 122.057978 s. Fail-fast leaves the
alignment covers/fault and all local execute-ADD roles unrun. The free-input
external activation qualification passed, but its companion negative audit
has not run; no completed request/alignment/arithmetic proof is claimed.
Independent review cleared the new code and unchanged production model, not
an alignment proof; final review verified all protected inputs, timeout status
and absence of counterexample traces or later jobs. The subsequently approved exact six-conjunct partition diagnostic is recorded
below; it isolates a timeout in the saved ALU-kind condition, with response
validity passing and all other conditions still mandatory. Further solver attempts stopped after this
unresolved narrower boundary; original ISA acceptance, IF composition and local gate
remain open. No commit or push.

### Exact alignment-conjunct diagnostic (2026-11-16)

Measured on `11c72b3` plus authenticated working-tree inputs, using the pinned
container through `python tools/env/run.py run --`:

```text
python3 dv/core/split_jalr_alignment.py --baseline build/t13/jalr-request --output build/t13/jalr-alignment-split
  PASS alignment conjunct: response-valid
  RuntimeError: Alignment conjunct alu-kind: TIMEOUT
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 71 tests in 1.386s
  OK
python3 tools/check_structure.py --include-untracked
  exit 0
```

Free-Boolean decomposition qualification passes; the omitted-immediate-condition
negative is rejected with capture true, the first five conditions true and the
omitted condition false. All six original conditions remain inventoried and
mandatory. Original guard/enable and every production/environment object are
unchanged; no peer assertion becomes an assumption. The response-valid partition
proves unbounded in 3.962384 s measured, but this is partial diagnostic
evidence without completed cover/fault qualification. The saved ALU-kind
partition times out at the unchanged120-second cap, wall 121.125216 s measured,
with no counterexample or trace. Fail-fast leaves ADD operation, first-cycle,
source-operand and immediate-operand partitions unrun. Original alignment covers,
faults, local ADD and full ISA acceptance remain unresolved.

Independent review verified the partition transformation, semantic leaf bindings,
Boolean negative witness, all protected hashes and final statuses. The test suite
independently exhausts all Boolean guard/condition assignments and rejects changed
guards/enables/operand widths and incomplete/duplicate inventories. No new RTL,
production change, timeout increase, acceptance waiver, commit or push occurred.
The first isolated obstacle is request-type ownership at capture, before operand
addition is part of the asserted predicate; this does not establish an RTL bug
or identify every remaining difficult condition. Independent review recommends
next observing actual request acceptance: prove that an accepted first-phase JALR
has incoming ALU kind, then separately prove that redirect capture still owns
that instruction/PC/phase through reset, response consume and request replacement.
Any ghost tracking must assert this relation, never assume it, and reuse prior
request capture/hold evidence only with exact authenticated applicability.

### Actual accepted-request tracking (2026-11-16)

Measured on `11c72b3` plus protected working-tree inputs, through the pinned
`python tools/env/run.py run --` environment:

```text
python3 dv/core/check_jalr_ownership.py --baseline build/t13/jalr-address-strengthened --output build/t13/jalr-ownership
  issue-prove PASS; issue-cover PASS; issue-fault FAIL as required
  retention-prove PASS; retention-cover PASS; retention-fault FAIL as required
  ValueError: No active retention-fault witness (post-processing only)
python3 dv/core/check_jalr_ownership.py --baseline build/t13/jalr-address-strengthened --resume-from build/t13/jalr-ownership --output build/t13/jalr-ownership-resumed
  first six jobs reused after exact model/configuration/status authentication
  JALR ownership retained-kind-prove: PASS
  RuntimeError: JALR ownership ownership-prove: TIMEOUT
python3 dv/core/audit_jalr_ownership.py --output build/t13/jalr-ownership-resumed
  PASS issue/retention/retained-kind audit; actual retained-kind fault rejected
  Identity status: TIMEOUT; aggregate: unresolved
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 74 tests in 1.843s
  OK
python3 tools/check_structure.py --include-untracked
  exit 0
```

| Obligation | Kind/status | Measured command wall time |
| --- | --- | --- |
| Accepted first-phase JALR kind is ALU | Unbounded PDR PASS | 3.948244 s |
| Request kind/phase retention and valid ownership | Unbounded PDR PASS | 4.052221 s |
| Recorded JALR kind remains ALU | Unbounded PDR PASS | 3.881496 s |
| Capture instruction/PC identity | TIMEOUT, no counterexample | 121.319890 s; cap120 s |

Issue/retention covers and their actual production-driver faults pass. The
companion retained-kind negative asserts the retained-state predicate alone,
so an earlier issue-predicate failure cannot terminate the witness prematurely.
It mutates the actual incoming kind at an accepted JALR; the trace subsequently
has ownerValid, ownerJalr and ownerKind1 with retainedKindHolds false. The
wrong-opcode external guard negative is also rejected. No assumption or
owner-valid precondition suppresses capture checks. The ghost tracks every
acceptance, including non-JALR requests, and clears only on actual consume/reset;
consume/capture checks use pre-edge state. Acceptance has priority, with mutual
exclusion asserted. Actual saved firstCycle is compared to the recorded ID phase.

The original retention-fault trace omitted unused ownerJalr. Role-specific
parsing repairs this without changing properties. The originally executed runner
is archived at `build/t13/jalr-ownership/check_jalr_ownership.executed.py`, with
its exact recorded hash. Original raw receipt is unchanged. Resume authenticates
all old inputs, byte-identical proof models, configurations differing only in
model path, actual status files and re-parsed witnesses. No completed sequential
job was rerun for this parser fix. Synthetic tests cover minimal optimized trace
fields and require a later retained-state violation after actual bad acceptance.

Capture identity times out at the unchanged120-second limit without a trace;
its x0/replacement covers and actual PC-bit fault remain unrun. The replacement
cover as implemented permits a previous different execution phase, including a
JALR link phase; it does not establish a non-JALR instruction history. No held
response or replacement coverage is claimed from unrun jobs. Full alignment,
arithmetic, ISA/IF acceptance and the local gate remain open. No commit/push.

Independent final review cleared the component proofs, reused receipts and
post-acceptance retained-kind fault. It requested direct protection of the
identity status file in the auditor; that check is now implemented. The original
executed auditor is archived with its recorded SHA at
`build/t13/jalr-ownership-resumed/audit_jalr_ownership.executed.py`; the old audit
and all positive-proof receipts are unchanged. The hardened command ran into a
separate directory:

```text
python3 dv/core/audit_jalr_ownership.py --output build/t13/jalr-ownership-resumed --audit-output build/t13/jalr-ownership-control-audit
  PASS issue/retention/retained-kind audit; actual retained-kind fault rejected
  Identity status: TIMEOUT; aggregate: unresolved
```

Only its short guard/negative qualifications were rerun; no positive PDR job was
repeated. For the next diagnostic, review recommends separating capture's
ownerValid/ownerJalr tags from the wider instruction/PC equality. Together with
proved retention and retained-kind relations, those tags would suffice for the
original ALU-kind condition; full instruction/PC identity and operand obligations
remain required. No tag proof or composition result is claimed yet.

### Capture ownership flag partition (2026-11-16)

Measured on `11c72b3` plus authenticated working-tree inputs in the pinned
container (`python tools/env/run.py run --`):

```text
python3 dv/core/split_jalr_ownership.py --baseline build/t13/jalr-ownership-resumed --output build/t13/jalr-ownership-split
  PASS ownership conjunct: owner-valid
  RuntimeError: Ownership conjunct owner-jalr: TIMEOUT
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 77 tests in 1.320s
  OK
python3 tools/check_structure.py --include-untracked
  exit 0
```

The exact five-condition union is ownerValid, ownerJalr, ownerFirst,
ownerInstruction==idInstruction and ownerPc==idPc, all under the original capture
guard. Free-Boolean SAT qualification passes; omitting PC equality is rejected
with capture and the other four conditions true. Each partition preserves all
production/ghost state, assumptions, interfaces and assertion enable; no peer
assertion is assumed. All five remain mandatory.

Capture owner-valid **unbounded PDR PASS**, 6.300894 s measured. Capture
owner-JALR **TIMEOUT** at unchanged120-second cap, wall 121.409461 s measured,
without a counterexample. Fail-fast leaves first-phase, instruction and PC
identity partitions unrun. These positive partitions remain diagnostic until
cover/fault qualification; no aggregate ownership or derived ALU-kind proof is
claimed. In particular, owner-JALR still needs proof before retention and
retained-kind results can establish the original kind-at-capture obligation.

Independent review cleared exact split semantics, production preservation,
negative witness and meaningful synthetic tests. An initial test fixture shared
comparison/net lists, so its operand mutation affected both sides; independent
fixture copies repair the test without changing an assertion or tolerance. The
final tests cover all64 Boolean assignments and reject changed guards, enables,
identity operands/widths and incomplete/duplicate inventories. The owner-JALR
timeout occurs without wide instruction/PC equality in the asserted predicate;
removing those comparisons has not resolved this control-ownership obstacle.
No new production RTL, longer job limit, commit or push.

Independent final review authenticated all protected inputs and final statuses;
read-only phase/control inspection found no concrete stale-response defect.
The recommended next diagnostic is a transition-local assertion: an outstanding
integer execute request, absent consume/reset, prevents actual combinational IF
instruction-write and ID-clear events and preserves the ID phase/tag across the
edge. Observe the actual IF write-enable, not registered instr_new_id_o.

If FPU state dominates that control proof, the existing FpuProtocolModel is a
possible substantive reduction, contingent on authenticated concrete-port-trace
inclusion. Require exact current integrated/T12 FPU binding, unchanged non-FPU
state/environment and arbitrary finish/result/flags without fairness/deadlines.
Every model restriction needs evidence, including reset/cancel payloads and no
same-edge acceptance/completion; the prior integration assertion result alone
is insufficient for that last restriction. Preserve concrete timeout receipts.
No new phase-stability or abstract ownership proof has run; no arithmetic or
ISA acceptance condition changes.


### Transition-local phase stability (2026-11-16)

Measured on `11c72b3` plus authenticated working-tree inputs via the pinned
`python tools/env/run.py run --` environment:

```text
python3 dv/core/check_phase_stability.py --baseline build/t13/jalr-address-strengthened --output build/t13/phase-stability
  Phase stability write-prove: PASS
  Phase stability write-cover: PASS
  Phase stability write-fault: FAIL (required real fault)
  Phase stability clear-prove: PASS
  Phase stability clear-cover: PASS
  Phase stability clear-fault: FAIL (required real fault)
  Phase stability step-prove: PASS
  Phase stability step-cover: PASS
  Phase stability step-fault: FAIL (required real fault)
python3 dv/core/audit_phase_stability.py --output build/t13/phase-stability
  PASS phase stability audit: input/witness hashes valid; wrong-opcode guard rejected
python3 dv/core/strengthen_jalr_ownership.py --phase build/t13/phase-stability --owner build/t13/jalr-ownership-resumed --output build/t13/jalr-ownership-strengthened
  inherited-monitor named-state equivalence: proved
  inverted inherited owner-JALR binding: rejected
  RuntimeError: Strengthened owner-JALR: TIMEOUT
python3 -m unittest discover -s dv/core -p test_*.py
  Ran 81 tests in 1.789s
  OK
python3 tools/check_structure.py --include-untracked
  exit 0
```

| Property | Result | Measured command wall time |
| --- | --- | --- |
| No IF instruction write while holding | Unbounded PDR PASS | 10.610338 s |
| No ID clear while holding | Unbounded PDR PASS | 7.818669 s |
| Instruction/PC/phase tag stable across a holding edge | Unbounded PDR PASS | 12.955898 s |
| Owner-JALR plus all three asserted phase invariants | TIMEOUT, no counterexample | 121.178246 s; cap120 s |

Holding includes a just-accepted request or existing owner and excludes actual
consume/reset. It applies to all integer requests, with no JALR precondition.
The full tag includes instruction, PC, valid, first-phase, compressed and dummy
bits. The delayed check uses the tag and holding sampled on the same edge and
is disabled only by reset/priorHolding, never by current ownership or consume.
Actual IF `newInstruction` is the production ID-register D-mux select, not the
registered instr_new pulse. Write/clear faults modify real production pulse
drivers. The phase fault modifies the actual first-phase driver under registered
stabilityActive and yields currentTag=previousTag XOR4, avoiding combinational
fault-enable feedback. Independent review clears all nine jobs, source/witness
hashes and the companion guard negative. This proves phase stability, not ISA.

An initial companion-audit key mismatch (`retirement` versus the runner's
`event`) failed in post-processing, not formal. Its failed receipt remains in
`audit.parser-error.json`. Correcting the key did not rerun a sequential proof.
The final audit validates the actual active witnesses and recorded hashes.

The strengthened job reuses the audited phase prepared model. It keeps the
original step assertion and adds no-write, no-clear and capture=>ownerJalr as
assertions; no peer assumption is introduced. Its inherited ownership monitor
is projected to the exact old interface and checked by named-state induction
with equal reset/clock/transition/output semantics; SAT time0.064738 s measured.
An inverted inherited tag output is rejected. This is stronger qualification
than comparing two output formulas with unrelated state. The full production
proof still times out at the unchanged short cap, without a counterexample.
Its active target cover/fault and wider composition remain pending. Independent
review verifies inherited-state reset/clock/transition/output correspondence,
exact preservation of the full phase/production model and final timeout hashes.
No further global solver retry, longer timeout, acceptance waiver, commit or push.

The next recommended step is a small compositional induction, not another global
retry. Let J(tag) be valid, noncompressed, nondummy first-phase JALR, and prove
ownerValid implies ownerJalr equals J(currentTag). Reset establishes the relation;
exact ghost acceptance/consume transitions and proved tag stability preserve it.
The proved retention assertion also excludes simultaneous accept/consume, which
is necessary on the acceptance case. Authenticated capture=>ownerValid and the
structural capture=>J(tag) then imply ownerJalr at capture. Qualify every ghost
D/reset/clock equation and predicate against the emitted monitor, and encode
base/step/final as free-state SAT implication assertions with explicit proved
theorem antecedents, not production assumption cells. Mutation negatives and
active capture/ownership-fault evidence remain mandatory. This compositional
proof has been reviewed as a proposed method only; it has not been executed.

## Numbers

Measured by the commands above on `11c72b3` plus the source hashes recorded in
receipts:

- Current lockstep: 21776 architectural retirements, 1634 seeded mixed-stream
  retirements with six software interrupts, and 191201 hard-float flight
  retirements. FP operands/results/state and memory are compared at retirement;
  architectural/random FCSR probes check flags. Flight flags are not independently
  observed by the text ISS interface. Eight checker mutations were rejected.
- Current mapped core area: **875676.2560 um2**; worst path **24.698816 ns**;
  zero electrical violations. This includes the core/FPU/register files/clock
  gate, not the MCU SRAM/peripherals or physical layout.
- Previous failing path: `_56440_/Q` (`floatExecution.fpu.c[24]`) to `_57285_/D`
  (`after.io_fromPreMul_sExpSum[4]`), through the preMul exponent subtraction.
- Timing history (all measured, same constraint): initial 29.036039 ns;
  registered metadata 26.152401; selected instruction 24.976124; corrected CSR
  qualification 25.454292; completion boundary 25.303064; arithmetic commit
  25.052952; integer write qualification 25.673807; store qualification
  25.046576; load commit 25.290892. Each is a distinct retained failing snapshot,
  not a pass or a relaxed threshold.
- Assumed unchanged budget: **24.96 ns** = 41.6 ns times 0.60. GF180 7t5v0,
  SS/125C/3.0V, assumed 0.5 ns slew and 0.05 pF load, ideal clock, pre-layout
  mapping with no wire delay. Tool/library/flow hashes are in each timing receipt.
- Structural latency estimate: completion registration adds one clock per
  execution phase; the CSR request path needs one further qualification clock.
  No end-to-end flight rate/area-fit conclusion is drawn from these checks.

## Deviations from the brief

The user approved registered F decode and continued core timing closure after
seeing the initial failure. The constraints and assertions remain intact.
Independent review guided the CSR qualification, response ownership, phase-write
settling, and monitor correction. Current default-profile equivalence passed.

F-enabled exact cycle equivalence to T11 is not a valid blanket claim: misa.F,
added phase latency, cycle-counter observations and wall-clock interrupt timing
are explicit differences. Retirement/refinement checks and conditional local
proofs must carry this profile; its ISA evidence cannot be transported by the
F-disabled equivalence result.

The prior failing path was internal HardFloat arithmetic. T13's May-change
list permits FPU interface glue only. The user explicitly approved extending this
scope on 2026-11-15 to the existing HardFloat patch and exact arithmetic proofs.
The independently reviewed implementation is an exact, latency-preserving replacement of
`sNatCAlignDist = sExpAlignedProd - rawC.sExp` with the existing prefix adder:
sign-extend the signed ten-bit second operand to eleven bits before complement,
add carry one, then reinterpret the eleven-bit result as signed. No vendor
snapshot edit, pipeline cycle or timing-budget change was made.

The proof receipt now captures production and prepared-model inputs before use,
checks that they remain unchanged, and requires an exact protected inventory.
This fixes stale-PASS reuse and regeneration races identified by independent
review. A queued obsolete proof rerun was canceled before emission/proving; its
running receipt is not evidence. A subsequent attempt hit the existing emission
timeout while waiting for the full Scala-suite build lock; it was rerun after
that suite finished, without increasing any timeout. Only the final authenticated run may feed
T13's FPU contract abstraction.

The user approved exact critical-ISA assertion partitioning on 2026-11-15.
The complete original prepared model (including setundef and clock/reset stimulus)
is partitioned by deleting only nonselected assertion cells, never replacing them
with assumptions. Every selected cell and all other model content stay identical;
all original assertions must appear exactly once before aggregate success. Every
job retains depth 144/check64 and the 120-second cap. Covers and real RTL faults
remain mandatory after the positive assertion set passes.

The initial JSON reload hit a Yosys setundef automatic-name collision before any
solver started. Private generated setundef cell keys are now renamed reversibly;
cell parameters/connections/attributes are byte-structurally unchanged, and raw
and stabilized hashes plus the inverse map are recorded. Independent review
verified all seven executed models/configurations and exact assertion accounting.
The first tooling receipt was overwritten on rerun; its captured error is
transcribed, explicitly as a note rather than a fresh receipt, in
`build/t13/partition-tooling-note.txt`.

## Open issues

- Complete original JALR acceptance is independently cleared through exact
  assertion accounting and concrete qualification. Preserve all historical
  timeout/failure receipts; they are not retroactively relabeled passing.
- Resolve the remaining critical `lw` and `c_add` ISA checks at the unchanged
  depth 144/check cycle 64 and 120-second cap, using a justified reduction rather
  than repeated full-model attempts. The widened-model LW attempt at
  `build/t13/critical-wide/result.json` timed out (rc8, measured 121.48 seconds
  including cleanup), with no counterexample; fail-fast left C.ADD and concrete
  qualification unrun in that invocation. The isolated C.ADD run at
  `build/t13/critical-c-add-wide/result.json` also times out without a
  counterexample (rc8, measured 121.484 seconds including cleanup); its
  concrete qualification remains unrun. The full instruction sweep remains unrun
  under the user's instruction to focus on critical checks.
- New review finding: the original formal `FpuProtocolModel` shares one arbitrary
  payload for invalid response data and next valid completion data. Exact
  all-port trace inclusion is therefore not established. Preserve its old
  28-safety receipt as a result for that model, not as independently qualified
  full-port overapproximation evidence. The new model with independent invalid and
  completion payloads now has independently reviewed exact concrete trace
  inclusion. The same 28 assertions and eight abstract-model covers now pass,
  with an independently reviewed fresh 271-state production binding. These
  covers do not establish concrete execution coverage; no production RTL bug
  is inferred from this model gap.
- IF conditional proof is independently cleared for its explicit raw-encoding
  domain. It excludes the four compressed F encodings even on invalid/error
  payloads; it is not whole-core latency refinement. Pinned riscv-formal does
  not provide CSR/F checks; local CSR/integration properties, T12 and lockstep
  provide the separate evidence described above.
- The focused T13 local gate cannot pass while critical ISA evidence is
  unresolved. Resolve that evidence before a fresh final gate and acceptance
  review; the scoped gate was independently reviewed and remains fail-closed.
  Production RTL did not change during this continuation; previous measured
  timing, FPU vectors and architectural/random/flight lockstep remain recorded.
- The user explicitly authorized committing and pushing this incomplete T13
  checkpoint for review on 2026-11-16, including the problem description in
  the commit. This authorization does not mark T13 complete or waive any check.
  The existing `t11-baseline` tag accompanies the checkpoint so reviewers can
  resolve its comparison baseline. Generated evidence remains ignored under
  `build/`; commands, results and limitations are recorded here. No formal
  sweep was repeated for the checkpoint commit.
