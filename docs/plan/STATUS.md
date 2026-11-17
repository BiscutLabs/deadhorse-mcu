# Status

Single progress tracker. Last updated: 2026-11-16.
States: `[ ]` not started, `[~]` in progress, `[!]` blocked, `[x]` complete,
`[-]` withdrawn.
Decision checks record the user's approvals, not implementation completion.
No implementation task or gate is completed by the planning reconciliation.

## Decisions

Details: [10-decisions-and-risks.md](10-decisions-and-risks.md).

| | ID | Decision | State |
| --- | --- | --- | --- |
| [x] | D1 | RISCay import | Approved direction; qualification remains open |
| [x] | D2 | Performance core | Approved direction; qualification remains open |
| [x] | D3 | Internal NoC | Superseded by D43 |
| [x] | D4 | Initial-chip scope | Approved direction; qualification remains open |
| [x] | D5 | Debug hardware | Approved direction; qualification remains open |
| [x] | D6 | Low-frequency clock | Approved direction; qualification remains open |
| [x] | D7 | Sleep peripherals | Approved direction; qualification remains open |
| [x] | D8 | Production test | Approved direction; qualification remains open |
| [x] | D9 | Physical flow | Approved direction; qualification remains open |
| [x] | D10 | Clocked islands | Superseded by D17 |
| [x] | D11 | USB cutoff | Approved direction; qualification remains open |
| [x] | D12 | Memory capacity | Approved direction; qualification remains open |
| [x] | D13 | Control-loop target | Approved direction; qualification remains open |
| [x] | D14 | NoC source ownership | Superseded by D43 |
| [x] | D15 | Standard-cell library | Approved direction; qualification remains open |
| [x] | D16 | Design language | Approved direction; qualification remains open |
| [x] | D17 | Timing discipline | Approved direction; qualification remains open |
| [x] | D18 | Historical lite-core option | Deferred historical option; no initial implementation |
| [x] | D19 | FPU inclusion | Approved direction; qualification remains open |
| [x] | D20 | FPU implementation | Approved direction; qualification remains open |
| [x] | D21 | Actuator publication | Approved direction; qualification remains open |
| [x] | D22 | UART sleep modes | Approved direction; qualification remains open |
| [x] | D23 | Tool environment | Approved direction; qualification remains open |
| [x] | D24 | Buses and ownership | Approved direction; qualification remains open |
| [x] | D25 | DMA | Approved direction; qualification remains open |
| [x] | D26 | IMU | Approved direction; qualification remains open |
| [x] | D27 | Barometer | Approved direction; qualification remains open |
| [x] | D28 | GPS and compass | Approved direction; qualification remains open |
| [x] | D29 | Airspeed | Approved direction; qualification remains open |
| [x] | D30 | RC | Approved direction; qualification remains open |
| [x] | D31 | Actuator fault detection | Approved direction; qualification remains open |
| [x] | D32 | Actuator count | Approved direction; qualification remains open |
| [x] | D33 | Actuator parts | Approved direction; qualification remains open |
| [x] | D34 | Boot authentication | Approved direction; qualification remains open |
| [x] | D35 | External clock | Approved direction; qualification remains open |
| [x] | D36 | Performance SRAM access | Approved direction; qualification remains open |
| [x] | D37 | Reset containment | Approved direction; qualification remains open |
| [x] | D38 | Supply monitor | Approved direction; qualification remains open |
| [x] | D39 | Pin multiplexing | Approved direction; qualification remains open |
| [x] | D40 | USB boundary | Approved direction; qualification remains open |
| [x] | D41 | Debug access policy | Approved direction; qualification remains open |
| [x] | D42 | Fabrication target | Approved direction; qualification remains open |
| [x] | D43 | Whole-chip bus, no NoC | Approved direction; qualification remains open |
| [x] | D44 | Multiply/divide formal split | Approved change of acceptance; not yet implemented |

## Tasks

