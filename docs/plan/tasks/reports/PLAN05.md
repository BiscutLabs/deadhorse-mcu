# PLAN05 report

## Outcome

Phase 1 and Phase 2 are complete under the approved scoped-proof policy; the
frozen Phase2 fast tier passes with inherited deferrals. PLAN05 remains in
progress because Phase3 production boot-ROM integration and acceptance are open.

## What changed

- Recorded E1-E9 as D92-D100 and the explicit phase-end CI rule as D101 in
  plan10 and STATUS. Added the complete PLAN05 brief and task-index entry.
- Reconciled plans01/03/06/07/08/16 for a dormant lite watcher, sole performance
  boot master, removed loader/toMain, AON SPI/GPIO, unified timers, powered
  retained memory, watchdog freeze and verification-only RVFI. Future area,
  leakage and main SRAM options are measured/estimated below with explicit scope.
- Replaced the boot proposal with C1-C9. Independent review accepted a bounded,
  stackless DMA/QSPI-idle guard before SRAM use on performance-only reset; it
  neither aborts DMA nor implements buffer recovery. Exact binary ABI/recovery
  encodings and polling counts have passed independent review; Phase3 execution remains pending.
- Updated soc.yaml, the authoritative SoC specification and map checker for
  the new ownership, regions, interrupts, retained split and pad alternatives.
  Earlier integration descriptions remain explicitly historical in the appendix.
- Added the Phase1 integration contract and AON register descriptions; revised
  boot/timer/pinmux descriptors. Phase 2 now implements the AON blocks and timer/boot bindings below; final
  production qualification remains open.
- Added the RV32E watcher, independent radio/MMIO oracle, measurement runner,
  CRC check and receipt checks. A test-only fixture composes the unchanged lite
  hart, production debug router and AON fabric. The Phase 1 measurement predates the Phase 2 RTL changes below.
- Optimized CRC using word-sized polynomial factorization and forced inlining,
  then constant-folded the validated fixed address/command prefix. All packet
  reads and prefix checks remain. Startup selects the required AON/SPI pad mux
  before enabling outputs. Packet format, clock, limits and existing cases stay.

Phase 2 working changes (not yet accepted/committed):

- Removed ordinary toMain and loader instances from the production binding;
  dedicated debug transport remains. QSPI resets to performance ownership.
- Added performance-owned lite hold/drain/release and program-write protection;
  retained storage is now 512 words (2 KiB), with matching pinned GF180 macro
  views prepared and vendor-model tests passed. Physical macro qualification remains open.
- Added AON SPI and GPIO, shared short-pulse capture, acknowledged pad ownership,
  and production bindings. Independent review's idle-clear race is fixed and
  its fault control is caught by the GPIO tests.
- Added the three four-channel general timers and expanded timer pin routing.
  Independent review found stale-active START validation and a watchdog route
  bypass; both were repaired, with focused passing regression cases.
- Added performance watchdog pause through dormant/startup and production RVFI
  selection. Dormant/watchdog tests pass; lite RVFI equivalence passes, while the performance proof remains deferred.
- Existing tests migrate only for approved interface changes. The retirement
  inventories below account for removed loader/PWM/boot-order functionality;
  old implementation files are deleted after focused replacement checks.

Independent B5/B7 migration audit (runtime migration remains open):

| Existing coverage | Authorized disposition / retained obligation |
| --- | --- |
| RecoveryLoaderSpec (seven cases), RecoveryWireSpec, T18 formal/provenance/timing runner | Retire with D93 loader; no UART recovery substitution claimed until T36 tests |
| SocI1Spec loader wire/CRC/lock case | Retire loader protocol; preserve memory placement/ownership through performance load and C3 |
| BootReleaseSpec/Formal and SocBootReleaseSpec | Replace lite-releases-performance with performance-first/held-lite/release/drain; preserve independent and stopped-clock resets |
| SocLiteSpec | Replace I2C upload/START with performance program writes; preserve RV32E execution, WFI, timer/mailbox IRQ and reset tests; retire loader status fault only |
| SocI1ResetSpec ordinary toMain direction | Retire that removed direction; preserve toAon cancellation/drain and dedicated debug bridge checks |
| SocI1Spec opposite-direction admission | Replace with concurrent toAon plus denied lite-to-main requests; preserve serial/wire/IRQ/decode/mailbox/reset coverage |
| QspiSpec/QspiOwnerSpec/SocQspiSpec | Replace ownership transfer with performance reset ownership and denial of all others, including origin0; preserve flash wire/CS/reset/fault tests |
| SocXipSpec | Performance configures XIP; retain actual-core instruction/data execution and reset behavior |
| SocClockResetSpec/SocPowerThresholdSpec | Replace loader and lite-owned power setup; retain POR/bypass/wake/threshold/brownout/reasons/fault tests |
| SocClientPhaseSpec/probe/firmware | Lite targets its own AON watchdog period; performance ROM copies/releases it; acceptance/dispatch/commit/return phases preserved |
| SocWatchdogPhaseSpec/SocWatchdogOfferedSpec | Replace startup only; retain all watchdog acceptance/dispatch/drain/side-effect assertions |
| SocResetPhaseSpec | Use explicitly quiescent performance ROM instead of loader-held core; retain SBA phases/commit counts/missing-reset fault |
| SocTestBoot users (boot, core reset, PWM reset, pinmux reset, watchdog core) | Shared startup now follows performance-first; preserve behavior tests, migrate PWM semantics under D97 |
| OpenOCD loader.tcl | Replace loader collision with performance program-write/boot-control versus debug ownership collision |
| OpenOCD basic.tcl/inflight_reset.tcl | C3 denies direct SBA program stores; use authorized performance loading or data-memory addresses for pure SBA tests, retaining debug operations/reset coverage |
| SocI1Formal/check_i1_control | Replace loader predicates with C3; preserve error-target/reset-slot/data-integrity/drain properties |

