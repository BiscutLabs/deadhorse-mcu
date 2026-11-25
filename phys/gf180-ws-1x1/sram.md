# T35 SRAM physical handoff

Digital integration is not macro, retention, DRC/LVS or routed timing signoff.
Use the exact views from `hw/vendor/gf180_sram/gf180_sram.lock.json`, materialized by
its `prepare.py`; no replacement or repaired Liberty/LEF/GDS is authorized.

There are sixteen `gf180mcu_ocd_ip_sram__sram1024x8m8wm1` instances under
`digital.memory`, and four `gf180mcu_ocd_ip_sram__sram512x8m8wm1` instances
under `digital.subsystem.retained` (D109). Both have CLK, active-low CEN/GWEN,
active-low WEN[7:0], D[7:0] and Q[7:0]; main addresses are A[9:0] and retained
addresses are A[8:0]. The chip socket adds the `i_chip_core.soc` prefix.
Connect physical `VDD` and `VSS` to the qualified normal supply/ground grid;
the logical BlackBox omits physical power pins. SRAM has no reset pin.
Clock main instances at generated OSC_IN/6 and retained instances at AON.
Keep all twenty macro clock loads in CTS. No new false path or multicycle
exception applies to these SRAM interfaces, including the destructive test mux.

LEF width/height and instance counts are extracted by
`hw/top/reference/measurements/t35_budget.py`; the area estimate is their
product, never the stale Liberty `area`. The existing **assumed** 0.40 mm²
macro-halo/channel allowance remains until placement establishes actual routing
clearances. `sram-placement.yaml` uses an **assumed 20 um** preliminary halo
for geometric checks only; this neither replaces the budget allowance nor
establishes routing clearance or completed physical placement. The
pinned LEF declares no SYMMETRY; retain its native orientation unless T38
qualifies another orientation. T38 must preserve power access, signal-pin
access and enough space for clock/reset/test routing, then remeasure.

T35 STA pairs the five pinned standard-cell and SRAM corners at the same
process/temperature/voltage point. Preserve macro setup, hold, minimum period,
pulse width and clock-to-Q arcs. SRAM has no removal arc; reset-removal reports
belong to the surrounding controller registers. Negative pre-CTS hold remains
a physical-flow item, never permission to add delay RTL or omit a check.

The vendor functional Verilog has artificial event delays, guessed specify
delays and zero initialization. It is used only for functional pin simulation.
The independent digital model starts with arbitrary RAM. Neither proves
retention or operating limits. Reconcile the macro's stale address-width/area
metadata, truth-table labels and characterization inconsistencies before
physical signoff. Nominal-rail clock-gated retention is the digital contract;
there is no low-voltage, brownout or power-off data-retention guarantee.

T37 must exclude the SRAM arrays from scan, include the BIST/control/status
flops, and preserve the keyed, reset-held destructive test protocol. Status
and failing-address records stay outside tested memory. Test clocks must run
both main and AON; a stopped AON clock deliberately holds system reset rather
than allowing an incomplete test to pass. T38 must verify test-mode entry,
pin-reset abort and clock integrity at the pad level.
