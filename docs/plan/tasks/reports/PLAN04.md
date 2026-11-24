# PLAN04 Clock/reset architecture

## Outcome

Original acceptance remains incomplete because source-clock/gate composition
is unproved; the implementation is carried into T33's completed D86 closeout,
with explicit proof deferrals and no physical or I3 signoff.

## What changed

Work originated on main at `2c33976` and is published with the T33 closeout:

- Plans 03/06/07/08/10/16, STATUS, task index, T33/T34 briefs: D78/D79
  architecture reconciliation; D81 keeps the oscillator on while USB is enabled;
  D82 limits frozen-loader SCL to minimum qualified AON frequency / 8; D83 makes
  bypass-mode pin reset cold; D84 makes POR_BYPASS static while powered.
- SoC/loader specifications, `soc.yaml`, map checker and fault tests: selected
  clocks, five clock/control pad functions, lite-owned oscillator child at
  0x40000400, analog model interfaces and labelled assumptions.
- `hw/ip/osc_ctrl/`: register YAML, AON sequencer, stability counter,
  shared-ICG handshake, phase-completing /6 divider, reset-held strap bootstrap,
  analog BlackBox interfaces and digital models, simulations and partial proof.
- Production peripheral assembly/configuration and preparation: new child,
  existing UART wake monitors/sleep inputs, individual wake causes and safety
  holds. UART, USB and loader block RTL/register maps are unchanged.
- Focused SoC decode test keeps its reserved-hole assertion at the next
  unassigned child, 0x40000500, and adds oscillator-child default/ownership checks.
  No existing test is dropped or silently marked passing.

Independent review found stale closure acknowledgement, raw stability versus
AON authorization, and reset-truncated divider pulses. Corrections are present;
full composition review is still required. DeadhorseSoc now binds the analog
interfaces/models, oscillator control, shared ICG, /6 divider, qualified reset
and pad functions. The same full digital assembly remains in the named
SocExternalClockTest for existing independent-clock tests, including historical
9 MHz trials. Production supports 8 MHz only. No production feature is removed.

The UART request/modes now use a shared CDC FIFO and read acknowledgement;
surrounding registers use the FIFO's locally qualified reset releases. Review
also found stale source authorization across oscillator-off sleep; OSC_EN falling
now asynchronously resets that path, with release on ungated /6. The fault
regression catches the previous early-open behavior. Reset causes are provisional
T33 status signals, separate from the unchanged loader watchdog ABI; cold reset
takes priority over an overlapping pin pulse wholly inside cold reset.

## Checks run

Every command below ran this session in the working tree based on `2c33976`.
Prefix is `python tools/env/run.py run --`; intermediate results are not
frozen acceptance.

