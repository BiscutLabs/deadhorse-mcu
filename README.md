# deadhorse-mcu

Deadhorse is a clocked two-core RISC-V MCU targeting GF180MCU. Its approved
baseline combines a Chisel Ibex-derived RV32IMFC performance core, a retained
lite core, programmable sleep peripherals and actuator timing.
No neuromorphic IP or chip-to-chip link is included in the initial MCU.

Start with [AGENTS.md](AGENTS.md), the [plan](docs/plan/README.md),
[approved decisions](docs/plan/10-decisions-and-risks.md),
[status](docs/plan/STATUS.md) and [task briefs](docs/plan/tasks/README.md).

This repository contains planning documents and historical measurement tools.
The decision reconciliation does not implement hardware or establish physical
fit, performance, power, test coverage or shuttle qualification.
