# analog

Analog macro contracts and simulation models. No characterized Deadhorse
analog layout or silicon result is available.

- [LF RC interface](lf_rc/README.md): startup, trim and clock model boundary.
- [POR/brownout interface](por_brownout/README.md): thresholds, hysteresis,
  release and D85 switching contract.
- [Characterization and physical handoff](characterization.md): provenance,
  measurement matrix, missing views and inputs for later layout briefs.

T34 reuses the Chisel models in
[AnalogModels.scala](../hw/ip/osc_ctrl/src/main/scala/deadhorse/osc_ctrl/AnalogModels.scala).
Run `python tools/env/run.py run -- python dv/soc/analog/check.py --output build/t34/models`
for scoped model/interface acceptance. D87 excludes aggregate CI and unrelated
IP tests; this command cannot qualify an analog circuit or close I5.
