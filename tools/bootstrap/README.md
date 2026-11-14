# Bootstrap scripts

`riscay_bootstrap.sh <riscay-mcu checkout> [python-only|full]` installs
RISCay-MCU's pinned JDK, firtool, sv2v and Icarus Verilog inside the
checkout, builds its test firmware and runs its gate. It mirrors RISCay's
own CI workflow. Its header lists prerequisites and what was verified.

Used by task [T06](../../docs/plan/tasks/T06-riscay-baseline.md).
