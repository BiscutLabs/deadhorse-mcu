# Deadhorse MCU plan

Draft v0.8, 2026-11-13. Decided so far: D11 (USB integrated last), D14 (NoC
vendored, drift accepted), D16 (Chisel is the design language) and **D17
(the chip is entirely clocked; the clockless plan is abandoned)** and D18
(lite core clocked first, with a coarse Click pipeline as a later option). The other
decisions in [10-decisions-and-risks.md](10-decisions-and-risks.md) are
still open.

Deadhorse is the production rebuild of
[RISCay-MCU](https://github.com/BiscutLabs/RISCay-MCU): an entirely clocked,
heterogeneous RISC-V microcontroller on GF180MCU whose first application is the
flight controller for a small tilt-rotor VTOL. It starts from RISCay's
clocked design and its sleep, reset and boot architecture, replaces its toy
CPU, bus and peripherals. The neuromorphic
IP itself is out of scope for this plan. RISCay's asynchronous work is not
used.

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
| [tasks/README.md](tasks/README.md) | Task briefs for Phase 0 and the spikes, written for hand-off |
| [../spec/](../spec/) | Register-map format and actuator block |

## Ground rules for this plan

1. **Adopt before building.** We are not writing much RTL. Every block is
   first matched against RISCay-MCU, Coldfoot, or an open, verified design.
   New RTL needs a written reason.
2. **Chisel is the design language.** Everything
   Deadhorse writes, and the SoC top, is Chisel. SystemVerilog appears only
   as vendored blocks behind a Chisel black box.
3. **Every number has a provenance.** *Measured* means a tool produced it and
   the source is named. *Estimated* means derived by hand from measured
   inputs. *Assumed* means a placeholder that a named task will replace.
4. **Measure before freezing.** Phase 1 in the roadmap is four short
   measurement spikes. The architecture is not frozen until they report.
5. **Standard synchronous discipline.** One clock per domain, two
   crossings in the whole chip, every crossing through one reviewed block,
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
