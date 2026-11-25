# 16 SoC integration

## PLAN05 target migration

D92-D101 supersede the loader/shared-main-peripheral/lite-first portions of
PLAN03. Keep DeadhorseSoc as the single production top. Remove recovery loader
and general toMain; preserve toAon, mailbox and dedicated lite debug transport.
Main serial/QSPI controllers are performance-owned. Add LF-only AON SPI/GPIO,
performance-controlled lite reset/program writes, measured2KiB retained RAM,
and three four-channel general timers replacing separate main timers/PWM.
Production excludes RVFI; all verification configurations retain it.

One performance ROM boots the chip; lite has no ROM. Dormant watcher filters
radio packets without the external oscillator, wakes main through mailbox,
and resumes performance after WFI. Performance watchdog freezes through committed
dormant and restart qualification; lite watchdog remains active. No RAM power-off.

The inventory below records pre-migration implementation, not approval to keep
superseded features. PLAN05 Phase1 must close contracts/measurement before RTL;
Phase2 and Phase3 each require fast CI. Stage exits and inherited proof/physical
debt remain open. Scoped iterations use relevant tests and defer expensive proof
timeouts under the user's policy; this does not waive phase-end checks.


PLAN03 reconciles the built digital MCU on main under D72–D76. This plan
describes one production chip and the remaining qualification work; it does
not mark an integration stage or tape-out gate complete. Current evidence and
proof debt live in [STATUS](STATUS.md) and the [PLAN03 report](tasks/reports/PLAN03.md).

## One production top

`DeadhorseSoc` contains every built production feature. `SocProduction` and
`hw/top/reference/soc.yaml` are the single production configuration and map.
No new opt-in profiles. Small named test configurations (minimal I0 boot,
USB-stub substitution, CPU-boundary bus stimulus) are verification fixtures,
not selectable production variants; they must not redefine production features.
The old profile history is an appendix of [the SoC contract](../spec/soc.md).

Every future block replaces its own stub/interface in this top and passes
the existing system tests. Main frequency remains an elaboration parameter.
The local performance instruction/SRAM path stays outside the registered
peripheral fabric. All crossings use shared CDC primitives; reset asserts
asynchronously and releases through the shared per-domain release block.
Map generation, register-window fit, ownership and interrupt/pin metadata
remain sourced from soc.yaml and the peripheral register YAMLs.

## Current inventory

| Block | Owner | Production state / remaining qualification |
| --- | --- | --- |
| Faithful Chisel RV32IMFC performance core/shared MAC | T10–T13 | Integrated; depth160/full ISA/refinement debt retained |
| Local ROM/performance SRAM path, main/AON fabrics, bridge/mailbox | T14/T20 | Integrated; macro/ROM realization and system composition open |
| Three UARTs, SPI, I2C host | T15–T17 | Integrated; bounded serial scopes and four T14/eight T17 deferrals visible |
| I2C recovery loader | T18 | Integrated, frozen by D73; T31 withdrawn |
| USB CDC-ACM | T19 | Real production block; digital acceptance and scoped physical evidence recorded; chip-level qualification still open |
| GPIO, four main capture/compare channels, main microsecond timebase and AON deadlines | T21 | Integrated; main service needs main clock, AON deadlines survive main stop |
| Generic PWM and timer/DMA requests | T22 | Integrated; application protocols and policy remain firmware |
| Basic DMA | T23 | Integrated; memory-range proof unresolved |
| Limited pin mux and interrupt routing | T24/T20 | Integrated; complete chip connectivity/physical pin freeze open |
| Real lite hart | T25 | Integrated; baseline/control proofs and simulation; full ISA/machine debt |
| Both watchdogs/output disable | T26 | Integrated; full-width channel and system reset qualification debt |
| Lite-first boot release | T28 | Integrated; production ROM policy remains T36 |
| QSPI command/native XIP | T29/T30 | Integrated; flash/pad qualification and production boot remain |
| Dedicated SPI ADC | D74 | Retired from production, pins/window unassigned; firmware uses general SPI/DMA |
| JTAG both harts | T32 | Brief ready, stub awaiting implementation |
| Clock/reset/power/sleep controller | PLAN04/T33 | D78 external 48 MHz, /6 main, LF AON; PLAN04 oscillator/POR subset in progress; T33 full reset/reason/threshold/retained sleep remains |
| Analog LF RC and POR/brownout | PLAN04/T34 | No internal HF; interface/models then extracted layout later; safe-default POR and strap fallbacks |
| 16 KiB performance + 3 KiB retained SRAM macros/BIST | T35 | Behavioral memories today; macro footprint budgeted, not integrated |
| Production boot ROM | T36 | Test/bootstrap content today; production CRC/A/B/golden/recovery pending |
| Test/scan and pad-level chip | T37/T38 | Briefs ready; no chip signoff claim |

