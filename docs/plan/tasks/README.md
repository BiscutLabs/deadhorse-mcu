# Task briefs

Read [../../../AGENTS.md](../../../AGENTS.md) and the assigned brief's Read first
list before work. Progress lives only in [../STATUS.md](../STATUS.md).
PLAN01 is documentation only; no other task is started by this revision.

| ID | Brief | Dependencies | Readiness |
| --- | --- | --- | --- |
| PLAN01 | [Decision reconciliation](PLAN01-reconcile.md) | User approval conversation | Assigned documentation work |
| T08 | [Pinned Linux environment](T08-environment.md) | None | Brief ready; commands not yet run |
| T01 | [Scaffold and CI](T01-scaffold.md) | T08 | After pinned environment |
| T02 | [Historical flight-loop CI](T02-flight-loop-ci.md) | T01, T08 | Historical workload only |
| T03 | Interconnect study | T01, T08, sanitized source and rights | Blocked on transport handoff/Q8 |
| T04 | Interconnect study | T03 | Blocked; old dependency closure not approved |
| T06 | [RISCay baseline](T06-riscay-baseline.md) | T01, T08 | Full clean gate still unverified |
| T07 | [Clocked Chisel build](T07-chisel-build.md) | T01, T06, T08 | Rewritten; direct Chisel, no async dependency |
| T05 | [Register generator](T05-regmap-generator.md) | T07 | Format fixture; actuator ABI deferred |
| T09 | [GF180 timing flow](T09-timing-flow.md) | T01, T06, T07, T08 | New brief; commands not yet run |
| T10 | [Chisel core/FPU](T10-core-fpu.md) | T07, T09 | Resolve source pins/verification contract first |
| S1 | [Selected core measurement](S-spikes.md#s1-core) | T10, T09, T02 | Not a core selection exercise |
| S2 | Interconnect study | T07, T09; T03/T04 for reuse | Sanitized source prerequisite unresolved |
| S3 | [Memory](S-spikes.md#s3-memory) | T02, T07, T08 | Modeling can precede S1 |
| S4 | [Latency/test](S-spikes.md#s4-latency-and-test-access) | S1, T08, T09 | Architecture approved; coverage unmeasured |

## Evidence inherited from initial planning

The original plan reports a successful RISCay Python baseline and firmware
bootstrap and historical flight-loop reproduction.
Those results were not rerun by PLAN01. Maven Central blocked the original
Scala/build verification. The historical QEMU off-by-one issue remains T02's
work; no test failure was fixed by editing this plan.

All newly specified commands in T07-T10/S1-S4 are explicitly unverified until
those tasks run. A written acceptance command is not an implemented tool.
Missing tools cannot be skipped to claim success.

## Further briefs still required

RISCay source adoption/restructuring; shared CDC; analog macro layout and
threshold controls; physical-flow/pad-ring import; peripheral/DMA/pin-mux and
SoC integration; final actuator ABI after policy tests; production test and
board/silicon integration. Prepare these from the approved contracts before
assigning implementation. USB implementer deliverables and shuttle qualification
remain external evidence dependencies. D18 and chip-to-chip work are deferred.

## Writing a new brief

State goal, Read first, inputs, May change, deliverables, executable acceptance
checks and stop conditions. Mark commands not yet run as unverified. Keep new
RTL clocked Chisel with independent tests, formal negative controls and T09
timing. Never use upstream verification as proof of a reimplementation.
