# Lite-core formal scope

All commands run through the pinned environment, with explicit commands rather
than either CI tier. Results and source/artifact hashes live under `build/t25`;
the ledger/report classify each obligation separately.

## Faithful adoption

`state_equivalence.py` uses the existing `dv/core/state_equiv.py` exact named
state decomposition against namespace-only pinned source. It checks every
register, clock/reset/init value, next-state function and public output without
assumptions or exclusions. Output, reset-value and next-state netlist mutations
must fail. This qualifies `ClockedCore`, not the extended `LiteCore`.

The earlier `check.py --cases baseline` output-only PDR formulation timed out.
Its covers and trace-data fault passed; the timeout is preserved and must not
be retried unchanged. The exact decomposition closes the original equivalence
claim without adding trust or a smaller bound.

## Adapter and control safety

`check.py --cases adapter control` checks the production adapter and core.
The adapter has an independent transaction scoreboard: one request, stable
payload, fixed origin/alignment/byte lanes, held reply and locally consumed
terminal Halt. The core properties cover start gating, outstanding credit,
sleep/interrupt quiescence, response-to-retirement sequencing and stable offers.
Faults corrupt the actual returned data or let IRQ change a held address.
Covers exercise fetch/read/write, fault retirement, sleep and interrupt entry.
These are interface/control properties, not machine-mode architectural proofs.

Assumptions: initial reset asserted, then arbitrary; one digital AON clock.
No input protocol or data restrictions are assumed. Repeated reset cancels
the model and checker together, matching the common service-reset boundary.
Analog reset release/CDC/physical clock timing is outside this proof.

## Instruction semantics

`instructions.py --instructions <names> --output <fresh-build-path>` connects
the production RVFI port to pinned, unmodified `riscv-formal/insns` models.
Checks apply at every retirement, not only a selected startup cycle. The
RV32I models are extended in the Chisel checker for RV32E high-register
illegality and an actual accepted memory-error response. They use aligned
physical memory lanes. No instruction, operand, bus or interrupt assumptions
are added. Trapping paths require a trap and no architectural destination
write; nontrapping paths check operands, destination, PC and memory lanes.

Each selected instruction requires successful and trapping covers plus a
negative control that corrupts the actual next PC and its retirement report.
Positive jobs request unbounded proof; timeout is unresolved, never bounded
success. A passing subset is not full RV32E qualification. CSR semantics,
register-file consistency, instruction-fetch consistency and architectural
interrupt entry/return remain separate obligations until explicitly closed.
All solver jobs retain the 120-second cap; cover/fault witness horizon is
32 clock samples, sufficient for multiple registered fetch/data handshakes.