Preparation, CI inventory and receipts must migrate with these cases. No old
runtime suite is treated as passing merely because compilation succeeds.

The retained nine PWM DMA endpoints migrate to timer channels0-8, with shared
period metadata and preserved request/acknowledgement/overrun behavior. All
thirteen existing PWM/timer pads remain; thirteen output selectors and four
capture selectors are specified. Six GPIO-capable pads use three existing GPIO
pads, two retired loader pads and one spare; SPI plus radio IRQ/power coexist.
BOOT_MODE reuses a reset-sampled MOSI alternate. These are reviewed contracts,
not measured electrical/physical fit.

The map suite retains its twelve tests, renaming
the physical-pad-accounting method and updating owner/timer/address expectations
only for the approved contract changes. Added twelve ownership/pad/IRQ/memory
faults. Removed block tests are explicitly listed under the approved retirement inventories below.

## Checks run

### Frozen Phase2 publication

`python tools/env/run.py run -- python tools/ci.py --tier fast --output
build/plan05/phase2-fast02 --usb-evidence
build/plan05/usb-boundary07/acceptance-manifest.json`
passes all **33 measured commands** in **3807.603677 measured seconds**.
Code base is `29cab7e500488d18fd9699f03fa34db70edac67f` plus the exact
working-source hashes in that receipt. The retired loader accounts for the
explicit change from the historical fast inventory. Final output:

```text
PASS faithful-floating-timing
PASS faithful-floating-smoke
PASS faithful-local-no-f-formal
PASS fast tier active checks; 12 deferred, unproved (see receipt)
```

Four T14 and eight T17 inherited proofs remain deferred and unproved. The
separate PLAN05 AON-SPI, GPIO checker and performance-RVFI deferrals below
remain open; fast-tier success does not discharge them. USB simulation passes
29 measured cases and its aggregate joins fresh checks to authenticated prior
proof/physical evidence with the recorded qualification limits. Full CI was
not run. Independent review authenticated the frozen implementation, emitted
snapshots, measurements and evidence; publication checks preserve all tested
non-documentation sources.


Pinned commands used `python tools/env/run.py run --` on main
`29cab7e500488d18fd9699f03fa34db70edac67f` plus working changes. Watcher receipt
hashes sources before/after and records emitted RTL, ELF, binary, executable,
compiler versions and commands. Build artifacts remain uncommitted.

| Command | Result |
| --- | --- |
| `python sw/lite/watcher/measure.py --routed --output build/plan05/watcher-opt05` | PASS; `PUBLISH 4 2764`, `CASE 2 4 2996 167`, `STACK 4 8`, `status: pass` |
| `python hw/top/reference/check_soc_map.py --output build/plan05/map03` | PASS: 21 regions; estimated pad inventory40 output-capable/12 input-only against unchanged40/12 capacity |
| `python -m unittest discover -s hw/top/reference -p test_soc_map.py` | PASS: `Ran 12 tests in 9.957s ... OK` |
| `python -m unittest sw.lite.watcher.test_measure` | PASS: `Ran 2 tests ... OK`; missing-positive/stack/duplicate/empty receipts rejected |
| `python tools/check_structure.py --include-untracked` | PASS: exit0, no findings |
| Host `git diff --check` | PASS: exit0; repository LF/CRLF notices only |

Phase 2 scoped commands, measured on the same base commit plus working changes:

- `python tools/sbt.py 'set hw / Test / unmanagedSourceDirectories := Seq(file("/work/hw/ip/aon_spi/src/test/scala"),file("/work/hw/ip/aon_gpio/src/test/scala"))' 'hw/testOnly deadhorse.aon_spi.AonSpiSpec deadhorse.aon_gpio.AonGpioSpec'`: PASS, five tests; measured Scala test time 31.938 s, sbt 43 s.
- `python tools/sbt.py 'set hw / Test / unmanagedSourceDirectories := Seq(file("/work/hw/ip/timers/src/test/scala"),file("/work/hw/ip/aon_gpio/src/test/scala"),file("/work/hw/ip/boot_control/src/test/scala"))' 'hw/testOnly deadhorse.timers.GeneralTimersSpec deadhorse.aon_gpio.AonGpioSpec deadhorse.boot_control.BootControlSpec deadhorse.boot_control.LiteBootStateSpec'`: PASS, thirteen tests; measured Scala test time 72 s, sbt 98 s. Includes the GPIO idle-clear negative control.
- `python tools/sbt.py 'set hw / Test / unmanagedSourceDirectories := Seq(file("/work/hw/ip/timers/src/test/scala"),file("/work/hw/ip/pinmux/src/test/scala"))' 'hw/testOnly deadhorse.timers.GeneralTimersControlSpec deadhorse.pinmux.PinmuxWatchdogSpec'`: PASS, six tests, measured Scala time 35.291 s, sbt 72 s. START uses applied compare; DMA simultaneous event/ack, overrun/mask/stop and watchdog disable/re-arm checked; both legacy timer pin routes disable without a main edge.
- `python hw/vendor/gf180_sram/prepare.py --source build/t35/macro-upstream`: PASS, 53 locked views including 512-word macro. Preparation is not macro functional/timing acceptance.
- `python dv/soc/prepare_io.py`: PASS map and register preparation.
- `python tools/sbt.py 'hw/runMain deadhorse.top.EmitSoc build/plan05/first-emission usb-stub-test 8'`: PASS on an intermediate snapshot, measured sbt 35 s. Subsequent changes are not covered by that emission.

