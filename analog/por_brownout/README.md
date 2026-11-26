# POR/brownout macro contract

Status: T34 interface/model contract. T43/D111 adds an experimental transistor
layout with clocked qualification logic and checked physical connectivity;
qualified detection latency and guaranteed voltage limits remain open.
`PorBrownoutMacro` and `PorBrownoutModel` retain the PLAN04/T33 boundary.

| Pin | Direction / width | Contract and production binding |
| --- | --- | --- |
| vdd, vss | Analog supplies | Chip VDD/VSS; qualify against digital and SRAM operating limits |
| threshold | Input, 2 bits | T33 registered AON selector, high bit tied low; cold/service-reset default 00 |
| test | Input, 1 bit | Tied low; reserved/inert in model; never a reset-release bypass |
| supplyReset_n | Output, active low | `OscClockReset.supplyReset_n`: async assertion, per-domain synchronized release; static POR_BYPASS and external pin retain D83/D84 behavior |
| powerOn_n | Output, 1 bit | Initial-power epoch diagnostic, intentionally unused by production reset logic |
| brownout | Output, 1 bit | Sticky indication to `ResetCauses.brownout`, sampled by existing AON cause logic |

| Encoding | Falling / rising threshold | Status |
| --- | --- | --- |
| 00 | 3.10 / 3.20 V | Assumed safe-default model values; physical safety unqualified |
| 01 | 3.20 / 3.30 V | Assumed higher setting; may not release with nominal-3.3 V regulator tolerance |
| 10, 11 | Same as 00 | Reserved safe-default behavior in model; T33 rejects writes of these values |

Threshold selection uses T33's existing shadow/keyed-apply/active registers,
not a new T34 ABI. No selection may bypass the startup default or mask an
undervoltage reset. Unknown/X/Z controls must not bypass qualification;
two-state simulation does not establish this for an unknown threshold selector.
Test is inert in the model. Four-state models and physical behavior remain
required before signoff; unknown inputs are not assumed safe.

## Model and D85 requirements

The environment supplies `reference`, **assumed 1 MHz**, and `supplyMv`, an
unsigned 12-bit millivolt stimulus (a simulation encoding, not a device rating).
Below the selected falling threshold reset asserts asynchronously. Release
requires **assumed 1000 consecutive reference rising edges** at or above the
selected rising threshold: **estimated 1000 / 1 MHz = 1 ms**. Supply in the
hysteresis window preserves released state but cannot release asserted reset.
A sample below the rising threshold restarts incomplete qualification.

Changing selection at valid supply may leave reset released. If voltage is
below the new falling threshold, assertion is immediate in the ideal model.
During incomplete qualification, any selection change discards old samples;
the next edge is the first sample under the new setting. No earlier samples
may be reused. This models D85, not measured analog transition behavior.

The assumed initial-power boundary is 100 mV. Below it, `powerOn_n` and the
brownout indication clear asynchronously. Above it, one reference edge after
release sets `powerOn_n`; a subsequent reference edge observing asserted reset
sets sticky brownout. A short dip below falling but above 100 mV still holds
reset for full requalification, allowing cause capture on the next reference
edge. No cause-retention promise is made across loss of power, a stopped
reference, or real pulses shorter than the eventual detection specification.
The physical macro must create its own qualification timebase: the model's
reference is not a new chip input, nor an assumption that AON already runs.

The modeled zero-delay assertion is an idealization. Characterization must
establish maximum detection plus reset-distribution delay, and show the rail
cannot pass below the qualified logic/SRAM limit before reset takes effect.
The assumed 100 mV margin above a characterized 3.0 V corner is not sufficient
evidence: threshold error, noise, supply slew and board hold-up must be included.

Area allowance: **assumed 0.15 mm2**. Physical test injection/observation is
not implemented; T37/T38 and the later analog brief own test access. Static
POR_BYPASS remains a board fallback, not an analog pass result. See the
[characterization matrix](../characterization.md).
