# T21 timer properties

Run `python3 dv/soc/check_io_formal.py --output build/<fresh> --cases main8 main9 aon`
inside the pinned environment. This is a focused check, not CI.

The main jobs assert timestamp update consistency, registered clock demand,
and output enable only in compare mode. They do not independently prove the
prescaler's elapsed-time ratio; the pin/MMIO tests check both supported ratios,
wrap, tick/APPLY collision, captures and restart. Covers witness timestamp1
(which may be preloaded) and active compare+IRQ. The fault corrupts the actual
timestamp output and must fail its specific assertion. No cadence-proof claim.

The AON job asserts each remaining-count transition: cancel, legal arm, hold
or decrement. It covers IRQ+wake and rejects corrupted duration loading.
Counter recurrence alone is not a complete wake-delivery proof; exact expiry,
ARM/CANCEL priority and stopped-main wake also have directed pin/MMIO tests.

All jobs start with reset low, then permit arbitrary reset, requests, addresses,
data, strobes and pins. No environment assumption on bus software or internal
state is added. The runner checks one initial-reset assumption, exact emitted
assertion inventory and concrete cover/fault witnesses. Jobs use ABC PDR for
unbounded properties, BTOR for covers/faults and a 120-second cap.
Receipts bind source, generated register inputs, configuration, logs and models.
Analog clocks, pads, metastability and physical reset timing are excluded.