No aggregate CI or formal sweep has run during Phase 2 iterations. The
strengthened `SocWatcherPathSpec` passed: both wrong-address/valid-CRC and
valid-address/wrong-CRC cases stayed dormant, SPI output enables remained active,
and the valid packet produced the expected mailbox word and mailbox wake cause.
Measured IRQ-to-OSC_EN-rise latency: 2633 AON edges; estimated time is
2633*1000/32000 = 82.28125 ms. Main and USB clocks were stopped during packet
handling. This uses the production peripheral path with clock acknowledgements
modeled at its boundary, not full B11 two-core/clock-wrapper acceptance.
Firmware source and binary hashes are checked against watcher-opt05.

`python hw/ip/boot_control/formal/check.py --output build/plan05/boot-formal01`
passed: unbounded state/ownership jobs, early-drain/incorrect-key/wrong-owner
negative controls, and both cover jobs. Independent review verified the
three-state oracle and denied-owner scope (0,2..7); positive MMIO/top composition
is separately tested and is not implied by this proof.

`python tools/sbt.py 'hw/Test/compile' 'hw/testOnly deadhorse.pinmux.PinmuxTimerSpec'`
passed after migrating removed retained-memory/toMain probe references: measured
55 s compile and 8.993 s Scala test time (10 s sbt). All test sources compile;
this does not mean historical runtime suites have been migrated or passed.
Pinmux coverage checks twelve output identities, four capture routes, conflicts,
live-channel protection and asynchronous watchdog disable.

The first pinmux-route attempt failed because the test constructed a hardware
shift outside elaboration (`1.U << 8`); replacing it with literal256 preserves
the test stimulus. The strengthened watcher and retained byte/authority tests
passed in that mixed run (three passed, one testbench error). Initial RVFI
emission exposed an invalid child-internal Wire reference in the no-RVFI lite
wrapper; conditional connection fixed elaboration. Lite equivalence then passed;
performance binding required preserving frontend register-driver identities
because output removal renamed the fcsr net. Those attempts remain recorded.
The performance RVFI SAT job in `build/plan05/rvfi03` timed out at its unchanged
120 s cap. No functional counterexample was found. The preserved runner receipt
says failed because its exception classifier originally recognized "timed out"
but not "timeout"; the log clearly records the timeout. Corrected future
classification without rerunning. Status is deferred/unproved under the user's
minimal-proof policy. Measured prepared correspondence: 236 state elements and
one multiplication congruence pair; SAT reported 251699 variables/672907 clauses.
No depth applies to this one-step all-state obligation. No unchanged retries or
portfolio sweep; partitioning output cones is the next focused formulation.
Lite RVFI equivalence and its three fault controls passed. Independent review
accepted the scoped evidence; performance RVFI equivalence remains unproved.
Phase2 fast02 passes after the recorded USB evidence-binding repair. The
required Phase3 fast check remains open.

The watcher retains twelve packet scenarios: invalid address with valid CRC,
invalid CRC, valid and repeated valid at each of three leaf response delays.
All six valid publications and three stack samples are accounted for. Separate
wrong-payload firmware fails with `FAIL mail payload mismatch`. The native C
CRC test checks all16,777,216 remainder/byte pairs against independent serial
polynomial division and the0x29b1 check vector; its corrupted-remainder build
fails with `CRC_REMAINDER_MISMATCH`. This is an exhaustive function check, not
an unbounded whole-core proof or exhaustive compiled-RV32 qualification.

Independent review confirmed the CRC identity, conditional prefix folding,
actual inlining, unchanged requirements, final source/artifact hashes, full
scenario inventory and intended negative-control failures. It also reviewed
Phase1 memory/boot ownership, timer/DMA semantics, pad/mux/capture contracts,
map-checker/test migrations and the single-master C contract. Findings were
resolved before Phase1 acceptance.

At this intermediate checkpoint no broad IP regression, long proof sweep, fast CI or full CI had run. The user
reaffirmed minimal relevant-only tests during this iteration. The explicit
Phase2/Phase3 fast-tier requirements remain pending at their respective ends.

Additional scoped Phase2 evidence on the same base commit plus working sources:

