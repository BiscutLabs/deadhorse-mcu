# PLAN04 Clock/reset architecture

## Outcome

Blocked before RTL by the user's explicit stopped-oscillator USB-resume rule
and a frozen recovery-loader service-clock conflict; D78/D79 are recorded,
but implementation and architecture-document reconciliation are incomplete.

## What changed

- `docs/plan/10-decisions-and-risks.md`: recorded C1/C2 as D78/D79, amended
  D6/D35/D38 and resolved Q15 to external 48 MHz divided by six, main 8 MHz.
- `docs/plan/tasks/PLAN04-clock-reset.md` and task index: transcribed the
  assigned scope, acceptance and explicit stop rules; checks remain unverified.
- `docs/plan/STATUS.md`: approval records and blocked task entry.
- This report records the production-contract audit. No PLAN04 changes to
  RTL, soc.yaml, tests, timing constraints, assumptions or register maps.

Existing uncommitted T32 work on main at `9b80375109826e41d28cae95b1b80c653bfc34ff`
is preserved. It is not a PLAN04 implementation or a passing baseline.

## Checks run

Read-first review, independent source audit and documentation checks only.
Inspected production
bindings with `rg` and PowerShell `Get-Content`; no new simulation/formal/timing
result is claimed. In particular, none of these PLAN04 acceptance commands ran:

| Command | Status / reason |
| --- | --- |
| `python3 hw/top/reference/check_soc_map.py` | Not run; production map unchanged pending contract decisions |
| `python3 tools/sbt.py "hw/testOnly deadhorse.top.* deadhorse.osc_ctrl.*"` | Not run; controller not implemented |
| `python3 hw/ip/osc_ctrl/formal/check.py --output build/plan04/formal` | Not run; controller/properties not implemented |
| `python3 tools/timing/check.py --top DeadhorseSoc --domains main,aon,usb --output build/plan04/timing` | Not run; generated-clock implementation/constraints not implemented |
| `python3 tools/ci.py --tier fast` | Not run for PLAN04; user stop condition reached before implementation |

Documentation checks run on the local main working tree:

```text
python tools/env/run.py run -- python tools/check_structure.py --include-untracked
  -> exit 0; no output
git diff --check -- docs/plan/10-decisions-and-risks.md docs/plan/STATUS.md docs/plan/tasks/README.md
  -> exit 0; only a Git LF/CRLF normalization warning
```

Independent agent review confirms the blocker evidence, approval scope and
area arithmetic. Its decision-table formatting finding was corrected; this
review qualifies the partial documentation only, not the unimplemented RTL.

The prior T32 fast run failed its 9 MHz performance-core timing check; exact
command/evidence remain in [T32](T32.md). D78 selects 8 MHz but does not turn
that failed run into a pass. The later D80 T32 timing follow-up independently
closes the original 9 MHz screen and passes the repository fast gate; it does
not implement PLAN04. Full tier has not run for PLAN04. Approved decision and
stop documentation can be published separately; no PLAN04 RTL is delivered.

## Numbers

All numbers below are **estimated**, not new measurements:

- Frozen loader nominal maximum SCL: 32,000 AON edges/s / 8 edges per SCL
  period = 4,000 Hz. This is not a tolerance-qualified operating limit; use
  the minimum qualified RC frequency when specifying a recovery host.
- D78 main frequency: external assumed 48 MHz / 6 = 8 MHz; unchanged 60%
  timing rule gives 0.60 * 1000 / 8 = 75 ns before physical qualification.
- Approved analog allowance reduction: assumed 0.50 - (0.10 RC + 0.15
  POR/brownout) = 0.25 mm2. Current T32-inclusive plan08 estimated use
  12.855509285 - 0.25 = 12.605509285 mm2; estimated headroom under 12.92
  is 0.314490715 mm2. The existing assumed 0.10 mm2 digital clock/reset/power
  allowance is still included and must be replaced by the new measured logic.
- Earlier PLAN03 budget: 12.783522307 - 0.25 = 12.533522307 mm2, giving
  0.386477693 mm2 headroom. This explains the assignment's approximate 0.39
  expectation; it excludes the later T32 budget update and is not current fit.

Original measurement commands and revisions underlying those area estimates
remain in plan08 and the PLAN03/T32 reports. PLAN04 has not remeasured them.

## Deviations from the brief

Stopped before the comprehensive plan edits, soc.md/soc.yaml contract and RTL,
under the assignment's explicit stop rule. No alternate USB wake or recovery
clock architecture has been selected without approval. No test was removed,
weakened or relabelled as passing. D78/D79 remain approved regardless of the
pending implementation-contract choices.

## Open issues

1. **USB resume while OSC_IN is stopped.**
   `hw/ip/usb/src/main/scala/deadhorse/usb/Usb.scala` binds `resume.clk` to
   `usbClock`; its `sourceWake` register also uses that clock before shared
   synchronization into AON. `UsbResume.scala` explicitly requires its clock
   to run while attached. `usbClockRequest` is the synchronized USB enabled
   state, not transaction busy, so honoring it also prevents oscillator-off
   sleep while USB is enabled. Disabling USB detaches it and cannot substitute
   for attached host-resume detection. Pending user choice: keep OSC_EN high
   while USB is enabled and test resume in oscillator-on sleep, or authorize
   an AON resume detector plus the corresponding USB request-contract change.
   The latter changes USB behavior beyond mere connection of existing signals.
2. **Recovery loader clock.**
   `ClockedI2cTarget.scala` requires at least eight service edges per SCL and
   does not stretch SCL; `docs/spec/i2c-recovery-loader.md` states the same
   contract. `SocI1Peripherals.scala` binds the loader directly to AON. The
   former active-service clock cannot simply be replaced by nominal 32 kHz
   while retaining ordinary-speed recovery I2C. Pending user choice: a slow
   recovery-host contract qualified against minimum RC rate, preserving loader
   RTL, or separately authorized service-clock architecture. Existing tests
   and acceptance have not been changed.
3. **Boot readiness versus boot firmware.** Production LiteHart starts only
   on `acceptedLiteStart` from the recovery loader in SocI1Peripherals.
   Autonomous ROM boot is explicitly a T36 prerequisite/deliverable. PLAN04
   must distinguish domain release from autonomous boot and preserve the
   existing loader-start path unless separately authorized to implement T36.
4. **Reset cohorts and fallback bootstrap.** Existing external-pin warm reset
   retains loader lock; POR/brownout cold reset clears it. Combining all
   sources into the loader cold reset would violate the preserved reset
   matrix. Strap capture must not depend on the faulty RC/POR it bypasses;
   define and test an external-reset-held sampling sequence with a valid
   fallback clock, and safe initialization for normal POR-only power-up.
5. **UART monitor binding.** The existing UartWake block is not bound in the
   production top; Uart sleep mode is tied off and enabled RX asserts hold.
   Reuse its wake-only mode and sender preamble contract; do not infer wake
   polarity from raw RX independently of the configured UART polarity.
6. Complete plans 03/06/07/08/16 and T33/T34 reconciliation, source/pad contracts,
   implementation, all required tests/proofs/faults, measured area/timing,
   independent implementation review and fresh fast CI after the decisions.
   No PLAN04 deliverable is yet credited as implemented in T33.
7. Existing `DeadhorseSoc.coreSleeping` comes from the core's conservative
   sleep indication; no new WFI port is inherently required. Qualify it with
   coreReady/boot release and drained traffic: its reset value alone does not
   prove that WFI executed. Preserve individual wake causes before combining
   them, and do not use all AON demand as external-oscillator demand.
