# Attribution and adaptations

The LF topology is adopted from the pinned RISCay-MCU generator at
`4671317186003740ceb61360ba08c59bbdf10136`, itself based on Tim Edwards /
Efabless's Apache-2.0 `sky130_ef_ip__rc_osc_500k`, revision
`343f4481b2199efe4ddba48428c89fcf1029ae9a`. The supply monitor is adopted from
the same RISCay revision. Source hashes are in `inputs.lock.json`; source
checkouts remain under build. No upstream qualification or endorsement is
inherited.

Deadhorse adaptations under D111: supported GF180 device names and 1 kOhm
poly; folded resistors preserving contact terms; autonomous weak-transistor
startup; compact guarded device placement and routing; MIM timing capacitors
for the LF candidate; selectable monitor threshold and qualified-release
hysteresis feedback; clocked Chisel readiness and POR qualification/cause
logic. Generated layout and circuit files remain experimental until the
reported checks close. See the T43 report for unsuccessful alternatives and
remaining electrical qualification.

Foundry device geometry and models are Copyright 2022 GlobalFoundries PDK
Authors, Apache-2.0. Imported PNP leaf geometry and foundry electrical models
remain unmodified. PCell-generated devices have explicit access-metal additions
in the generators; those additions are subject to DRC and extracted LVS. The
extraction-deck correction is separately recorded in `pnp-extraction.patch`. The standard-cell digital
layout is generated from the project's Chisel and pinned GF180 library.
