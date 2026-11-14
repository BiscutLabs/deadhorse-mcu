# Deadhorse MCU plan

Draft v0.4, 2026-11-13. Decided so far: D10 (two clocked islands), D11 (USB
integrated last) and D14 (interconnect source policy). The other decisions in
[10-decisions-and-risks.md](10-decisions-and-risks.md) are still open.

Deadhorse is the production rebuild of
[RISCay-MCU](https://github.com/BiscutLabs/RISCay-MCU): a clockless,
heterogeneous RISC-V microcontroller on GF180MCU whose first application is the
flight controller for a small tilt-rotor VTOL. It keeps RISCay's async
methodology and sleep architecture, replaces its toy CPU, bus and peripherals. The neuromorphic IP itself is out of
scope for this plan.

## Reading order

| Doc | Contents |
| --- | --- |
| [01-product-definition.md](01-product-definition.md) | What we are building, for which airframe, and what is out of scope |
| [02-requirements.md](02-requirements.md) | Numbered requirements, each marked measured, estimated or assumed |
| [03-architecture.md](03-architecture.md) | Target block architecture, timing regions, cores, bus, address ownership |
| [04-riscay-carryover.md](04-riscay-carryover.md) | What is reused from RISCay-MCU, what is replaced, and the import method |
| [06-power-clock-reset.md](06-power-clock-reset.md) | Sleep modes, oscillators, timing reference, reset and failsafe |
| [07-peripherals-memory-boot.md](07-peripherals-memory-boot.md) | Peripheral set, actuator block, memory sizing, boot and debug |
| [08-physical-verification.md](08-physical-verification.md) | Slot, area and pad budgets, analog macros, verification and signoff gates |
| [09-roadmap.md](09-roadmap.md) | Phases, the measurement spikes that come first, and exit gates |
| [10-decisions-and-risks.md](10-decisions-and-risks.md) | Decisions needing approval, ranked risks, open questions |
| [11-repository-structure.md](11-repository-structure.md) | Folder layout and rules |
| [tasks/README.md](tasks/README.md) | Task briefs for Phase 0 and the spikes, written for hand-off |
| [../spec/](../spec/) | Register-map format and actuator block |

## Ground rules for this plan

1. **Adopt before building.** We are not writing much RTL. Every block is
   first matched against RISCay-MCU, Coldfoot, or an open, verified design.
   New RTL needs a written reason.
2. **Every number has a provenance.** *Measured* means a tool produced it and
   the source is named. *Estimated* means derived by hand from measured
   inputs. *Assumed* means a placeholder that a named task will replace.
3. **Measure before freezing.** Phase 1 in the roadmap is four short
   measurement spikes. The architecture is not frozen until they report.
4. **RISCay's async rules still apply:** decide architecture before writing
   verification; one matched delay per stage; no clock added to fix an async
   problem; clocks only where a written obligation demands one; track area,
   clocked state and worst-corner timing on every change.

## Sources used

| Source | Revision | Used for |
| --- | --- | --- |
| RISCay-MCU | `4671317` (2026-11-12) | Baseline design, desync flow status, analog candidates, area and timing ledgers |
| chisel-async | `aef1f09` (2026-11-10) | Library capabilities and qualification limits |
| Flight-loop measurement | 2026-11-13, `sw/flight/loop-measurement/` | Instruction counts, code and RAM size for the inner control loop |
| Flightory Stallion VTOL product page | read 2026-11-13 | Airframe, motor, ESC and servo counts |

Agents and engineers picking up work start at the repository's `AGENTS.md`
and then [tasks/README.md](tasks/README.md).

## Confidentiality

Proprietary third-party interconnect details are excluded from this repository.
