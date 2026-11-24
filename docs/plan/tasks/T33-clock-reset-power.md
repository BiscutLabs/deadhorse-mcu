# T33 Clock, reset and power controller

## Goal, inputs and readiness

Complete I3 digital clock/reset/sleep control after PLAN03, parallel with T32.
Use the production watchdogs, boot release, shared reset-release/CDC/clock-gate
wrappers and plan06; T34 behavioral macro interfaces may be agreed in parallel.
D78 resolves Q15: external 48 MHz OSC_IN directly clocks USB and registered
/6 main at 8 MHz; AON is LF RC with a reset-held external fallback. There is
no internal HF oscillator. PLAN04 delivers the oscillator controller, divider,
macro interface models, POR/pin reset hookup and strap binding; credit only
the evidence actually delivered in its report, not this assignment.

## Deliverables

1. Complete the reviewed clock/reset-domain and reset-reason register contract
   around PLAN04's OSC_IN divider/controller. No internal/external main source
   mux or runtime AON switching. Finish reset/test overrides and qualify the
   shared ICG and reset-held fallback at cell level. Do not redo accepted
   PLAN04 work; list remaining physical obligations explicitly.
2. POR, brownout, external and both watchdog reset causes; asynchronous assert,
   synchronized per-domain release only after supply/clock qualification.
   D37/D70 performance reset resets the core/client epoch and disables PWM,
   preserving shared buses, DMA, other peripherals and lite/retained state.
   Lite watchdog resets the MCU. Retain reason across perf reset, not power loss.
3. Drain/cancel transactions and perform a last pending-wake check before
   gating. Hold wake capture and HF requests in AON. Timers, GPIO, UART modes,
   USB resume and JTAG wake must survive stopped main; enabled peripherals keep
   their needed clocks. Retained sleep is clock gating, not power gating.
4. Complete brownout threshold selection with safe default and glitch-safe
   changes, reset-reason recording and retained-sleep entry/exit beyond PLAN04's
   oscillator controller. Use T34 LF RC and POR/brownout interfaces/models;
   no internal HF macro, PLL, seamless failover or analog accuracy claim.
   D81 keeps the oscillator on while USB is enabled; test attached light sleep.
   D82 keeps the frozen loader on LF AON with rate-qualified recovery SCL.

## Read first

AGENTS.md; plan README, STATUS, 03, 06, 07, 08, 10, 11–14 and 16;
docs/spec/soc.md and bus.md; PLAN03 report and the verification-debt register.
Skills: deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties, gf180-synth-timing-check,
formal-timeout-triage; regmap-authoring for new registers.

## Shared acceptance and publication (unverified)

D86 closeout exception (user, 2026-11-24): defer proof obligations requiring
extensive timeout work, with their exact unresolved status and evidence in
STATUS/report/ledgers. Keep proof entrypoints and assertions unchanged. Run
the frozen T33-specific regression and structural checks, not full CI or
unrelated IP tests; neither aggregate CI tier is claimed. This overrides the
aggregate CI requirement below for this closeout only. Independent review
and physical/stage-gate obligations remain. Completion must be labelled
"completed with D86 exceptions".

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

hw/ip/power_reset, necessary shared wrappers, top clock/reset/wake bindings,
power/reset register description, behavioral analog interface models, dv/soc
power tests, affected specs/ledgers and own report/tracker. No peripheral
behavior changes or application-specific output policy.

## Task acceptance (unverified)

- `python dv/soc/power/check.py --output build/t33/power`: actual production
  sleep/wake and reset at every grant/response phase, coincident wake/sleep,
  stopped external source, divider/reset-held AON selection, UART receive/wake-only/disabled, USB
  resume and JTAG wake; independent event/epoch oracle. Reset containment must
  preserve shared DMA/traffic and disable PWM for performance watchdog expiry.
- Unbounded controller proofs for no lost captured wake, no gate while required
  work/demand exists, legal release order and stale-response exclusion. Model
  only documented source readiness/fairness; list and justify assumptions.
  Reachability and missing-wake/early-release/wrong-reset-scope faults required.
- Enumerate every CDC/RDC path and qualify every reset cause and gate. Measure
  gate enable setup/hold, reset recovery/removal and minimum pulses with actual
  clock contracts; test glitch-free muxing at the cell-model level. Analog
  behavior remains T34/extracted characterization, never inferred from proof.
- Integrate T32 wake handshake, update area/timing budget; full tier at I3 exit.

## Stop conditions

Stop for altered D78/D79 architecture, altered D70 containment, new power-gated mode, changed
timing/assumptions or a required analog behavior not covered by the reviewed
interface. Record physical qualification still owed after digital acceptance.
