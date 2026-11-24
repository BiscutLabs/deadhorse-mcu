# LF RC macro contract

Status: T34 interface and digital simulation contract; no oscillator circuit,
layout or characterized timing/power/trim curve is delivered. Production uses
`LfRcMacro` in `DeadhorseSoc`; `SocAnalogModelTest` substitutes `LfRcModel` only.
No internal HF oscillator is included (D78).

| Pin | Direction / width | Contract and production binding |
| --- | --- | --- |
| vdd, vss | Analog supplies | Chip VDD/VSS; nominal 3.3 V assumed, valid range to qualify with selected devices and SRAM |
| enable | Input, 1 bit | Tied high in production, including reset and retained sleep; no firmware shutdown |
| trim | Input, 6 bits | Tied to startup code 0 before and after reset; no trim register/storage or loading path exists |
| test | Input, 1 bit | Tied low; reserved, no clock-valid or reset-release bypass |
| clock | Output clock | Feeds `OscClockReset.rcClock`, then reset-held AON source selection and counted bootstrap |
| ready | Output, 1 bit | Diagnostic, intentionally unused by production; counted received AON edges are the existing release authority |

Code 0 is the **assumed** startup setting. Codes 1–63 are reserved/unqualified
and the digital model treats them as code 0; none may bypass startup. There
is no claimed tuning direction, step size or frequency range for these codes.
The later macro design must implement safe reserved-code behavior or obtain a
reviewed encoding revision. Unknown/X/Z trim/test controls must not bypass
qualification. These model inputs do not affect ready/clock/reset logic;
two-state tests cover binary encodings only. Four-state simulation and
power-ramp electrical behavior remain explicit qualification gaps, not an
assumption that unknown controls are safe.

The nominal 32 kHz rate, within 5% after trim and less than 1 microamp supply
current are **assumed targets** from plan06. Untrimmed code0 must start safely;
its frequency bounds must be characterized before firmware can rely on time or
the recovery-loader SCL limit. These targets have not been measured on this
macro. Its area allowance is **assumed 0.10 mm2**, not a footprint.

## Simulation-only behavior

`source` is supplied by the simulation environment; `out` forwards its edges.
The model is not a synthesized oscillator or an enable-controlled clock gate.
The environment parks source low to represent stop and schedules actual edges
to represent startup/restart, jitter or a never-starting oscillator.
`power_n` represents supply availability (production test wrapper uses assumed
100 mV). Low power asynchronously clears readiness. With power and enable high,
ready asserts after **assumed four supplied rising edges**. A disabled sampling
edge clears readiness; stop tests supply this edge before parking source.
Changing enable/trim while consumers run is not a production operation.
Trim/test cannot shorten that qualification; frequency accuracy is not modeled.

Supply loss, startup and a stopped source are tested at model ports. Production
tests separately exercise both AON strap selections, POR bypass and counted
reset release. Absent-external-oscillator evidence remains the inherited T33
test, not a new T34 run. Analog ready itself is not a new
trusted input to the reset controller.

## Calibration and test handoff

There is currently no production firmware/JTAG trim-loading path, OTP, eFuse,
trim retention or analog test mux. T34 adds none. T37/T38 and the later macro
brief must specify a reviewed test/calibration access route and storage choice
before physical freeze; new trim storage requires an explicit decision.
Frequency may be measured at the macro clock in standalone characterization;
this does not claim package-level access. AON_CLK_IN is the existing first-
silicon fallback and is not a trim mechanism. See the
[characterization matrix](../characterization.md).
