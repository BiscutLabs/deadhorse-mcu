# Deadhorse MCU plan

Approved planning baseline v0.9, reconciled 2026-11-13. The
[decision register](10-decisions-and-risks.md) records all user approvals and
the questions deliberately deferred to testing. This documentation revision
does not start implementation or mark physical/verification gates complete.

Deadhorse rebuilds RISCay's clocked design into project conventions, with a
Chisel Ibex-derived RV32IMFC core, area-focused multicycle FPU, retained lite
core, a whole-chip bus with a domain bridge and mailbox, and programmable
sleep peripherals. No
neuromorphic IP or chip-to-chip link enters the initial MCU. Use the approved
Linux container and shared CDC/verification conventions when implementation
is subsequently assigned.

## Reading order

| Doc | Contents |
| --- | --- |
| [01-product-definition.md](01-product-definition.md) | What we are building, for which airframe, and what is out of scope |
| [02-requirements.md](02-requirements.md) | Numbered requirements, each marked measured, estimated or assumed |
| [03-architecture.md](03-architecture.md) | Target block architecture, clock domains, cores, bus, address ownership |
| [04-riscay-carryover.md](04-riscay-carryover.md) | What is reused from RISCay-MCU, what is replaced, and the import method |
| [06-power-clock-reset.md](06-power-clock-reset.md) | Sleep modes, oscillators, timing reference, reset and failsafe |
| [07-peripherals-memory-boot.md](07-peripherals-memory-boot.md) | Peripheral set, actuator block, memory sizing, boot and debug |
| [08-physical-verification.md](08-physical-verification.md) | Slot, area and pad budgets, analog macros, verification and signoff gates |
| [09-roadmap.md](09-roadmap.md) | Phases, the measurement spikes that come first, and exit gates |
| [10-decisions-and-risks.md](10-decisions-and-risks.md) | Decisions needing approval, ranked risks, open questions |
| [11-repository-structure.md](11-repository-structure.md) | Folder layout and rules |
| [12-formal-verification.md](12-formal-verification.md) | Formal verification policy, tools, what is proved per block, gate conditions |
| [13-test-environment.md](13-test-environment.md) | Pinned tool environment, block tests, reference models, one test body on four targets, firmware and airframe in the loop |
| [14-timing-design-rules.md](14-timing-design-rules.md) | Rules against long combinational paths, and the per-block GF180 timing check |
| [15-skills.md](15-skills.md) | The agent skills and when to use each |
| [16-soc-integration.md](16-soc-integration.md) | SoC integration: block inventory, staged assembly with stubs, top-level rules, open clock plan, block briefs still needed |
| [STATUS.md](STATUS.md) | Progress tracker: decisions, tasks, gates, and a change log |
| [tasks/README.md](tasks/README.md) | Task briefs for Phase 0 and the spikes, written for hand-off |
| [../spec/](../spec/) | Register-map format and actuator block |

## Ground rules for this plan

1. **Adopt before building.** Reuse the named clocked IP and conventions where appropriate. D2/D19/D20
   explicitly require a Chisel core/FPU implementation; it needs new verification.
   Coldfoot imports are transport-only and require a sanitized handoff.
2. **Chisel is the design language.** Everything
   Deadhorse writes, and the SoC top, is Chisel. SystemVerilog appears only
   as vendored blocks behind a Chisel black box.
3. **Every number has a provenance.** *Measured* means a tool produced it and
   the source is named. *Estimated* means derived by hand from measured
   inputs. *Assumed* means a placeholder that a named task will replace.
4. **Measure before freezing.** Phase 1 measures the selected design through four
   spikes after their implementation prerequisites; it is not a core selection exercise. The architecture is not frozen until they report.
5. **Standard synchronous discipline.** One clock per domain, every crossing
   through one reviewed implementation (including JTAG and optional USB),
   glitch-free gating, and area, timing and clock-domain structure tracked
   on every change.

## Sources used

| Source | Revision | Used for |
| --- | --- | --- |
| RISCay-MCU | `4671317` (2026-11-12) | Clocked baseline design, sleep and reset design, boot chain, analog candidates |
| Flight-loop measurement | 2026-11-13, `sw/flight/loop-measurement/` | Instruction counts, code and RAM size for the inner control loop |
| Flightory Stallion VTOL product page | read 2026-11-13 | Airframe, motor, ESC and servo counts |

Agents and engineers picking up work start at the repository's `AGENTS.md`
and then [tasks/README.md](tasks/README.md).

## Confidentiality

Proprietary third-party interconnect details are excluded from this repository.