| Command | Last result / scope |
| --- | --- |
| `python hw/top/reference/check_soc_map.py --output build/plan04/map` | PASS provisional SoC map: 20 regions; not RTL or pin-fit acceptance |
| `python -m unittest discover -s hw/top/reference -p test_soc_map.py` | Ran 11 tests; OK |
| `python dv/soc/prepare_i1.py` | PASS map and generated register descriptions, including osc_ctrl |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.OscSequencerSpec"` | All 5 tests passed, including lost-wake fault; subsequent authorization/closure changes are covered by all-focused02 below |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.OscClockSpec"` | All 4 tests passed: phase/reset/ratio and wrong-divider fault, source counting, gate authorization/closure |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.ResetBootstrapSpec"` | All 5 tests passed: both straps, dead-RC/stuck-POR fallback, normal POR boot and asynchronous reset; downstream cold-only initialization is not covered |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.AnalogModelSpec"` | All 1 tests passed: slow/fast ramps, hysteresis and brownout model; not analog qualification |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.OscCtrlSpec"` | All 1 tests passed: lite ownership, defaults, byte masks, denied effects and holes |
| `python hw/ip/osc_ctrl/formal/check.py --policy-only --output build/plan04/formal-policy02` | PASS: unbounded policy safety, four covered witnesses, lost-wake/gate-refusal faults rejected |
| `python tools/sbt.py "hw/testOnly deadhorse.top.SocI1Spec -- -z serial"` | FAILED before stimulus: Verilator treats vendor dm_csrs.sv:207 CMPCONST as fatal |
| `python tools/check_structure.py --include-untracked` | Exit 0 at intermediate snapshot |
| `git diff --check` (host Git) | Exit 0; LF/CRLF notices only |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.OscSleepTransferSpec deadhorse.osc_ctrl.ResetBootstrapSpec"` | All 7 tests passed after D84 and local FIFO reset qualification; includes premature-ack fault |
| `sby -d build/plan04/por-initial01/check build/plan04/por-initial01/check.sby` | Historical latched-bypass diagnostic ERROR: reset feedback produces topological loop; not a counterexample or proof |
| `sby -d build/plan04/por-initial02/check build/plan04/por-initial02/check.sby` | D84 arbitrary-initial-state POR check bounded PASS through 8 steps; superseded by unbounded reset-formal01 |
| `python hw/ip/osc_ctrl/formal/reset_check.py --output build/plan04/reset-formal01` | PASS: POR initial-state, normal and bypass PDR proofs; six concrete reset/strap/early-release faults rejected; covers for both AON selections in each mode |
| `python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.OscBoundarySpec"` | All 2 tests passed: startup, retained service state through deep sleep, fresh-epoch gate safety; stale-authorization fault rejected |
| `python tools/sbt.py "hw/runMain deadhorse.top.EmitSoc build/plan04/production-emit01 production 8"` | Production physical-macro top emitted; later cause/gate-reset edits require fresh emission |
| `python tools/sbt.py "hw/testOnly deadhorse.top.SocDebugLintSpec"` | All 5 tests passed: exact pinned diagnostic setup, changed file/message/rule and source drift rejected; unrelated CMPCONST remains fatal |
| `python tools/sbt.py "hw/testOnly deadhorse.top.SocClockResetSpec"` | All 5 production-wrapper tests passed: both AON/bypass settings, POR ramps, hysteresis/brownout/pin causes, never/late-start fault containment |
| `python hw/top/reference/check_soc_map.py --output build/plan04/map` and map unittest command above | PASS and 12 tests OK after explicit D84 strap metadata and negative controls |
| `python -m unittest tools.timing.test_timing` | Ran 27 tests; OK; added D78 8 MHz/32 kHz characterization points, other limits unchanged |

The partial proof's exact source/model hashes and job results are in
`build/plan04/formal-policy02/result.json`. It assumes initial asserted reset,
then arbitrary resets, settings, demands, wake and source-report inputs. It does
not establish truthful source reports, actual gate pulses, POR/strap reset
composition or analog behavior. The default formal checker now fails closed;
`--policy-only` explicitly selects the partial diagnostic. Historical policy01
PASS predates review corrections and is not evidence for the current sources.