- `python tools/sbt.py 'hw/testOnly deadhorse.sram.SramSpec -- -z 512'`: PASS4 model/vendor-macro tests; measured34.254s Scala /44s sbt. All512 rows, byte masks, seeded transfers, fault control and resized March coverage. Unchanged1024-word cases not rerun.
- `python dv/soc/plan05/prepare_dormant.py`, then `python tools/sbt.py 'hw/testOnly deadhorse.top.SocDormantSpec deadhorse.watchdog.WatchdogPauseSpec'`: PASS2, measured54.351s Scala /64s sbt. Actual clock wrapper/performance firmware and measured watcher; no OSC_IN edges during watch phase, invalid CRC no wake, valid payload resumes WFI, SRAM/GPIO retained, one ROM entry, perf watchdog frozen. Diagnostic startup4AON/stable6OSC edges are not board wake-latency evidence. B11 still lacks timer/DMA/real-USB entry blocking, hung-lite watchdog and post-wake benchmark.
- `python tools/sbt.py 'hw/testOnly deadhorse.qspi.QspiSpec deadhorse.qspi.QspiOwnerSpec deadhorse.top.SocQspiSpec deadhorse.top.SocLiteSpec deadhorse.top.SocI1ResetSpec'`: initially7/8PASS, measured132s Scala /145s sbt; SocLite hit unchanged reply deadline. Removing loader-wire setup removed >1000AON edges before polling. Independently reviewed repair adds1000 setup ticks for the unchanged1000-tick timer;100-poll deadline is unchanged. `hw/testOnly deadhorse.top.SocLiteSpec` then PASS1, measured33.058s Scala /43s sbt. Diagnostic failure log retained.
- `python tools/sbt.py 'hw/testOnly deadhorse.top.SocI1Spec'`: PASS8, measured153s Scala /166s sbt. Serial ownership/IRQ, exact decode, main-to-AON plus denied lite-to-main concurrency, retained byte lanes/C3, independent resets, actual USB cancellation, SPI/I2C wire oracles and faults retained. Retired loader wire/CRC/lock case replaced by performance program loading/release/reset retention under D93/C3.
- `python hw/ip/aon_spi/formal/check.py --output build/plan05/aon-spi-formal01`: positive unbounded job TIMEOUT at120s cap (measured121.299s process); deferred/unproved. TX/RX-index and CS faults rejected (measured.567/4.177/.566s); all3 covers reached (measured25.626s). No unchanged retry. Framing property checks CS against internal lifecycle; independent wire tests check exact edges/data.
- GPIO formal attempts `aon-capture-formal01` through05 retain failed checker diagnostics. Initial eventual-capture property proved for both polarities and missing-capture fault rejected, but missed the idle-clear retention fault. Added sticky checker incorrectly treats acknowledged/coalesced pipeline echoes as new obligations; independent review confirms this is not a demonstrated RTL defect. Full formal capture qualification is deferred under minimal-proof policy; existing short-pulse/idle-clear simulation faults remain passing. No failing assertion silently waived or reported proved.
- Fresh production `EmitSoc build/plan05/timing02/emit production 8`, `plan04_map.py`, `plan04_screen.py --base build/plan05/timing02 --usb-reference build/t33/pre-fast03/fast/usb/timing/usb --screen-name ss125 --sram-corner ss_125C_3v00`, `plan04_area.py`, `t35_budget.py` and `plan05_area_leakage.py --base build/plan05/timing02`: completed intermediate mapping/screen/estimates. Both AON strap modes satisfy same-domain classes except approved USB warning; electrical/gate violations zero. See plan08/06 for full provenance/method. Timing01 stopped at strict USB parent-input alias audit; reviewed real boundary buffers restore injectivity with original-pin equivalence, wrong-input/cycle faults and unchanged certificate rules.

Independent review accepted the scoped dormant/wake observation, SRAM-view
mapping changes, conservative USB identity-buffer transformation and timing/area
arithmetic. It explicitly leaves B11/integration, GPIO checker repair, SPI and
performance RVFI proofs open. This was before the first Phase2 fast run below.

Additional scoped integration results (main29cab7e5 plus working sources):

- `hw/testOnly deadhorse.top.SocBootReleaseSpec deadhorse.boot_control.BootControlSpec deadhorse.top.SocBootStrapSpec`: initial4/5PASS; early test observation saw held deassert before synchronized liteStart. Reviewed repair waits for the accepted start under the same3000-tick bound. Subsequent boot-release positive/negative both passed in timer-binding01. Control and strap tests passed; `boot_control/formal/check.py --output build/plan05/boot-formal02` passed all10 jobs.
- `hw/testOnly deadhorse.top.SocIoSpec -- -z "functional I/O"`, corresponding focused SocPwmSpec and SocPinmuxSpec, then SocXipSpec/SocPowerThresholdSpec: all7 tests PASS in timer-xip-threshold02; measured Scala18.282/2.753/39.571/89s respectively. Existing waveform/ownership/reset checks migrate to shared timers; explicit STOP acknowledges the unchanged watchdog interlock. XIP and threshold setup now execute on performance, retiring only loader-specific setup. Initial timer-binding01 missing-STOP failures are retained.
- `python hw/ip/timers/formal/check_general.py --output build/plan05/timer-formal03`: PASS48 assertions unbounded ABC PDR, measured2.522s; three faults rejected, all12 covers. Earlier emission dependency and witness hierarchy naming failures are retained. Scope is compare-boundary stability, qualified-edge timestamp storage and output registration, not full timer functional equivalence.
- Independent review accepted the timer tests/properties, XIP/threshold ownership migration and dormant entry-inhibition test design. SRAM leakage wording corrected to unconditional library scalar used as a standby proxy, with CEN-high assumed; not a characterized conditional measurement.

### Timer retirement inventory under D97/E6

The legacy `hw/ip/pwm` block and `MainTimers.scala` are retired after merged
mode tests passed. Git history retains their source/evidence. Tests removed
with the old architecture are accounted for below; current integration
migration is not yet complete.

