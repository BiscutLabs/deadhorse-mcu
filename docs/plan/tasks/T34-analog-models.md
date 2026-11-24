# T34 Analog macro interfaces and behavioral models

## Goal, inputs and readiness

Define I5's long-lead analog interfaces and simulation models after PLAN03;
may start before or alongside T32/T33. This brief does not implement analog
layout/extraction. Read plan06, pinned GF180 device/voltage limits and the
available RISCay oscillator/POR/monitor provenance. No Coldfoot IP import.

## Deliverables

1. Pin-level contracts for nominal 32 kHz LF RC and POR/brownout with
   selectable thresholds. D78 removes the internal HF oscillator; D79 requires
   safe POR default, hysteresis and qualified release, with POR_BYPASS fallback.
   Reuse PLAN04 interfaces/models where accepted rather than replacing them
   silently. List supplies/grounds,
   enables, trims, ready/clock-valid/reset outputs, test/calibration signals,
   encodings and safe hardware defaults before flash/software initialization.
2. Clocked digital behavioral adapters/models for simulation, with documented
   simulation-only clock generation and voltage/ramp inputs. Model startup,
   stop/restart, not-ready, threshold changes, hysteresis and qualified release.
   Bad/unknown trim encodings must not bypass safe startup/reset. Keep analog
   macro boundaries explicit; no model is claimed to implement analog devices.
3. Characterization plan: PVT and mismatch, frequency/trim range and monotonicity,
   jitter/duty cycle, startup/restart, leakage/active power, slow/noisy supply
   ramps, threshold/hysteresis accuracy and switching, reset minimum pulses,
   invalid supply, loading and brownout. State measurement methods and corners.
   Carry plan06's assumed LF targets: within 5% after trim and <1 uA; whole-chip
   sleep<50 uA at25 C. External oscillator startup is a board-part requirement;
   oscillator-off wake takes milliseconds plus qualification, while light sleep
   keeps OSC_EN high. No internal HF or former 200 us deep-wake target remains.
   These are targets, not simulated silicon results.
4. Map interface models into the single SoC with T33; list trim/calibration
   loading and test access. Propose later layout/extraction/DRC/LVS briefs with
   measured macro dimensions/views; plan08 assumes 0.10 mm2 LF RC and 0.15 mm2
   POR/brownout. Demonstrate safe threshold defaults before firmware or flash
   settings; numerical encodings/limits remain assumptions until characterized.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 07, 08, 10, 11–14 and 16;
docs/spec/soc.md and bus.md; PLAN03 report and the verification-debt register.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage; regmap-authoring for new registers.

## Shared acceptance and publication (unverified)

User amendment D87 (2026-11-24): use relevant T34 model/interface/integration
checks instead of aggregate fast/full CI; do not run unrelated IP tests.
Defer proofs needing extensive timeout work and explicitly retain their debt.
Independent review and frozen scoped evidence remain required. This amendment
does not waive physical characterization or close any integration/signoff gate.

All acceptance below is **unverified**. Proposed new checker interfaces are
deliverables to create, not existing or passing tools. Each checker must emit
source/tool hashes, commands, classified results, assumptions, covers and actual
fault controls under build/. No source-text matching tests. Preserve existing
tests, assertions, solver caps, timing budgets and inherited debt.

Integrate in the single production DeadhorseSoc and soc.yaml; no feature
profiles. Use named test fixtures only. Obtain independent contract review before
RTL, then independent implementation/evidence review. Run the fast tier on main
before starting and on the frozen final snapshot, and the full tier if completing
I2, I3, I4 or I5 (D76). Record both tier statuses and all deferrals. Update the task
report and STATUS; commit/push only after required checks/review. Do not tick
this brief's acceptance boxes or a gate.

Pinned invocation prefix: `python tools/env/run.py run --`. Existing checks:
`python hw/top/reference/check_soc_map.py`,
`python tools/check_structure.py --include-untracked`,
`python tools/ci.py --tier fast --output build/<task>/fast`.
Use the reviewed USB evidence interface when required; never skip USB.

## May change

analog/<macro> interface/model documentation, hw/top analog wrappers, T33
interface bindings, dv/soc analog-model tests, environment model support,
affected contracts and own report/tracker. No oscillator circuit redesign,
layout, OTP, PLL or LF crystal-driver implementation in this brief.

## Task acceptance (unverified)

- `python dv/soc/analog/check.py --output build/t34/models`: every model pin
  binds to its specified digital consumer; startup/stop/restart/ramp/threshold
  scenarios and wrong-ready/early-release fault controls pass an independent
  timeline oracle. All simulation-only values are labeled assumed.
- Digital safety checks enforce safe defaults, ready/reset sequencing and
  valid trim encodings; formal covers/faults where applicable. Do not call
  analog jitter, metastability or supply accuracy formally proved.
- Independent analog/digital interface review, full characterization matrix,
  named missing foundry views and later-layout brief inputs. No gate signoff.

## Stop conditions

Stop for targets incompatible with qualified process/SRAM limits, changed
threshold policy, new trim-storage hardware or missing provenance. Report
unknown physical figures as unknown, not values copied from simulation.
