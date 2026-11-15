# Architectural test source

Byte-identical riscv-tests subset at commit
`3df703cd52d5f0d8224e3c50bf03c6cb70efff98`, from the
[upstream repository](https://github.com/riscv-software-src/riscv-tests/tree/3df703cd52d5f0d8224e3c50bf03c6cb70efff98).
[lock.json](lock.json) records all copied file hashes. The upstream
[BSD licence](upstream/LICENSE) is retained. No ISA test or scalar macro is
modified. RV64 bodies are included because RV32 tests include them with RV32
settings. Only RV32UI, RV32UM and RV32UC are executed.

`riscv_test.h` implements the upstream environment-macro interface: explicit
integer-register initialization, a jump from Ibex's reset vector, and pass/fail
stores to QEMU's finisher. `link.ld` preserves the compressed test's alignment
while placing startup at the reset address. Every test in these RV32 directories
is required; none is excluded for failure. `suites.py` verifies hashes before
compiling. This is not privileged-mode or full compliance certification.
