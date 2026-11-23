# PLAN04 Tapeout clock/reset architecture

## Goal, inputs and readiness

Implement the user's 2026-11-22 PLAN04 assignment on main under D78/D79.
Record approvals independently of implementation evidence. Preserve all existing
block behavior, register maps, shared CDC and D37/D70 reset containment.
This task delivers a subset of T33; analog layout is outside its scope.

Read AGENTS.md; plans 03, 06, 07, 08, 10 and 16; docs/spec/soc.md;
hw/top/reference/soc.yaml; T32-T38 briefs; PLAN03 report. Load task-execution,
clocked-Chisel, formal-properties, reference-model-testing, GF180 timing and
formal-timeout-triage skills before implementation.

## Deliverables

### A. Architecture and planning

Update plans 03/06 for on-die nominal 32 kHz RC AON, external 48 MHz CMOS
OSC_IN directly supplying USB, and registered divide-by-six main at 8 MHz.
Remove internal HF oscillator. Preserve shared crossings despite related clocks.
OSC_EN is high during/after reset, with board pull-up, and controls standby.
AON_CLK_SEL sampled during reset selects RC or fallback AON_CLK_IN, then holds.
POR_BYPASS sampled during reset permits external-pin-only reset/release.

Specify release order: POR/brownout and pin release, AON oscillator running,
AON stability count and domain release, lite boot, external oscillator stable,
main release. Distinguish clock/domain readiness from the T36 autonomous boot
implementation. Describe oscillator-off sleep with external startup plus counts
(milliseconds) and lighter oscillator-on sleep with fast wake.

Update plan07 for OSC_IN, OSC_EN, AON_CLK_IN, AON_CLK_SEL and POR_BYPASS.
Require external oscillator 48 MHz, CMOS, 3.3 V, true microamp standby, frequency
tolerance well within USB full-speed +/-0.25%, datasheet startup basis and a
labelled assumed maximum. Reuse the existing dedicated clock pad for OSC_IN.

Update plan08 analog allowance from assumed 0.50 mm2 to assumed 0.10 mm2 LF
RC plus 0.15 mm2 POR/brownout. Recalculate current headroom and pad budget;
digital additions must fit the existing assumed 0.10 mm2 clock/reset/power
allowance. Analog deliverables are LF RC trim and POR/brownout safe default,
hysteresis and qualified release. Update D6/D35/D38/Q15 and risks K3/K4/K12;
add startup-time, USB stopped-clock wake and POR first-silicon failure risks.

### B. Production implementation (T33 subset)

Update soc.md and soc.yaml before RTL. Describe analog pin-level interfaces and
all new pads/strap sampling. Use BlackBoxes with behavioral models only for RC
and POR/brownout; POR model exercises supply ramp, thresholds, hysteresis and
brownout. External reset OR non-bypassed POR/brownout holds ordinary domains
reset, with asynchronous assertion and shared synchronized release, AON first.
Preserve distinct cold/warm reset semantics and latch POR/brownout/pin cause for
T33. Do not let fallback strap sampling depend on a failed source it bypasses.

Implement registered divide-by-six, 50% duty cycle, generated-clock constraints;
USB retains direct OSC_IN. Add hw/ip/osc_ctrl with AON-clocked RUN, STOPPING,
OFF and STARTING states and regmap YAML for sleep request, wake enables,
startup delay, stable count, state, fault and last wake cause.

Stop only after firmware request, perf WFI and all existing UART/SPI/I2C/DMA/
PWM/QSPI/mailbox/bridge/USB/timer clock requests and holds are released.
Close the shared main ICG before lowering OSC_EN. Capture enabled AON timer,
GPIO, UART monitor, USB AON resume, lite mailbox and JTAG placeholder wakes
in every state. Wake raises OSC_EN, waits programmable AON startup delay, then
requires programmable OSC_IN count observed through shared synchronization.
OSC_IN counter is held reset while OSC_EN is low. Startup failure sets sticky
fault, retains OSC_EN high and never opens an unverified clock gate.

Prove each with a negative control: reset-high OSC_EN until completed sleep;
no OSC_EN fall under request/hold; gate opens only after fresh stability;
no lost wake in any state; glitch-free reset behavior and exact divider ratio;
POR blocks domain release unless bypassed and bypass makes POR irrelevant;
straps remain fixed after reset release.

Production tests: slow/fast POR ramps, reset-high OSC_EN, both clock/bypass
straps; brownout whole-chip reset and recorded cause, hysteresis rejection;
each sleep/wake source including USB with stopped oscillator and JTAG pulse;
never-start/late oscillator fault and closed gate; retained main state and
unchanged flight-loop benchmark after wake. Measure domain worst paths, OSC_IN
counter, AON controller and all new digital area with generated 8 MHz main.

### C. Remaining T33/T34 scope

Rewrite plan16 and task index; revise T33 to retain full pin/POR/watchdog reset
sequencing, reset-reason register, threshold selection with safe default and
retained-sleep sequencing beyond this controller. Identify PLAN04 deliveries
by evidence so T33 does not redo them. Revise T34 to LF RC and POR/brownout
pin interfaces, digital behavioral models, trim/threshold encodings with safe
defaults and plan06 characterization targets; no internal HF macro.

## Acceptance (unverified)

- [ ] `python3 hw/top/reference/check_soc_map.py`
- [ ] `python3 tools/sbt.py "hw/testOnly deadhorse.top.* deadhorse.osc_ctrl.*"`
- [ ] `python3 hw/ip/osc_ctrl/formal/check.py --output build/plan04/formal`
- [ ] `python3 tools/timing/check.py --top DeadhorseSoc --domains main,aon,usb --output build/plan04/timing`
- [ ] `python3 tools/ci.py --tier fast`
- [ ] Independent controller/reset/proof/plan review; report all numbers as
  measured with command/revision or assumed (derived estimates show arithmetic).
- [ ] Commit and push to main only after fast passes under D76.

These command interfaces are proposed by the assignment, not existing results.
Startup delay/count and POR thresholds/release remain assumptions until the
external part and T34 macro are qualified. No other block behavior or register
map changes. Stop and ask for missing/misinterpreted hold/wake/reset signals,
USB resume undetectable with oscillator stopped, negative area budget or main
8 MHz timing failure. Progress belongs in STATUS and the report, not these boxes.
