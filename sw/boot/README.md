# Performance boot ROM

PLAN05 C1-C9 uses one performance-side ROM at reset entry0x80. It validates
paired A/B/golden bundles, loads and verifies SRAM and held lite program RAM,
then releases lite if requested and enters the application. Performance-only
reset validates the same retained generation and preserves the watcher; failure
stays in ROM. Dormant wake resumes WFI and does not enter this ROM.

Run `python dv/soc/prepare_production.py` in the pinned environment to generate
maps and build `build/t36/rom/rom.hex`. The compiler, source/map hashes, image,
symbols, size and stack-use outputs are recorded in its build receipt. Reuse
requires exact source and artifact identity. Nothing generated is committed.

UART0 recovery uses gateway-v1 framing with the restricted firmware capability
profile: reserved staging RAM and commit-last inactive-slot updates. It is not
an unrestricted hardware gateway. JTAG is the fallback; there is no I2C loader.
The exact ABI, reset behavior, command encodings and assumed transport limits
are in [the boot contract](../../docs/spec/boot-rom-proposal.md).

`python dv/soc/boot/check.py --output build/t36/boot-N` runs focused native and
production NOR/UART wire checks. Formal reset-context checks and mapped ROM/
whole-SoC measurements are separate. Tests are finite evidence, not a firmware
proof; see [T36](../../docs/plan/tasks/reports/T36.md) for actual results/debt.


Recovery services RX at bounded safe points after preserving the request
snapshot and between flash commands; concurrent frames return BUSY. This avoids
the observed eight-byte FIFO overflow during BEGIN processing. The final wire
campaign checks BUSY during BEGIN and COMMIT, duplicate handling and commit-last
power-loss recovery. The6776-byte ROM's observed peak stack is448 of512bytes.
D104 records the maximum1KiB lite-image load above250ms as an explicit accepted
exception; the588-byte watcher still meets that target. T42 tracks the fix.