## Integration stages and exits

| Stage | Implemented portion | Remaining exit evidence / owner |
| --- | --- | --- |
| I0 skeleton | Core/local memories/fabric/UART boot | Complete inside-SoC ISA/target-interface qualification; T20 |
| I1 existing peripherals | Real serial, bridge/mailbox/loader/USB and lite binding | Generated-top decode/IRQ/reset proofs and complete crossing inventory/system cases; T20 |
| I2 application I/O | GPIO/timers/PWM/DMA/pin mux | Timer-driven application against independent airframe/output model; debt and full tier at exit |
| I3 AON | Lite, watchdogs, boot release | T33 clock/reset/retained sleep/wake and containment; full tier at exit |
| I4 boot/debug | QSPI command/XIP | T32 both-core debug and T36 production two-image boot/recovery; full tier at exit |
| I5 chip | Digital top and measured planning budget | T34 interfaces and later extracted analog work, T35 SRAM/BIST, T37 test/scan, T38 pads/physical flow, FPGA/system evidence; full tier at exit |

Stages overlap in implementation. A built block or passing fast tier does not
close its stage. No stage is marked complete by PLAN03. D76 requires fast CI
on main before new block work and after every task; the full tier runs at each
I2/I3/I4/I5 exit. Deferrals remain explicit and unwaived.

## Measurements and selected clock architecture

[Production measurements](../spec/soc-production-measurements.md) report
measured main paths 64.830223/65.965767 ns at assumed 8/9 MHz, mapped logic
3.322808384/3.3165169408 mm2, and every block/domain allocation and USB class.
Commands, source hashes and scope are in that report. Main passes the
estimated 60% budgets 75/66.666667 ns; USB retains its certified timing classes
and approved15 ns ordinary warning ceiling, with strict FP12.5 ns.

Production fixed-point mean/worst3879.791667/4350 cycles and hard-float
7809.833333/9007 cycles are measured with real boot/release and SRAM arbitration.
Against T13 round 2, estimated worst overhead is0% and34/8973=0.3789156%.
D75 still records the earlier accepted 4821-cycle result. No further memory
arbitration or multiplier optimization is authorized without Q16 need.

The [plan08 budget](08-physical-verification.md), including T32 and PLAN04's
approved analog allowances, estimates 12.605509285 mm2 against 12.92 mm2,
leaving 0.314490715 mm2 with named allowances. This is narrow
planning headroom, not physical fit. Macro/ROM/analog/pad/scan and real routing
must replace estimates before tape-out.

| Domain | Assumed screening rate | Source decision / physical work |
| --- | --- | --- |
| Main | 8 MHz selected; historical 9 MHz screening retained as evidence | D78 registered /6 from OSC_IN; generated-clock timing required |
| USB | 48 MHz | Existing external-reference accuracy requirement; physical qualification retained |
| AON | Nominal 32 kHz | D78 LF RC or reset-held external fallback; D82 slow recovery I2C; no fast-service source |
| JTAG | TCK | T32 rate/CDC contract, T38 pad qualification |

Q16 remains open: at assumed9 MHz, measured worst hard-float9007 cycles
estimates1000.777778 us before other firmware. S1's separate performance-floor
decision is not waived by acceptable integrated overhead. The existing SPI
host's 4 MHz target remains unresolved at selected main 8 MHz; do not silently
change that limit. D82 separately approves slow recovery I2C under the frozen
loader's eight-service-edges-per-SCL requirement. PLAN04/D81 adds oscillator-on
USB light sleep; attached USB does not support oscillator-off host resume.

## Remaining execution order

Under D88/D89, T39 runs a finite existing-regression campaign: standalone
core/lite checks, production clocks/reset and flight/wake, two-hart debug and
complete fast CI. New ISA/ISS frameworks, broad seeded coverage and complete
state observers are deferred; open proofs retain their original owners.
Existing T32/T33/T34 implementation/model evidence keeps its exceptions.
T39 uses current memory models and loader/bootstrap paths, so it does not
depend on T35/T36.
T35 and T36 follow, then T37/T38; replay affected T39 checks after those changes.
T38 acceptance requires current scoped core/SoC evidence with its limits. These are separately
assigned briefs, not implementation authorization from this document. D76
remains the execution CI policy unless separately amended for the assigned task.
Resolve interface dependencies before consuming unfinished designs.
T31 stays withdrawn; no further loader extension without a new decision.

System qualification remains T20 plus the stage owners: production target
transport, all connected interrupts and decode, reset/epoch drainage and full
CDC/RDC inventory, independent sensor/application tests and complete core
lockstep. Record each inherited block proof's exact scope; do not promote
simulation or bounded evidence to unbounded proof. Hardware stays general
purpose; first-board ESC/servo signals and application safety are firmware and
bench validation, not additional on-chip actuator controllers.