| Old check | Replacement or retirement reason |
| --- | --- |
| PwmChannelSpec independent per-channel period/live-frequency/random update oracle | Old state machine retired under E6; GeneralTimersSpec covers all12 PWM/compare/capture channels with duration/timestamp oracles and actual faults. Shared bank periods require STOP; old busy-APPLY rejection is superseded |
| PwmChannelSpec duty/prescaler endpoints, queued snapshot | GeneralTimersRegisterSpec tests0/65535/65536/invalid65537 duty, maximum prescaler and snapshot across unapplied shadow writes |
| PwmSpec strobes, ownership, decode, waveforms, reset | GeneralTimersSpec/RegisterSpec plus SocPwmSpec/CoreResetSpec on merged map |
| PwmSpec seeded DMA collision model | TimerDmaSpec retains original1000-edge seed22 oracle verbatim on moved helper |
| PwmSpec DMA overrun/mask/ack/STOP | GeneralTimersControlSpec/RegisterSpec and unchanged five DMA formal assertions |
| PwmWatchdogSpec stale STOP/APPLY/reset | SocWatchdogEpochSpec and GeneralTimersControlSpec cover ready-epoch STOP and asynchronous break; accepted-APPLY crossing watchdog reset and stale-epoch STOP now pass in timer-watchdog05 |
| MainTimers absolute-deadline/IMU-specific semantics | Retired under E6 conventional general timers; capture timestamps/compare waveforms covered on all12 channels |
| MainTimers8/9MHz timebase wrap/load/stop and time/hold assertions | GeneralTimersRegisterSpec and GeneralTimerFormal preserve these claims, adding time/hold fault controls |
| MainTimers mode-only enables / PwmChannel12 assertions | Old state machines retired;12-channel registered-drive/output/capture/boundary properties in GeneralTimerFormal replace their applicable output/compare claims |
| PwmDenied7 / PwmDma5 / watchdog break3 assertions | Migrated to actual merged timer/TimerDmaRequests/TimerBreak bindings; no claims dropped |
| TimersSpec AON2 tests / AonTimerFormal4 assertions | Retained unchanged |
| SocDmaSpec / SocWatchdogSpec / SocWatchdogEpochSpec | New bank offsets/STOP/routing; same DMA, reset, ownership, deadlines and negative controls. Lite data moves to approved1KiB data base; reset-reason reads move to authorized performance owner |

Measured on 29cab7e5 plus receipt-hashed working sources:
`python hw/ip/timers/formal/check_aux.py --output build/plan05/timer-aux01`
passes all6 jobs. `python hw/ip/timers/formal/check_general.py --output
build/plan05/timer-formal04` proves50 assertions at8/9MHz, rejects5 faults and
reaches12 covers. No aggregate CI invoked.

`timer-move02.log`: all5 timer/control/register tests passed. Its subsequent
SoC DMA elaboration found unbound SRAM-test fixture inputs; inactive fixture
bindings repaired. `timer-soc03.log`: DMA waveform/reset passed, watchdog
expiry failed because the continuous-clock fixture never acknowledged stability,
so the newly required watchdog pause remained active. `watchdog-migrate04.log`:
clock-ready fixture correction passes both retained-STOP positive/negative cases;
watchdog scope tests expose an obsolete lite reset-reason access. That read is
migrated to performance without changing any expiry bound.

`core-timer-reset01.log`: both core timer/pinmux reset tests and hung-lite
watchdog containment pass. `clock-migration01.log`: all7 focused wake/reset
tests pass with performance-owned boot/setup. `flight01/result.json` records
identical before/after-wake workload results: measured fixed-point worst4350
cycles and hard-float worst9007, with checksums and negative controls intact.

### Loader retirement inventory under D93/E2

Removed `hw/ip/i2c_recovery_loader`, its production pin/observation stubs and
its T18-only fast/full-tier entry. General I2C host tests/CI are unchanged.
No UART/T36 recovery or JTAG acceptance is implied by removing this block.

| Removed check | Reason or replacement |
| --- | --- |
| RecoveryLoaderSpec7 cases: upload/start/lock, metadata/CRC, memory backpressure/status snapshots, reset abort, address/wake/timeout, SCL spacing, data-corruption fault | Entire hardware I2C loader protocol removed by E2; T36 must implement UART image/recovery validation and faults |
| RecoveryWireSpec addressed-frame/restart/timeout case and RecoveryPeer | Removed I2C target wire protocol; general I2C host remains |
| Loader formal target/control/denied jobs and provenance/timing runners | No retained loader RTL to qualify; historical receipts remain in T18 report/git history |
| test_ci_tiers T18-only success-receipt case | Removed retired child job; asserts loader absence in both-tier plan; all other tier policy checks retained |
| OpenOCD loader-ownership scenario and second I2C host | Removed loader/debug race under E2; basic SBA test now rejects program writes and exercises data-region writes, while boot-control/ownership tests retain C3 |
| SocI1Formal loader-done/exclusive-port assertions | Removed nonexistent second writer; retains request/response timing/permission claims, migrates actual C3 program/data authorization and fault |
| BootReleaseSpec and BootReleaseFormal | Retired lite-start-authorizes-performance state machine under E1; LiteBootStateSpec/formal, BootControlSpec and production boot/reset tests cover the reversed boot authority/drain |
| Historical oscillator flight fixture | plan04_flight entry now forwards to production PLAN05 benchmark; identical workloads/checksums and before/after-wake metrics retained, old lite-owned main-control firmware retired |

Loader wire setup in client/watchdog/threshold/XIP/boot tests is replaced by
real performance ROM execution and public GPIO triggers where a phase must be
selected. Reset-phase SRAM targets use the resized legal data window. Full
phase matrices and fault controls are preserved; current results are reported
separately, not inferred from source migration.

### Final migration checks in progress

- `hw/testOnly deadhorse.top.SocClientPhaseSpec -- -z "lite=true"`:
  PASS all14 reset phases, measured63.000s Scala/76s sbt in
  `build/plan05/client-watchdog05.log`. Missing-pin control PASS, measured
  25.495s Scala/26s sbt. Existing performance matrix passed in client-phase01.
  Runs02/03 were interrupted because OSC-cycle IPC was unnecessary for the
  entirely AON lite path. Reviewed scheduling now observes every AON edge for
  lite, preserves single-step performance/reset intervals and every deadline.
  Run04 exposed a wrong passive fabric branch; correcting it to af.master(0)
  preserved the original return-phase assertion and the complete matrix.