| | ID | Item | Owner | Depends on | Report |
| --- | --- | --- | --- | --- | --- |
| [x] | PLAN01 | [Reconcile decisions](tasks/PLAN01-reconcile.md) | Codex | User approvals | [Report](tasks/reports/PLAN01.md); documentation only |
| [x] | T08 | [Pinned Linux environment](tasks/T08-environment.md) | Codex | none | [Report](tasks/reports/T08.md); clean rebuild and runtime smoke pass |
| [x] | T01 | [Scaffold/CI](tasks/T01-scaffold.md) | Codex | T08 | [Report](tasks/reports/T01.md); local gate and fresh-context review pass |
| [x] | T02 | [Historical loop CI](tasks/T02-flight-loop-ci.md) | Codex | T01, T08 | [Report](tasks/reports/T02.md); exact QEMU matches, historical summary preserved, local gate passes |
| [-] | T03 | Interconnect study | n/a | n/a | Withdrawn by D43; no source imported |
| [-] | T04 | Interconnect study | n/a | n/a | Withdrawn by D43 |
| [x] | T06 | [RISCay baseline](tasks/T06-riscay-baseline.md) | Codex | T01, T08 | [Report](tasks/reports/T06.md); upstream gates/export pass, area within tolerance, local gate and independent review pass |
| [x] | T07 | [Chisel build](tasks/T07-chisel-build.md) | Codex | T01, T06, T08 | [Report](tasks/reports/T07.md); direct build, simulation, both formal routes, local gate and independent review pass |
| [x] | T05 | [Register generator](tasks/T05-regmap-generator.md) | Codex | T07 | [Report](tasks/reports/T05.md); generator/model, simulation, both formal routes, local gate and independent verification pass |
| [x] | T09 | [Timing flow](tasks/T09-timing-flow.md) | Codex | T01, T06, T07, T08 | [Report](tasks/reports/T09.md): timing gate and authorized RegBlock repair verified |
| [x] | T10 | [Ibex reference and harness](tasks/T10-ibex-reference.md) | Codex | T07, T08 | [Report](tasks/reports/T10.md): sequential/whole-core harness, candidate suites and divide stress pass; full local gate and independent review pass; D44 limits retained |
| [x] | T11 | [Ibex conversion](tasks/T11-ibex-conversion.md) | Codex | T10, T09 | [Report](tasks/reports/T11.md): user-approved focused verification complete; exact revision proof carries prior ISA evidence; current tests/timing/lockstep and independent review pass; repeated full CI stopped, not passed |
| [x] | T12 | [FPU](tasks/T12-fpu.md) | Codex | T07, T09 | [Report](tasks/reports/T12.md): standalone RV32F, focused local gate, arithmetic-abstracted control proof, reference tests, GF180 timing and independent review pass; full CI intentionally not rerun |
| [!] | T13 | [F integration](tasks/T13-core-f-integration.md) | Codex | T11, T12 | [Faithful 9.6 MHz trial](tasks/reports/T13-faithful-9p6mhz.md) fails 65.306 ns / 62.5 ns; fast passes in 475.169 s; default unchanged, full not rerun and acceptance incomplete |
| [ ] | S1 | [Core measurement](tasks/S-spikes.md#s1-core) | unassigned | T13, T09, T02 | Architecture selected; measurements outstanding |
| [ ] | T14 | [Bus, bridge and mailbox](tasks/T14-bus-mailbox.md) | unassigned | T07, T09 | Replaces the NoC work |
| [-] | S2 | Interconnect study | n/a | n/a | Withdrawn by D43 |
| [ ] | S3 | [Memory](tasks/S-spikes.md#s3-memory) | unassigned | T02, T07, T08 | |
| [ ] | S4 | [Latency/test](tasks/S-spikes.md#s4-latency-and-test-access) | unassigned | S1, T08, T09 | |

Former P0-f/P0-g now have briefs T08/T09. P0-a actuator split and P0-b parts
are approved decisions D26-D33, not bench qualification. P0-c USB boundary is
approved; implementer delivery/sizing remains open. P0-d die-link agreement is
deferred. P0-e analog work has not started and still needs an assigned brief.

## Gates (not checked by PLAN01)

**G0**

- [ ] D1/D2 recorded and reviewed against the implementation briefs
- [ ] Scaffold and CI working
- [ ] USB boundary and outstanding sizing/delivery assumptions reviewed

**G1: architecture freeze**

- [ ] Formal tool smoke and shared CDC proof
- [ ] S1 selected core/full F correctness, area, timing, loop target/fallback
- [ ] T14 bus, domain bridge and mailbox: contract reviewed, proofs, area/timing
- [ ] S3 memory capacity, banking and XIP validated
- [ ] S4 latency and production-test evidence
- [ ] Clock, reset, ownership/CDC partition and simultaneous pin map frozen
- [ ] Shuttle, library, SRAM and analog process options qualified
- [ ] USB reservation based on implementer evidence or explicitly omitted
- [ ] No unresolved assumptions affecting area, pads or clock domains

**G2: SoC/FPGA**

- [ ] Simulated flight and real sensor/actuator timing checks
- [ ] Independent channel rates, atomic publication, timeout/recovery validated
- [ ] Retained sleep, UART modes, DMA/ownership, wake and reset containment
- [ ] Both-core JTAG, boot/recovery, external-clock selection and USB stub/interface
- [ ] HF-off retained sleep demonstrated when no selected peripheral requires HF
- [ ] Clean CDC and every block within its GF180 timing budget or recorded exception
- [ ] Every block requiring a full proof has it or a recorded bounded-result reason
- [ ] riscv-formal passes on both cores; independent full-F verification; no unreviewed assumption
- [ ] Scan gate-level checks, SRAM self-test and analog test connectivity

**G3: physical signoff**

- [ ] Static timing
- [ ] Clock tree/gating
- [ ] Clock-domain crossings
- [ ] Reset
- [ ] Electrical rules
- [ ] SRAM timing
- [ ] DRC/LVS/antenna
- [ ] Post-layout simulation
- [ ] Scan
- [ ] Sleep current
- [ ] Equivalence before/after scan and final netlist
- [ ] USB integrated or cutoff applied before Phase 3 floorplan freeze

**G4: silicon**

- [ ] Bring-up, production test/calibration, characterization and flight validation

## Log

- 2026-11-16: T13 in progress -> blocked, Codex; faithful Chisel 9.6 MHz trial fails 65.305771 ns / 62.5 ns, with zero electrical violations and expected negative rejection. Independent review accepts the measurement; fast tier passes 21 commands in 475.169 s. Full tier not rerun. No production clock/profile or RTL behavior change; recommend a separately qualified 9 MHz trial. [Report](tasks/reports/T13-faithful-9p6mhz.md).

- 2026-11-16: T13 resumed for the approved faithful Chisel 9.6 MHz timing trial, Codex; preserve the default clock, all checks and both existing profiles. No RTL behavior change or full formal sweep.

- 2026-11-16: T13 12 MHz trial complete, Codex; both registered no-F and F cores pass the 50 ns allowance with unchanged margin/electrical checks and byte-identical RTL. Actual over-budget negative still fails; default-flow self-tests and fast tier (460.822 s) pass. Independent review clears the experiment. Global clock unchanged; full tier not rerun and T13 remains blocked on outstanding acceptance. [Trial report](tasks/reports/T13-12mhz.md).

- 2026-11-16: T13 resumed for the user-authorized 12 MHz timing trial, Codex; preserve default 24 MHz assumptions and failure evidence, use the same 60 percent margin and electrical checks, and independently review both core profiles. No full formal sweep or RTL change is planned.

- 2026-11-16: T13 in progress -> blocked, Codex; performance measured before proof work; approved three-rung triage accepts concrete LW (144/64) and abstracted shorter-window C.ADD (54/19), with concrete covers and both faults. Independently reviewed fast tier passes in 475.113 s. Requested full run fails registered no-F timing after 3217.428 s (51 commands passed, 26 unrun); no RTL or limit change. User-authorized commit/push follows fast acceptance; full/T13 completion not claimed. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 blocked -> in progress, Codex; pulled timeout-triage skill and user-authorized performance-first measurements, at most three triage rungs, fast/full CI tiers, report condensation and consolidation proposal. No RTL changes or further bespoke instruction proofs authorized.

- 2026-11-16: T13 remains blocked, Codex; user explicitly requested commit/push of the incomplete checkpoint for their review, with the unresolved formal-verification problem described in the commit. No acceptance requirement or status was changed; the existing T11 baseline tag accompanies the checkpoint.

- 2026-11-16: T13 in progress -> blocked, Codex; one native solver-query refinement and one exact two-group split preserve all checks. LW control/register partition passes at depth 144; memory/trap partition reaches the unchanged 120-second cap without a counterexample. No further cascade, concrete qualification or C.ADD runs were launched. Focused gate remains unresolved and T13 uncommitted; workflow commit `ac45fd4` is pushed.

- 2026-11-16: T13 continued, Codex; widened-model integration safety and fresh production binding pass independent review. One critical LW attempt reaches the unchanged short cap without a counterexample; C.ADD is checked separately. Focused gate authenticates prior evidence but correctly refuses unresolved critical checks.

- 2026-11-16: T13 continued, Codex; all33 original JALR assertions close with exact accounting, concrete covers/faults and independent review. Corrected FPU model has constructive trace inclusion; unchanged28 safety assertions/eight abstract covers pass, with fresh production-binding companion pending. Remaining critical load/compressed-add checks and final focused gate remain open.

- 2026-11-16: T13 continued, Codex; exact operand, RF source and capture/staged arithmetic compositions close original JALR next-PC assertion with active covers/faults and independent review. Local IF equivalence passes in explicit raw-encoding domain. 104 harness tests pass. Full critical-ISA accounting and final gate remain open; reviewer found an invalid/completion-payload coupling in the old FPU formal model, so a new inclusion-qualified model is being prepared without changing production RTL.

- 2026-11-16: T13 continued, Codex; exact monitor reset/step/final SAT composition proves full capture ownership identity with all mutation negatives and independent review. Active capture-valid and real production PC fault qualification pass; 88 harness tests pass. Workflow-only commit `ac45fd4` pushed separately. Remaining arithmetic, ISA/IF and local gate stay open; no full formal sweep.

- 2026-11-16: User authorized minor fixes and verification refinements with quick research and independent agent review; updated task workflow and resumed T13 compositional ownership checks. Acceptance requirements remain unchanged.

- 2026-11-16: T13 in progress -> blocked, Codex; no-write/no-clear/transition-tag stability prove unbounded with active covers, real faults and independent review. Authenticated inherited-monitor equivalence passes; one owner-JALR attempt retaining all three phase helpers as assertions still times out at unchanged120 seconds without counterexample. Eighty-one harness tests and structure pass; no further global retry, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved transition-local instruction/phase stability checks while integer execution is outstanding. Retain exact production model, assumptions, short limits and independent review.

- 2026-11-16: T13 in progress -> blocked, Codex; exact ownership split passes owner-valid, then times out on owner-JALR alone at unchanged120 seconds without counterexample. Remaining first/instruction/PC partitions unrun. Qualification and omitted-PC negative pass; independent review authenticates final models/statuses and finds no concrete stale-response defect. Seventy-seven harness tests and structure pass. No kind composition, acceptance waiver, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved isolating existing capture ownership flags from instruction/PC identity. Exact full-inventory partition, original assumptions and short limits retained; independent review required.

- 2026-11-16: T13 in progress -> blocked, Codex; actual accepted-request classification, kind/phase retention and retained JALR kind prove with active covers and real faults. Exact authenticated reuse resolves a trace-parser issue without rerunning completed proofs. Redirect instruction/PC identity times out at unchanged120 seconds without counterexample; later covers/fault unrun. Independent review clears scoped control evidence and authenticated reuse; hardened companion audit verifies identity status directly. Seventy-four harness tests and structure pass. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved observing actual request acceptance and tracking instruction/PC/phase through redirect capture. No assumptions or limits changed; independent review required.

- 2026-11-16: T13 in progress -> blocked, Codex; approved exact six-conjunct alignment diagnostic passes response validity, then times out on saved ALU-kind ownership at the unchanged120-second limit without counterexample. Remaining four partitions and original cover/fault/ADD obligations unrun. Boolean equivalence and omitted-condition negative pass, seventy-one harness tests and structure pass, and independent review verifies models/hashes/statuses. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved exact partitioning of the existing saved-request alignment conjuncts. Preserve the full condition inventory, unchanged production/environment, short limits and independent review.

- 2026-11-16: T13 continuation -> blocked, Codex; independently reviewed narrower saved-request alignment also times out at unchanged120 seconds without counterexample. Later covers/fault and local ADD roles unrun; independent final review verifies protected hashes/statuses and clears no proof result. Further solver attempts stopped. Sixty-eight harness tests and structure check pass; no acceptance waiver, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 continued autonomously, Codex; narrow diagnostic capture arithmetic timed out with original acceptance unchanged. Pursue independently recommended saved-request alignment and local ADD lemmas under the same short caps; no architecture or acceptance change.

- 2026-11-16: T13 in progress -> blocked, Codex; capture-source correspondence proves unbounded with active x0/alias covers and actual source-bit fault. Exact authenticated resume repairs a witness-parser issue without rerunning completed proofs. Capture arithmetic times out at unchanged120-second cap without counterexample; later arithmetic roles unrun. Source-only guard audit passes and retains unresolved aggregate status. Independent review clears reuse/source evidence; remaining acceptance prevents commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user requested autonomous continuation through remaining focused proofs and review, asking only for substantive problems. Continue capture arithmetic/source correspondence without changing checks or limits.

- 2026-11-16: T13 focused transport continuation completed, Codex; redirect capture/identity/retirement/RVFI transport proves unbounded within unchanged short cap; active cover, actual PC-bit fault and guard-negative audit pass. Independent review clears the scoped proof and audit; sixty-three Python tests pass. Target arithmetic and remaining acceptance keep T13 blocked; no complete-checker retry, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved the focused JALR redirect-target transport proof, retaining asserted capture validity, instruction identity, original environment and short limits.

- 2026-11-16: T13 in progress -> blocked, Codex; focused target-PC predicate passes exact guard qualification and sign-extension fault, but sequential proof times out at unchanged 120-second cap without counterexample. Later proof/cover/fault roles did not run. Repaired shared audit metadata using exact hash-matching immutable snapshots, without rewriting raw results or rerunning proofs. Sixty Python tests and structure check pass; independent review clears harness and metadata repair, not target proof or task acceptance. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user continued with the focused JALR jump-target PC proof, exact pinned-checker guards and independent review. Preserve every acceptance obligation and short limit.

- 2026-11-16: T13 focused return-value continuation completed, Codex; JALR link invariant proves unbounded and original line177 plus helper passes within unchanged 120-second cap. Exact guard qualification, wrong-increment rejection, active x0/nonzero covers and real output-fault witness pass independent review. Fifty-two Python tests and structure check pass. Remaining next-PC/ISA/IF/local gate keep T13 blocked; no complete-checker retry, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved targeted JALR return-value invariant and independent review. Preserve original guards, all acceptance obligations and the 120-second cap; no complete ISA sweep.

- 2026-11-15: T13 in progress -> blocked, Codex; approved all-retirement JALR address invariant and original address assertion pass with exact guard qualification, real fault/witness checks and independent review. One complete JALR attempt retains all original checks but times out at unchanged 120 seconds without counterexample; no sweep or further retry. Forty-seven Python tests and structure check pass. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 resumed, Codex; user approved one targeted all-retirement JALR source-address invariant, exact checker-guard qualification and independent review. Existing ISA checks and 120-second limit unchanged.

- 2026-11-15: T13 in progress -> blocked, Codex; approved exact ISA partitioning implemented and independently audited. Six of 33 JALR assertions pass, source-register-address assertion times out at unchanged 120 seconds without counterexample; fail-fast stops all later jobs. Forty-one Python tests and structure check pass. Original assertions, assumptions, depths, covers and fault obligations remain intact. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 blocked -> in progress, Codex; user approved splitting critical ISA assertions into smaller proof jobs. Preserve the complete assertion inventory, assumptions, depth 144/check cycle 64, 120-second limits, covers and real fault controls; no acceptance waiver.

- 2026-11-15: T13 in progress -> blocked, Codex; approved exponent repair passes timing, exact whole-top equivalence, complete FPU regression and 51 core tests. All 28 integration safety assertions prove unbounded under the authenticated FPU contract; fault/covers and local compressed/CSR proofs pass independent review. Twelve untouched modules prove against rebuilt T11. Three critical ISA bounds and one jump induction trial time out at 120 seconds without counterexamples; further retries stopped. Remaining refinement/local gate incomplete; no commit/push. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 blocked -> in progress, Codex; user approved the narrow internal FPU exponent-subtractor repair through the existing HardFloat patch, exact arithmetic proofs and revalidation. All timing and verification limits unchanged.

- 2026-11-15: T13 in progress -> blocked, Codex; core repairs and architectural/random/flight lockstep pass, default profile exactly matches tagged T11. Remaining timing path is internal FPU arithmetic outside the brief's interface-glue scope; narrow patch approval requested after independent review. Integration formal remains unresolved at unchanged short timeouts. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 blocked -> in progress, Codex; user approved registered F decode and continued timing closure with all checks and limits unchanged.

- 2026-11-15: T13 in progress -> blocked, Codex; initial integrated timing fails the unchanged budget. Independent review supports registered F decode; awaiting approval required by the brief. Work uncommitted; acceptance incomplete. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 not started -> in progress, Codex; user assigned next task with independent review and commit/push. Preserve T11 baseline tag, implement F integration first, keep checks focused without another hours-long ISA sweep.

- 2026-11-15: T12 in progress -> done, Codex; focused gate and independent review pass. Exact emitted-RTL identity qualifies canonical upstream-byte restoration. All operations retained; unchanged timing budget passes. [Report](tasks/reports/T12.md); T13 not started.

- 2026-11-15: T12 not started -> in progress, Codex; user assigned standalone FPU with independent review and commit/push. Focus checks on T12 per user direction; no repeated whole-core formal sweep.

- 2026-11-15: T11 in progress -> done, Codex; user directed critical verification instead of another hours-long sweep. Final CSR repair passes exact leaf/core/top and registered revision proofs, all 58 simulations, block/whole-top timing and current arch/flight lockstep. Independent review approved evidence transport from the prior complete ISA sweep. Full CI stopped at user direction, not reported as passed; no gate condition changed. [Report](tasks/reports/T11.md).

- 2026-11-15: T11 full local gate passed the registered ISA sweep but stopped on standalone CSR timing. An equivalent mstatus-only RMW repair passes configured proofs, CSR tests and block/whole-top timing; independent review approves. Exact CI check set retained with timing moved earlier; fresh full gate running. No commit/push or gate change.

- 2026-11-15: T11 gated-top qualification continues. Actual RF/core/ICG timing
  measured over budget; no timing acceptance claimed. Reference benchmark uses
  identical constraints and is explicitly comparison-only. Independent review
  approved clock-gate STA checks and benchmark isolation after clock-identity
  regression repair. Registered core directed tests and baseline leaf proofs
  pass; current full ISA, integration, timing and local CI remain pending.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved adding the shared GF180 clock-gate wrapper, verification and target bindings. All prior acceptance obligations remain; no gate marked complete.

- 2026-11-15: T11 in progress -> blocked, Codex; approved ID normalization passes all 20 configured cases and faults. Faithful Chisel core proves 163 states/one structural multiplier with all active translated children; core tests and fresh independent review pass. Required project clock-gate wrapper is absent; adding a shared implementation exceeds T11's interface-bundle allowance. [Scope proposal](../../hw/ip/perf_core/CLOCK-GATE-DEPENDENCY.md) awaits approval. Registered execution integration and full acceptance remain open; no commit/push or gate change.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved the single ID analysis-copy qualifier removal. Hash/location/reversal qualification and independent review precede acceptance; original failure and all verification obligations remain recorded.

- 2026-11-15: T11 in progress -> blocked, Codex; approved CSR normalization passes fresh proof/faults, tests, timing and independent review. ID translation tests/timing pass, but a separate unique-case selector produces the same unrestricted-input proof conflict. Single-qualifier trial independently proves 15 states with all faults rejected; explicit extension approval pending. Remaining core/top scan finds no more selectors of this kind. [Investigation](../../hw/ip/perf_core/ID-PRIORITY-INVESTIGATION.md). No commit/push or gate change.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved removing the two unique qualifiers only from the generated CSR formal-analysis copy. Preserve source priority, vendor/production RTL, all input combinations, proof obligations and negative controls; qualify hashes, receipts and affected proof paths before acceptance.

- 2026-11-15: T11 in progress -> blocked, Codex; decoder, LSU, IF, controller and WB checkpoints pass focused checks and fresh independent reviews. CSR tests/timing pass, but original formal reference optimizes unique selectors differently for conflicting inputs. Independent review reproduces a priority-preserving analysis-copy proof and recommends explicit baseline approval; original failure retained, no gate/decision changed, no commit/push. [Investigation](../../hw/ip/perf_core/CSR-PRIORITY-INVESTIGATION.md).

- 2026-11-15: T11 in progress, Codex; approved registered execution passes induction, production-binding equivalence, fault rejection, completion covers, simulation and independently reproduced timing. Independent review approved this scope; decoder/core work continues and whole-core acceptance remains open. No gate or decision changed.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved registered execution boundaries, extra ALU/divide cycles and necessary pipeline-control changes, with transaction/refinement and retirement checks. Timing limits and other acceptance requirements remain unchanged.

- 2026-11-14: T11 in progress -> blocked, Codex; approved iterative multiplier implemented and independently reviewed; all 21 simulations, 13 configured equivalence checks and new arithmetic/division proofs pass. Revised local gate exits 1 on unchanged 24.96 ns limit: multdiv 25.093014 ns and EX 25.975801 ns. Awaiting explicit ALU/divide retiming decision; whole core incomplete, no commit/push. [Report](tasks/reports/T11.md).

- 2026-11-14: T11 in progress, Codex; user approved iterative multiplier state/latency change with reviewed arithmetic/transaction refinement and whole-core retirement comparison. Faithful baseline and unchanged-module exact proofs retained; no timing limit waived. Local CI checkpoint passed before redesign.

- 2026-11-14: T11 in progress, Codex; qualified explicit combinational buffering/sizing and electrical-limit rejection without changing STA constraints. ALU, counters, register file, compressed decoder, fetch FIFO and prefetch parent pass leaf proofs/timing with independent review. Multiplier/divider structural equivalence passes including sign-fault rejection; its timing fails and is under investigation. Full-core acceptance remains open.

- 2026-11-14: T11 blocked -> in progress, Codex; user approved combinational repairs for measured timing failures throughout T11 after retaining each faithful baseline proof. Ports, state, reset, cycle behavior, timing budgets and verification checks remain unchanged.

- 2026-11-14: T11 in progress -> blocked, Codex; authorized counter repair passes equivalence, simulation, timing and independent review. Continued with faithful ALU, which proves equivalent but fails unchanged timing budget; independent review confirms path and stateless timing-mode checks. Awaiting decision on broader same-state combinational repairs; no whole-core acceptance or commit claimed.

- 2026-11-14: T11 blocked -> in progress, Codex; user approved localized combinational counter increment restructuring, preserving registers, ports, reset, cycle behavior, timing budget and all verification checks.

- 2026-11-14: T11 in progress -> blocked, Codex; configured CSR/counter leaf proofs and simulations pass, but mapped 64-bit mcycle timing fails the unchanged T09 budget. Stopped before structural improvements; measured evidence and proposed next decision in report. No full-core or CI acceptance claimed.

- 2026-11-14: T11 blocked -> in progress, Codex; user approved preserving inherited combinational boundaries for the faithful baseline, necessary production-isolation/gated-clock timing support and core timing-ledger entries. Timing budgets and acceptance checks remain unchanged.

- 2026-11-14: T11 readiness rechecked after T10 completion, Codex; comparison interfaces are available. Registered-output/no-retiming conflict and production timing/isolation scope remain unresolved; report refreshed, no RTL started.

- 2026-11-14: T10 continuation in progress -> done, Codex; all-module and whole-core unbounded self-equivalence, candidate formal/lockstep paths and real source-fault rejection, pinned architectural/flight suites, and required divide stress pass. Full local gate and final independent review pass; limitations and measured runtimes recorded in the report/ledger. No Chisel conversion started and no gate checked.

- 2026-11-14: T10 done -> in progress, Codex; user assigned harness completion after review found T11 acceptance interfaces missing. Sequential/whole-core self-equivalence is the first required checkpoint; no Chisel conversion authorized in this continuation.

- 2026-11-14: T11 not started -> in progress -> blocked, Codex; independent readiness review confirmed the inherited combinational-output conflict and required verification/timing scope extensions. Concrete clarification in [report](tasks/reports/T11.md); no RTL or acceptance changes, no gate checked.

- 2026-11-14: T10 in progress -> done, Codex; revised D44 acceptance passes: 66 original bounded partitions and four bounded/arithmetic-abstracted ALTOPS partitions with covers and both multiply faults, integer lemmas, required real-arithmetic stress, physical isolation and full local gate. Independent review reproduced checks and found no actionable issues. Optional C failed frontend feasibility without a valid model; raw arithmetic remains unresolved as approved. See report. No physical/verification gate checked.

- 2026-11-14: T10 blocked -> in progress, Codex; user assigned implementation of D44 with revised acceptance, independent review and commit/push on completion.

- 2026-11-14: Plan change, Claude at user's direction; D44 approves splitting the multiply instruction check (ALTOPS integration check, integer lemma, required stress simulation; unabstracted check kept as non-gating diagnostic). T10 and T11 briefs and the formal plan updated; K22 added. The T10 brief's May change list now includes the reference-rejection guard in tools/timing/check.py, which its step 3 already required. T10 stays blocked until the split is implemented and its checks pass. No gate checked.

- 2026-11-14: T10 remains blocked, Codex; user explicitly authorized commit/push of the incomplete checkpoint so another agent can review. This does not approve task completion or change any acceptance check.

- 2026-11-14: T10 in progress -> blocked, Codex; investigation favors arithmetic solver complexity: the unchanged MUL property also times out at a separate 1,800-second diagnostic limit. Fixed the independently reviewed QEMU shutdown-trace boundary bug; 17,680 multiplication products pass independent comparison, all 66 non-multiply partitions have bounded/cover/fault evidence across runs, and nonzero-destination multiply faults are detected. Normal acceptance remains unchanged and unsuccessful; no commit/push. See report and investigation note.

- 2026-11-14: T10 blocked -> in progress, Codex; user requested investigation of bug versus insufficient proof time. Running isolated extended-time diagnostics and independent multiplication checks; acceptance limits remain unchanged.

- 2026-11-14: T10 in progress -> blocked, Codex; exact adaptation documented and reviewed, both frontends/equivalence/retirement checks pass. Corrected reference formal run completed 46 bounded/covered partitions with rejected faults, then MUL/MULH/MULHSU reached the unchanged 600-second solver limit. Full CI did not pass. Physical ingress hook awaits scope approval; no commit/push. See report and core formal ledger.

- 2026-11-14: T10 blocked -> in progress, Codex; user authorized removing the exact unused declaration in the generated analysis copy and requested a durable bug-triage note. Originals remain byte-exact; adaptation hash/bytes/reversal recorded in dv/core/ADAPTATIONS.md and adaptations.json. All acceptance checks and independent review still required.

- 2026-11-14: T10 not started -> in progress, Codex; user assigned next task with the same checks, independent review and commit/push workflow. Preparing reference pin, front-end elaboration and comparison harnesses; no Chisel core conversion started.
- 2026-11-14: T10 in progress -> blocked, Codex; independently reproduced slang failure on input-dependent unused declaration initialization in Ibex v2.1.0. Sources remain unmodified; no suppression or compatibility patch applied. Awaiting explicit decision under the brief's front-end stop condition; no commit/push.

- 2026-11-14: T09 not started -> in progress, Codex; user assigned the next task with independent review, full local checks, commit and push. Required OpenSTA and pinned GF180 slow-corner libraries are available.
- 2026-11-14: T09 in progress -> blocked, Codex; independent review reproduced RegBlock coverage timing at 44.802906 ns against 24.96 ns. Kept the failing check intact; requested scope to fix core timing, prohibited by T09's current brief. No commit/push.
- 2026-11-14: T09 blocked -> in progress, Codex; user explicitly approved extending T09 to repair RegBlock timing while preserving behavior, budget, all checks and independent review before commit/push.
- 2026-11-14: T09 in progress -> complete, Codex; timing self-test and full local gate passed. Coverage RegBlock measured 19.390715 ns under unchanged 24.96 ns ceiling after authorized decode repair; independent fresh-context review reproduced the result and found no actionable issues. No architecture gate changed.

- 2026-11-14: T05 in progress -> done, Codex; approved partial-write contract implemented; Python/Chisel model comparisons, formal proofs/faults/covers, full local gate and independent verification passed. [Report](tasks/reports/T05.md). No physical gate checked.

- 2026-11-14: T05 blocked -> in progress, Codex; user approved byte-masked rwh writes and complete-field wo writes with transaction-wide error suppression; specification clarified and implementation resumed.

- 2026-11-14: T05 in progress -> blocked, Codex; independent review confirmed unspecified byte-strobe behavior for rwh/wo; concrete clarification submitted to user under the brief's ambiguity stop rule. [Report](tasks/reports/T05.md). No implementation started.

- 2026-11-14: T05 not started -> in progress, Codex; user assigned next task with independent review, commit and push; checking register-map contract before implementation.

- 2026-11-14: T07 in progress -> done, Codex; pinned direct Chisel build, behavioral negative control, native BTOR2 and SymbiYosys induction/fault/cover checks passed; merged-tree local gate and independent verification passed. [Report](tasks/reports/T07.md). Remote D43 plan retained; no gate checked.

- 2026-11-14: Plan change, Claude at user's direction; D43 removes the NoC and restores a whole-chip bus with domain bridge and mailbox. D3/D14 superseded. T03/T04/S2 blocked -> withdrawn. T14 added, unstarted. R-NOC replaced by R-BUS; K8 closed, K14 rewritten, K21 added. No gate checked.

- 2026-11-14: T07 not started -> in progress, Codex; user assigned pinned Chisel build and formal smoke, routine tooling repairs, independent review, commit and push.

- 2026-11-14: T06 in progress -> done, Codex; clean upstream gates/export, mapped area within the original tolerance, exact architectural storage, local gate and independent verification passed. [Report](tasks/reports/T06.md). Remote plan update merged; no gate checked.

- 2026-11-14: Plan change, Claude at user's direction; D2 revised to an equivalence-checked Ibex conversion. T10 split into T10 (reference/harness), T11 (conversion), T12 (FPU), T13 (F integration/improvements); S1 now depends on T13. Risks K19/K20 added. Briefs unstarted; no gate checked.

- 2026-11-14: T06 not started -> in progress, Codex; assigned next unblocked task, Maven preflight passed, pinned baseline checkout prepared.

- 2026-11-14: T02 in progress -> done, Codex; repeated exact QEMU matches, unchanged historical summary, negative controls and local gate passed; independent review verified the fixes. [Report](tasks/reports/T02.md). No gate checked.

- 2026-11-14: T02 blocked -> in progress, Codex; user approved scoped LF enforcement and routine tooling repairs with checks intact, independent review, commit and push.

- 2026-11-14: T02 in progress -> blocked, Codex; baseline shell launch failed on Windows CRLF checkout. Independent review confirmed a scoped LF-attribute fix; awaiting approval under the failed-command stop rule.

- 2026-11-14: T02 not started -> in progress, Codex; user assigned continued plan implementation with independent review and automatic commit/push after verification.

- 2026-11-14: T08 in progress -> done, Codex; immutable image built, clean rebuild reproduced inventory/versions/smoke, local gate passed; [report](tasks/reports/T08.md).
- 2026-11-14: T01 in progress -> done, Codex; scaffold acceptance passed, fresh-context reviewer verified fixes and found no remaining issues; [report](tasks/reports/T01.md). No gate checked.

- 2026-11-14: T01 not started -> in progress, Codex; preparing the assigned scaffold while the T08 image builds; acceptance remains dependent on T08.

- 2026-11-14: T08 blocked -> in progress, Codex; user authorized resolving bootstrap/build failures until built, retaining verification.

- 2026-11-14: T08 in progress -> blocked, Codex; initial Docker build failed on CA trust before package installation; awaiting approval to correct bootstrap. T01 not started.

- 2026-11-14: T08 not started -> in progress, Codex; user assigned T08/T01 with local-only checks and a fresh-context review afterward.

- 2026-11-13: PLAN01 in progress -> done, Codex; documentation checks passed, [report](tasks/reports/PLAN01.md). No implementation started.

- 2026-11-13: PLAN01 not started -> in progress, Codex; user assigned plan/brief reconciliation and authorized commit/push, no implementation.
- 2026-11-13: User decisions D1-D42 reconciled; superseded/deferred items explicitly identified. No gate checked.
- 2026-11-13: T07 brief rewrite removes its stale async blocker; task remains unstarted. T03/T04/S2 record sanitized-source blockers. T08/T09/T10 briefs added, unstarted.
- 2026-11-13: Original tracker created; no implementation task started.