Initial failures and corrections are preserved in this record: obsolete pad
expectations; an ineffective old overlap fault that set already-zero boot ROM
to zero (now overlaps debug memory); inferred anonymous-module cast; missing
existing simulator ICG binding; invalid test-side Chisel clock-literal creation.
Those focused checks passed after correction without relaxed assertions/caps.
The SoC CMPCONST setup is repaired with an independently reviewed exact-file,
exact-source-hash and message control. The fixed two-hart BlackBox wrapper hash
is checked too. Other warnings remain fatal, with negative controls. Pinned
Verilator's line-only control did not suppress this late diagnostic; combining
line and match is rejected by its parser. Its own generated waiver format and
[official control-file documentation](https://verilator.org/guide/latest/control.html)
support exact file/message matching. No vendor source or hardware parameter is
changed. The subsequent serial test exposed an older inactive-JTAG assertion
under active T32 TAP stimulus. The two non-debug callers now park TCK low/TMS
high before applying input sweeps; every original safety assertion and the
separate exhaustive stub and active TAP tests remain. The rerun passed:

```
python tools/env/run.py run -- python tools/sbt.py "hw/testOnly deadhorse.top.SocI1Spec deadhorse.top.SocI1CoreResetSpec"
  -> 10 tests succeeded, 0 failed (build/plan04/focused-integration02.log)
```

The stability counter's original decrement measured 13.242579 ns against the
unchanged 12.5 ns limit. A plain nibble decomposition measured 12.848482 ns.
Keeping parallel decrement candidates, following the core's existing
carry-select pattern, measured 10.086461 ns. No state or latency is added.
Independent review accepted the arithmetic and its unbounded equivalence;
the wrong-decrement negative control and stable cover pass. The standalone
ICG runner now records literal test-enable ties rather than demanding a timed
path from a constant. Dynamic enable pins retain all four setup/hold queries;
unknown ties fail closed, with unit coverage. These are implementation/tooling
repairs, not timing-limit changes.

```
python tools/env/run.py run -- python hw/ip/osc_ctrl/formal/stability_equivalence.py --output build/plan04/stability-equivalence03
  -> correct proved; fault fault_rejected; cover covered; PASS
python tools/env/run.py run -- python tools/sbt.py "hw/testOnly deadhorse.osc_ctrl.OscClockSpec"
  -> 4 tests passed (counter-repair01.log, first decomposition; final version covered by all-focused02 below)
python -m unittest tools.timing.test_timing -q
  -> 28 tests OK (historical host check; later pinned 32-test result recorded below)
```

The broad production/oscillator suite completed in `all-focused01.log`:
107 tests, 100 passed and seven failed (measured, test wall time 26 m 40 s).
Its already compiled fixture exposed six unconnected DMA-harness clock-control
cases and one watchdog stimulus exceeding the native fabric's unchanged
128-running-cycle timeout before watchdog expiry. Connecting continuous-clock
fixture inputs cleared all six DMA cases in `corrected-focused01.log`.
The watchdog fixture now advances AON with sparse main edges while waiting for
its synchronized warning, then holds main through expiry. Unrelated cause/SRAM
reads move after DMA completion. All original assertions and limits remain;
the corrected watchdog rerun passed all five tests in measured 71 s test time
(`production-sleep-debug02.log`, `python tools/sbt.py "hw/testOnly deadhorse.top.SocWatchdogSpec"`). The production loader/WFI test initially
failed because simulator memory randomization replaced the ROM image. The
read-only retirement trace showed `0xaf4a` at boot PC `0x80` instead of firmware
word `0x400122b7`. Reusing the existing ROM tests' `memories=false` policy,
while retaining register randomization, fixes this fixture. The unchanged
sleep/wake assertions then passed all three UART deep wakes in measured 277 s
test time (`production-sleep-debug03.log`, `python tools/sbt.py "hw/testOnly
deadhorse.top.SocClockResetSpec -- -z \"real loader\""`). Real loader programming,
WFI, GPIO retention and firmware-checked wake causes are exercised. No failing
test is dropped. At that snapshot, production wake/retention was incomplete;
the completed scenarios and complete-suite result follow below. Full composition
remains incomplete. Frozen fast CI now passes as recorded below; full tier has
not run.
The prior T32 fast PASS_WITH_DEFERRALS is prerequisite evidence only, not
acceptance of these modifications. No commit or push.

After the ordered gate-command repair, `python tools/sbt.py "hw/testOnly
deadhorse.osc_ctrl.* deadhorse.top.SocClockResetSpec"` passed all 28 tests
in measured 511 s test time (`gate-commands-production01.log`). This includes
unchanged boundary acknowledgement deadlines, persistent-work cancellation,
adjacent request changes, and the real-firmware UART wake case. Independent
review accepted the repair by inspection; complete formal composition remains
unresolved, as detailed in the oscillator ledger. No acceptance claim follows
from these focused passes.

The production AON timer and lite-mailbox wake extension passed:

```
python tools/env/run.py run -- python dv/soc/prepare_osc_sleep.py
  -> PASS production oscillator sleep firmware prepared
python tools/env/run.py run -- python tools/sbt.py 'hw/testOnly deadhorse.top.SocClockResetSpec -- -z "timer and lite-mailbox"'
  -> 1 test succeeded, 0 failed; measured 289 s test time / 300 s sbt
     (build/plan04/production-extra-wakes01.log)
```

Both wakes originate in real AON peripherals driven by the lite firmware, with
the external oscillator model stopped during OFF. Firmware checks each cause;
the public GPIO signature and core/service status check retained main state.
Independent review accepted the stimulus and unchanged UART checks. GPIO and
actual JTAG DMI wake, USB light-sleep resume and paired flight-loop results
follow below. Full frozen acceptance remains separate.

```
python tools/env/run.py run -- python tools/sbt.py 'hw/testOnly deadhorse.top.SocClockResetSpec -- -z "GPIO wake" -z "JTAG wake"'
  -> 2 tests succeeded, 0 failed; measured 447 s test time / 458 s sbt
     (build/plan04/production-pin-wakes01.log)
python tools/env/run.py run -- python -m unittest tools.timing.test_timing hw.top.reference.measurements.test_plan04_screen
  -> 32 tests, OK (build/plan04/timing-units-wake01.log)
python tools/env/run.py run -- python tools/check_structure.py --include-untracked
  -> exit 0 (build/plan04/structure-wake01.log)
```

GPIO1 uses the real acknowledged AON wake configuration; JTAG sends a DMI
dmstatus read through the pinned TAP and production pending-TCK crossing.
Both firmware checks verify the expected wake cause before reporting success.
JTAG wake functionality is measured, not an end-to-end latency bound: shifting
the request advances clocks before the final polling window.

```
python tools/env/run.py run -- python tools/sbt.py 'hw/testOnly deadhorse.top.SocClockResetSpec -- -z "USB resume"'
  -> 1 test succeeded, 0 failed; measured 228 s test time / 238 s sbt
     (build/plan04/production-usb-wake01.log)
```

The real USB resume detector and AON path wake main from light sleep; OSC_EN
and pull-up stay high. Firmware checks wake bit 5 and the final retained-state
signature. Stimulus durations are derived from the assumed model clocks:
10,000 AON ticks / 32 kHz = 312.5 ms idle, then 640 / 32 kHz = 20 ms K.
The USB idle qualifier is unchanged. This checks the production wake path,
not complete enumeration/resume protocol compliance or measured wake latency.

The first flight measurement was stopped while waiting for the Scala lock,
before emission/compilation: independent review rejected a broad warning flag
inherited from the historical runner. The replacement uses the exact reviewed
vendor-file/hash/message exception; other diagnostics remain fatal. The new
runner authenticates both workloads and their loaded SRAM payloads, preserves
the existing cycle cap and records ROM/firmware/helper hashes.
The second flight run stopped before compile because the explicit emitter
strips a trailing vendor source-location comment. Independent review verified
that sole byte difference and the new exact hash; the diagnostic exception's
file, rule, message, two-hart parameter and wrapper hash remain unchanged.

```
python tools/env/run.py run -- python hw/top/reference/measurements/plan03_production_benchmark04.py build/plan04/flight-prepared01
  -> PASS workload preparation; unchanged workload objects checked
python tools/env/run.py run -- python hw/top/reference/measurements/plan04_flight.py --prepared build/plan04/flight-prepared01 --output build/plan04/flight-sleep03
  -> fixed PASS unchanged before/after wake 3879.7916666666665 4350
  -> hard-float PASS unchanged before/after wake 7809.833333333333 9007
  -> result.json status pass; source/hash recheck passed
```

Measured on `2c33976` plus the receipt-hashed working tree, with assumed
48 MHz OSC_IN, generated 8 MHz main and 32 kHz AON:

| Workload | Windows per run | Baseline mean / worst cycles | After deep wake mean / worst cycles |
| --- | ---: | ---: | ---: |
| Fixed point | 120 | 3879.791667 / 4350 | 3879.791667 / 4350 |
| Hard float | 120 | 7809.833333 / 9007 | 7809.833333 / 9007 |

Every window matches exactly, not just the aggregate. Both variants match the
historical target-ISS checksum receipt, authenticated to the byte-identical
freshly rebuilt workload. ROM copies the same SRAM payload before either
baseline WFI or UART deep sleep; the real recovery loader and lite core perform
release/wake. Checksum corruptions are rejected. This is paired workload and
retention evidence, not whole-program ISS lockstep or a new loop-rate acceptance.
Measured simulation wall times are 106.145/151.543 s for fixed baseline/wake and
107.475/157.990 s for hard-float baseline/wake. Independent review streamed all
four raw traces/cycle files, recomputed the loop measurements and checked all
213 recorded input hashes; no simulation rerun was represented as review.

The complete focused acceptance suite passed on the unchanged RTL snapshot:

```
python tools/env/run.py run -- python tools/sbt.py 'hw/testOnly deadhorse.top.* deadhorse.osc_ctrl.*'
  -> Run completed in 48 minutes, 2 seconds.
  -> Total number of tests run: 114; suites completed 33, aborted 0.
  -> Tests: succeeded 114, failed 0, canceled 0, ignored 0, pending 0.
  -> All tests passed; Total time: 2887 s.
```

Measured by `build/plan04/all-focused02.log`, based on `2c33976` plus the
working tree. The fresh map command `python hw/top/reference/check_soc_map.py
--output build/plan04/map-final01` also passed: 20 regions, provisional map only.
The USB boundary refresh's first attempt (`usb-boundary01`) stopped before RTL
emission because its runner supplied an absolute path to the relative-path-only
EmitSoc interface. The runner argument was corrected; no emitter or RTL change.
The corrected run passed and was independently reviewed:

```
python tools/env/run.py run -- python hw/top/reference/measurements/plan04_usb_boundary.py --base build/plan04/production-timing12 --output build/plan04/usb-boundary02
  -> PASS fresh-emission; PASS fresh-hierarchy; PASS compose
  -> PASS plan03_bus_hold.py; PASS plan03_bus_timing.py; pass
```

Fresh production/standalone USB equivalence matches 357 state elements and
rejects the actual pull-up inversion. The complete composed graph matches the
historical placement input before reuse. Independent read-only review checked
549 output hashes, source/HDL/library seals, 2,344 collector-input hashes and
all 15 corner summaries; it did not rerun STA or proof engines.
Measured source-qualified standalone worst bus hold is +0.123681 ns. Routed
request worst setup/hold is +27.351143/+0.846525 ns and delay 13.207504 ns;
response is +27.121695/+0.804226 ns and delay 13.396587 ns. These retain the
historical fixture's 24.96 ns bus ceiling, 41.6 ns app/AON periods and
20.8333 ns USB period with asynchronous clock groups. This is not generated
8 MHz/32 kHz whole-chip physical timing, upstream clock/reset qualification or
crossing-phase signoff. The unchanged collector accepts the refreshed evidence.

Frozen fast CI completed on the same source snapshot, including Markdown,
in both attempts below. The first attempt remains failed evidence:

```
python tools/env/run.py run -- python tools/ci.py --tier fast --output build/plan04/frozen-fast01 --usb-evidence build/plan04/usb-boundary02/acceptance-manifest.json
  -> failed (partial tier run), register-formal returned 1
  -> measured wall time 3686.526394 s; 25 preceding checks completed
python tools/env/run.py run -- python hw/lib/formal/regblock_proof.py
  -> PASS RegBlock formal: build/t05/formal/run-ogbhia81/receipt.json
python tools/env/run.py run -- python tools/ci.py --tier fast --output build/plan04/frozen-fast02 --usb-evidence build/plan04/usb-boundary02/acceptance-manifest.json
  -> PASS fast tier active checks; 12 deferred, unproved (see receipt)
  -> all 34 steps completed; measured wall time 3886.079379 s
```

Fast01's register negative control found the intended assertion failure, but
a backward host-clock step produced a negative elapsed-time prefix. Pinned SBY
could not parse the witness status and returned ERROR/16. The checker correctly
refused that result. Logs are preserved in `build/t05/formal/run-e874ccqa/`.
Independent inspection of the pinned tools confirmed wall-clock subtraction in
`smtio.timestamp` and a status regex excluding minus signs in the
[SBY witness parser](https://raw.githubusercontent.com/YosysHQ/sby/main/sbysrc/sby_engine_aiger.py).
The unchanged targeted retry, logged in `regblock-clock-retry01.log`, passed both
proof routes and all faults/covers. Review verified identical input hashes,
assumptions, limits, versions, 34 emitted coverage files and four prepared
coverage models; the same assertion fails at step 3 with normal FAIL/2 status.
No RTL, tool, assertion, cap or acceptance rule was changed. Fast02 then passed
the entire tier and its frozen-source audit; Fast01 is not relabelled passed.
Independent review verified all 34 successful commands, the 14 child receipt
hashes/statuses and the identical 1,648-entry source inventories in both CI
runs. At that point only this report, STATUS and the oscillator ledger changed;
structure and whitespace checks passed. The subsequent dedicated ResetCauses
harness and runner are new verification sources, outside that frozen CI receipt.
Production RTL is unchanged. A final frozen qualification refresh is required
after the remaining proof work and before publication.

The 12 carried deferrals are four T14 bus properties and eight T17 I2C
properties, still unproved. USB passed its acceptance aggregate, including
29 simulations and the refreshed evidence; standalone SIE remains explicitly
diagnostic-only (measured RO 22.734825 ns, estimated 12.5 ns budget / existing
15 ns warning ceiling, `fast/usb/timing-sie.log`). Engine and wrapper remain
the acceptance targets. USB physical/analog qualification limits remain in the
CI receipt. Full tier was not run. At that checkpoint publication was blocked:
fast CI does not discharge the new oscillator composition obligations. D86 now
permits publication through T33 with those obligations explicitly deferred.

The full formal entry point was also invoked, without starting any solver:

```
python tools/env/run.py run -- python hw/ip/osc_ctrl/formal/check.py --output build/plan04/formal
  -> error: Full PLAN04 composition is not implemented; --policy-only is a partial diagnostic
  -> nonzero exit (build/plan04/formal-acceptance-status01.log)
```

The two requested 30-minute helper-invariant attempts (minimum full-width count;
shutdown command/completion ownership and latched closure) remain awaiting
approval under formal-timeout-triage. Existing assertions, assumptions and
120-second per-job caps remain unchanged. No additional attempt was made.

Dedicated reset-cause verification subsequently passed:

```
python tools/env/run.py run -- python hw/ip/osc_ctrl/formal/reset_causes_check.py --output build/plan04/reset-causes04
  -> normal-correct proved; bypass-correct proved
  -> six fault_rejected; normal-cover covered; bypass-cover covered; PASS
```

Measured on `2c33976` plus receipt-hashed sources: unbounded ABC PDR normal
0.365824 s and bypass 0.265190 s; all seven cover witnesses reached within the
unchanged 24-global-step cap. Claims include cold clear, encoding, required
pin/held-brownout capture, sticky causes and raw-source provenance. Capture
qualification requires two AON cold-release edges; cold reset clears
cause history, and brownout's three active edges begin after qualification.
Initial cold reset and static bypass are the only DUT-input constraints; cover history
alone has a separate initialization. Clocks/reset inputs are otherwise
arbitrary. Review added spurious-cause faults and tightened the short-pulse
cover to observe its completion before the next AON rising edge. Earlier
receipts 01–03 are preserved as intermediate evidence. Independent review
validated all eight source hashes, 394 artifact hashes and the actual pulse
witness (pin falls/rises while AON stays low, before its next rising edge).
See the formal README
and oscillator ledger for exact scope; no production RTL changed.

## Numbers

The current table is `production-timing12`, including both count transfer and
ordered gate command/completion FIFOs. Earlier mapping10/11 results remain in
their build receipts as historical baselines. Intermediate composition
and count-contract results, including the unresolved count proof and its
step-0 triage table, are in `docs/ledger/osc-formal.md`.

- **Estimated:** main 48 MHz / 6 = 8 MHz; unchanged 60% budget
  0.60 * 1000 / 8 = 75 ns.
- **Estimated:** recovery nominal SCL ceiling 32000 / 8 = 4000 Hz. With
  assumed -5% LF tolerance this is 3800 Hz; neither is guaranteed until
  minimum AON frequency is qualified.
- **Assumed:** startup delay 512 AON ticks, stable count 256 OSC_IN edges,
  timeout 4096 AON ticks. **Estimated** nominal delay 16 ms and stable count
  5.333 microseconds. Board-part maximum startup assumed 5 ms using the
  primary datasheet cited in plan07; no part is selected.
- **Assumed model values:** POR falling/rising 3.10/3.20 V, qualified release
  1000 ticks at assumed 1 MHz (estimated 1 ms), initial-power epoch below
  0.10 V. T34 must establish safe process/SRAM limits and tolerances.
- **Measured/estimated:** fresh whole-top mapped logic 3.539272666 mm2;
  estimated complete budget 12.610083284 mm2 and headroom .309916716 mm2.
  Commands, allowance arithmetic and limitations are in plan08 and below.
- **Estimated inventory:** 39 output-capable / 12 input-only pads against
  assumed 40/12 capacity; OSC_IN reuses the dedicated clock pad.
- **Measured:** policy02 PDR job 0.366007 s, from the command/receipt above
  on its hashed working-tree sources. This is a policy-only proof time.
- **Measured, mapped pre-layout, no wires:** new block characterization on
  `2c33976` plus receipt-hashed working-tree sources, pinned Yosys 0.71+34 and
  OpenSTA 3.2.0, GF180 7t5v0 SS/125C/3.00V. Emission command:
  `python tools/env/run.py run -- python tools/sbt.py "hw/runMain deadhorse.osc_ctrl.EmitOscTiming build/t20/i1/osc_ctrl/osc_ctrl_regs.json build/plan04/digital-timing03/emit"`.
  Measured commands were `python tools/env/run.py run -- python
  scratch/plan04_blocks.py` and `python tools/env/run.py run -- python
  scratch/plan04_timing03.py`, which call `tools.timing.check.measure` with
  each emitted block, clock `clk` and the listed operating point.
  Exact expanded tool commands/hashes are in
  each directory's `commands.jsonl`/`result.json`. Control/divider/causes are
  from digital-timing01; stability/gate from digital-timing03.

| Block | Operating point | Worst RR ns, measured | Budget ns, estimated | Mapped area µm², measured |
| --- | --- | ---: | ---: | ---: |
| OscCtrl | aon-32khz | 20.165342 | 18750 | 35380.0384 |
| OscStability | usb-48mhz, strict non-USB block limit | 10.086461 | 12.5 | 4298.2016 |
| OscDivider | usb-48mhz, strict non-USB block limit | 4.996649 | 12.5 | 318.3040 |
| OscMainGate | main-8mhz | 11.284177 | 75 | 1134.9184 |
| ResetCauses | aon-32khz | 5.824966 | 18750 | 777.1008 |

The gate row is refreshed from `digital-timing06/emit/gate` using
`tools.timing.check.measure('OscMainGate', sources, 'clk',
Path('build/plan04/digital-timing06/gate'), operating_point='main-8mhz')`;
`gate-timing06.log` records the exact command output. Other isolated rows are
historical characterizations; current integrated domains are measured below.
All five characterization results report zero slew/capacitance violations.
Measured refreshed ICG E setup slacks are +120.549622/+121.821388 ns; hold slacks
+3.567250/+3.031145 ns. TE is tied zero, not an omitted dynamic path.
This partial sum excludes reset bootstrap, FIFO handoff and integrated fanout;
it is not the new whole-chip area budget or complete boundary/hold signoff.

Fresh production timing commands (pinned prefix above), on `2c33976` plus
receipt-hashed working-tree sources:

```
python tools/sbt.py "hw/runMain deadhorse.top.EmitSoc build/plan04/production-timing12/emit production 8"
python hw/top/reference/measurements/plan04_map.py --base build/plan04/production-timing12 --usb-reference build/t32/timing-fast01/fast/usb/timing/usb --stability-reference build/plan04/digital-timing06/stability
python hw/top/reference/measurements/plan04_screen.py --base build/plan04/production-timing12 --usb-reference build/t32/timing-fast01/fast/usb/timing/usb
python hw/top/reference/measurements/plan04_area.py --base build/plan04/production-timing12
python hw/top/reference/measurements/plan04_budget.py --base build/plan04/production-timing12
python -m unittest tools.timing.test_timing hw.top.reference.measurements.test_plan04_screen -q
  -> 32 tests OK
```

Measured mapped, no-wire timing in both static AON strap modes is identical.
Budgets are estimated from the unchanged 60% rule and certified exceptions.
USB cell names below have prefix `digital.subsystem.usb.`; other names are full
mapped identities in the authenticated canonical netlist.

| Domain/class | Worst ns, measured | Budget ns | Start -> end | Result |
| --- | ---: | ---: | --- | --- |
| main RR | 67.828392 | 75 | `_209348_/Q` -> `_209287_/D` | Pass |
| main USB FF | 10.045056 | 75 | `_7477_/Q` -> `_7310_/D` | Pass |
| AON RR | 65.042152 | 18750 | `_215995_/Q` -> `_225133_/D` | Pass |
| AON USB FF | 2.488224 | 18750 | `_7236_/Q` -> `_7237_/D` | Pass |
| TCK RR | 18.478176 | 6000 | `_206917_/Q` -> `_212953_/D` | Pass |
| OSC_IN RR | 10.086461 | 12.5 | `clocks.counter._187_/Q` -> `clocks.counter._179_/D` | Pass, strict |
| USB CC | 20.921200 | 50 | `_7042_/Q` -> `_7596_/D` | Pass |
| USB CC reset | 12.001124 | 12.5 | `_7280_/Q` -> `_6543_/D` | Pass |
| USB CF | 10.944381 | 12.5 | `_7254_/Q` -> `_6522_/D` | Pass |
| USB FC | 11.993650 | 12.5 | `_7609_/Q` -> `_7435_/D` | Pass |
| USB FF | 13.485458 | 12.5 | `_6398_/Q` -> `_7356_/D` | Existing 15 ns warning ceiling; placement recheck mandatory |
| USB CP | 12.811203 | 37.5 | `_7057_/Q` -> `_7683_/D` | Pass |
| USB FP | 9.182744 | 12.5 | `_7583_/Q` -> `_7683_/D` | Pass, strict |

The mapping preserves the locally optimized strict OSC_IN counter and certified
USB island. Fresh-source named-state equivalence and actual output-inversion
faults authenticate each island; pin bijections and sealed JSON/Verilog hashes
bind the timed graph. Global ABC targeting alone did not retain the counter's
local timing result. Independent review accepted the preserved-island mapping
and same-domain screen. All 21,221 CLK/CLKN pins have audited domain assignments;
both AON modes report zero dynamic gate-check and electrical-report violations.

This is **not full clock/boundary signoff**. Historical mapping10 raw pulse-width
reports include measured -701.822205 ns slack at `_203912_/CLK`. Focused command
`sta -no_init -exit build/plan04/pulse-diagnostic03.tcl` shows the main ICG's
10,166 direct sinks and 33.705650 pF load; the nested core gate has 4,169 sinks
and 13.582296 pF, versus the examined cell table's 0.3538 pF upper load point.
Out-of-range extrapolation even produces negative slews clipped by OpenSTA.
The unbuffered pre-CTS clock tree is unqualified; these violations remain in
the receipt, rather than being waived or interpreted as credible physical
arrival times. Analysis used OpenSTA's primary `report_dcalc` and
`report_check_types` documentation. IO contracts, cross-domain/RDC and physical
clock checks remain separate open obligations.

Measured isolated new digital logic is 56,339.8080 um2: OscClockReset
15,370.7904, OscCtrl 34,209.9968, OscSleepTransfer 6,063.1424 and ResetCauses
695.8784. Estimated scan uplift is 8,712.7488 um2; the sum spends .065052557
mm2 of the original .10 controller allowance. Whole-top scan uplift is added
once in the budget; isolated cost only reduces the remaining allowance.
The complete estimate is
`(3.539272666 + .419276614 + .034947443 + .50 + .05 + .05)/.55
+ 3.108271060 + .10 + .15 + .50 + .40 = 12.610083284 mm2`.
The accounting method was reviewed independently; this refreshed receipt still
requires final snapshot review.

## Deviations from the brief

D81 explicitly replaces stopped-oscillator attached USB resume with light-sleep
resume and an enabled-USB shutdown interlock. D82 explicitly qualifies recovery
SCL against minimum AON frequency / 8, preserving loader RTL. D83 explicitly
makes bypass-mode external reset cold; normal-mode warm reset and watchdog
containment remain unchanged. D84 explicitly replaces reset-latched POR_BYPASS
with a static powered-session board strap. AON_CLK_SEL remains reset-latched.
No assertion, timing limit or test tolerance is relaxed.

## Open issues

1. Complete production source-gate handshake qualification. Digital reset/strap
   routing and dedicated ResetCauses properties pass, as do production
   cause-capture simulations. Preserve existing loader START; autonomous lite
   ROM boot remains T36.
2. Finish source-clock and actual gate composition proofs with all required
   faults. D84 reset/strap proofs pass; FIFO delivery and actual gate-pulse
   simulations pass, but do not discharge all composition obligations.
3. Complete formal acceptance and its final source-bound aggregation/review.
   The 114-test SoC/oscillator suite, paired flight-loop scenarios and frozen
   fast CI pass on their recorded snapshots; the new ResetCauses verification
   sources postdate fast02 and require final frozen refresh. Full-tier CI is unrun.
4. Complete clock/reset physical qualification beyond the measured same-domain
   screen and historical USB fixtures in the physical flow. No whole-chip
   clock-tree/RDC/analog signoff, T33 completion or gate is claimed. Publication
   proceeds through T33's D86 exception, while PLAN04's original formal
   acceptance remains incomplete. Pending helper-attempt requests are
   superseded by D86 deferral; no unresolved result is promoted to a proof.
