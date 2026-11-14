# deadhorse-mcu

Deadhorse is a clocked two-core RISC-V MCU targeting GF180MCU. Its approved
baseline combines a Chisel Ibex-derived RV32IMFC performance core, a retained
lite core, whole-chip bus, programmable sleep peripherals and actuator timing.
No neuromorphic IP or chip-to-chip link is included in the initial MCU.

Start with [AGENTS.md](AGENTS.md), the [plan](docs/plan/README.md),
[approved decisions](docs/plan/10-decisions-and-risks.md),
[status](docs/plan/STATUS.md) and [task briefs](docs/plan/tasks/README.md).

This repository contains the plan, initial scaffold and historical measurement tools.
The decision reconciliation does not implement hardware or establish physical
fit, performance, power, test coverage or shuttle qualification.

## Layout

See the [repository structure](docs/plan/11-repository-structure.md) for block,
firmware, verification and physical-design ownership. Generated output belongs
under ignored `build/`; temporary work belongs under ignored `scratch/`.

## Local checks

Build the pinned Linux tools with `python tools/env/run.py build`, then run
`python tools/env/run.py run`. This executes `python3 tools/ci.py` in the recorded
immutable Docker image. There is no GitHub Actions workflow.
See [environment setup](tools/env/README.md) for prerequisites and smoke checks.
