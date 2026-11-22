# Pin mux formal scope

Run `python3 hw/ip/pinmux/formal/check.py --output build/t24/fresh-formal`
in the pinned environment. Use a fresh output directory. The runner checks
the assertion/assumption inventories, expected fault identities and concrete
cover/fault witnesses. Source and emitted-model hashes bind each receipt.

| Job | Unbounded sampled claim | Actual fault | Covers |
| --- | --- | --- | --- |
| pad | Active selection, handover interval, selected enable/data and disconnected outputs follow the preceding inputs | Output enable stuck high | Each enabled/high source, handover disabled, disconnected |
| reset | At a sample with reset asserted, active selection, data, enable and settling are zero | Output-enable flop resets high | Reset disabled and enabled/high after release |
| denied | Non-owner transactions receive only error/zero-data replies; cannot enable any pad | Owner check bypassed | Error reply |

Assumptions: initial reset asserted, then arbitrary assertion/release; one
digital main clock. The denied harness maps the owner tag to a non-owner and
represents every non-owner tag. Source data, enables, selections and bus
requests are otherwise unconstrained. No lemma assumptions, reduced widths,
memory abstractions or protocol-enable restrictions.

ABC PDR runs unbounded safety; btormc finds finite cover and negative witnesses.
Existing per-job cap remains 120 seconds. The reset monitor is not disabled
by the reset it checks. Conversion of asynchronous reset for the solver gives
a sampled digital property, not an analog or inter-edge timing proof.
Stopped-clock simulation checks asynchronous pad disable in the production
block and assembled SoC. Core/AON reset composition and clock demand through
the accepted MMIO write/handover are tested separately. Physical hold, reset
removal, pad delays and clock-tree behavior remain outside this qualification.