- `hw/testOnly deadhorse.top.SocWatchdogPhaseSpec deadhorse.top.SocWatchdogOfferedSpec`:
  PASS4 including wrong-key/early-write controls, measured79s Scala in
  client-watchdog05. All acceptance/dispatch/commit/drain limits unchanged.
- `python hw/top/reference/formal/check_i1_control.py --block memory --output
  build/plan05/retained-control02`: PASS control proof/cover/C3 fault. Runtime
  command/log/engine timings are in the receipt. Earlier01 was an inventory
  failure: a tautological debugAccess=false assertion is folded away, so the
  independently reviewed inventory is5 harness plus2 production assertions.
  This is ordinary-memory admission scope, not debug-composition proof.
- `python hw/top/reference/check_soc_map.py` and map unittest discovery:
  PASS21regions and12tests; measured10.857s unit runtime. Macro metadata now
  names1024-row main and512-row retained cells, matching actual emitted RTL.
  Wrong retained row/cell faults are rejected.
- Debug basic test PASS using actual OpenOCD/TAP in debug02/basic. Global
  reset-halt could not return while lite intentionally stays boot-held; the
  fixture now drives the same public reset pin then services performance/lite
  in boot order. Follow-up exposed stale cold-retained lite debug ownership
  across whole reset. Reviewed fix clears ownership/resetting while aonUp is
  low, retaining the pending halt; the final focused runtime check is pending.
  No permission, timeout or halt-on-reset expectation was weakened.
- Structure01 exposed a non-UTF8 newly written GPIO formal README; corrected
  encoding. Structure02 exposed links to retired block documentation; links
  now explicitly identify historical source or replacement timer contract.
  Final structure result remains pending.

Final reviewed migration evidence:

- Debug03 `probe.py --script dv/soc/debug/reset.tcl`, `basic.tcl --aon32000`
  and `inflight_reset.tcl`: PASS, measured61.583/75.767/17.628s respectively.
  Real pending-reset-halt monitor activated; no application fetch/start/retire
  before debug entry. Denied program writes and both owned commands checked.
- `hw/testOnly deadhorse.top.SocResetPhaseSpec -- -z "warm-pin missingPin=false"`:
  PASS all14 native/retained SBA phases; measured394s Scala/401s sbt.
  Missing-pin negative PASS, measured34.617s Scala/36s sbt. Brownout/bypass
  matrices remain in the suite but were not rerun under scoped-test policy.
- Structure03 PASS exit0. Final diff check found whitespace left by removed
  port initializers; trimmed affected working Scala files only, no logic change.
- Independent review reproduced timing/area/leakage arithmetic and checked
  source/artifact chains and debug receipts. T36 brief explicitly retains IRQ
  injection during updates, no stale release and fixed-ROM handoff to T38.

### Deferred-proof step0 record

| Job | Measured size / progress | Cap / result | Covers / faults | Next step, not run |
| --- | --- | --- | --- | --- |
| AON SPI positive, aon-spi-formal01 |621cells;5412wire bits;50aldff+36dff cells; mapped ABC336FF, frame101 reached |120s; measured121.299s TIMEOUT, unproved |3covers at depth512 in25.626s; TX/RX/CS faults rejected | Decompose FIFO occupancy/ownership before byte ordering; no unchanged rerun |
| Performance RVFI removal, rvfi03 |236matched state objects plus one multiplication congruence; SAT251699variables/672907clauses |120s timeout; receipt runner classified failure, interpreted as unresolved solver result | Lite70-state proof and3faults pass; performance whole-state closure absent | Split cone-local transition claims; no changed cap or assumption |
| GPIO sticky capture, aon-capture-formal05 | Checker counterexample after acknowledged/coalesced capture residue; not a positive proof timeout | Failed checker; not a demonstrated production counterexample | Earlier eventual capture pass omitted idle-clear fault; independent wire tests catch idle-clear and missing capture | Repair monitor/rearm accounting; no excluded overlap assumption |

Quarter/half-depth growth measurements were not run under the user's minimal
proof policy; none is fabricated. These jobs remain explicit debt rather than
acceptance proofs. Existing proofs/assertions and solver caps are unchanged.

### Phase2 fast01 and evidence refresh

`python tools/env/run.py run -- python tools/ci.py --tier fast --output build/plan05/phase2-fast01 --usb-evidence build/plan04/usb-boundary02/acceptance-manifest.json`
failed after **measured 1,732.076684 s** on 29cab7e5 plus the frozen working-source
hashes: `Missing or stale evidence: build.sbt`. Environment, structure, Python
units, core smoke, bus tests/formal/timing, UART, SPI and I2C active checks passed;
the existing four bus and eight I2C proof deferrals remain unproved. USB stopped
before its functional suite. Remaining fast jobs did not run.

The removed loader formal-source directory changes the historical USB evidence
binding. Exact fresh SIE/sampling HDL and canonical/selected-model replays match;
no proof solver rerun is needed. Fresh composition/sampling/throughput witnesses
are required by the unchanged collectors. Physical review also found 35 inserted
bus-input buffers, one constant input and a shared address-bit source. A new
boundary fixture preserves that topology/load and all 73 historical launch queries,
including explicit no-path accounting. Its fresh boundary qualification passes;
standalone USB internal measurements remain historical, authenticated by exact HDL
identity. No old physical result is relabelled as a new measurement.

`python tools/env/run.py run -- python hw/top/reference/measurements/plan05_usb_finalize.py --input build/plan05/usb-evidence01 --output build/plan05/usb-evidence-qualified01`
passes strict packet and sampling collectors without rerunning proof solvers.
Fresh composition, sampling and full-size throughput witnesses pass. The first
final audit's wrong `ep0` folder name and its failed receipt remain preserved;
the corrected finalizer authenticates the original producer and every artifact.
Independent review checked 196 evidence hashes with no mismatch.

