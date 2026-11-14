# Status

Single progress tracker. Last updated: 2026-11-14.
States: `[ ]` not started, `[~]` in progress, `[!]` blocked, `[x]` complete.
Decision checks record the user's approvals, not implementation completion.
No implementation task or gate is completed by the planning reconciliation.

## Decisions

Details: [10-decisions-and-risks.md](10-decisions-and-risks.md).

| | ID | Decision | State |
| --- | --- | --- | --- |
| [x] | D1 | RISCay import | Approved direction; qualification remains open |
| [x] | D2 | Performance core | Approved direction; qualification remains open |
| [x] | D3 | Internal NoC | Approved direction; qualification remains open |
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
| [x] | D14 | NoC source ownership | Approved direction; qualification remains open |
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

## Tasks

| | ID | Item | Owner | Depends on | Report |
| --- | --- | --- | --- | --- | --- |
| [x] | PLAN01 | [Reconcile decisions](tasks/PLAN01-reconcile.md) | Codex | User approvals | [Report](tasks/reports/PLAN01.md); documentation only |
| [x] | T08 | [Pinned Linux environment](tasks/T08-environment.md) | Codex | none | [Report](tasks/reports/T08.md); clean rebuild and runtime smoke pass |
| [x] | T01 | [Scaffold/CI](tasks/T01-scaffold.md) | Codex | T08 | [Report](tasks/reports/T01.md); local gate and fresh-context review pass |
| [ ] | T02 | [Historical loop CI](tasks/T02-flight-loop-ci.md) | unassigned | T01, T08 | |
| [!] | T03 | Interconnect study | unassigned | T01, T08 | Blocked on sanitized transport handoff and Q8; no source imported |
| [!] | T04 | Interconnect study | unassigned | T03 | Historical scripts require unapproved mixed dependencies; awaiting sanitized closure |
| [ ] | T06 | [RISCay baseline](tasks/T06-riscay-baseline.md) | unassigned | T01, T08 | |
| [ ] | T07 | [Chisel build](tasks/T07-chisel-build.md) | unassigned | T01, T06, T08 | Brief rewritten; no build run |
| [ ] | T05 | [Register generator](tasks/T05-regmap-generator.md) | unassigned | T07 | |
| [ ] | T09 | [Timing flow](tasks/T09-timing-flow.md) | unassigned | T01, T06, T07, T08 | |
| [ ] | T10 | [Selected core/FPU](tasks/T10-core-fpu.md) | unassigned | T07, T09 | Source pins/contract resolved on assignment |
| [ ] | S1 | [Core measurement](tasks/S-spikes.md#s1-core) | unassigned | T10, T09, T02 | Architecture selected; measurements outstanding |
| [!] | S2 | Interconnect study | unassigned | T07, T09, T03/T04 for reuse | Sanitized source/reference handoff unresolved |
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
