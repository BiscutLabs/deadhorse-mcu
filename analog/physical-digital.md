# Digital logic inside the physical analog macros

D111 implementation work in progress; these circuits are not yet production
physical views. They use the shared reset-release primitive and the existing
clocked Chisel toolchain. There is no main-domain service oscillator or new
package interface.

The LF readiness circuit uses four local clock edges: two in `ResetRelease`,
then two data-shift flops. All four use the common initializer reset; the
synchronized indication is data, avoiding an intermediate same-clock reset
release boundary. The analog initializer must hold it in reset
until the actual mapped flops can initialize; the physical circuit must prove
this in extracted power-ramp simulation. Disable clears readiness and its
history. Production enable is tied high. Reserved trim/test remain inert.
The asynchronous disable response is a physical detail; the existing model
samples disable on a supplied source edge before the environment stops it.
Both require four fresh edges before ready can return.

The POR qualification/cause circuit uses an autonomous internal timebase input;
the complete physical macro must supply it internally.
The model's 1 MHz reference and 1 ms release are assumptions, not measured
physical limits. Keep 1000 consecutive qualification edges and characterize
the resulting physical delay. Ordinary undervoltage must clear qualification
without clearing the cold-power epoch or sticky brownout indication.

The analog monitor's hysteresis feedback must use qualified release, so an
incomplete qualification cannot count samples in the hysteresis window.
Threshold selection applies at the analog selector immediately. A one-hot
encoding is sampled through four shared single-bit synchronizers only to
acknowledge stability; those sampled bits never select an analog threshold.
A mismatch asynchronously clears the count and its shared reset-release
qualification history. Final release also explicitly checks that no mismatch
is pending. Reserved selections use the safe threshold. The two safe-release
edges and selector acknowledgement add latency before the 1000-edge count;
they do not shorten qualification. Already-released valid supply remains
released across a selection change unless the analog comparison asserts reset.

## Scoped digital evidence

Measured on base commit `b99f75454bad2bad788872e03fbe8afbc9cf9d1d` plus the
receipt-hashed working sources, using the pinned `tools/env/run.py` environment:

- `python3 hw/ip/osc_ctrl/formal/lf_ready_check.py --output build/t43/lf-ready-formal03`:
  unbounded ABC PDR proof, reachable-ready cover and targeted early-ready
  rejection pass. The only assumption is initial `power_n=0`; later power and
  enable are arbitrary. The cover and fault use the same four-edge circuit.
- `python3 hw/ip/osc_ctrl/formal/por_physical_check.py --output build/t43/por-physical-formal04`:
  unbounded SMT k-induction at the production 1000-edge parameter passes
  minimum uninterrupted raw-good duration, cold-epoch/cause persistence and
  capture, and reserved-code decoding. Range helpers are proved assertions,
  never assumptions. The only assumption is initial `cold_n=0`; later inputs
  are arbitrary. Covers use the same generator at nine edges; the bypass
  negative control retains the production 1000-edge parameter.
- `python3 tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.AnalogPhysicalSpec"`:
  two tests pass, including the early-ready negative control.
- `python3 tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.PorPhysicalSpec"`:
  three tests pass. Directed cases include both eight and 1000 edges,
  final-edge selection changes, selector excursions between local edges,
  short raw-bad pulses, reserved codes, cold clear and retained causes.

The POR formal elapsed counter tracks raw-good duration, not duration since
the latest selector change. Full D85 selector-restart behavior currently has
directed simulation evidence, not an unbounded proof. Physical pulse
recognition, switching glitches, metastability and cold initialization are
separate unresolved analog obligations. Independent review accepted these
digital components with those limits.

No complete-macro analog or physical acceptance follows from those checks.
Full macro current includes this logic and its actual clock load. The existing
analog characterization matrix remains open. The digital LF model's assumed
four supplied edges do not define an electrical 50%-of-VDD initializer
threshold during a power ramp; all measured ramp excursions must be recorded.