`python tools/env/run.py run -- python hw/top/reference/measurements/plan05_usb_boundary_refresh.py --base build/plan05/timing03 --output build/plan05/usb-boundary07`
prepares a fresh emission-identical production binding. `plan05_usb_physical.py`
with that `--base` and `--phase prepare`, then pinned physical OpenROAD on
`bus-physical01/run.tcl`, `--phase extract`, OpenROAD on each
`bus-physical01/extract-{min,nom,max}/run.tcl`, and `--phase audit` all pass.
Final output: `PASS scoped D77 physical evidence; tape-out limits retained`.
Measured on 29cab7e5 plus sealed working sources: worst request/response delays
13.973360/13.910799 ns against the unchanged 24.96 ns fixture budget; minimum
routed holds +0.848731/+0.844791 ns; conservative hold-only minimum +0.123681 ns.
All 15 PVT/RC cases pass. This retains the historical conservative fixture clocks
(41.6 ns application/AON, 20.8333 ns USB), not whole-chip placement signoff.
The four topology faults fail as required. Boundary06's JSON import failure is
preserved: moving port aliases behind buffers left original Q nets unnamed.
Boundary07 adds explicit Q net names only; independent review verified unchanged
cell/pin connectivity. No timing limit or assertion changed.

## Numbers

Measured by opt05 above on its receipt-hashed sources. Times are estimated as
cycles / assumed nominal32,000Hz. Targets grant immediately, with no competing
master and assumed response delays shown below. Real production leaf latency,
contention and LF-frequency tolerance remain unqualified.

| Target response edges (assumed) | Publication cycles (measured) | Publication ms (estimated) | Return-to-WFI cycles (measured) | Return ms (estimated) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 2173 | 67.90625 | 2354 | 73.5625 |
| 2 | 2370 | 74.0625 | 2568 | 80.25 |
| 4 | 2764 | 86.375 | 2996 | 93.625 |

Worst modeled return margin is estimated `3200 - 2996 = 204` cycles, or
`204 / 32000 * 1000 = 6.375ms`. This isolated fixture cannot close B11; the later production dormant tests
listed above supply the actual AON-block and stopped-OSC_IN evidence.

Measured ELF code/constants588bytes + data/bss8bytes + conservative stack8bytes
=604bytes. Static and observed stack agree; startup has no frame and global
trap dispatch is disabled. Required allocation with margin is estimated
`ceil(604 * 1.25) = 755` bytes. D96 selects2KiB, split1KiB program/1KiB data;
both halves have margin. Physical SRAM resizing and digital BIST-range checks are implemented; physical signoff is separate.

### B12 refreshed Phase2 measurements

Measured on main29cab7e5 plus working-source and netlist hashes in
`build/plan05/timing03/`. Commands: `EmitSoc ... production 8`, followed by
`plan04_map.py`, `plan04_screen.py --screen-name ss125 --sram-corner ss_125C_3v00`,
`plan04_area.py`, `t35_budget.py`, `plan05_area_leakage.py`, all with
`--base build/plan05/timing03` and the unchanged authenticated USB/counter
references recorded above. Same-domain pre-layout timing uses ideal clocks,
pinned slow-corner cells/macros, no routing wires; physical CDC/RDC/hold remain
unqualified. Both AON strap modes have the same worst rows below.

| Class | Measured worst ns | Budget ns | Start | End | Result |
| --- | ---: | ---: | --- | --- | --- |
| aon.FF | 2.488224 | 18750 | `digital.subsystem.usb._7236_/Q` | `digital.subsystem.usb._7237_/D` | pass |
| aon.RR | 66.842003 | 18750 | `_210962_/Q` | `_217749_/D` | pass |
| main.FF | 10.045056 | 75 | `digital.subsystem.usb._7477_/Q` | `digital.subsystem.usb._7310_/D` | pass |
| main.RR | 69.030312 | 75 | `_203680_/Q` | `_200182_/D` | pass |
| tck.RR | 18.468393 | 6000 | `_205616_/Q` | `_205724_/D` | pass |
| usb.CC | 20.921200 | 50 | `digital.subsystem.usb._7042_/Q` | `digital.subsystem.usb._7596_/D` | pass |
| usb.CC_reset | 12.001124 | 12.5 | `digital.subsystem.usb._7280_/Q` | `digital.subsystem.usb._6543_/D` | pass |
| usb.CF | 10.944381 | 12.5 | `digital.subsystem.usb._7254_/Q` | `digital.subsystem.usb._6522_/D` | pass |
| usb.CP | 12.811203 | 37.5 | `digital.subsystem.usb._7057_/Q` | `digital.subsystem.usb._7683_/D` | pass |
| usb.FC | 11.993650 | 12.5 | `digital.subsystem.usb._7609_/Q` | `digital.subsystem.usb._7435_/D` | pass |
| usb.FF | 13.485458 | 12.5 | `digital.subsystem.usb._6398_/Q` | `digital.subsystem.usb._7356_/D` | warning |
| usb.FP | 9.182744 | 12.5 | `digital.subsystem.usb._7583_/Q` | `digital.subsystem.usb._7683_/D` | pass |
| usb.RR | 10.086461 | 12.5 | `clocks.counter._187_/Q` | `clocks.counter._179_/D` | pass |

Electrical capacitance/slew violations: measured0; gate violations: measured0
in both strap modes. Approved USB warning ceiling remains15ns; all other
class limits are unchanged. Raw hold/removal rows remain physical-flow debt.

| Block allocation | Measured mapped mm2 | Measured FF cells |
| --- | ---: | ---: |
| aon_fabric | 0.002212762 | 17 |
| aon_gpio | 0.016207162 | 134 |
| aon_io_fabric | 0.001762746 | 13 |
| aon_spi | 0.041451962 | 298 |
| aon_timers | 0.056098336 | 362 |
| clock_reset | 0.017506720 | 137 |
| debug_bridge | 0.058271584 | 471 |
| dma | 0.142918496 | 768 |
| general_timers | 0.232467290 | 1541 |
| gpio | 0.016944749 | 143 |
| i2c | 0.046088224 | 285 |
| jtag_debug | 0.220334419 | 1386 |
| lite_boot_control | 0.015050291 | 123 |
| lite_core | 0.210699686 | 1061 |
| lite_watchdog | 0.053690202 | 378 |
| mailbox | 0.063408352 | 528 |
| main_fabric | 0.004937005 | 35 |
| main_memory_control | 0.014800038 | 87 |
| main_to_aon | 0.059896032 | 483 |
| oscillator_controller | 0.026252397 | 191 |
| other_state | 0.371074413 | 2843 |
| output_clock_glue | 0.010027674 | 0 |
| performance_core | 0.809989286 | 4169 |
| performance_watchdog | 0.054329005 | 379 |
| pinmux | 0.043254221 | 240 |
| power_reset | 0.011713587 | 98 |
| qspi_xip | 0.108980704 | 833 |
| reset_causes | 0.000687098 | 8 |
| retained_memory_control | 0.002711072 | 2 |
| shared_glue | 0.241880307 | 2 |
| spi | 0.067445325 | 487 |
| sram_bist | 0.044959891 | 333 |
| uart0 | 0.050379840 | 347 |
| uart1 | 0.050360083 | 347 |
| uart2 | 0.050500576 | 347 |
| uart_sleep | 0.005235552 | 45 |
| usb | 0.202595008 | 1349 |

Exclusive backward-cone allocation counts shared/output/unnamed state once;
these are partitions of the whole netlist, not independently optimized blocks.
Measured standard cells: 3.427122093mm2. Estimated total
with unchanged allowances: 12.020820471mm2; headroom
0.899179529mm2 against12.92. Plan08 records arithmetic and
16/24/32KiB options. Larger SRAM options do not fit even before extra decoding.

Mapped leakage plus powered-SRAM library proxy (estimated, not power signoff):
| Corner / assumed supply | Min / mean / max estimated microamps |
| --- | --- |
| tt_025C_3v30 / 3.3V | 4.296266 / 4.714768 / 5.460495 |
| ff_125C_3v60 / 3.6V | 150.984362 / 197.909816 / 270.681821 |

Excludes AON switching, analog, pads/pulls, board oscillator/regulator/radio
and future ROM/scan. SRAM scalar leakage is an unconditional Liberty value
used as a standby proxy under assumed CEN-high, not a characterized standby
state. The complete microamp system target remains unqualified.

### Preserved failures and earlier evidence

| Receipt | Result and scope |
| --- | --- |
| watcher / watcher02 | Measurement tooling failures: constant table misclassified as function; initial AUIPC transient misclassified as live SP. Fixed without relaxing warnings or live-stack bounds |
| watcher03 / watcher04 | Isolated core passes, but omits production routing; not integrated latency acceptance |
| watcher-routed01 / routed02 | Initial candidate fails; fastest publication3581 measured cycles, estimated111.90625ms, return3784cycles/118.25ms |
| watcher-opt01 | Compiler signedness warning; corrected explicit unsigned comparison, warnings remain errors |
| watcher-opt02 | Table-free CRC correct but slow case fails: publication3422cycles, return3654cycles |
| watcher-opt03 | Compiler outlines CRC helper despite inline; intended prefix folding regresses. Failed receipt preserved |
| watcher-opt04 | Forced-inline correction passes with same final cycle counts; measured592byte footprint before required mux initialization |
| map01 | Expected contract-table mismatch during map/spec migration; corrected specification, map02/map03 pass |

An earlier documentation check found mixed encoding/doubled CR endings in
edited files; UTF-8/newline correction restored the intended diff. Final checks
above pass. No failed evidence has been reclassified as passing.

## Deviations from the brief

Initially stopped at the explicit latency condition, then resumed after user
approval for focused firmware optimization. The deadline, packet and clock
were unchanged. Phase1 measurement uses existing core/routing RTL with modeled
leaves, as new AON peripheral RTL belongs to Phase2. This scope is explicit;
production integration remains required. No assertions or assumptions were
relaxed, and no production feature/test was silently dropped.

The first Phase2 fast run failed at stale USB evidence and is preserved.
After reviewed requalification, the complete frozen fast02 run passes. Phase3
and its required fast tier remain pending.

## Open issues

Final debug/reset checks and the source-bound Phase2 timing/area receipt are
complete. USB boundary requalification and Phase2 fast CI pass. AON SPI positive proof, GPIO sticky-capture checker,
performance RVFI equivalence and inherited formal/physical debt remain deferred
under the scoped policy; no timeout or checker failure is called a proof.

Phase3 production ROM and boot/update/recovery tests remain unimplemented.
Its exact ABI/command encodings and hardware reset-epoch discriminator have
passed independent review; software-model draft checks do not substitute for
production RTL or serial-wire acceptance. T36 retains its ROM allowance and
all original update/power-loss obligations. Full CI has not run and is deferred
by user policy. Physical/analog qualification and complete deep-sleep system
current remain open; the leakage estimate excludes analog/board switching power.
