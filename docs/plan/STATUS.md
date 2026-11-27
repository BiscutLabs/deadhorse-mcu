# Status

Single progress tracker. Last updated: 2026-11-27
States: `[ ]` not started, `[~]` in progress, `[!]` blocked, `[x]` complete,
`[-]` withdrawn.
Decision checks record the user's approvals, not implementation completion.
No implementation task or gate is completed by the planning reconciliation.

## Decisions

Details: [10-decisions-and-risks.md](10-decisions-and-risks.md).

| | ID | Decision | State |
| --- | --- | --- | --- |
| [x] | D1 | RISCay import | Approved direction; qualification remains open |
| [x] | D2 | Performance core | Approved direction; qualification remains open |
| [x] | D3 | Internal NoC | Superseded by D43 |
| [x] | D4 | Initial-chip scope | Approved direction; qualification remains open |
| [x] | D5 | Debug hardware | Approved direction; qualification remains open |
| [x] | D6 | Low-frequency clock | Approved direction; qualification remains open |
| [x] | D7 | Sleep peripherals | Approved direction; qualification remains open |
| [x] | D8 | Production test | Approved direction; qualification remains open |
| [x] | D9 | Physical flow | Approved direction; qualification remains open |
| [x] | D10 | Clocked islands | Superseded by D17 |
| [x] | D11 | USB cutoff | Approved direction; qualification remains open |
| [x] | D12 | Memory capacity | Approved direction; qualification remains open |
| [x] | D13 | Control-loop target | Approved direction; qualification remains open |
| [x] | D14 | NoC source ownership | Superseded by D43 |
| [x] | D15 | Standard-cell library | Approved direction; qualification remains open |
| [x] | D16 | Design language | Approved direction; qualification remains open |
| [x] | D17 | Timing discipline | Approved direction; qualification remains open |
| [x] | D18 | Historical lite-core option | Deferred historical option; no initial implementation |
| [x] | D19 | FPU inclusion | Approved direction; qualification remains open |
| [x] | D20 | FPU implementation | Approved direction; qualification remains open |
| [x] | D21 | Actuator publication | Historical approval; dedicated hardware superseded by D69; application validation remains open |
| [x] | D22 | UART sleep modes | Approved direction; qualification remains open |
| [x] | D23 | Tool environment | Approved direction; qualification remains open |
| [x] | D24 | Buses and ownership | Approved direction; qualification remains open |
| [x] | D25 | DMA | Approved direction; qualification remains open |
| [x] | D26 | IMU | Approved direction; qualification remains open |
| [x] | D27 | Barometer | Approved direction; qualification remains open |
| [x] | D28 | GPS and compass | Approved direction; qualification remains open |
| [x] | D29 | Airspeed | Approved direction; qualification remains open |
| [x] | D30 | RC | Approved direction; qualification remains open |
| [x] | D31 | Actuator fault detection | Historical approval; dedicated hardware superseded by D69; application validation remains open |
| [x] | D32 | Actuator count | First-application capacity retained; specialized hardware roles superseded by D69; qualification remains open |
| [x] | D33 | Actuator parts | Approved direction; qualification remains open |
| [x] | D34 | Boot authentication | Approved direction; qualification remains open |
| [x] | D35 | External clock | Approved direction; qualification remains open |
| [x] | D36 | Performance SRAM access | Approved direction; qualification remains open |
| [x] | D37 | Reset containment | Generic containment retained; actuator-specific failsafe state superseded by D69; qualification remains open |
| [x] | D38 | Supply monitor | Approved direction; qualification remains open |
| [x] | D39 | Pin multiplexing | Approved direction; qualification remains open |
| [x] | D40 | USB boundary | Approved direction; qualification remains open |
| [x] | D41 | Debug access policy | Approved direction; qualification remains open |
| [x] | D42 | Fabrication target | Approved direction; qualification remains open |
| [x] | D43 | Whole-chip bus, no NoC | Approved direction; qualification remains open |
| [x] | D44 | Multiply/divide formal split | Approved change of acceptance; not yet implemented |
| [x] | D45 | SIE and EP0 protocol multicycle timing | Approved 2026-11-18; certification and qualification required |
| [x] | D46 | EP0 address predecode and small overrun | Approved 2026-11-18; continue implementation, preserve measured margins |
| [x] | D47 | Scoped USB packet proofs | Approved 2026-11-18; at most 45 minutes, unchanged acceptance and solver caps |
| [x] | D48 | USB value-stability certificate | Approved 2026-11-18; includes reset assertion/release, exact production/mapped binding |
| [x] | D49 | USB PHY multicycle eligibility | Approved 2026-11-18; only value-certified endpoints, full-rate paths unchanged |
| [x] | D50 | Conditional small-model USB packet proof | Approved 2026-11-18; clean size parameters only, at most 60 minutes, original assertions and full-size simulation |
| [x] | D51 | USB reset-aware timing closure | Approved 2026-11-18; proved reset/capture contract and focused enable fanout work, limits unchanged |
| [x] | D52 | USB full-rate timing and qualification | Approved 2026-11-19; sizing/equivalent factoring and scoped verification, limits unchanged |
| [x] | D53 | Conditional 16-byte USB bulk packets | Approved 2026-11-19; 1 Mbit/s target, measure per direction before adoption |
| [x] | D54 | Test USB retry ownership repair | Approved 2026-11-19; immutable pending payload/ZLP, preserve queued data and all acceptance limits |
| [x] | D55 | USB consume timing repair | Approved 2026-11-19; compare enable capture and endpoint predecode, unchanged wire acceptance |
| [x] | D56 | USB protocol bank clock gating | Approved 2026-11-19; shared GF180 gate, identical update edges and retained timing checks |
| [x] | D57 | USB timing warning band and scope | Approved 2026-11-19; fix only consume now, 60–70% warning, mandatory real-wire post-placement recheck |
| [x] | D58 | USB pre-enable capture class | Approved 2026-11-19; conditional 3/2 certified-launch capture class, proof required; strict full-rate 12.5 ns; packetData full-rate amendment and consumer stop rule |
| [x] | D59 | USB 15 ns warning ceiling | Approved 2026-11-19; D58 FP stays strict 12.5 ns; real-wire post-placement recheck mandatory |
| [x] | D60 | USB packet stimulus E1 | Approved; exact producer guarantees required |
| [x] | D61 | USB CDC push spacing E2 | Conditional approval; spacing must be proved |
| [x] | D62 | USB small-model cover depth E3 | Approved depth 128 for covers only |
| [x] | D68 | Split AON/main timer services | Approved 2026-11-21; implementation/qualification in T21 |
| [x] | D69 | General-purpose MCU hardware boundary | Approved 2026-11-21; conventional timer/PWM/DMA, application policy in firmware; PLAN02 reconciliation |
| [x] | D70 | Performance watchdog reset scope | Approved 2026-11-21; core/client reset and PWM disable, preserve shared services |
| [x] | D71 | Retire hardware-scaled ADC register | Approved 2026-11-21; raw acquisition and firmware conversion, other offsets unchanged |
| [x] | D72 | One production DeadhorseSoc | Approved 2026-11-21; PLAN03 consolidation required |
| [x] | D73 | Freeze recovery loader; withdraw T31 | Approved 2026-11-21; existing reset/lock policy retained |
| [x] | D74 | Retire dedicated SPI ADC | Approved 2026-11-21; unbind in B2, delete separately after B2 passes |
| [x] | D75 | T20 integrated-loop exception | Approved historical 4,821-cycle result; production measurement still required |
| [x] | D76 | Fast CI on main; full at integration-stage ends | Approved 2026-11-21; deferrals remain visible and unwaived |
| [x] | D77 | USB asynchronous-boundary qualification | Approved 2026-11-22; exact CDC/RDC sink qualification required, raw diagnostics and physical debt retained |
| [x] | D78 | Tapeout clock architecture | Approved 2026-11-22: LF RC AON with strap fallback, external 48 MHz USB and divided 8 MHz main, OSC_EN standby control; Q15 resolved; implementation unverified |
| [x] | D79 | On-die POR/brownout with bypass | Approved 2026-11-22: safe default, external reset combination; D84 supersedes reset-sampled POR_BYPASS with a static powered-session strap; implementation unverified |
| [x] | D80 | T32 proof deferral and timing iterations | Approved 2026-11-23: defer epoch read-data proof; up to three adaptive timing loops, including carry-forward of improving failures; unchanged acceptance limits |
| [x] | D81 | USB oscillator-on sleep | Approved 2026-11-23: enabled USB holds OSC_EN high; attached resume uses light sleep; no stopped-oscillator USB resume or USB RTL change |
| [x] | D82 | Recovery I2C at LF AON rate | Approved 2026-11-23: frozen loader; host SCL limited to minimum qualified AON frequency divided by eight; nominal 4 kHz is an estimate |
| [x] | D83 | Cold external reset in POR bypass | Approved 2026-11-23: bypass-mode pin reset initializes/clears loader lock, retained watchdog history and debug POR state; normal-mode warm pin reset and watchdog containment unchanged |
| [x] | D84 | Static POR bypass strap | Approved 2026-11-23: POR_BYPASS fixed while powered, default low, directly selects reset; AON_CLK_SEL remains reset-latched. Removes circular POR initialization; D83 remains in force |
| [x] | D85 | Brownout threshold switching contract | Approved 2026-11-23: no unsafe release pulse; immediate assertion below new falling threshold; full new rising-threshold qualification after assertion. Physical validation remains T34 |
| [x] | D86 | T33 verification exceptions | Approved 2026-11-24: defer extensive timeout/composition proof work; frozen T33-specific checks, no full CI or unrelated IP tests; no aggregate CI claim or physical/I3 gate closure |

| [x] | D87 | T34 scoped verification exceptions | Approved 2026-11-24: relevant analog/model/integration checks only; no aggregate CI or unrelated IP tests; defer extensive timeout proofs, retain physical qualification debt |

| [x] | D88 | Plan core/SoC qualification | User direction 2026-11-24: prepare T39 for fresh standalone and integrated RISC-V verification ahead of T38 acceptance; planning only, no campaign or new CI/proof waiver |

| [x] | D89 | Focused existing-regression campaign | User direction 2026-11-24: significantly narrow T39; existing lite/core/SoC, flight/wake, debug and complete fast CI, with broader ISS/coverage work deferred, frozen code and reviewed documentation publication; no stage/proof closure |

| [x] | D90 | T35 scoped verification | User direction 2026-11-24: SRAM/BIST and affected integration tests only, no aggregate CI; defer extensive timeout proof work, retain independent review and physical/interface stop conditions |
| [x] | D91 | T36 scoped verification | User direction 2026-11-24: boot-ROM and affected integration checks only, no aggregate CI; defer extensive timeout proof work; retain independent review and boot-path/ownership/image-policy stop conditions |
| [x] | D92 | Single performance boot master | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D93 | Remove recovery loader | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D94 | Performance-owned main peripherals | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D95 | AON watcher peripherals | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D96 | Watcher-sized retained memory | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D97 | Unified general timers | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D98 | Verification-only RVFI | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D99 | Measure main SRAM options only | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D100 | Powered retained memory in dormant modes | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D101 | PLAN05 phase-end qualification | Approved 2026-11-24; PLAN05 scoped completion recorded; inherited proof/physical debt remains |
| [x] | D102 | DMA circular UART RX, shadow reload | User-approved 2026-11-24; T40 after PLAN05 design changes, +0.010 mm2 mapped-cell cap, scoped tests/no aggregate CI, one formal triage round. D92-D101 remain unchanged; no DMA implementation acceptance |
| [x] | D103 | Four reset cohorts; performance watchdog joins warm | User-approved2026-11-24; T41 queued after PLAN05; no RTL or acceptance |
| [x] | D104 | Temporary maximum lite-image load exception | Historical approval2026-11-24; closed by D108/T42 strict production load: measured20,051,604quanta, estimated208.870875ms versus250ms, no bypass |
| [x] | D105 | Official wafer.space physical base and template PDK | User-approved2026-11-24; supersedes D9 source; T43 scoped migration and logical chip top before T38; pad/SRAM stops retained; no implementation |
| [x] | D106 | DMI-only asynchronous cancellation | User-approved2026-11-25; immediate hard-clear quarantine and acknowledged flush; DM cold-only; implementation unverified |
| [x] | D107 | Bridge timeout quarantine and BIST pin abort | User-approved2026-11-25; immediate cancellation, acknowledged flush, existing selective pin abort; implementation unverified |
| [x] | D108 | T42 main-clock local grant | User-approved2026-11-25; only production toAon admission; preserve FIFO/epoch/owners/full readback,250ms and scoped/no-CI policy |
| [x] | D109 | T43 fd_io pads and current SRAM inventory | User-approved2026-11-25; common3.3V supply, sixteen1024x8 plus four512x8; no capacity change or electrical/physical acceptance |
| [x] | D110 | T43 local-drive readback while driving pads | User-approved2026-11-25; legal fd_io IE/OE controls; released pins sample external level, driven pins read local value; pad tests and USB electrical qualification remain |
| [x] | D111 | Compact LF/POR physical implementation | User-approved2026-11-25; extends T43 to implement missing physical macros, seek practical minimum area, finish checks and merge to main; no contract or qualification waiver |
| [x] | D112 | T38 basic layout/fit before T37 | User-approved 2026-11-26; follow-up narrows this run to basic placed fit and already-completed CTS. Routing, DRC, production-GDS qualification and aggregate CI deferred; no limit or signoff waiver |
| [x] | D113 | Reset physical contract and distribution | User-approved 2026-11-27; T44 pauses T37, preserves cohorts/core/FPU/interface behavior, qualifies resetless payload and local release distribution; six AON event inputs separately listed with all checks retained; baseline/final fast CI and zero class-C/reset-electrical failures required |

## Tasks

Current verification receipt: [T39](tasks/reports/T39.md), the D89 finite
existing-regression campaign. Broader ISA/ISS coverage and inherited proof debt
remain explicitly deferred; affected checks must replay after memory/boot/scan
changes before T38 acceptance. No integration-stage exit is claimed.

| | ID | Item | Owner | Depends on | Report |
| --- | --- | --- | --- | --- | --- |
| [x] | PLAN01 | [Reconcile decisions](tasks/PLAN01-reconcile.md) | Codex | User approvals | [Report](tasks/reports/PLAN01.md); documentation only |
| [x] | PLAN02 | [General-purpose MCU scope](tasks/PLAN02-general-mcu.md) | Codex | User direction D69 | [Report](tasks/reports/PLAN02.md); documentation checks and independent review pass; no RTL or CI |
| [x] | PLAN03 | [SoC consolidation and tape-out planning](tasks/PLAN03-soc-consolidation.md) | Codex | D72–D77; existing T20–T30 evidence | One production top, ADC retirement, B4 measurements, B5 debt register/triage and B6 briefs independently accepted. Frozen fast03 passes all active checks with twelve T14/T17 deferrals explicitly unproved. [Measured paths](../spec/soc-production-measurements.md), [report](tasks/reports/PLAN03.md). Full tier, T20 system qualification and chip physical acceptance remain open |
| [!] | PLAN04 | [Tapeout clock/reset architecture](tasks/PLAN04-clock-reset.md) | Codex | D78/D79/D81–D84; D86 closeout | [Report](tasks/reports/PLAN04.md): original composition/formal acceptance remains incomplete. Implementation, measured timing/area and finite wake/retention evidence carried into T33's completed D86 closeout. Minimum-count/shutdown helpers deferred rather than awaiting approval. Historical fast02 evidence retains its original scope; full tier and physical/I3 qualification remain open |
| [x] | PLAN05 | [Dormant coprocessor and single-master boot](tasks/PLAN05-dormant-coprocessor.md) | Codex | D92-D101/D104; T36 | [Report](tasks/reports/PLAN05.md): all implementation/scoped checks pass with explicit proof debt and D104 maximum-image latency exception. Both frozen fast tiers pass; Phase3 measured 3869.903314s, 12 inherited proof deferrals. Main67.850388ns/75, estimated chip11.323913603mm2; full tier unrun |
| [x] | T08 | [Pinned Linux environment](tasks/T08-environment.md) | Codex | none | [Report](tasks/reports/T08.md); clean rebuild and runtime smoke pass |
| [x] | T01 | [Scaffold/CI](tasks/T01-scaffold.md) | Codex | T08 | [Report](tasks/reports/T01.md); local gate and fresh-context review pass |
| [x] | T02 | [Historical loop CI](tasks/T02-flight-loop-ci.md) | Codex | T01, T08 | [Report](tasks/reports/T02.md); exact QEMU matches, historical summary preserved, local gate passes |
| [-] | T03 | Interconnect study | n/a | n/a | Withdrawn by D43; no source imported |
| [-] | T04 | Interconnect study | n/a | n/a | Withdrawn by D43 |
| [x] | T06 | [RISCay baseline](tasks/T06-riscay-baseline.md) | Codex | T01, T08 | [Report](tasks/reports/T06.md); upstream gates/export pass, area within tolerance, local gate and independent review pass |
| [x] | T07 | [Chisel build](tasks/T07-chisel-build.md) | Codex | T01, T06, T08 | [Report](tasks/reports/T07.md); direct build, simulation, both formal routes, local gate and independent review pass |
| [x] | T05 | [Register generator](tasks/T05-regmap-generator.md) | Codex | T07 | [Report](tasks/reports/T05.md); generator/model, simulation, both formal routes, local gate and independent verification pass |
| [x] | T09 | [Timing flow](tasks/T09-timing-flow.md) | Codex | T01, T06, T07, T08 | [Report](tasks/reports/T09.md): timing gate and authorized RegBlock repair verified |
| [x] | T10 | [Ibex reference and harness](tasks/T10-ibex-reference.md) | Codex | T07, T08 | [Report](tasks/reports/T10.md): sequential/whole-core harness, candidate suites and divide stress pass; full local gate and independent review pass; D44 limits retained |
| [x] | T11 | [Ibex conversion](tasks/T11-ibex-conversion.md) | Codex | T10, T09 | [Report](tasks/reports/T11.md): user-approved focused verification complete; exact revision proof carries prior ISA evidence; current tests/timing/lockstep and independent review pass; repeated full CI stopped, not passed |
| [x] | T12 | [FPU](tasks/T12-fpu.md) | Codex | T07, T09 | [Report](tasks/reports/T12.md): standalone RV32F, focused local gate, arithmetic-abstracted control proof, reference tests, GF180 timing and independent review pass; full CI intentionally not rerun |
| [!] | T13 | [F integration](tasks/T13-core-f-integration.md) | Codex | T11, T12 | [Acceptance reconciliation](tasks/reports/T13.md#deferred-acceptance-for-s1): simulation/timing evidence retained; remaining formal acceptance deferred for S1, not proved; standard full tier unrun. [Pipeline timing study](tasks/reports/T13-pipeline-timing.md). [Area study](tasks/reports/T13-area-study.md). [Ten-proposal study](tasks/reports/T13-ten-proposals.md). [Round 2](tasks/reports/T13-round2.md). |
| [!] | S1 | [Core measurement](tasks/S-spikes.md#s1-core) | Codex | T13, T09, T02 | [Report](tasks/reports/S1.md): timing and baseline comparisons pass; hard-float 1.090122 MIPS at 9 MHz below 2.5 floor; independent review confirms; latency/IRQ sweep and CI tiers unrun |
| [x] | T14 | [Bus, bridge and mailbox](tasks/T14-bus-mailbox.md) | Codex | T07, T09 | [Active checks complete with four user-approved unproved deferrals; fast 29/29 and independent review pass; full not run](tasks/reports/T14.md) |
| [x] | T15 | [UART peripheral](tasks/T15-uart.md) | Codex | T05, T07, T09, T14 | [Report](tasks/reports/T15.md): UART acceptance, GF180 timing and independent review pass; fast 30/30 with inherited T14 deferrals, no UART deferrals; full not run |
| [x] | T16 | [SPI host](tasks/T16-spi-host.md) | Codex | T05, T07, T09, T14, T15 | [Report](tasks/reports/T16.md): SPI acceptance, GF180 timing and independent review pass; fast 31/31 with inherited T14 deferrals, no SPI deferrals; full not run |
| [x] | T17 | [I2C controller](tasks/T17-i2c-host.md) | Codex | T05, T07, T09, T14, T16 | [Report](tasks/reports/T17.md); 19 simulations, GF180 timing and fast CI active checks pass; eight I2C formal jobs remain deferred/unproved |
| [x] | T18 | [Lite I2C recovery loader](tasks/T18-i2c-recovery-loader.md) | Codex | T06, T07, T09, T14 | [Report](tasks/reports/T18.md). Wire-to-memory recovery and warm-reset lock retention verified. |
| [!] | T19 | [USB CDC-ACM](tasks/T19-usb.md) | Codex | T05, T07, T08, T09, T14 | [PLAN03 closure](tasks/reports/PLAN03.md): packet inventory, sampling/spacing, applied exceptions, scoped routed/boundary qualification and aggregate pass. Whole-chip physical/analog/reset qualification and optional partial-header diagnostic remain; no tape-out signoff |
| [!] | T20 | [Reference SoC integration, I0–I1](tasks/T20-soc-integration.md) | Codex | T13–T19/S3; D72/D75 | Production top and B4 timing/area/fixed+float measurements accepted in [PLAN03](tasks/reports/PLAN03.md); D75 retained. Full generated-top formal/CDC, target-interface and inside-SoC architectural qualification remain open; no physical signoff |
| [x] | T21 | [GPIO and split timers; historical ADC retired](tasks/T21-flight-io.md) | Codex | T05, T07, T09, T14, T20 interfaces | [Report](tasks/reports/T21.md): focused checks reviewed; GPIO/main/AON timers now in production under PLAN03. D74 retires ADC. Whole-system/physical qualification separate |
| [x] | T22 | [General-purpose PWM](tasks/T22-pwm.md) | Codex | D69, T21, T20 interfaces | [Report](tasks/reports/T22.md): generic PWM and production binding implemented; frozen focused simulations, scoped proofs, setup/electrical timing and independent review pass. DMA integrated in T23; its proof debt and physical qualification remain. Current fast tier under PLAN03 |
| [!] | T23 | [Basic DMA controller](tasks/T23-dma.md) | Codex | D25, D69, T22, T20 interfaces | [Report](tasks/reports/T23.md): RTL, frozen 62 tests/four top emissions and block timing pass; one range proof unresolved; PLAN03 B5 sole-range Z3 attempt unresolved; approved helper work needed. Fast tier is tracked under PLAN03 |
| [x] | T24 | [Limited GPIO output pin mux](tasks/T24-pinmux.md) | Codex | D39, D69, T21–T23 interfaces | [Report](tasks/reports/T24.md): functional RTL, frozen 71 tests/four top emissions, 18 assertions and timing pass; independently reviewed; production consolidation/fast tier under PLAN03; physical qualification separate |
| [!] | T25 | [Clocked lite core adoption](tasks/T25-lite-core.md) | Codex | D1, T06, T14, T18, T20/T24 interfaces | [Report](tasks/reports/T25.md): real AON hart/loader binding, 28 frozen tests/four top emissions, baseline/control proofs and mapped timing pass; independent review clear. Full ISA/machine formal open after capped ADDI partition; destination-data claim unresolved. Fast tier tracked under PLAN03 |
| [!] | T26 | [Digital watchdog/reset supervision](tasks/T26-watchdog.md) | Codex | D70, T20/T22/T24/T25 interfaces | [Report](tasks/reports/T26.md): D70 RTL, frozen functional/top checks, output-disable proofs and corrected mapped setup/electrical screens pass; independent review clear. Full-width watchdog proof unresolved; PLAN03 B5 partition results in debt register; physical qualification open. Fast tier tracked under PLAN03 |
| [x] | T27 | [Historical raw ADC acquisition](tasks/T27-adc-raw.md) | Codex | D69, D71; superseded by D74 | [Historical report](tasks/reports/T27.md); completed implementation later retired from production and deleted separately under PLAN03/D74. External ADC access is firmware through general SPI/DMA |
| [x] | T28 | [Lite-first performance release](tasks/T28-boot-release.md) | Codex | T25/T26/T27 interfaces, plans07/16 | [Scoped digital handoff verified](tasks/reports/T28.md); production boot/physical qualification open, current production consolidation/fast tier under PLAN03 |
| [x] | T29 | [Bounded QSPI command interface](tasks/T29-qspi-command.md) | Codex | Plans04/07, T28 interfaces | [Command-mode RTL verified](tasks/reports/T29.md); frozen focused checks and independent review pass; XIP integrated by T30; production boot/physical open, current production consolidation/fast tier under PLAN03 |
| [x] | T30 | [Native QSPI read path](tasks/T30-qspi-xip.md) | Codex | Plans03/07, T29 interfaces | [Native flash RTL verified](tasks/reports/T30.md); frozen focused checks and independent review pass; production boot/physical open, current production consolidation/fast tier under PLAN03 |
| [-] | T31 | [Retained locked-image restart](tasks/T31-retained-loader-restart.md) | n/a | D73 | Withdrawn; loader frozen at existing feature set and reset policy. [Historical proposal](tasks/reports/T31.md) |
| [!] | T32 | [Two-hart JTAG debug](tasks/T32-jtag-debug.md) | Codex | PLAN03; T33 interface coordination | [Report](tasks/reports/T32.md), [timing follow-up](tasks/reports/T32-timing-followup.md): D80 defers the unproved epoch read-data claim. Mapped timing closes at measured 65.141479 ns below unchanged 66.666667 ns, with all-state equivalence and fault control. Frozen fast timing-fast01 passes all 34 active commands in measured 3850.781049 s; twelve inherited deferrals remain unproved. Full tier unrun; physical reset/clock-tree debt remains |
| [x] | T33 | [Clock/reset/power controller](tasks/T33-clock-reset-power.md) | Codex | PLAN04; T32/T34 coordination; D85/D86 | [Report](tasks/reports/T33.md): completed with D86 exceptions. 82 credited task cases, map/tool checks and independent review pass (commands/times in report). Initial inherited I/O scope error and failed aggregate preserved; corrected continuation explicitly selected. Difficult composition proofs remain deferred; no fast/full CI or physical/I3 signoff |
| [x] | T34 | [Analog interfaces/models](tasks/T34-analog-models.md) | Codex | PLAN03; D87 | [Report](tasks/reports/T34.md): completed with D87 exceptions. Frozen relevant models/production POR cases, scoped reset proofs, pin audit and fault controls pass. Production HDL unchanged. Physical characterization, four-state qualification and calibration/test access remain open; neither CI tier run |
| [x] | T35 | [SRAM macros and BIST](tasks/T35-sram-bist.md) | Codex | T32/T33 implementation with recorded deferrals; coordinate T36; D90 | [Scoped completion](tasks/reports/T35.md): production macros/BIST, 43 relevant Scala tests, four TAP scenarios and unchanged flight cycles; two proofs deferred, physical signoff open; no CI under D90 |
| [x] | T36 | [Production boot ROM firmware](tasks/T36-boot-rom.md) | Codex | PLAN05 Phase2; D91-D101/D104 | [Report](tasks/reports/T36.md):5 metadata tests,7 formal jobs,12 native tests/3 faults and36 wire cases pass with D104 maximum-image load exception296.923125ms; watcher170.891875ms. Final ROM timing/area pass; Phase3 fast passes all 33 commands in measured 3869.903314s, 12 inherited deferrals; full tier unrun |
| [!] | T37 | [Test mode and scan](tasks/T37-test-scan.md) | Codex | T44 first; T35/T36; coordinate T38 | Paused by D113 until T44 reset acceptance. [Report](tasks/reports/T37.md): Docker migration recovered; graph and placed-fit checks pass. Ten scoped timing screens retain setup/hold/reset/electrical failures. Rejected delay-family experiment is not the T44 baseline; coverage/manufacturing obligations remain open |
| [!] | T38 | [Chip top and pad ring](tasks/T38-chip-top-pads.md) | Codex | D112 basic fit; T35/T36/T43 | [Basic fit complete](tasks/reports/T38.md): production placement/CTS fits the 12.901981 mm2 core; zero placement violations, complete macro inventory and graph/clock audits pass. Full T38 remains deferred: scan, routing, timing closure, DRC and signoff. No aggregate CI |
| [x] | T39 | [Focused core and SoC regression](tasks/T39-core-soc-qualification.md) | Codex | D89; existing T13/T25 cores and T20/T32–T34 integration; proof debt retained | [Report](tasks/reports/T39.md): scoped regressions and all 34 fast commands pass; twelve inherited T14/T17 deferrals remain unproved. Independent evidence/documentation review accepted; no RTL changes. Broader qualification deferred; full tier not run |
| [x] | T40 | [DMA circular UART RX](tasks/T40-dma-circular-uart-rx.md) | Codex | D102; completed PLAN05 and T41; T23 proof debt retained | Scoped implementation complete: frozen19 DMA/SoC tests, driver/map checks, all four simulation faults, timing and area pass. Measured added0.003462mm2 below0.010 cap. Circular formal closure/reload-fault proof deferred at caps; finite range bounded36, inherited unbounded debt remains. No aggregate CI. [Report](tasks/reports/T40.md) |
| [x] | T41 | [Reset consolidation](tasks/T41-reset-consolidation.md) | Codex | D103; completed PLAN05/T36; T33/T34/T32 interfaces | Scoped completion under D103/D106/D107, independently reviewed. Four cohorts, paired-image warm ROM and relevant reset/boot/sleep/debug checks pass. Measured release instances 89→30 and reset controls 150→59; mapped setup passes with approved USB warning, estimated headroom 1.586 mm². Lite initialization/SRAM ownership proofs deferred at caps; shared startup/shutdown and qualified DMI composition remain open. Physical hold/RDC/reset-removal deferred; no aggregate CI. [Receipt](tasks/reports/T41.md) |
| [x] | T42 | [Lite boot-transfer latency](tasks/T42-lite-boot-transfer.md) | Codex | D104/D108; PLAN05; T41 | [Report](tasks/reports/T42.md): independently accepted scoped completion. Maximum measured20,051,604quanta, estimated208.870875ms/250ms with full readback/no bypass; D104 closed.18 relevant Scala cases,20 wire positives/1 ROM fault,2 load cases,2 unbounded local assertions/3 faults pass. Main67.515236ns/75; estimated headroom1.569452635mm2. Inherited composition/physical debt remains; no aggregate CI |
| [x] | T43 | [wafer.space template and PDK](tasks/T43-wafer-space-physical-base.md) | Codex | D105/D109/D110/D111; current production; prerequisite for T38 | [Report](tasks/reports/T43.md): independent review approves scoped acceptance. Matched PDK area/timing, pad binding/boot/reset, full template baseline and actual20SRAM+LF/POR floorplan/padring/connected PDN pass. Combined analog footprint measured0.2149688024mm2; estimated headroom1.6044838321mm2. Analog electrical qualification and full T38 signoff remain open. No aggregate CI |
| [~] | T44 | [Reset timing and distribution](tasks/T44-reset-distribution.md) | Codex | D113; baseline fast failures reported; T38 cts02 | [Report](tasks/reports/T44.md): reviewed I2C/USB provenance checkpoint passes focused checks, retaining all eight I2C deferrals and original USB proof qualifications. Historical physical evidence is bound to the current USB context; no fresh timing closure. Both partial fast failures remain visible. Mapped inventory reconciliation, reset RTL, physical qualification and final fast remain. T37 paused |
| [-] | S2 | Interconnect study | n/a | n/a | Withdrawn by D43 |
| [x] | S3 | [Memory](tasks/S-spikes.md#s3-memory) | Codex | T02, T07, T08 | [Report](tasks/reports/S3.md): representative allocations/model checks and independent review pass; fast 29/29 with inherited T14 deferrals, full not run |
| [ ] | S4 | [Latency/test](tasks/S-spikes.md#s4-latency-and-test-access) | unassigned | S1, T08, T09 | |

Former P0-f/P0-g now have briefs T08/T09. P0-a actuator split and P0-b parts
are approved decisions D26-D33, not bench qualification. P0-c USB digital delivery is integrated; whole-chip physical qualification remains open. P0-d die-link agreement is
deferred. P0-e analog work has the unimplemented T34 interface/model brief; layout/extraction remains later work.

## Verification debt

This is the consolidated register of unresolved, deferred or deliberately
limited proof obligations. Historical passes retain their model/assumption
scope. No row is waived by PLAN03 or by a passing fast tier. B5's only new
solver work is the single focused attempt on T23/T25/T26; exact results and
step-0 tables are in [the debt report](../spec/soc-verification-debt.md).

| Property / scope | Current status | Evidence that exists | Owner | Closure plan |
| --- | --- | --- | --- | --- |
| Faithful-F integration, original 28 assertions/depth160 | Deferred, unresolved | Depth40/80 bounded arithmetic-abstracted checks, concrete covers/fault and selected lockstep; [ledger](../ledger/core-formal.md) | T13 | Needs approved focused proof attempt; no unchanged long sweep |
| Complete repaired faithful-F configured ISA; changed-core no-F refinement | Deferred/unrun, not established | Local decode/CSR and unchanged-module equivalence; selected ISA/lockstep only | T13 | Complete configured sweep/refinement under a separate closure assignment; bounded evidence is not full proof |
| Historical full-depth C.ADD and concrete multiply/divide/F arithmetic scopes | Original broad checks unresolved; narrower approved scopes only | D44 algebra/seeded faults, protocol abstractions and bounded instruction windows in core/FPU ledgers | T10–T13 | Retain approved bounded/abstracted labels with reason; further acceptance change needs decision |
| BUS-FAIR-M0 | Deferred, unproved | Safety31/34, bounded diagnostics/covers; fast receipt preserves model identity | T14 | Needs approved helper/composition attempt |
| BUS-FAIR-M1 | Deferred, unproved | Same exact bus partition; no reachable counterexample | T14 | Same; no unchanged retry |
| BUS-FAIR-M2 | Deferred, unproved | Same exact bus partition; no reachable counterexample | T14 | Same; no unchanged retry |
| BRIDGE-RETURN-DATA | Deferred, unproved | Other13 assertions prove, concrete data fault and six covers; watchdog32 model | T14 | Needs approved data/ownership composition; default-parameter qualification also open |
| Shared CDC/mailbox/bridge production composition and physical assumptions | Limited block proofs; whole-chip wiring not fully proved | FIFO ordering/reset proofs, endpoint proofs and simulation | T20/T33/T38 | Complete generated-top crossing/RDC inventory and system composition; physical checks separate |
| T33 full-width oscillator startup minimum count | Deferred, unproved under D86; triage exhausted | Local cadence/bootstrap/qualification proofs; production late/never-start and reset/retention simulation | T33 | Separate assignment for minimum-count helper; no unchanged timeout rerun or implicit fairness assumption |
| T33 shutdown command/completion ownership, gate closure and retained holds | Deferred, unproved under D86; triage exhausted | FIFO transport proofs, local policy safety, actual STOPPING/cancel/wake/reset tests and gate-cell checks | T33 | Separate assignment for ownership/latched-closure helpers; keep original obligations |
| T33 unbounded stale-response/reset epochs and targetQuiet composition | Deferred, unproved under D86 | Finite production client/SBA/watchdog phase tests and local exact-model endpoint proofs | T33/T32 | Compose actual producer/drain/epoch guarantees; finite tests are not an unbounded proof; D80 remains separate |
| T33 mapped CDC/RDC composition and storage qualification | Deferred digital proof/qualification under D86; not signoff | Complete origin inventory and exact replayed source hierarchy; 395 unbound and 57 merged register identities retained, source latches/memories separately listed | T33/T38 | Close source-to-mapped and cross-epoch premises before whole-chip signoff; retain raw physical diagnostics |
| D111 analog electrical/clocked composition and selector-restart proof | Open; physical smoke is not electrical qualification | LF4-edge unbounded proof, POR1000-edge raw-good/cause/range proofs and directed D85 tests; selected macro DRC/LVS, local PDN checks and limited extracted diagnostics | Analog physical qualification/T38 | Qualify full RC and loading, POR initialization/feedback, selector restart, PVT/trim/noise and timing/antenna models; retain120s failures, no unchanged sweep |
| T17 WRITE-CORRECT | Deferred, unproved | Original320-edge job timed out; write fault rejected and wire tests | T17 | Focused partition/triage assignment; retain current bound |
| T17 WRITE-COVER | Deferred, unproved | Wire simulation, no formal cover completion | T17 | Same, preserve reachability obligation |
| T17 READ-CORRECT | Deferred, unproved | Original320-edge job timed out; wire simulation | T17 | Focused triage, no assumed success |
| T17 READ-COVER | Deferred, unproved | Simulation, formal witness unresolved | T17 | Same |
| T17 READ-CORRUPT | Deferred, unproved | Simulation fault tests do not replace original formal fault job | T17 | Same; qualify intended fault |
| T17 RECOVER-CORRECT | Deferred, unproved | Original256-edge job timed out; bus-recovery simulations | T17 | Focused triage |
| T17 RECOVER-COVER | Deferred, unproved | Simulation, formal witness unresolved | T17 | Same |
| T17 RECOVER-CORRUPT | Deferred, unproved | Original fault job timed out | T17 | Same; qualify intended fault |
| UART frame, SPI mode0/3 frame, I2C timeout, recovery-loader completion accounting | Bounded to each receipt's stated depth; not unbounded | Current fast block checks, independent wire models, covers/faults | T15–T18 | Retain planned bounded protocol scope with reason; do not promote to proof |
| USB full-size packet claims beyond accepted small-model scope | Qualified mixed-size policy, not all unbounded at16 bytes | Twelve independent-reset claims: five full16, seven small8 plus source-bound full-size simulation; E1/E2 references explicit | T19 | Retain D50/small-model acceptance label; broader full-size proof is not implied |
| USB partial-header/new-SETUP diagnostic | Unresolved optional diagnostic | Required sampling/spacing11 proofs and actual faults pass in PLAN03; complete aggregate passes its defined scope | T19 | Separate focused diagnostic if assigned; no change to accepted sampling claims |
| USB chip-level physical/reset/analog composition | Not a digital proof closure or tape-out signoff | Exact D77 sink qualification, standalone extracted USB and separate bus fixture; mapped SoC class certificates | T33/T38 | Actual pad/macro contracts, upstream reset/clock control, whole-chip CTS/RDC/hold/analog qualification |
| Full production decode, interrupt binding, reset order/epoch drainage and inside-SoC ISA/target interface | Open composition/acceptance | Map validation, focused SoC wire/MMIO/reset tests, real boot benchmarks and all-FP-result reference check | T20 | Focused generated-top formal/structural checks and complete architectural/system test coverage; performance is not lockstep |
| DMA memory offer within performance SRAM | Unresolved after PLAN03 sole-range Z3 attempt | Nine other safety assertions and seven denied checks prove; BMC9/18, covers/origin/owner faults and simulation | T23 | Needs approved cursor/remaining/offer invariant work; no new assumption or unchanged retry |
| Circular DMA range/underflow/exact-per-lap events | Deferred after T40 bounded growth/portfolio caps; reload mutation formal witness also capped | BMC16 only (before wrap); five covers through36; three-lap simulation and all four required simulation mutations pass; lock/half/done formal faults caught | T40 | One triage round exhausted. Separately reviewed per-channel conservation/shared-retirement partition needed before further proof work; no assumed helper |
| Lite ADDI destination data | Unresolved after exact concrete partition | Eight other meaningful ADDI claims prove; five memory claims trivial; baseline state/control proofs and ISA simulation | T25 | Needs approved retirement/operand-consistency helper work and targeted fault qualification |
| Lite other instructions, RF consistency, fetch correspondence, CSR/interrupt machine behavior | Open/unrun | Baseline exact31-state equivalence, adapter/control proofs, directed ISA/machine tests | T25 | Separate full-ISA/machine proof plan; ADDI partition is not ISA closure |
| Full-width watchdog channel | Five of twelve claims proved; seven unresolved; singleton fault scope explicit | Original12 claims retained, original concrete covers/three actual faults, output-disable proofs and whole-top simulation | T26 | Remaining captured-settings/crash-count relation needs approved helpers; singleton fault qualification listed in debt report |
| GPIO/timer wake and PWM elapsed-time/whole-top composition | Scoped safety proofs; broader progress/system proof open | GPIO/timebase/capture and PWM update/ownership proofs, actual simulations/faults | T20/T21/T22/T33 | Complete system cadence/wake/interrupt composition under real clock controller |
| QSPI dynamic owner handover, native address/permission and progress, reset composition | Simulation-backed; not unbounded liveness | Engine/owner/scheduler safety proofs, independent flash tests and actual arbitration/orphan faults | T29/T30/T36 | Complete production boot/system closure; any fairness premise must be justified |
| T32 SBA epoch current-request read data across independent reset | Deferred and unproved by D80; original assertion retained | Fifteen control claims, covers/faults and prior bounded data traces; production OpenOCD reset tests; mapped core equivalence is a separate claim | T32 | Resume the proposed production BridgeSource payload lemma only when assigned; no unchanged timeout rerun |
| T35 full-depth SRAM data/latency and composed BIST ownership | Deferred and unproved under D90 after one 120-second attempt each | Pin and small March proofs, covers/actual faults, full-size array/operation/status simulation and unchanged production flight cycles | T35 | Prove RAM-entry/observer and remote-release/FIFO helper invariants when assigned; broader banking/mux/CDC/RDC remains simulation-backed |
| Production ROM boot/update policy, debug, sleep controller, scan equivalence and pad connectivity | Not implemented or proved | Existing block contracts and scoped tests only | T32–T38 | Implement assigned briefs with properties/covers/faults; no blanket inherited proof |

Separate non-proof blockers stay visible: Q15 clock/service rates, Q16 loop
target and the S1 performance-floor decision; SRAM/ROM/analog/pad realization
and the narrow estimated area headroom; full CI and stage/system/FPGA/physical
acceptance. Retired ADC assertions belong to git history under D74, not active
production verification debt. T31 is withdrawn rather than deferred work.


## Gates (not checked by PLAN01)

**G0**

- [ ] D1/D2 recorded and reviewed against the implementation briefs
- [ ] Scaffold and CI working
- [ ] USB boundary and outstanding sizing/delivery assumptions reviewed

**G1: architecture freeze**

- [ ] Formal tool smoke and shared CDC proof
- [ ] S1 selected core/full F correctness, area, timing, loop target/fallback
- [ ] T14 bus, domain bridge and mailbox: contract reviewed, proofs, area/timing
- [ ] S3 memory capacity, banking and XIP validated
- [ ] S4 latency and production-test evidence
- [ ] Clock, reset, ownership/CDC partition and simultaneous pin map frozen
- [ ] Shuttle, library, SRAM and analog process options qualified
- [ ] USB reservation based on implementer evidence or explicitly omitted
- [ ] No unresolved assumptions affecting area, pads or clock domains

**G2: SoC/FPGA**

- [ ] Simulated flight and real sensor/actuator timing checks
- [ ] Independent channel rates, atomic publication, timeout/recovery validated
- [ ] Retained sleep, UART modes, DMA/ownership, wake and reset containment
- [ ] Both-core JTAG, boot/recovery, external-clock selection and USB stub/interface
- [ ] HF-off retained sleep demonstrated when no selected peripheral requires HF
- [ ] Clean CDC and every block within its GF180 timing budget or recorded exception
- [ ] Every block requiring a full proof has it or a recorded bounded-result reason
- [ ] riscv-formal passes on both cores; independent full-F verification; no unreviewed assumption
- [ ] Scan gate-level checks, SRAM self-test and analog test connectivity

**G3: physical signoff**

- [ ] Static timing
- [ ] Clock tree/gating
- [ ] Clock-domain crossings
- [ ] Reset
- [ ] Electrical rules
- [ ] SRAM timing
- [ ] DRC/LVS/antenna
- [ ] Post-layout simulation
- [ ] Scan
- [ ] Sleep current
- [ ] Equivalence before/after scan and final netlist
- [ ] USB integrated or cutoff applied before Phase 3 floorplan freeze

**G4: silicon**

- [ ] Bring-up, production test/calibration, characterization and flight validation

## Log

- 2026-11-27: Codex started T44/D113 on codex/t44-reset-distribution from main5b0cf938. Unchanged-main fast baseline failed at I2C retained-deferral model authentication after measured1587.572686s; I2C19 simulations and timing passed, but formal rejected stale model identity before launching its deferred job. Evidence: build/t44/baseline-main02. Diagnosing the prerequisite before reset RTL; T37 paused. User approved separate six AON GPIO event-input listing with all checks retained and no new exception. Full tier not run.
- 2026-11-27: T44 corrected frozen fast baseline failed after measured1709.364546s at stale USB sampling source evidence (Cdc.scala), after all checks through I2C passed. The four bus/eight I2C deferrals remain unproved; no reset RTL changed. Fresh production mapping measured20,392FFs,13,247with async controls; inventory classification remains incomplete. Evaluating the existing exact HDL/model replay, with unchanged collectors and no unchanged proof retries. Full tier not run.
- 2026-11-27: T44 focused packet provenance repair passes the existing twelve-claim collector with original small-model qualifications, no solver reruns, exact fresh HDL/canonical/observer identity and five rejected binding faults. Fresh USB context proof and full-size throughput tests pass; physical evidence exposed three reviewed internal-name-only emission differences, now covered by a strict pinned compatibility check. Reset implementation and final fast remain open; no new physical timing result or full-tier pass is claimed.

- 2026-11-26 Codex: T37 restored-candidate timing checkpoint: all ten mode/corner measurements complete with independent hash/constraint/clock review; graph and placed fit pass, timing does not. Test-reset dlyb exclusion substituted dlyc and increased area. Failed paths, new fault sites, raw coverage and electrical warnings retained in the report and hashed local archive. Docker verified on P: after cleanup; no aggregate CI or unrelated IP tests.

- 2026-11-26 Codex: Resume T37 after storage recovery under user direction. Qualify the inserted delay-cell semantics against every pinned corner, rerun graph/fit checks and continue scoped timing. Existing limits and negative controls remain; no aggregate CI.

- 2026-11-26 Codex: User-authorized cleanup and Docker migration completed. Estimated 102.80 GB of project allocation reclaimed from measured free-space deltas; 274.21 GB Docker disk copied with matching SHA-256, activated on P:, checked across restart, then C: original retired. Newest final placement files were empty after the disk-full failure; surviving repair inputs/checkpoint were backed up and only DetailedPlacement rerun (measured 13.095 s). The recovered candidate's graph audit rejects newly inserted `dlyc_1`, so fit/timing remain unqualified. No aggregate CI; no RTL changes or blanket Docker prune.

- 2026-11-26 Codex: T37 timing continuation blocked by C: exhaustion and Docker read-only/I/O errors. Measured repair process completed in 1590.136157 s; subsequent graph/fit/timing bundle could not write its receipt. No new candidate acceptance or area/timing improvement claim. Earlier scoped timing diagnostics expose USB setup, main/SRAM hold, tester-input hold and pad slew issues. Checker fixes independently reviewed; final frozen checks, commit and push deferred until storage recovery. User asked to free C: space or approve a Docker-data relocation plan; no pruning/restart/relocation performed.

- 2026-11-26 Codex: User approves scoped T37 timing continuation on main. Diagnose the test-reset buffer network, then measure functional, shift and capture modes with unchanged limits and relevant checks only; no aggregate CI.

- 2026-11-26 Codex: T37 reaches the requested pre-timing checkpoint. Measured physical-pin replay detects 604,033 baseline faults; added physical sites remain unresolved. Scan placement/CTS, original-graph/supply audit and basic fit pass independent review. The resizer's 24,185 delay buffers, mostly in test reset, are an explicit implementation-quality risk for the timing stage. Full coverage, timing and manufacturing acceptance remain open; no aggregate CI. Commands, hashes, measurements and exclusions are in the T37 report.

- 2026-11-26 Codex: Resume T37 physical-pin ATPG replay and scan buffering/placement/CTS under explicit user direction; stop before timing qualification. Scoped checks only, no aggregate CI.

- 2026-11-26 Codex: T37 scoped two-phase capture/entry model and suggestion export pass independent review. One120s ATPG attempt returns124 without patterns; host133.663s, with a subsequent preserved log-decoding failure, fixed for future runs without repeating ATPG. Existing common-supply normalization resolves the STA crash; single-corner ideal-wire shift queries run but clock slew exceeds library limits, so raw positive slacks are not acceptance. ATPG/physical fault replay and buffering/CTS/fit deferred; T37 remains incomplete. No aggregate CI.
- 2026-11-26 Codex: T37 fresh unplaced insertion accounts for20,380 scanned and12 excluded access FFs. Actual seven-chain connectivity, normal-mode graph equivalence, raw-POR protection, test clock/reset/macro isolation and64-vector serial load/unload pass with D/reset/chain/TE/SI faults rejected. Measured standard-cell area3.9390734656mm2; estimated planning total11.2177778062mm2, not physical fit. Independently reviewed structural/serial checkpoint; capture/ATPG/STA remain open. No aggregate CI.
- 2026-11-26 Codex: T37 logical access/pad wiring is integrated in the single production top; raw POR initializes the unscanned controller even without an external reset pulse. Focused entry/exit and normal POR boot tests pass, with pad safety/transparency proof and full original-child/top-wiring composition. Fresh mapping preserves seven hook cells. Area change is explicitly a mapper/load-alias effect, not isolated savings. Physical scan qualification remains open, no aggregate CI.
- 2026-11-26 Codex: T37 reviewed seven-lane shared-pad contract and standalone access controller pass focused tests, unbounded sampled-output proof, covers and actual key-fault controls. OpenROAD replacement pilot accounts for every existing FF, including negative-edge TAP state, with locked Liberty state-equation and complete signal/supply/boundary checks; real ODB D/reset mutations rejected. Corrected inverter well connections after review. Production integration/scan coverage/timing remain open; no aggregate CI.
- 2026-11-26 Codex: User requests broader scan/ATPG research and conditionally approves the original tool choice if no better approach emerges. Independent review supports OpenROAD plus separately pinned Quaigh. Small extracted-cone pilot detects20/20 enumerated gate-pin faults with4patterns and independent Liberty replay; this is not production scan coverage. Estimated ordinary scan-FF replacement0.402604mm2 excludes control/routing. Full T37 contract/insertion/protocol/equivalence remain open, no aggregate CI.
- 2026-11-26 Codex: T37 preflight reaches its explicit unavailable-ATPG stop. Both active pinned environments and the older physical image lack a generator; ABC fault-class analysis is not pattern generation. Proposed separately locked Quaigh with existing OpenROAD and independent simulator replay. Implementation/coverage remain open; no RTL, tool-lock or limit changes.
- 2026-11-26 Codex: Start T37 on main under the user's minimal relevant-test/proof policy, no aggregate CI. Check pinned scan/ATPG capability and review test-access contracts before RTL; no manufacturing coverage or signoff claim from T38's basic fit.
- 2026-11-26 Codex: D112 follow-up narrows T38 to basic layout/fit, deferring routing/DRC and production GDS. Placement and CTS completed; measured logic/buffer area 5.113576 mm2, SRAM 2.874559 mm2, analog 0.214969 mm2 and taps 0.301862 mm2 inside the measured 12.901981 mm2 core. Zero placement violations; original graph/library and both-mode clock/USB-pair checks pass. Layout image and receipts under build/t38/fit03; full T38 remains open, no aggregate CI.
- 2026-11-26 Codex: D112 starts T38 on main before T37 for pre-scan physical measurements. Reuse T43 actual macro/pad views and the authenticated production mapped graph; replace template-only clocks with production constraints. Focused graph/constraint checks only, no aggregate CI; scan, broad verification and complete signoff remain open.

- 2026-11-25 Codex: Completed T43 scoped acceptance under D111. Compact actual LF/POR generators, selected DRC/LVS, complete20SRAM+2analog fit, connectedVDD/VSS PDN and semantic power-overlap negatives pass; fresh four-case pad ROM boot/reset passes. Independent review verifies source/artifact binding and approves publication/merge. Estimated T35 headroom1.6044838321mm2 after measured analog footprints. Full RC/POR composition/PVT/trim and T38 signoff remain explicit debt; no aggregate CI or global placement.

- 2026-11-25 Codex: D111 user authorizes compact LF/POR physical implementation to finish T43, followed by reviewed merge to main. Resume T43 under the existing scoped-test policy; document the implementation extension before circuit/layout changes. No analog contract, area limit or qualification check is waived.
- 2026-11-25 Codex: T43 D111 digital LF readiness and POR qualification/cause components pass focused tests and scoped unbounded proofs with independent review. Corrected flat-C LF prototype measures32.328823kHz/787.344nA nominal; selected geometry DRC and unique LVS pass. RC extraction audit is unresolved; complete POR layout and Deadhorse floorplan/PDN remain open. No aggregate CI or merge to main.
- 2026-11-25 Codex: T43 upstream template flow completes through authenticated Linux-storage checkpoint resume (measured116.327022s; original interrupted bind-mounted run4719.256590s retained). DRC/LVS/antenna pass; nine slew, six fanout and106capacitance warnings remain disclosed. KLU startup diagnostic completes at measured92.778649kHz/902.012654nA for one nominal ramp, outside32kHz target and not production qualification. Logical/pad/PDK work is pushed; T43 remains blocked on actual LF/POR physical views and complete Deadhorse pre-placement fit. No aggregate CI.
- 2026-11-25 Codex: Continued T43 reuse work with authenticated current-PDK schematic diagnostics. Retuned RISCay topology measures32.251574kHz/287.807717nA nominal with external reset assistance; independent review reproduces the waveform frequency. Separate startup diagnostic is inconclusive after120s, not rerun unchanged. Added pinned reproducible diagnostic helpers and wrong-tool rejection. Production analog interfaces/RTL unchanged; no PVT/layout qualification or aggregate CI. Template baseline continues through physical checks.
- 2026-11-25 Codex: T43 D110 logical socket, exhaustive scalar pad proof/three faults, original and compatibility foundry-model tests, fresh production elaboration and real-ROM pad UART cold-boot/restart checks pass. Independent review approves limited logical checkpoint. Actual sixteen1024x8/four512x8 SRAM configuration prepared with geometric faults. RISCay upstream HEAD remains pinned4671317; schematic reuse does not supply compatible LF/POR layouts. Full template baseline remains running; no aggregate CI or complete physical-fit claim.
- 2026-11-25 Codex: User approved reviewed driven-pad readback proposal as D110. Resume T43 chip binding and scoped checks; no aggregate CI, no peripheral core-port test changes.
- 2026-11-25 Codex: T43 D109 approves fd_io and current16x1024x8+4x512x8 inventory. Versioned PDK migration reproduces old SoC/USB/DMA/timer/SRAM timing and area; estimated headroom remains1.5694526345mm2. Independent review approves limited provenance/measurement checkpoint. Logical pad map checked; await explicit raw-input-versus-local-drive readback decision. Chip-top physical/boot checks and historical T13 gate requalification remain; no aggregate CI.
- 2026-11-25 Codex: T43 checkpoint authenticates39 template files and candidate PDK; comparison measures15 corners with229 unchanged cells each, byte-identical LEF and24 matching SRAM views. Independent review's fail-closed/provenance refinements incorporated. Pending explicit pad-library/current-SRAM-inventory choices; active PDK unchanged, no aggregate CI or physical qualification.
- 2026-11-25 Codex: Started T43 on its own branch after T42. Rechecked upstream main d99f6e1ba14e549e80d5d83e113fbd82ed37ed5c and template PDK792ef67037d74c8c51811eab3ce23cf793491296; prepare authenticated collateral/library comparison and independently reviewed pad/SRAM recommendations. No aggregate CI; active PDK unchanged pending qualification.

- 2026-11-25 Codex: T42/D108 independently verified for publication by t36_contract_review (read-only; inspected final code, proofs, reset/ownership tests, trace controls, area/timing, source/receipt hashes and report). Frozen strict maximum load passes without D104; full readback and original window retained. Local grant removes8 measured flops, isolated area reduces720.0256um2. Scoped checks pass; inherited bridge/T41 composition and physical hold/reset debt remain, no aggregate CI. T42 complete and D104 exception closed.

- 2026-11-25 Codex: User approved the reviewed T42 local-grant proposal (D108). Implement only production toAon admission; retain cancellation, owner checks and full readback. Scoped tests/proofs and area/timing, no aggregate CI.

- 2026-11-25 Codex: Merged reviewed T40 into mainf680c3f and began T42 under scoped/no-CI policy. Completed passive production profiling and a concrete local-permit proposal; maximum-image target remains unmet under D104. Stop at T42's explicit hardware-approval boundary; production RTL/firmware unchanged.

- 2026-11-25 Codex: T40 scoped implementation independently verified on codex/t40-dma-circular-rx:19 DMA/SoC tests, driver/maps, four simulation fault controls, setup/electrical and area cap pass. Measured DMA delta0.0034618304mm2; estimated chip headroom1.5781216789mm2. Formal closure deferred after one capped triage round; report/ledger preserve shallow bounds and fault limitations. No aggregate CI.
- 2026-11-25 Codex: Merged reviewed T41 into main10a142c and started T40 on codex/t40-dma-circular-rx. Fresh baseline DMA synthesis precedes RTL; review shadow-lock/abort/reload/cursor contracts. D102 scoped tests and capped proofs only, no aggregate CI.

- 2026-11-25 Codex: T41 scoped completion independently accepted. Frozen test-manifest reconciliation, warm-wire qualification, local proofs and counter equivalence, setup/area screens and corrected publication checks pass. Four reset cohorts retain D106/D107 cancellation exceptions; release instances measured 89→30. Named proof and physical obligations remain visible in the receipt; no aggregate CI and no merge to main.

- 2026-11-25 Codex: T41 draft shared releases, first-release history regression, acknowledged lite initialization and warm two-image ROM checks added. Boot-control local proofs and focused tests pass; broad lite observable equivalence deferred after120s cap. Independent review phase-hole and debug-reset observation findings addressed; wider oscillator/BIST/production boot acceptance remains pending. No aggregate CI.

- 2026-11-25: T41 shared cancellation implemented and independently reviewed: scoped19 tests pass, DMI8 assertions unbounded, unchanged USB wrappers equivalent. Interim measured release instances89→80 and controls150→133; not mapped area or final task acceptance. Cold/warm distribution, owners and warm ROM remain; no aggregate CI.

- 2026-11-25: Recorded D107 approval for bridge timeout quarantine and existing selective BIST pin-abort handling. Resume T41 shared cancellation/reset implementation under D103/D106/D107; no further exception inferred.

- 2026-11-25: Completed remaining-source audit: bridge timeout also needs immediate quarantine; synchronized-abort negative is caught by a public-port phase sweep. Proposed a combined bridge exception and explicit preservation of BIST pin-abort capture; D106 remains DMI-only. T41 blocked pending this decision; no new cohort or weakened cancellation implemented.

- 2026-11-25: Recorded D106 user approval for the DMI-only asynchronous cancellation exception. Resume T41; audit other source families before replacing protocol resets. No broader exception or implementation acceptance inferred.

- 2026-11-25: T41 cancellation diagnostic passes2 tests: current transport cancels a queued request with main stopped; synchronized-clear fault is rejected. Independent review identifies a required DMI-only asynchronous quarantine exception to cold-only debug transport; no approval recorded, no assertion weakened. T41 blocked pending decision.

- 2026-11-25: Resumed T41 from reviewed inventory74bea3c. Checking exact DMI hard-clear cancellation before replacing reset-driven transport epochs; scoped port tests and independent review, no aggregate CI.

- 2026-11-24: T41 inventory independently reviewed before RTL: measured89 releases/178 release bits,150 normalized reset controls and15,071 unique reset-controlled bits. Fresh production emission unchanged from PLAN05; scoped structural checks and counting fixtures pass. Inventory-only commit; four-cohort RTL/boot/behavioral/area acceptance remains open; no aggregate CI.

- 2026-11-24: Started T41 inventory on its own implementation branch after rebasing planning onto maina5ae6f4 (T43/D105 planning only). Production RTL remains PLAN05. Enumerate all nested release trees and retention predicates before changes; no aggregate CI or long proof sweep.

- 2026-11-24: Added D105/T43 on a separate planning branch and made T38 depend on it. Replaced physical-source instructions with the official wafer.space template; no PDK or RTL changed. Current order remains T41, T40, T42; T43 is required before T38. PLAN05 macro inventory differs from the requested twenty1024x8 and must be reconciled before implementation.

- 2026-11-24: Rebased the separate T41 planning records onto completed PLAN05 main6572ecf. Preserved D104/T42, both phase-end fast receipts and all verification debt. No inventory or reset RTL work started.

- 2026-11-24: PLAN05/T36 scoped completion under D104. Frozen Phase3 fast01 passes all 33 commands in measured 3869.903314s; 12 inherited proof deferrals remain. Exact ROM boot/native/wire checks, main timing and ROM-inclusive area pass; maximum-image load remains an explicit 296.923125ms exception against250ms, queued in T42. Full tier and physical signoff unrun. T40/T41/T42 remain queued; T41 planning stays on its own branch.

- 2026-11-24: Final PLAN05/T36 scoped boot04 passes with D104; UART FIFO service defect fixed without test/timeout changes, all update/power-cut controls retained. Final ROM mapping and USB boundary08 audits pass. Freeze sources for Phase3 fast; full tier unrun. T41 planning published separately; T42 boot-latency follow-up queued.

- 2026-11-24: User accepts the maximum lite-image boot-load latency for now after the focused firmware attempt (diagnostic296.909ms at nominal model clock). D104/T42 retain the original250ms target as explicit debt. Resume remaining PLAN05 Phase3 checks; no bridge architecture change or other acceptance waiver. T41/D103 reset consolidation is separately queued, not started.

- 2026-11-24: PLAN05 Phase3/T36 stops at explicit250ms lite-load bound. Corrected machine-counter ROM passes16 wire cases; measured588-byte watcher interval16,497,924 model quanta (estimated171.853375ms at assumed96MHz), but supported1024-byte image exceeds250ms. Independent review confirms failure and unchanged limit. Metadata5 tests/7 proof jobs pass; remaining wire cases and Phase3 fast unrun. No Phase3 commit; request one focused optimization attempt preserving clock, verification and bound.

- 2026-11-24: Started PLAN05 Phase3/T36 on main5ba87bf after accepted Phase2 and merged T40 planning. Promoted reviewed ROM/reset-context drafts; only relevant boot tests and capped proofs during iterations. No Phase3 execution or acceptance yet.

- 2026-11-24: Queued D103/T41 on a separate planning branch based on PLAN05 Phase2 main5ba87bf. Rebase onto completed PLAN05 Phase3 before execution; no reset RTL, measured inventory or implementation acceptance yet. Explicit amendments preserve USB/analog boundaries and dormant watchdog freeze.

- 2026-11-24: Published reviewed PLAN05 Phase2 implementation through f96ad0d on main after frozen fast02. Merged the separate D102/T40 planning records; circular DMA remains scheduled, not implemented. Reserved its approved area cap against the current Phase2 estimate without crediting unaccepted ROM savings.

- 2026-11-24: PLAN05 frozen Phase2 fast02 passes all33 commands in measured3807.603677s after USB evidence/physical-boundary requalification. Independent review passes;12 inherited fast-tier proof deferrals and separate PLAN05 proof/physical debt remain explicit. Continue Phase3 boot ROM with relevant-only iterations and required phase-end fast; full CI not run.

- 2026-11-24: Resumed PLAN05 Phase2 after publishing the separate T40 planning branch (66afedc). Loader/toMain removal and performance-owned lite hold/release migration in progress. Relevant tests and short proof attempts only during iterations; required phase-end fast checks remain. No implementation acceptance yet.

- 2026-11-24: PLAN05 Phase1 complete after independent review: final opt05 includes required pad mux startup, retains all cases/faults and measures 604-byte footprint (estimated 755 with margin). Revised map has 21 regions and estimated 40/12 physical-pad demand; map and 14 focused Python tests pass. No production Scala RTL changed; new descriptors await Phase2 migration. Fast/full CI unrun, no commit/push.

- 2026-11-24: Approved watcher optimization passes opt04 with all original cases and fault controls. Measured worst2996cycles to WFI/2764to mailbox; estimated93.625/86.375ms at nominal32kHz. Measured592byte footprint selects2KiB under D96. Independent review passes; production peripherals/oscillator remain unqualified. Continue Phase1 contracts with relevant-only checks; phase-end fast CI remains required.

- 2026-11-24: User approved the focused PLAN05 firmware-only optimization. Resumed B3 while preserving the same packet, nominal clock, deadline and tests. Investigating CRC instruction cost; previous routed02 failure remains historical evidence.

- 2026-11-24: PLAN05 Phase1 watcher routed02 hits the explicit latency stop: measured 3581 cycles to mailbox, estimated 111.90625 ms at nominal 32 kHz even with optimistic target timing. Independent review validates source/artifact seals and fault detection. Proposed 2 KiB memory fits measured footprint, but production remains unchanged. Await focused firmware-optimization approval; remaining contracts, implementation and phase-end CI are open.

- 2026-11-24: Resumed PLAN05 on main with the complete C1-C9 contract. Recorded D92-D101, replacing the truncated draft and prior lite-first boot proposal. Phase1 review and watcher measurement precede RTL; fast CI is mandatory at both implementation phase ends.

- 2026-11-24: Added D102/T40 on an isolated planning branch, scheduled after PLAN05 design changes. Reserved the maximum mapped-cell increment in the T35 baseline budget; no DMA implementation, RTL test, proof, timing run or CI. Concurrent PLAN05 files remain untouched. Planning checks/review recorded in the receipt.

- 2026-11-24: T36 preflight identified the brief's explicit contract stop: loader-only lite start, no lite ROM/program-write authority and firmware/native-origin UART versus gateway-origin semantics. Prepared independently reviewed boot/recovery proposal; documentation/map checks pass. Await user decision before RTL/firmware; no CI or implementation acceptance.

- 2026-11-24: Assigned T36 on main with D91 scoped tests/proof deferrals and no CI. Reviewing cold-reset instruction source, ROM/start selection, memory ownership and frozen-loader recovery before implementation; existing stop conditions retained.

- 2026-11-24: T35 scoped implementation complete under D90: production SRAM macros and reset-held JTAG BIST; 43 relevant Scala cases, four TAP scenarios and production flight checks pass. Five-corner mapped timing fits unchanged class budgets with the inherited USB warning; estimated chip headroom 0.220200760 mm2. Data/latency and multiclock ownership proofs remain deferred/unproved; physical signoff remains open. No fast/full CI or unrelated suites run. See [report](tasks/reports/T35.md).
- 2026-11-24: User assigned T35 with D90 scoped verification: relevant SRAM/BIST/integration checks only, no aggregate CI, extensive timeout proofs deferred. Began pinned macro-view and independent contract review on main; existing memory maps, limits and physical stop conditions retained.
- 2026-11-24: T39 completes D89's finite campaign at code `fa21f70`: measured 29 focused Scala cases, 51 pinned RV32UI/UM/UC plus six project FP cases, fixed/hard-float production flight before/after wake and nine positive OpenOCD scenarios plus missing-halt fault pass. Complete fast03 passes 34 commands in measured 4766.942 s, with twelve inherited unproved T14/T17 deferrals. Commands, partial attempts and limitations in [report](tasks/reports/T39.md). Independent review and post-run documentation/code-identity checks pass; no RTL/test/tool/firmware changes. Full tier not run; broad ISA/ISS qualification, inherited debt and stage/physical acceptance remain open.
- 2026-11-24: D89 narrows T39 to existing core/lite/SoC, flight/wake, debug and complete fast-tier regressions. New external ISS/framework, broad seeded coverage and state observers are explicitly deferred. Frozen-code execution passes; final documentation review in progress. No RTL/test/limit changes or stage/proof closure.
- 2026-11-24: User assigned T39 execution. Began baseline fast CI on main; stopped the partial pre-fast01 run after independent review identified its stale pre-T33 USB production binding. Refreshing that binding against the current measured production top before restarting. No campaign pass, proof closure or CI waiver claimed.
- 2026-11-24: D88 assigns preparation/publication of T39. Added the complete core/SoC verification brief and placed it before T38 acceptance, with affected replay after T35/T36/T37. Documentation structure/link and diff checks plus independent review pass; [planning receipt](tasks/reports/T39-planning.md). Documentation work only; no campaign, RTL change, CI-policy extension, new proof result or gate closure.

- 2026-11-24: T34 scoped acceptance `build/t34/models02` passes with D87 exceptions: 12 model and four selected production tests, three reset proof jobs/six faults/two covers, nine pin-binding faults and five receipt checks. Measured aggregate 273.803 s (command in report); all 212 production emitted files match T33. Independent contract, implementation and final evidence review approved; audit `build/t34/independent-review.json`. No aggregate CI, unrelated IP tests or analog signoff.

- 2026-11-24: Started T34 under user decision D87. Reuse existing LF/POR models and production bindings; relevant checks only, no aggregate CI, extensive timeout proofs deferred. No analog layout or new trim storage.

- 2026-11-24 — Codex: T33 completed with D86 exceptions after independently verified focused acceptance: 52 fresh cases plus 30 authenticated completed cases from an interrupted run. One inherited unrelated I/O test ran before the selection mistake was detected; that case is not credited and closeout01 remains failed. Corrected explicit selection, preserved firmware/source hashes and five evidence-fault checks pass. Final docs record proof and physical debt; no CI tier or stage gate claimed. Publication on main follows standing authorization and review.
- 2026-11-24 — Codex: user approved D86 to finish T33 with explicit difficult-proof deferrals and no full CI or unrelated IP tests. Resumed focused closeout; pending helper-attempt requests superseded by deferral. No assertions, assumptions, timing budgets or proof statuses changed. Physical qualification and stage gates stay open.
- 2026-11-24 — Codex: T33 structural checkpoint independently reviewed. Exact frontend replay authenticates source hierarchy; every mapped crossing row retains complete endpoint identity/reset-cohort status, including unresolved aliases and non-FF storage. Fresh unchanged shared CDC jobs pass with artifact sealing and an identical-child ResetRelease premise; no exhausted controller job rerun. Missing reset STA paths trace to untimed raw input origins, not passing slack. Focused structural tests, map and structure checks pass; final aggregate/fast/full remain unrun. T33 blocked on composition/qualification and pending helper scopes; no commit/push.
- 2026-11-24 — Codex: independent review identified further authorized structural work separate from the exhausted proof attempts: reconcile crossing groups to actual primitive/reset boundaries and classify the missing STA reset endpoints. Continuing this work without new solver attempts or qualification waivers.
- 2026-11-24 — Codex: T33 finite production reset-phase coverage completed in scoped runs: lite/performance transaction phases, actual watchdog committed-return and offered-before-dispatch cases, and intended negative controls. Repaired a performance trace-monitor classification error without changing RTL or bounds; independently reviewed receipts/archives. T33 remains blocked on composition proofs/qualification; pending helper requests were not exceeded. Final aggregate/fast/full unrun; no commit/push.
- 2026-11-23: T33 assigned on main. Read-first and independent contract review identified internal whole-reset clock-policy/qualification mismatch and an AON-service adapter flush gap. User approved D85 live threshold-switching guarantee; no analog qualification or solver/acceptance waiver. Production sources stayed frozen through the prerequisite. pre-fast01 failed on a solver timestamp; pre-fast02 rejected a stale production USB evidence binding. The reviewed logging repair, refreshed USB binding and pre-fast03 pass precede staged implementation; final T33 acceptance remains open.

- 2026-11-23: PLAN04 dedicated ResetCauses verification passes independent review: two unbounded proofs, six intended faults and seven covers, including a pin pulse wholly between AON rising edges. Measured command/times and assumptions in report and oscillator ledger. These new verification files postdate fast02; production RTL is unchanged, final frozen qualification refresh remains required. Minimum-count and shutdown helper attempts remain awaiting scoped approval; no further attempt made. Full tier unrun; no commit/push.

- 2026-11-23: PLAN04 command/completion FIFO shutdown repair and production UART deep-wake test pass the focused suite (28 tests; measured command/time in report). Subsequent production timer/mailbox, GPIO, JTAG DMI and USB light-sleep resume tests pass; paired fixed-point and hard-float flight-loop retention measurements pass with identical before/after cycle windows, independently reviewed. Complete SoC/oscillator acceptance passed 114 tests in measured 2887 s sbt time. Mapping12 data-path screens pass in both AON modes; estimated total area 12.610083284 mm2 and headroom 0.309916716 mm2. Shutdown triage budget exhausted: fresh qualification and OSC_EN on main edges proved under startup abstraction; gate-low and retained-hold claims unresolved, as is minimum full-width count. Scoped helper approvals pending. USB boundary refresh passes with independent review. Frozen fast02 passed all 34 checks with 12 existing deferrals in measured 3886.079379 s. Fast01 remains failed partial evidence after a register-checker clock-backstep/parser error; the unchanged checker retry and full second run passed. Full tier not run. Blocked on formal closure/scoped helper approvals; no commit or push.

- 2026-11-23: PLAN04 shared-FIFO count handoff and actual main-edge freshness have intermediate proof evidence with faults/covers; minimum full-width stable count remains unresolved after PDR and one alternate-engine portfolio. Ledger records step-0 data and pending bounded helper-invariant work approval. All six repaired DMA tests and five watchdog tests pass without changing assertions or limits. Production sleep test reaches release but fails firmware sleep; read-only retirement diagnostics investigate ROM initialization. Mapping11 refresh started after the FIFO change; earlier mapping10 is historical. No frozen CI, commit or push.

- 2026-11-23: PLAN04 production mapping10 and both generated-clock/AON-mode screens reviewed independently: strict OSC_IN counter and main data-path budgets pass; USB retains its existing warning. New mapped digital logic and allowance arithmetic recorded in plan08/report. Raw clock-pulse violations trace to unbuffered clock loads outside library tables and remain unqualified physical-flow items. Broad focused simulation found missing DMA fixture inputs and a watchdog stimulus exceeding the existing native-bus timeout; reviewed repairs preserve assertions and limits, reruns pending. Full composition, production wake/retention and frozen CI remain open; no commit/push.

- 2026-11-23: User approved D84 after independent reset review: static POR_BYPASS fixed while powered directly selects reset; AON_CLK_SEL stays reset-latched. The previous latched bypass had circular initialization; its arbitrary-initial-state formal diagnostic returned a topological-loop ERROR, not a counterexample or proof. Replacing that reset selection and rechecking; no acceptance claimed.
- 2026-11-23: User approved D83: external pin reset is cold only in POR_BYPASS mode, initializing loader lock/watchdog/debug cold state without trusted POR. Normal-mode warm pin reset and watchdog containment remain unchanged. Resumed PLAN04 implementation and verification on main; no further approval required for this reset choice.

- 2026-11-23: PLAN04 controller, phase-safe divider, reset-held strap bootstrap and digital POR model have focused simulation evidence; policy-only formal passes on exact policy02 source hashes. Independent review found a cold-reset initialization conflict in POR_BYPASS: without trusted POR, first pin reset cannot be distinguished from later warm resets. Asked to make external pin reset cold only in bypass, preserving normal-mode warm reset and watchdog containment. Production hookup paused; no commit/push or task acceptance. Fresh fast/full and physical checks remain unrun.

- 2026-11-23: Resumed PLAN04 on main following approval of both recommendations: D81 keeps the oscillator on while USB is enabled; D82 preserves the loader and qualifies recovery SCL against minimum AON frequency / 8. Fresh T32 fast-tier receipt satisfies the prerequisite; PLAN04 changes still require their own frozen acceptance and independent review.

- 2026-11-23: T32 timing follow-up completes its active scope: frozen timing-fast01 passes all 34 active commands in measured 3850.781049 s, including the formerly failing faithful-core timing at 65.141479 ns under unchanged 66.666667 ns. Twelve inherited T14/T17 deferrals remain unproved; D80 separately defers the SBA epoch read-data proof. No RTL change in the timing follow-up. Full tier unrun; physical reset/clock-tree/CTS debt remains. Final reporting metadata and publication review follow the frozen run.

- 2026-11-23: T32 D80 third timing candidate and maintained-flow reproduction pass at measured 65.141479 ns; two local mapping trials regressed and were rejected. Exact mapped graph reproduction and all-state equivalence pass with a wrong-D control, independently reviewed. Main-9mhz mapping uses a 50000 ps optimization goal and core-only premapped JSON reload; acceptance stays 66.666667 ns. Hold minimum is measured +0.530017 ns; raw reset removal -0.975158 ns remains. Freeze and fast CI next; SBA proof remains deferred and unproved.

- 2026-11-23: User deferred the remaining T32 epoch read-data proof and authorized up to three adaptive timing-improvement loops. A better but still failing candidate may seed the next loop; unchanged timing budgets, functional/electrical checks and independent review remain required. PLAN04 USB/recovery choices remain pending. No proof rerun or waiver.

- 2026-11-22: PLAN04 assigned on main; read-first and independent production-contract audit completed before RTL. Recorded approved C1/C2 as D78/D79, amended D6/D35/D38 and resolved Q15. Stopped at the explicit USB stopped-oscillator wake conflict; recovery-loader service rate also needs a contract decision. Architecture reconciliation, implementation and all acceptance checks remain open; no commit/push. See PLAN04 report for exact source references, estimates and pre-existing T32 fast-CI failure.

- 2026-11-22: T32 non-proof timing diagnosis stops after the general data-buffer repair also fails (measured 72.056808 ns against estimated 66.666667 ns). Independent review confirms preserved functions/ports/clock-reset pins and unchanged constraints, but worse timing and added area; both candidates remain rejected diagnostics. No RTL/maintained timing-flow change or weakened acceptance. Final handoff retains epoch-data and faithful-core timing blockers, partial fast failure, full tier unrun and no commit/push.

- 2026-11-22: T32 checkpoint has two blockers: SBA epoch read-data and faithful-core 9 MHz timing. Frozen final-fast03 passes 31 commands then fails timing in measured 3788.395428 s; two remaining commands pass separately, not as CI. Reviewed verifier-only USB evidence derivation passes all collectors; four T14/eight T17 deferrals remain unproved. One identity-buffer-tree diagnostic preserves function but still exceeds the unchanged budget; continue non-proof diagnosis with a general data-buffer repair, retaining all functions/loads/limits. No candidate accepted or production RTL change. Full tier unrun; no commit/push.

- 2026-11-22: T32 final-fast01 fails after measured 1528.338531 s on I2C retained-lock identity following OpenOCD additions; simulations, timing, model and solver-flow identity pass. Exact old/new lock compatibility repair passes 15 verifier tests and focused formal refresh with the same eight unproved deferrals, independently audited. No RTL/check weakening or unchanged timeout rerun. Refreeze for full fast rerun; SBA epoch-data remains open, no commit/push.

- 2026-11-22: T32 focused extension closes production-bound first-entry/loader safety, covers and actual faults (ownership06), and maintains the qualified vendor-equivalence command. Actual FIFO sequence helpers prove with checked component binding; returned-data composition remains unresolved under unchanged caps. Stop the focused attempt without accepting candidate stage invariants; freeze for final fast CI. No production RTL changed in this round and no commit/push.

- 2026-11-22: User directed finishing JTAG after the remaining-task list; resume T32 and the proposed focused 45-minute proof-composition attempt, retaining 120-second jobs and all original assertions/assumptions. No gate is closed by this instruction. Finish independent proof/publication review and final frozen fast CI before commit/push.

- 2026-11-22: T32 current-model bindings and hardened transport proof pass independent review. Maintained fresh area/timing replay reproduces area07 exactly; raw physical negatives remain T33/T38 obligations. Refreshed USB sampling/model binding, full-size simulation and current bus topology pass; new hold/two-way STA and strict physical collector pass without altered limits. Historical placement/internal timing is labelled reused. Pause further epoch data work at the exhausted triage budget pending the separate extension reply; other formal/publication obligations and final fast/full status remain explicit. No T32 commit or push.

- 2026-11-22: T32 expanded assertion-enabled debug03 passes nine production OpenOCD scenarios and the missing-halt fault in measured 665.169853 s. All 42 targeted core/debug regressions and two full-DM reset tests pass. Independent review accepts command ownership/reset proofs and edge-aware TAP extraction equivalence; original/replacement CDC equivalence is not claimed. Reviewed USB register-class screening passes with the existing FF warning; raw physical boundary/tree issues remain. Epoch read-data proof remains unresolved, final CI unrun, no T32 commit/push.

- 2026-11-22: T32 reset composition found and fixed lost drain credit when BusFabric's registered grant survives withdrawal of req. Fifteen control assertions prove; all eight covers and three faults qualify, but end-to-end read data remains unresolved after three triage rungs. Fresh assertion-enabled OpenOCD debug02 qualifies seven scenarios and the missing-halt fault; focused loader ownership and stopped-AON SBA reset probes pass. Reviewed fresh area07 estimates 12.855509285 mm2 total with all allowances unchanged. Raw pulse/removal and USB timing qualification remain open; final fast/full CI unrun and no T32 commit/push.

- 2026-11-22: T32 broad area review resolves the area-only stop without changing features or allowances: physical observer projection plus layer-balanced reset mapping gives measured 3.487281549 mm2 cells and estimated 12.867882231 mm2 total, 0.052117769 below ceiling. Independent exact graph/port/pin audits, fanout/depth checks and full reset/register endpoint comparison pass; no new matched-screen violations. Existing raw removal/core-clock pulse/USB qualification debt remains. Resume original JTAG validation; final CI and publication still pending.

- 2026-11-22: User approved broader SoC area review to identify larger savings and replace remaining allowances with measurements, preserving all features/limits. Review production observation cones and pinned memory/ROM evidence; no unrelated task implementation or allowance reduction without evidence.

- 2026-11-22: Approved T32 area experiment removes the redundant SBA routing capture/reply stage while preserving downstream fabrics and quarantine. Measured mapped logic falls from 3.726062234 to 3.708726739 mm2; estimated total falls by 0.035254912 to 13.302659552 mm2, still over budget by 0.382659552. Scoped proofs including post-grant route fault, four unit tests and fresh OpenOCD basic/reset scenarios pass; same-domain register timing screen remains within main/AON/TCK budgets. No whole-SoC reset, final timing or CI acceptance; no commit/push. Focused investigation complete, broader area decision remains.

- 2026-11-22: User approved a focused T32 area-reduction investigation of debug routing and duplicated payload storage. Resume that scope only; both harts, SBA, shared CDC/reset guarantees, acceptance checks and the 12.92 mm2 ceiling remain unchanged. Prior area-stop evidence is retained.

- 2026-11-22: T32 stopped on its explicit area condition: measured production logic 3.726062234 mm2 gives estimated core use 13.337914464 mm2 after replacing the JTAG allowance, with all other allowances/utilization unchanged. Initial production-TAP OpenOCD scenarios and scoped formal checks pass on intermediate snapshots; the latest reset fixes and system composition still require validation. Final fast/full tiers unrun; implementation remains uncommitted. See T32 report for commands, evidence and remaining RTL tasks.

- 2026-11-22: T32 assigned: adopt pinned PULP debug for both harts, actual OpenOCD pin-level acceptance and shared CDC. Independent review binds the just-completed fast03 baseline to main 9b80375 (only reviewed PLAN03/STATUS result metadata differs); the redundant baseline-fast rerun was interrupted, never counted as a pass. Audit contracts before RTL, retain ordinary boot/loader ownership, and report remaining RTL tasks on completion.

- 2026-11-22: PLAN03 complete within its assigned scope. Final frozen fast03 at 58833fd plus hashed B5/B6 changes passes all 34 commands in measured 3628.413506 seconds; four T14 and eight T17 deferrals remain unproved. Independent audit matches all 1485 CI source hashes, 14 child receipts and 1561 USB source/input entries. Exact command, evidence and limits are in the report. Result-only reporting changes follow the freeze; no new RTL. Full tier unrun; no integration-stage or tape-out gate closed. T32/T33 are next separately assigned briefs.

- 2026-11-22: PLAN03 B5 completes one focused triage attempt per task: DMA range remains unresolved; ADDI leaves only destination data unresolved (eight meaningful proofs, five trivial memory claims); watchdog proves five of twelve, seven unresolved. Exact assumptions, caps, fault scope and step-0 data remain in the debt report. B6 publishes the one-top/stage reconciliation and unimplemented T32-T38 briefs; no new RTL. Final review and frozen fast tier precede publication.

- 2026-11-22: PLAN03 B4 independent review verified all 3,613 sealed source/evidence files and 23 tracked executed-producer snapshots. Mapped/digital measurement checkpoint accepted; complete T20 system proofs and chip physical qualification are not implied. Proceed to the authorized B5 attempts and B6 briefs.

- 2026-11-22: PLAN03 B4 approved mapping follow-up resolves both-frequency USB register failures without RTL/limit changes. Main measured 64.830223/65.965767 ns at 8/9 MHz; USB has only the existing 13.485458 ns FF warning. Production loops measure fixed 3879.791667 mean/4350 worst and hard-float 7809.833333/9007 cycles, both trials. Exact target-ISS floating results resolve an uncontracted host-oracle mismatch. Plan08 estimated budget is 12.783522307 mm2 including scan/BIST and named allowances; headroom 0.136477693 mm2. Independent numerical review passes; transitive seal and report updates remain before B5. Physical boundary/CTS/macro qualification and full CI remain open.

- 2026-11-22: User approved carrying the existing USB synthesis measures into full-SoC mapping and remeasuring. Resume PLAN03 B4 on main with production RTL, behavior and acceptance limits unchanged. Preserve the failed screen; freshly bind mapped certificates and independently review the integrated result before acceptance.

- 2026-11-22: PLAN03 B4 stopped at the user's both-frequency timing rule. Fresh complete production mapping, source/context and mapped USB certificates, and applied-pair audits identify four failing USB classes at main 8 MHz and five at main 9 MHz. Main RR meets 75 ns at 8 MHz (measured 70.504395 ns), misses 66.666667 ns at 9 MHz (70.190018 ns). Independent review verifies the failures and final 2238-file evidence seal. Propose carrying the existing standalone USB mapping measures into integrated synthesis; no RTL change shown necessary. Remaining B4 measurements, B5/B6 and full CI are open. Earlier completed work was pushed to main at e18e2e8 after the fast pass.

- 2026-11-22: PLAN03 B3 frozen USB acceptance and fast CI passed, independently verified against exact source/evidence hashes. Measured fast wall time 3637.986439 seconds, 34 commands; the four T14 and eight T17 deferrals remain explicitly unproved. USB's 29 tests, twelve-claim packet audit, sampling and D77 physical qualification pass within their recorded scopes. Full tier unrun. Continue with B4 production measurements; no new peripheral work. Exact commands and scope are in the PLAN03 report.

- 2026-11-22: PLAN03 D77 boundary measurements independently reviewed: all fifteen routed bus-source/USB cases pass both directions (measured request/response delay 13.207504/13.396587 ns against 24.96 ns, worst hold +0.846525/+0.804226 ns). Exact sampler/release qualification and two physical VBUS data hold buffers close the identified digital boundary issues in their stated scopes. Whole-chip/analog signoff remains open; evidence integration and fresh USB/fast runs are next, not yet passed. Commands and limitations are in the USB physical report.

- 2026-11-22: User approved the specific asynchronous-boundary contract as D77. Resume PLAN03 B3 with exact sampler/reset-release pin qualification, raw STA diagnostics retained, ordinary bus/internal checks unchanged and physical waveform/metastability evidence left explicit. Approval does not close a check; independent review and USB/fast reruns remain required.

- 2026-11-22: Approved B3 follow-up independently qualifies eleven sampling assertions, wrapper-context binding and actual exception/delay faults in every populated class. Fresh full-size simulation and read-only audit qualify all twelve packet claims. Routed candidate's three class-delay failures are resolved across fifteen PVT/RC cases, but raw asynchronous boundary hold/removal still fails. No production RTL or limit changed. Stop for the specific boundary acceptance proposal; aggregate/fast not rerun, full tier unrun, no push or B4–B6. Optional partial-header/new-SETUP cover remains unresolved diagnostic debt.
- 2026-11-22: User approved focused T19 closure before PLAN03 proceeds beyond B3: audit/reuse closed packet proofs, finish sampling/spacing and timing-exception qualification, repair routed paths under unchanged limits and behavior, and qualify hold/RDC against justified existing interface contracts. Existing proof caps/negative controls remain; stop for a needed behavior, assumption or limit change. Independent review and fresh USB/fast acceptance remain required. No new peripheral work or acceptance waiver.
- 2026-11-22: PLAN03 B3 frozen fast CI on local main `2504a31` failed at USB after measured 2864.272 seconds (`python tools/ci.py --tier fast --output build/plan03/fast01`, pinned runner). Earlier commands passed with the existing four T14 and eight T17 deferrals; all 23 USB simulations, focused formal, resume equivalence and byte CDC passed. Historical pre-enable fixture compilation failed on a newer verification-only observer; minimal historical-only fixture repair now passes complete engine/wrapper equivalence and phase/consumer fault controls. Packet evidence wiring and existing sampling/exception, routed timing and boundary qualification remain open. Independent review recommends a scoped T19 closure extension; requested, not yet approved. Stop at B3; no B4–B6, full tier or push.
- 2026-11-22: PLAN03 D74 retirement verified and independently accepted: removed only the ADC implementation/ports and its dedicated checks; 77 remaining SoC tests across the same 24 suites pass, exactly five approved cases fewer than baseline. All four top emissions and minimal-I0 compilation pass; retained pad proof, cover and three faults pass with zero assumptions. Firmware conversion helper/tests remain. Fast CI is next; no push or B4–B6 work yet.
- 2026-11-21: PLAN03 B2 accepted after independent review: all 82 original SoC tests across 24 suites pass; production/USB-stub emissions at 8/9 MHz and minimal-I0 compilation pass. Removed old profile alternatives/emitters; all four emitted RTL inventories remain byte-identical. Corrected the GPIO test boundary for production pinmux and retained exact register-state checks. ADC source deletion remains separate; neither CI tier nor B3–B6 has run.
- 2026-11-21: PLAN03 assigned on main; recorded D72–D76, froze new block work and withdrew T31. Read-first/source/test inventory started for B2. Existing D65 I0 fixture fixed/hard-float evidence is historical, distinct from required production-SoC measurements. Prior no-CI instructions are superseded by D76; no new check result claimed.

- 2026-11-21: User requested committing all accumulated work on main and pushing for review. This publication supersedes the historical local/uncommitted/no-push checkpoint notes. It includes the SoC/peripheral/native-flash implementation and the pending T31 proposal; it does not close unresolved task acceptance or approve T31's reset-policy change. Repository hygiene and independent snapshot review apply; neither CI tier is run. Final staging removes trailing blank lines only from existing verification scripts, with prior bytes and a hash manifest retained under build/commit-review.

- 2026-11-21: T31 proposal and brief independently reviewed; documentation checks pass and prior frozen implementation hashes are unchanged. Blocked before RTL on the pending explicit decision to permit host-commanded restart of a retained verified-and-locked image after warm/AON reset. No policy change, RTL acceptance, CI, commit or push is claimed.

- 2026-11-21: T31 contract preparation started under continued RTL. Independent review identified the existing explicit warm-reset image-invalidation policy; a narrow retained locked-image restart decision is pending before implementation. No RTL or CI change.

- 2026-11-21: T30 native QSPI read path completed on main. Ordered instruction/data flash reads share the existing engine with queued CS1 commands; reset drains preserve shared services. Real recovery-loaded lite and performance execution, all frozen focused tests/proofs/faults, mapped controller/local-memory timing and complete profiles pass. Independent review verified final hashes, reset binding and exact memory projection. Production boot, system performance, physical qualification and inherited proof/CI work remain open; no CI, commit or push.

- 2026-11-21: T30 started under continued RTL. Reviewed optional native XIP read path, bounded command/read arbitration, little-endian response and client-reset draining; preserve peripheral watchdogs and prior profiles, no CI.

- 2026-11-21: T29 command-mode QSPI completed on main. Bounded serial/quad transfers, keyed idle ownership handoff and existing pad/window/reset/demand integration verified. Frozen focused wire/engine/owner/SoC regressions, safety proofs/faults, mapped GF180 screen and all complete tops pass. Independent review verified corrected edge-count/gap oracles and final source/artifact/binding evidence. XIP, production boot, flash/physical qualification and inherited acceptance remain open; no CI, commit or push.

- 2026-11-21: T29 started under continued RTL on main. Reviewed bounded QSPI command-mode subset, existing pads/window, main-service reset and idle-only core ownership handoff. XIP and production boot remain separate; no CI.

- 2026-11-21: T28 scoped digital release completed on main. Real recovery START and lite firmware release performance through shared reset/epoch control; independent service reset preserves release, whole reset clears it. Frozen focused tests/proofs, conservative GF180 block screen and all complete-top variants pass; independent review accepted corrected in-flight command cancellation and exact evidence/bindings. Production flash/locked-image restart, physical qualification and inherited acceptance remain open. Neither CI tier run; coupled workspace remains uncommitted.

- 2026-11-21: T28 started under continued RTL. Independently reviewed lite-first performance core/client release using validated loader START, retained whole-reset-epoch flags and existing reset synchronizers. Earlier profiles, service reset containment and loader lock preserved; no clock-source choice, flash boot claim or CI.

- 2026-11-21: T27 D71 functional migration complete. Production raw ADC retires0x14 while preserving other offsets, ownership/reset and event semantics. Frozen 14 tests/four suites, engine/publication/owner proofs and legacy bounded scaler check with faults/covers, firmware arithmetic/both ABI links, full-wrapper setup/electrical screen and four whole tops pass. Independent review verified 1,168 source/640 artifact hashes and exact emitted decode/bindings. No CI, physical signoff, commit or push; inherited tasks remain open.

- 2026-11-21: User approved D71 retiring the unneeded scaled ADC register. T27 resumes production raw acquisition/MMIO/SoC integration and focused verification, preserving other offsets and protocol/reset semantics. No CI.

- 2026-11-21: T27 staged checkpoint independently reviewed: raw engine, generic firmware conversion, ten tests/three suites, seven unbounded assertions/covers/fault and mapped setup/electrical checks pass. Frozen aggregate retains its structure failure; encoding-only repair of inherited T26 documentation and separate structure recheck pass. Production0x14 ABI retirement awaits the user decision; current wrapper/map/SoC unchanged. No CI, commit or push.

- 2026-11-21: T27 started under continued RTL/D69. Independently reviewed staged raw ADC engine and firmware conversion; preserve production ABI pending explicit0x14 retirement decision. No CI or unrelated formal retries.

- 2026-11-21: T26 implements D70 with core/client-only performance-watchdog reset, PWM break/STOP acknowledgment and GPIO alternate-output disable; shared services and DMA survive. Actual epochReady blocks retained pre-reset STOP from clearing the break. Measured frozen 28 tests/11 suites, four top emissions and five output-disable assertions pass; supplemental 4-test epoch suite catches the explicit bypass fault. Original reset-net electrical failures are preserved; default-off verified reset buffers bring watchdog/PWM to zero electrical violations, with unchanged timing limits. Final source/artifact chain and identical measured buffer graphs independently verified. Full-width channel proof remains unresolved after capped initial/portfolio attempts; no helpers, CI, commit or push. Physical and broader I3 work remain open. See T26 report for commands and measured numbers.

- 2026-11-21: D70 explicitly approved: performance watchdog resets core/client epoch and disables PWM, preserving shared buses, DMA and other peripherals. Started T26 digital supervision on existing external clocks; no CI or production boot/sleep claim.

- 2026-11-21: T25 implemented the pinned clocked RV32E adoption, registered bus adapter, minimal machine CSR/trap/IRQ/WFI and opt-in real AON hart. Loader-wire firmware exercises retained SRAM, timer/mailbox IRQs, MRET/WFI, ownership and independent resets. Independent review resolved the START/halted handoff and RVFI lane convention. Frozen 28 tests/nine suites, four complete top emissions, provenance/map/structure, full baseline named-state and adapter/control proofs pass. Fresh mapped RR 63.398540ns against unchanged66.666667ns estimate; physical qualification separate. ADDI architectural proof remains unresolved after PDR/portfolio/data-cut attempts under120s caps; full ISA/machine formal stays open. Independent review verified all current hashes and emitted bindings. No CI, commit or push; coupled work remains local on main.

- 2026-11-21: User requested continued RTL after T24. Started T25 pinned clocked lite-core adoption and AON binding. Baseline equivalence precedes the already-required CSR/IRQ/WFI extension; loader-started profile preserves existing clocks, memory permissions and earlier profiles. Contract review before RTL, no CI, inherited acceptance issues remain open.

- 2026-11-21: T24 implemented three registered GPIO output selectors with GPIO/timer/PWM alternatives, reset disconnect, disabled handover and clock retention. Frozen focused checks passed 71 tests in 19 suites, ten map checks, structure and four whole-SoC emissions; 18 unbounded assertions, eight covers, three actual faults and the unchanged GF180 timing screen pass. Independent review verified 1104 source/591 artifact hashes and emitted wiring, plus formal/timing manifests. Existing dedicated pins, raw GPIO input/wake and prior profiles preserved. No CI, commit or push; coupled local work remains on main and inherited T23 range proof/physical qualification remain open.

- 2026-11-21: User requested continued RTL after T23. Started T24 limited output alternate functions on existing GPIO pads under D39/D69; dedicated pins/input/wake preserved, contract review before implementation, no CI. T23 proof remains separately open.

- 2026-11-21: T23 implemented four DMA channels and optional SoC/SRAM binding. Frozen focused run passed 62 tests, ten map checks, structure and four whole-top emissions; DMA and memory-control GF180 screens pass the existing budget. Nine engine and seven denied-wrapper safety assertions prove; one memory-range assertion remains unresolved after portfolio/exact partition, with covers and actual faults passing. Independent RTL/formal/timing and frozen-evidence review cleared this incomplete checkpoint, verifying 1092 source and 575 artifact hashes. Helper-invariant approval requested under timeout triage. No CI, commit or push; inherited local T20/T21/T22 work preserved on main.

- 2026-11-21: User requested continued RTL after T22. Started T23 basic DMA contract and integration under D25/D69; performance-owned memory and existing endpoint permissions, preserved prior profiles, independent review and focused checks. No CI.

- 2026-11-21: T22 functional PWM checkpoint complete: buffered independent channels, MMIO, request/overrun interface, IRQ10/pins/clock-demand binding and explicit reset contract. Frozen simulations and four whole-SoC emissions pass; safety/update proofs, covers/faults and GF180 setup/electrical screen pass with independent source/evidence review. No CI or physical qualification; DMA controller remains separate. Work remains local on main with inherited dependencies.

- 2026-11-21: User requested continued RTL under D69. Started T22 generic PWM channels in the existing reserved window/pins; contract review precedes implementation. DMA controller remains separately scoped; no CI.

- 2026-11-21: PLAN02 completed: D69 reconciled across active hardware/reset requirements; specialized actuator proposal retained as superseded history. Documentation scope/link/decision checks and independent review pass. Generic PWM/DMA and ADC scaling migration need scoped implementation; no RTL, ABI, test or acceptance-limit changes, no CI, no implementation gate closed.

- 2026-11-21: User approved D69: moderately general-purpose MCU, conventional peripherals rather than dedicated flight-actuator hardware. PLAN02 reconciles current planning; firmware owns protocols and application fault policy. No RTL/ABI/test changes or CI.


- 2026-11-21: T21 functional implementation complete: GPIO, ADC and D68 main/AON timers bind through the explicit SoC profile. Frozen focused simulations, four whole-top emissions, scoped proofs/covers/faults and independent source/artifact reviews pass; GPIO mapped reset buffering clears electrical failures. No CI; physical qualification and inherited T20 issues remain open. Changes remain local with the prior uncommitted T20 dependencies.

- 2026-11-21: User approved D68 split timers: preserve AON sleep deadlines and add the precise main timebase/capture/compare service in unused GPIO space. Implementation proceeds under T21; no clock choice or CI change.

- 2026-11-21: User assigned functional GPIO/ADC/timer implementations after pin-contract closure. Created T21 brief; preserve I1 profile and approved AON timer semantics. Proposed main/AON timer split awaits explicit decision; GPIO and ADC proceed independently, no CI.

- 2026-11-21: Completed requested GPIO/ADC/timer logical contracts and safe RTL bindings: provisional three GPIO, four shared capture/compare channels and receive-only ADC pins. Estimated simultaneous allocation 40/10 against cited 40/12 slot, not physical fit. Frozen focused integration passes, final map faults and six static-pad assertions/four actual enable faults qualify; independent review clears hashes and emitted tops. No CI, commit/push or full T20 completion; physical/system/CDC/timing work remains.

- 2026-11-21: User requested GPIO/ADC/timer pin contracts and remaining integration RTL. Independently reviewed provisional 3-GPIO/4-timer/receive-only-ADC allocation against cited 40/12 slot; extending safe I1 ports and executable pin accounting, no new functional peripheral or CI.

- 2026-11-21: RTL-first checkpoint completes the defined inactive QSPI/actuator/JTAG/IMU boundary in both I1 variants. Frozen focused simulations and map tests pass, static-pad proof/covers/actual fault qualify without assumptions, both whole tops emit and independent review clears the source/artifact evidence. Undefined GPIO/ADC/timer pin allocation and system/CDC/timing qualification remain; no CI or commit/push.

- 2026-11-21: User requested remaining RTL first. Completing the approved I1 inactive QSPI/actuator/JTAG and IMU input boundary, with independent contract review and focused checks; no CI, no new peripheral implementation or GPIO pin-allocation decision.

- 2026-11-21: User assigned continued I1 integration. Reviewed existing reset, ownership and routing contracts; implement existing blocks and honest stubs with focused integration checks. No peripheral behavior change, clock-source decision or CI; inherited qualifications remain.
- 2026-11-21: User requested continuation after the I1 checkpoint. Reuse the independent USB wire host against the integrated fabric/MMIO boundary and extend reset recovery coverage; keep CI disabled and work on main.
- 2026-11-21: Frozen continuation passes four focused simulations across USB wire/MMIO, both bridge directions and full-core MMIO reset, including actual data/reset wiring faults. Independent review strengthened cancellation to require an error before destination clock restart. Production RTL unchanged from prior checkpoint; no CI, commit or full T20 completion claim.
- 2026-11-21: I1 checkpoint on main: existing serial/AON blocks, bridges/mailbox, recovery loader/retained SRAM and real-or-stub USB bound into DeadhorseSoc. Frozen focused run passes 13 simulations and emits both complete variants; four source-bound ABC PDR glue groups, covers and actual faults pass. Independent review resolved nested gateway timeout recovery and checked proof receipts. Full T20 acceptance remains incomplete; fast/full CI unrun, changes uncommitted.

- 2026-11-20: D67 measured original-MAC control RR 66.563103 ns versus FA 66.426033 ns and 4:2 69.822578 ns. Retain unchanged arithmetic with verified extraction/reinsertion and reversible private naming; both trial-clock screens, electrical, hold/reset and gate checks pass. Independent review confirms graphs, hashes, scripts and timing. The earlier improvement is synthesis-order sensitive; no RTL, clock decision, CI, commit or complete T20 acceptance.

- 2026-11-20: User approved D67 isolated fused-MAC synthesis experiment: compare full-adder and 4:2 compressor trees with prefix final addition, preserving FMA, production RTL, latency and all limits. Exact arithmetic proof, verified reinsertion, integrated timing and independent review required; no CI.

- 2026-11-20: D66 grouped MAC carry candidate proves six leaf/333 core states equivalent with nine rejecting faults; 26 simulations and unchanged 4,350/9,007 worst-cycle measurements pass. Same GF180 mapping regresses RR 70.011482 to 79.044106 ns through loss of fused MAC compression; independently reviewed and rejected. Archived candidate and restored original core byte-for-byte. D65 remains local, 9 MHz setup unresolved. No CI, commit or push.

- 2026-11-20: User approved D66 focused MAC carry-network experiment. Preserve signed multiply, ownership, interfaces and latency; requalify exact equivalence, unchanged performance and timing, with independent review. No CI or clock decision.

- 2026-11-20: Reset-only mapped buffer trees verified; direct release loads reduced to eight each, all 2,869 RN/SETN endpoints checked, electrical/hold/reset and dynamic ICG checks pass. Reporting optimization reproduces baseline path bytes exactly; 32 focused timing tests pass. Two cell-sizing trials regressed and were rejected; 60000 ps mapping produced the same netlist. XOR balancing improves full-top RR to 70.011482 ns (RVFI capture), while functional RF is 69.443718 ns; both still miss 9 MHz. Independent evidence review complete; requested separate same-cycle core MAC scope. No core RTL change, CI, commit or push.

- 2026-11-20: User authorized reset-distribution buffering/sizing first, followed by remeasurement and mapping/loading diagnosis of the core decode-to-register-file path. Preserve reset behavior and all timing/performance limits; focused checks and independent review only, no CI.

- 2026-11-20: D65 measured worst 4,350 fixed / 9,007 hard-float cycles within unchanged limits; fourteen simulations, eleven control proofs, covers/fault and five fixture tests pass. Corrected a startup-SP checker false positive without changing bounds. Independent review verified raw windows/hashes. Integrated request/grant paths max 51.692348 ns, but whole-I0 RR 71.469757 ns misses 9 MHz's 66.666667 ns budget and 2,866 electrical violations remain at both clocks. No macro timing/area qualification, further RTL restructuring, CI, commit or push; candidate remains local.

- 2026-11-20: User approved D65 current-request arbitration including contention. Retain registered fairness/responses and reject new data during response return; focused unchanged checks and independent review, no CI.

- 2026-11-20: D64 idle-only donation rejected. Fourteen simulations passed; unchanged control proof found registered-MMIO-response/new-accept overlap. Fresh performance and complete RVFI/cycle traces equal baseline: worst 4,821 versus limit 4,785. Independent review verified hashes/counts and diagnosed the counterexample. Archived candidate/test and restored baseline. No timing qualification, hard-float, CI, commit/push or broader arbitration change.

- 2026-11-20: User approved research recommendation's narrow same-cycle idle instruction-slot donation experiment (D64), including a grant-output exception subject to checks. Late independent review and a pinned read-only trace recount find zero idle-fetch data-wait opportunities in baseline. Test only the approved scope; no contested-request redesign or CI.

- 2026-11-20: T20 two-idle qualifier passed fourteen simulations and unchanged control proof/covers/fault, but measured fixed worst 4,819 remains 34 cycles above 4,785; mean slightly worsens versus baseline. Independent source/hash/raw-window review confirmed. Archived candidate/test and restored baseline arbitration; passive bus diagnosis retained locally. Hard-float, CI, further restructuring and commit/push not run.

- 2026-11-20: User approved the narrow two-consecutive-fetch-idle parking experiment. Passive request/grant trace exactly reproduces baseline RVFI and cycles; testing the qualifier with unchanged workloads, limits and checks. No CI.

- 2026-11-20: Approved T20 parking experiment passed the 13 unchanged regressions, added parking/restart/reset test and control proof/covers/fault. Fresh QEMU-compared fixed workload regressed to mean 4,314.125 / worst 4,835 cycles; unchanged limit 4,785 still fails. Independent review confirmed raw counts/hashes. Rejected and archived candidate/test, restored exact prior arbitration; hard-float and further restructuring not attempted. No CI or commit/push.
- 2026-11-20: User approved the focused registered idle-data-grant parking experiment following the 4,821-cycle performance stop. Preserve first-fetch readiness, busy/reset exclusions, fairness, all tests and the unchanged +10% limit. No bank-parallel rewrite or CI authorized by this experiment.
- 2026-11-20: T20 integrated fixed-point measurement passes unchanged QEMU comparison and observation faults, but worst 4,821 cycles exceeds the unchanged 4,785-cycle stop threshold. Independent raw-trace/receipt review confirms result. Stopped before hard-float/arch suite and restructuring; requested approval for a narrow registered idle-grant parking experiment. Production arbitration remains unchanged; no CI.
- 2026-11-20: T20 continuation starts integrated lockstep/performance qualification using an independently reviewed QEMU-map verification configuration of the real I0 memory/fabric path. Production defaults and round-2 limits unchanged; no CI.
- 2026-11-20: T20 I0 boot/control milestone on main: production faithful RV32IMFC, native local ROM/banked SRAM path, retained MMIO, main fabric and UART0 connected. Thirteen focused simulations pass; eleven local-memory control assertions prove with covers and a rejecting fault. Independent review resolved reset-test and receipt gaps. Integrated lockstep, performance/timing, I1, pin fit and gateway target transport remain open. No CI; no T20 completion or gate claimed.
- 2026-11-20: T20 initial contract/map milestone on main: documented reset scopes, memory permissions, bridge/loader/stub boundaries and inherited limits; provisional schema emits configuration and checks spec/register/IRQ consistency. Seven focused tests pass with negative controls. No connected SoC RTL, timing, solver or CI result claimed; gateway target transport remains a user question, Q15/Q16 remain open.

- 2026-11-20: User directed merging all current work into main and working directly on main, then assigned the SoC tasks. Main now includes f1c17ba and the T20 brief. T20 starts with the SoC contract and independent interface review before RTL; Q15/Q16 and inherited block qualifications remain open. Existing no-CI instruction retained.

- 2026-11-20: User authorized committing the preserved T13/S1 local checkpoint before pulling and merging the SoC plan updates. S1 remains blocked and T13 formal acceptance remains deferred/unproved; two focused accounting tests pass again, no CI or measurement rerun. No SoC implementation starts through this reconciliation.
- 2026-11-20: Plan change, Claude at user's direction: added [16-soc-integration.md](16-soc-integration.md) (staged SoC plan, block inventory, local memory path rule, open clock plan) and brief T20 for stages I0–I1. Registered the remaining block briefs in order. Added open questions Q15 (main clock source/frequency) and Q16 (loop-rate target) and risk K23. No implementation started; no gate checked.

- 2026-11-19: D58 supersedes the aligned-enable consume candidate. Stopped both D57 frozen jobs and preserved that candidate under build; original RegNext flags/data and certificate are restored. Independent review confirms packetData feeds OUT memory wordData=RegNext(writeData) outside bitEnable, triggering the explicit consumer stop rule before implementation/proof. No consumer or assertion changed. Decision needed: keep packetData full-rate, or explicitly permit/prove a valid-qualified downstream state mismatch. No D58 equivalence/CI pass or commit/push.

- 2026-11-19: User stopped the broader T19 run and approved D57. Both D56 frozen jobs were cancelled; the complete unaccepted candidate is preserved under build. Active source retains only aligned IN flag capture/certification plus the new USB warning policy. No gating, boundary, packet-proof or offered-load change is retained. New focused/frozen verification is required; prior candidate results are not acceptance for this snapshot.

- 2026-11-19: D55/D56 post-step-3 timing triggers the explicit stop: engine CF endpoint→control.inReady and FF PHY nrzi→shift remain over 12.5 ns; wrapper also fails CF/FF. No further RTL, packet-proof attempt or increased-load throughput test. Digital EP0 bank equivalence/shared-gate proof and faults pass; freeze/check/review checkpoint preparation continues without claiming acceptance.

- 2026-11-19: T19 resumed from 099c27f under D55/D56. Finish pad/reset contract and SIE fixture, compare consume options and measure shared-clock-gated EP0 banks. Stop if timing still fails after these steps; only then attempt the separately authorized re-posed packet proof and throughput-margin measurement. No limits or qualification claims changed.

- 2026-11-19: D54 confirms short/ZLP retry defects and repairs offered ownership. Final five directed tests (383 phase cases), all 18 frozen USB tests, and unbounded boundary proof/covers/fault pass; unchanged slow-service regression now reaches the intended rate rejection with bytes intact. Independent review is clear for this scoped result. Timing and original packet/qualification obligations remain; frozen USB/fast fail, full tier unrun. No merge.

- 2026-11-19: D54 resumes T19 to test the approved retry-lifecycle hypothesis: reproduce appended short-packet payload and terminal-ZLP lost-ACK behavior, then test immutable offered ownership until ACK/reset. No timing, proof or qualification limit changes; no merge.

- 2026-11-19: D53 frozen candidate measured 1.022483 Mbit/s simultaneously each direction under the documented MMIO/clock schedule; mapped wrapper area 197043.3472 um² versus D52 measured 332364.2560 um² (estimated 40.715% reduction). New slow-service test exposes an inherited lost-ACK short-packet replay defect. Integrated CF/FC/FF failures and packet/qualification obligations remain. Aggregate and fast CI fail with source hashes unchanged; full tier unrun. Independent review clears only an incomplete checkpoint. Separate packet-lifecycle repair approval is pending; no merge.

- 2026-11-19: D53 starts after reviewed D52 baseline d45e50f was committed/pushed. User requests 16-byte bulk buffers if throughput is acceptable, target 1 Mbit/s; conservatively assess each direction through the full MMIO/CDC wrapper. Coordinate packet-size parameters and exact-source proofs without changing timing, cadence or service/solver limits.

- 2026-11-19: D52 frozen USB aggregate and fast CI fail at USB with source inventories unchanged. Eleven USB simulations, eleven focused formal cases, resume equivalence and supporting controls pass; two integrated CF setup paths, standalone SIE, packet and sampling/exception/boundary qualification remain blocking. Three-rung packet attempt exhausted without closure. Independent review clear for an incomplete checkpoint; full tier unrun, no merge.

- 2026-11-19: T19 resumed under D52. Size remaining full-rate/reset/decode cones and factor resume comparisons without latency changes, then remeasure before further qualification. Packet work is separately scoped under existing caps and triage limits; no changed assumptions or acceptance.
- 2026-11-18: D51 frozen USB aggregate and fast CI fail with exact tested source inventories unchanged. Eleven simulations, ten non-packet formal cases and supporting controls pass; integrated full-rate timing, packet and sampling/exception obligations remain open. Independent review is clear for the blocked checkpoint; full tier unrun, no merge.
- 2026-11-18: D51 local proofs/controls pass and enable→PHY RX worst over both transitions measures 9.351625 ns against 12.5 ns. Integrated packet-boundary/reset/resume paths still fail; stop further restructuring and freeze for aggregate/fast checks. Packet obligations unchanged; full tier unrun.
- 2026-11-18: T19 resumed under D51: prove reset-aware capture eligibility before changing classes, investigate enable fanout, then finish boundary/fixture/pipeline work. Packet proofs remain separate; previous failures are preserved.
- 2026-11-18: D48-D50 frozen aggregate and fast CI fail at USB with exact source hashes unchanged. Eleven USB tests, eight non-packet formal cases and supporting controls pass; timing and packet obligations remain open. Independent review is clear for the blocked review checkpoint. Full tier not run; user-requested commit/push does not qualify T19 or authorize merge.
- 2026-11-18: D48-D50 post-step-4 stop: literal reset-inclusive certificate retains unreset headers; replicated enable path still measures 13.296519 ns versus 12.5 ns, with other full-rate failures. Shared reset-data substitution and eleven USB tests pass; independent review confirms D50 is ineligible without buffer restructuring. Freeze for aggregate/fast checks; full tier unrun, no acceptance claim.
- 2026-11-18: T19 resumed under explicit D48-D50 decisions. Apply value-stability/PHY certification, enable replication and synchronized reset-data changes in order; stop on remaining timing failures after steps 1-4. Conditional small-model proof cannot restructure buffers. No prior failure or qualification obligation is waived; no merge authorized.
- 2026-11-18: User explicitly authorized commit/push of the independently reviewed T19 timing/proof checkpoint despite the recorded failed gates. T19 remains blocked; no acceptance requirement or merge is authorized. Unrelated core/S1 work is excluded.
- 2026-11-18: Final frozen T19 aggregate and fast CI fail at USB. EP0 certificate-preserving mapping measures 13.370109 ns state[5] to header_5[6] (12.5 ns budget), superseding the earlier numerical pass and triggering the explicit stop. D47 remains exhausted/unresolved; independent transport-reset composition is open. Functional sources stayed frozen; only reports updated afterward. Full tier not run; no commit/push/merge.
- 2026-11-18: Initial T19 frozen checks exposed shared HardFloat preparation outside the SBT compile lock. Both owned runs were stopped with failure evidence preserved. Independently reviewed runner repair moves preparation inside the lock; concurrent compile/emission then pass with all eighty production SV files unchanged. Fresh frozen acceptance/fast runs are required; no gate or commit/push is accepted.
- 2026-11-18: T19 D47 attempt stopped within the approved time box. Sparse-memory refinement proves with a mis-phase fault; final IN/OUT positive jobs still time out, while real covers/faults pass. Independent review confirms unchanged original assertions and byte-identical production buffer emission. D46 EP0 numerical timing passes; standalone SIE, combined engine and full wrapper expose larger full-rate and hold/reset failures. Sources are being frozen for aggregate/fast checks; no acceptance, commit, push or merge is claimed.
- 2026-11-18: User approved the scoped sparse-memory refinement and pointer/ownership proof attempt (D47). Time box starts 2026-11-19 02:12:29 UTC and ends 02:57:29 UTC; approval does not close packet-buffer acceptance.
- 2026-11-18: User approved address-nonzero flag with identical reset priority and equivalence invariant, and directed that the small timing overrun not block work (D46). T19 resumed without changing the nominal timing budget or reporting unproved qualification as passed.
- 2026-11-18: T19 header storage/decode moved onto common protocol enable under follow-up approval. All 11 USB tests pass; source/mapped enable checks and strengthened reset cadence proof pass. Class timing exposes `address[4]` to `decodeValidQ` at measured 12.649599 ns versus estimated 12.5 ns; address reset override prevents certification. Independent review confirms another explicit stop. SDC selector defect corrected and representative 4/3 edges checked; complete qualification remains open. Packet step-0 diagnostics and pinned SRAM estimate recorded. No acceptance/CI pass or commit/push.
- 2026-11-18: User approved the proposed EP0-only SETUP-header/decode restructuring onto the common protocol-enable phase, preserving protocol behavior and all verification requirements. T19 resumed; D45 eligibility, timing limits and mandatory proofs remain unchanged.
- 2026-11-18: T19 D45 eligibility check reproduced the EP0 failure on `header_6[5]` to unconditional `decodeValidQ`. Independent review confirms the path is outside the approved class and triggers the user's stop condition. No RTL/constraints/pipelines changed; aggregate, fast/full CI and packet-proof triage not rerun; no commit/push. Approval is recorded, qualification remains open.
- 2026-11-18: T19 resumed on `codex/t19-usb-review`. User approved D45, extending the proposed SIE four-edge class to enable-certified EP0 register pairs. All certificate, reset, classification, timing and negative-control obligations remain; no gate or implementation completion implied.
- 2026-11-18: T19 user explicitly requested commit/push of the incomplete implementation for further review. Publish a review checkpoint with known failures preserved; T19 remains blocked and the SIE timing proposal remains unapproved. Unrelated core/S1 changes are excluded.
- 2026-11-18: T19 conversion/integration checkpoint blocked. Independent wire/MMIO tests and selected formal properties pass; EP0/engine timing, packet-buffer proofs, sampling-equivalence and wrapper qualification remain open. Prepared narrow SIE multicycle proposal for user decision; no exception applied, no gate checked, no commit/push. See T19 report and USB ledgers.
- 2026-11-18: T19 resumed at the user's instruction to perform the suggested conversions and tackle T19. Approval covers selective Chisel buffer/control conversion and retaining the vendor PHY sampler/decoded outputs under the proposed narrow exception. Timing/electrical limits, shared MCU-domain CDC, protocol verification and physical qualification remain required.

- 2026-11-18: T19 source assessment complete; production integration blocked pending scoped vendor-PHY sampling/output exception decision. GF180 diagnostic fails timing and electrical checks; independent review confirms EP0 worst path. Selective Chisel adaptation proposed, no requirement waived, no gate checked, no commit/push.

- 2026-11-18: T19 assigned and in progress. User supplied peripherals-ip and requested USB adoption alongside the serial peripherals. D11/D40 already cover USB; added implementation brief. Assess source provenance, shared CDC boundary and GF180 feasibility before production import; no gate checked.

- 2026-11-18: Completed the T13 five-target study. The faithful core now shares the integer multiplier with the FPU and reuses the FPU addend register. Fast CI passed. [Round 2 measurements](tasks/reports/T13-round2.md).

- 2026-11-18: Started the T13 five-target area and timing study, including the faithful-core writeback experiment.

- 2026-11-18: Completed the ten-proposal faithful-F optimization study. No trial reduced both mapped whole-core area and worst-path delay. [Results](tasks/reports/T13-ten-proposals.md).

- 2026-11-18: Started the ten-proposal optimization study on the committed eight-bank faithful-F core. Retain only verified reductions in both whole-core area and delay.

- 2026-11-18: Completed the T13 faithful-F area study. Eight-bank FP register reads reduced mapped core area by 1.448% and shortened the worst path by 0.131546 ns. All other variants missed the timing cutoff. [Report](tasks/reports/T13-area-study.md).

- 2026-11-18: T13 area study assigned. Compare five alternatives on the committed faithful RV32IMFC core. A smaller whole-core area qualifies only if its measured worst delay does not increase.

- 2026-11-17: T13 timing study completed. Parallel ALU operand selection measured 64.389893 ns with 0.239% more area and exact cycle equivalence. Earlier formal acceptance and S1 throughput remain open. [Report](tasks/reports/T13-pipeline-timing.md).

- 2026-11-17: T13 pipeline timing study assigned. Compare five faithful-F hypotheses at the same GF180 operating point and retain a verified improvement within the 5% whole-core area limit.

- 2026-11-17: T18 completed. Standalone acceptance and fast CI passed their active checks. The recovery loader has no deferred checks. External reset and lite watchdog invalidate the image and retain the programming lock.

- 2026-11-17: T18 resumed. User confirmed external and lite-watchdog resets preserve the programming lock. POR/brownout clear it.

- 2026-11-17: T18 waiting on the lock-reset policy. The historical clocked loader test and the adapted wire target test passed. End-to-end Deadhorse acceptance remains open.

- 2026-11-17: T18 implementation assigned. Began wire protocol, memory completion and reset-contract review against the pinned clocked source.

- 2026-11-17: T18 adoption brief prepared. Traced the pinned clocked I2C target through loader control to program SRAM and identified the clocked wire-level recovery test. Implementation remains open.

- 2026-11-17: T17 complete, Codex; byte-command I2C controller with stretching/recovery, ownership and retained sleep. Final aggregate passes 19 simulations and 12 runner tests; measured GF180 22.349216 ns against 24.96 ns. Fast CI's 32 commands pass active checks with eight explicit T17 and four inherited T14 deferrals. Independent review/authentication passed; no gate change. See [report](tasks/reports/T17.md).

- 2026-11-17: T17 assigned -> in progress, Codex; user authorized the next I2C task after T16. Prepare/review controller contract, 100/400 kHz timing, stretching/recovery, ownership and retained sleep; loader adoption and core work remain separate. No gate change.

- 2026-11-17: T16 in progress -> done, Codex; SPI modes 0/3, two chip selects, timestamped full-duplex transfers and owner/sleep/IRQ/DMA interfaces pass final aggregate and all 31 active fast-tier jobs. Independent RTL, boundary-test and gate review approved. No SPI deferrals; four inherited T14 obligations remain unproved. Report/ledgers retain bounded formal scope, physical limits and failed initial attempts. No gate checked; earlier S1/T13 work remains separate.

- 2026-11-17: T16 assigned -> in progress, Codex; user assigned SPI controller completion. Preparing reviewed contract, modes 0/3 with two chip selects, bounded timestamped transfers, generated registers and owner/sleep/DMA interfaces; no core optimization or gate change.

- 2026-11-17: T15 in progress -> done, Codex; recovered implementation passes fresh aggregate acceptance and all 30 active fast-tier jobs, with independent RTL/gate review and serial rerun. No UART deferrals; four inherited T14 obligations remain explicitly unproved. Report and ledgers record measured timing/area and bounded formal scope. Full not run; no gate checked. Earlier S1/T13 work remains separate.

- 2026-11-17: T15 resumed, Codex; recovered UART implementation and verification artifacts after the prior session's system error. Running fresh aggregate acceptance and fast CI, with independent RTL and gate review; earlier S1/T13 checkpoint remains separate.

- 2026-11-17: T15 assigned -> in progress, Codex; user directed completion of remaining IP before core performance optimization and approved the proposed UART task. Prepare/review UART contract, implement three reusable instances with ownership, DMA request and sleep/wake boundaries, test and independently review. Formal timeouts remain deferred/unproved; S1 is not closed.

- 2026-11-17: S1 in progress -> blocked, Codex; fresh faithful-F timing passes65.726219/66.666667ns, mapped area839962.5472um2. Independent review confirms baseline QEMU comparisons and exact loop counts: fixed5.251500MIPS, hard-float1.090122MIPS at9MHz. The below2.5MIPS stop rule halts further measurements/optimization; no formal or CI tier run, no commit/push. [Report](tasks/reports/S1.md).

- 2026-11-17: S1 not started -> in progress, Codex; user approved T13 acceptance review followed by S1 and directed that formal timeouts be deferred for later. Independent audit retains T13 as incomplete, with the explicit measurement dependency exception described in its report. No ISA proof, production clock adoption or acceptance-limit waiver is implied.

- 2026-11-17: S3 in progress -> done, Codex; aggregate acceptance passes in 72.288 s, main fixture allocations estimated 10176/10616 B with reserved stack, lite subset 648/664 B; independent review clear. Fast 29/29 in 1187.791 s with inherited T14 proof deferrals; full not run. No capacity increase, production RTL change or full-firmware/physical qualification claimed. [Report](tasks/reports/S3.md).

- 2026-11-17: S3 not started -> in progress, Codex; user directed the next task after T14 active checks passed. T02/T07/T08 prerequisites complete; measure separate hard-float firmware allocation/stack, banked access and assumption-qualified flash interference. No core/profile change.

- 2026-11-17: T14 in progress -> done under explicit user deferrals, Codex; 16 simulation tests, active formal and 15 timing configurations pass; fast tier 29/29 in 1185.432 s, independent review clear. Four named proofs remain deferred/unproved; full tier not run. [Report](tasks/reports/T14.md).

- 2026-11-17: T14 blocked -> in progress, Codex; user authorized completion if tests pass with deferrals recorded, then the next ready task. Closing the active gate with explicit deferred/unproved property records; no proof retries or helper work on the deferred obligations.

- 2026-11-17: User deferred the three T14 bus fairness proofs and one bridge return-data proof for later. Attempts and proposed helper work stopped; assertions and failure/timeout evidence retained as unproved. Production watchdog qualification, final review and CI handling of the deferral remain open; no completion or gate pass recorded. [Report](tasks/reports/T14.md).

- 2026-11-17: T14 in progress -> blocked, Codex; 14 combined simulations and 15 module timing configurations pass; CDC, mailbox and direction proofs pass. Three bus fairness assertions and bridge return-data equality remain unresolved after bounded triage; production watchdog qualification remains open. Helper-proof approval requested; no CI tier, commit or push claimed. [Report](tasks/reports/T14.md).

- 2026-11-16: T14 started, Codex; user assigned bus, shared CDC bridge and mailbox. Review contracts first, preserve reset containment and endpoint ownership, use focused block proofs and independent review; no T13 formal sweep.

- 2026-11-16: T13 remains blocked, Codex; user-requested full non-formal validation passes 54/54 jobs in measured 2387.400 s (39m 47s), with 259 Python tests and 71 RTL tests across 20 suites. Both F profiles pass architectural/random/flight lockstep; candidate timing gates pass. Reference Ibex benchmark still exceeds the old default budget. Formal, including environment solver probes, explicitly not run; neither standard CI tier ran this continuation. Default checks unchanged, no RTL changes; independent evidence review complete. [Report](tasks/reports/T13-nonformal.md).

- 2026-11-16: T13 in progress -> blocked on remaining acceptance, Codex; user-requested bus-error repair verified. WithF tracks granted beats; idle/pregrant errors ignored and real faults preserved. Fast tier **PASS**, all 26 commands, measured 824.220 s (13m 44s), including 14 RTL tests. **Full tier not run.** Final stronger reset test also passes. Faithful timing 65.726219 / 66.666667 ns; registered F 24.947506 / 24.960000 ns. Original integration depth160 and one portfolio time out; diagnostic40/80, concrete covers/fault pass. Independent review complete; no assumptions/bounds changed. [Report](tasks/reports/T13-bus-error.md).

- 2026-11-16: T13 resumed, Codex; user requests the unsolicited bus-error fix. Replay concretely, qualify responses by granted ownership, preserve real faults and existing assertions, obtain independent review.

- 2026-11-16: T13 in progress -> blocked, Codex; faithful F candidate implemented and independently reviewed. Final ADDI/LW/C.ADD depth-40 checks, simulation and 12 unchanged-module proofs pass. Integration assertion fails at bound 10 on unsolicited error/trap/cancellation; final timing fails 67.791702 / 66.666667 ns. Fast tier **failed (partial tier run)**, measured 426.823 s to stop; 15 commands passed, failed at integrated-timing. Full tier **not run this continuation**. No assertion/assumption/budget relaxation, production adoption or commit/push. [Report](tasks/reports/T13-faithful-f.md).

- 2026-11-16: T13 resumed, Codex; user directed continuation after the faithful 9 MHz timing pass. Integrate the existing FPU on the faithful pipeline as an explicitly separate candidate; preserve old profiles, default clock and checks until qualification.

- 2026-11-16: T13 in progress -> blocked, Codex; fresh faithful RV32IMC 9 MHz trial passes 65.305771 ns / 66.666667 ns by retaining the tighter 62500 ps mapping target. Initial looser mapping failure and diagnostics preserved; no RTL/default clock change. Independent review and final fast tier pass (21 commands, 474.641 s); full not rerun. Production clock/profile adoption and faithful F integration remain open. [Report](tasks/reports/T13-faithful-9mhz.md).

- 2026-11-16: T13 resumed for the approved faithful Chisel 9 MHz trial, Codex; preserve the default clock, all checks and the failed 9.6 MHz measurement. No RTL behavior change or full formal sweep.

- 2026-11-16: T13 in progress -> blocked, Codex; faithful Chisel 9.6 MHz trial fails 65.305771 ns / 62.5 ns, with zero electrical violations and expected negative rejection. Independent review accepts the measurement; fast tier passes 21 commands in 475.169 s. Full tier not rerun. No production clock/profile or RTL behavior change; recommend a separately qualified 9 MHz trial. [Report](tasks/reports/T13-faithful-9p6mhz.md).

- 2026-11-16: T13 resumed for the approved faithful Chisel 9.6 MHz timing trial, Codex; preserve the default clock, all checks and both existing profiles. No RTL behavior change or full formal sweep.

- 2026-11-16: T13 12 MHz trial complete, Codex; both registered no-F and F cores pass the 50 ns allowance with unchanged margin/electrical checks and byte-identical RTL. Actual over-budget negative still fails; default-flow self-tests and fast tier (460.822 s) pass. Independent review clears the experiment. Global clock unchanged; full tier not rerun and T13 remains blocked on outstanding acceptance. [Trial report](tasks/reports/T13-12mhz.md).

- 2026-11-16: T13 resumed for the user-authorized 12 MHz timing trial, Codex; preserve default 24 MHz assumptions and failure evidence, use the same 60 percent margin and electrical checks, and independently review both core profiles. No full formal sweep or RTL change is planned.

- 2026-11-16: T13 in progress -> blocked, Codex; performance measured before proof work; approved three-rung triage accepts concrete LW (144/64) and abstracted shorter-window C.ADD (54/19), with concrete covers and both faults. Independently reviewed fast tier passes in 475.113 s. Requested full run fails registered no-F timing after 3217.428 s (51 commands passed, 26 unrun); no RTL or limit change. User-authorized commit/push follows fast acceptance; full/T13 completion not claimed. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 blocked -> in progress, Codex; pulled timeout-triage skill and user-authorized performance-first measurements, at most three triage rungs, fast/full CI tiers, report condensation and consolidation proposal. No RTL changes or further bespoke instruction proofs authorized.

- 2026-11-16: T13 remains blocked, Codex; user explicitly requested commit/push of the incomplete checkpoint for their review, with the unresolved formal-verification problem described in the commit. No acceptance requirement or status was changed; the existing T11 baseline tag accompanies the checkpoint.

- 2026-11-16: T13 in progress -> blocked, Codex; one native solver-query refinement and one exact two-group split preserve all checks. LW control/register partition passes at depth 144; memory/trap partition reaches the unchanged 120-second cap without a counterexample. No further cascade, concrete qualification or C.ADD runs were launched. Focused gate remains unresolved and T13 uncommitted; workflow commit `ac45fd4` is pushed.

- 2026-11-16: T13 continued, Codex; widened-model integration safety and fresh production binding pass independent review. One critical LW attempt reaches the unchanged short cap without a counterexample; C.ADD is checked separately. Focused gate authenticates prior evidence but correctly refuses unresolved critical checks.

- 2026-11-16: T13 continued, Codex; all33 original JALR assertions close with exact accounting, concrete covers/faults and independent review. Corrected FPU model has constructive trace inclusion; unchanged28 safety assertions/eight abstract covers pass, with fresh production-binding companion pending. Remaining critical load/compressed-add checks and final focused gate remain open.

- 2026-11-16: T13 continued, Codex; exact operand, RF source and capture/staged arithmetic compositions close original JALR next-PC assertion with active covers/faults and independent review. Local IF equivalence passes in explicit raw-encoding domain. 104 harness tests pass. Full critical-ISA accounting and final gate remain open; reviewer found an invalid/completion-payload coupling in the old FPU formal model, so a new inclusion-qualified model is being prepared without changing production RTL.

- 2026-11-16: T13 continued, Codex; exact monitor reset/step/final SAT composition proves full capture ownership identity with all mutation negatives and independent review. Active capture-valid and real production PC fault qualification pass; 88 harness tests pass. Workflow-only commit `ac45fd4` pushed separately. Remaining arithmetic, ISA/IF and local gate stay open; no full formal sweep.

- 2026-11-16: User authorized minor fixes and verification refinements with quick research and independent agent review; updated task workflow and resumed T13 compositional ownership checks. Acceptance requirements remain unchanged.

- 2026-11-16: T13 in progress -> blocked, Codex; no-write/no-clear/transition-tag stability prove unbounded with active covers, real faults and independent review. Authenticated inherited-monitor equivalence passes; one owner-JALR attempt retaining all three phase helpers as assertions still times out at unchanged120 seconds without counterexample. Eighty-one harness tests and structure pass; no further global retry, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved transition-local instruction/phase stability checks while integer execution is outstanding. Retain exact production model, assumptions, short limits and independent review.

- 2026-11-16: T13 in progress -> blocked, Codex; exact ownership split passes owner-valid, then times out on owner-JALR alone at unchanged120 seconds without counterexample. Remaining first/instruction/PC partitions unrun. Qualification and omitted-PC negative pass; independent review authenticates final models/statuses and finds no concrete stale-response defect. Seventy-seven harness tests and structure pass. No kind composition, acceptance waiver, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved isolating existing capture ownership flags from instruction/PC identity. Exact full-inventory partition, original assumptions and short limits retained; independent review required.

- 2026-11-16: T13 in progress -> blocked, Codex; actual accepted-request classification, kind/phase retention and retained JALR kind prove with active covers and real faults. Exact authenticated reuse resolves a trace-parser issue without rerunning completed proofs. Redirect instruction/PC identity times out at unchanged120 seconds without counterexample; later covers/fault unrun. Independent review clears scoped control evidence and authenticated reuse; hardened companion audit verifies identity status directly. Seventy-four harness tests and structure pass. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved observing actual request acceptance and tracking instruction/PC/phase through redirect capture. No assumptions or limits changed; independent review required.

- 2026-11-16: T13 in progress -> blocked, Codex; approved exact six-conjunct alignment diagnostic passes response validity, then times out on saved ALU-kind ownership at the unchanged120-second limit without counterexample. Remaining four partitions and original cover/fault/ADD obligations unrun. Boolean equivalence and omitted-condition negative pass, seventy-one harness tests and structure pass, and independent review verifies models/hashes/statuses. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved exact partitioning of the existing saved-request alignment conjuncts. Preserve the full condition inventory, unchanged production/environment, short limits and independent review.

- 2026-11-16: T13 continuation -> blocked, Codex; independently reviewed narrower saved-request alignment also times out at unchanged120 seconds without counterexample. Later covers/fault and local ADD roles unrun; independent final review verifies protected hashes/statuses and clears no proof result. Further solver attempts stopped. Sixty-eight harness tests and structure check pass; no acceptance waiver, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 continued autonomously, Codex; narrow diagnostic capture arithmetic timed out with original acceptance unchanged. Pursue independently recommended saved-request alignment and local ADD lemmas under the same short caps; no architecture or acceptance change.

- 2026-11-16: T13 in progress -> blocked, Codex; capture-source correspondence proves unbounded with active x0/alias covers and actual source-bit fault. Exact authenticated resume repairs a witness-parser issue without rerunning completed proofs. Capture arithmetic times out at unchanged120-second cap without counterexample; later arithmetic roles unrun. Source-only guard audit passes and retains unresolved aggregate status. Independent review clears reuse/source evidence; remaining acceptance prevents commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user requested autonomous continuation through remaining focused proofs and review, asking only for substantive problems. Continue capture arithmetic/source correspondence without changing checks or limits.

- 2026-11-16: T13 focused transport continuation completed, Codex; redirect capture/identity/retirement/RVFI transport proves unbounded within unchanged short cap; active cover, actual PC-bit fault and guard-negative audit pass. Independent review clears the scoped proof and audit; sixty-three Python tests pass. Target arithmetic and remaining acceptance keep T13 blocked; no complete-checker retry, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved the focused JALR redirect-target transport proof, retaining asserted capture validity, instruction identity, original environment and short limits.

- 2026-11-16: T13 in progress -> blocked, Codex; focused target-PC predicate passes exact guard qualification and sign-extension fault, but sequential proof times out at unchanged 120-second cap without counterexample. Later proof/cover/fault roles did not run. Repaired shared audit metadata using exact hash-matching immutable snapshots, without rewriting raw results or rerunning proofs. Sixty Python tests and structure check pass; independent review clears harness and metadata repair, not target proof or task acceptance. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user continued with the focused JALR jump-target PC proof, exact pinned-checker guards and independent review. Preserve every acceptance obligation and short limit.

- 2026-11-16: T13 focused return-value continuation completed, Codex; JALR link invariant proves unbounded and original line177 plus helper passes within unchanged 120-second cap. Exact guard qualification, wrong-increment rejection, active x0/nonzero covers and real output-fault witness pass independent review. Fifty-two Python tests and structure check pass. Remaining next-PC/ISA/IF/local gate keep T13 blocked; no complete-checker retry, commit or push. [Report](tasks/reports/T13.md).

- 2026-11-16: T13 resumed, Codex; user approved targeted JALR return-value invariant and independent review. Preserve original guards, all acceptance obligations and the 120-second cap; no complete ISA sweep.

- 2026-11-15: T13 in progress -> blocked, Codex; approved all-retirement JALR address invariant and original address assertion pass with exact guard qualification, real fault/witness checks and independent review. One complete JALR attempt retains all original checks but times out at unchanged 120 seconds without counterexample; no sweep or further retry. Forty-seven Python tests and structure check pass. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 resumed, Codex; user approved one targeted all-retirement JALR source-address invariant, exact checker-guard qualification and independent review. Existing ISA checks and 120-second limit unchanged.

- 2026-11-15: T13 in progress -> blocked, Codex; approved exact ISA partitioning implemented and independently audited. Six of 33 JALR assertions pass, source-register-address assertion times out at unchanged 120 seconds without counterexample; fail-fast stops all later jobs. Forty-one Python tests and structure check pass. Original assertions, assumptions, depths, covers and fault obligations remain intact. No commit/push. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 blocked -> in progress, Codex; user approved splitting critical ISA assertions into smaller proof jobs. Preserve the complete assertion inventory, assumptions, depth 144/check cycle 64, 120-second limits, covers and real fault controls; no acceptance waiver.

- 2026-11-15: T13 in progress -> blocked, Codex; approved exponent repair passes timing, exact whole-top equivalence, complete FPU regression and 51 core tests. All 28 integration safety assertions prove unbounded under the authenticated FPU contract; fault/covers and local compressed/CSR proofs pass independent review. Twelve untouched modules prove against rebuilt T11. Three critical ISA bounds and one jump induction trial time out at 120 seconds without counterexamples; further retries stopped. Remaining refinement/local gate incomplete; no commit/push. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 blocked -> in progress, Codex; user approved the narrow internal FPU exponent-subtractor repair through the existing HardFloat patch, exact arithmetic proofs and revalidation. All timing and verification limits unchanged.

- 2026-11-15: T13 in progress -> blocked, Codex; core repairs and architectural/random/flight lockstep pass, default profile exactly matches tagged T11. Remaining timing path is internal FPU arithmetic outside the brief's interface-glue scope; narrow patch approval requested after independent review. Integration formal remains unresolved at unchanged short timeouts. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 blocked -> in progress, Codex; user approved registered F decode and continued timing closure with all checks and limits unchanged.

- 2026-11-15: T13 in progress -> blocked, Codex; initial integrated timing fails the unchanged budget. Independent review supports registered F decode; awaiting approval required by the brief. Work uncommitted; acceptance incomplete. [Report](tasks/reports/T13.md).

- 2026-11-15: T13 not started -> in progress, Codex; user assigned next task with independent review and commit/push. Preserve T11 baseline tag, implement F integration first, keep checks focused without another hours-long ISA sweep.

- 2026-11-15: T12 in progress -> done, Codex; focused gate and independent review pass. Exact emitted-RTL identity qualifies canonical upstream-byte restoration. All operations retained; unchanged timing budget passes. [Report](tasks/reports/T12.md); T13 not started.

- 2026-11-15: T12 not started -> in progress, Codex; user assigned standalone FPU with independent review and commit/push. Focus checks on T12 per user direction; no repeated whole-core formal sweep.

- 2026-11-15: T11 in progress -> done, Codex; user directed critical verification instead of another hours-long sweep. Final CSR repair passes exact leaf/core/top and registered revision proofs, all 58 simulations, block/whole-top timing and current arch/flight lockstep. Independent review approved evidence transport from the prior complete ISA sweep. Full CI stopped at user direction, not reported as passed; no gate condition changed. [Report](tasks/reports/T11.md).

- 2026-11-15: T11 full local gate passed the registered ISA sweep but stopped on standalone CSR timing. An equivalent mstatus-only RMW repair passes configured proofs, CSR tests and block/whole-top timing; independent review approves. Exact CI check set retained with timing moved earlier; fresh full gate running. No commit/push or gate change.

- 2026-11-15: T11 gated-top qualification continues. Actual RF/core/ICG timing
  measured over budget; no timing acceptance claimed. Reference benchmark uses
  identical constraints and is explicitly comparison-only. Independent review
  approved clock-gate STA checks and benchmark isolation after clock-identity
  regression repair. Registered core directed tests and baseline leaf proofs
  pass; current full ISA, integration, timing and local CI remain pending.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved adding the shared GF180 clock-gate wrapper, verification and target bindings. All prior acceptance obligations remain; no gate marked complete.

- 2026-11-15: T11 in progress -> blocked, Codex; approved ID normalization passes all 20 configured cases and faults. Faithful Chisel core proves 163 states/one structural multiplier with all active translated children; core tests and fresh independent review pass. Required project clock-gate wrapper is absent; adding a shared implementation exceeds T11's interface-bundle allowance. [Scope proposal](../../hw/ip/perf_core/CLOCK-GATE-DEPENDENCY.md) awaits approval. Registered execution integration and full acceptance remain open; no commit/push or gate change.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved the single ID analysis-copy qualifier removal. Hash/location/reversal qualification and independent review precede acceptance; original failure and all verification obligations remain recorded.

- 2026-11-15: T11 in progress -> blocked, Codex; approved CSR normalization passes fresh proof/faults, tests, timing and independent review. ID translation tests/timing pass, but a separate unique-case selector produces the same unrestricted-input proof conflict. Single-qualifier trial independently proves 15 states with all faults rejected; explicit extension approval pending. Remaining core/top scan finds no more selectors of this kind. [Investigation](../../hw/ip/perf_core/ID-PRIORITY-INVESTIGATION.md). No commit/push or gate change.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved removing the two unique qualifiers only from the generated CSR formal-analysis copy. Preserve source priority, vendor/production RTL, all input combinations, proof obligations and negative controls; qualify hashes, receipts and affected proof paths before acceptance.

- 2026-11-15: T11 in progress -> blocked, Codex; decoder, LSU, IF, controller and WB checkpoints pass focused checks and fresh independent reviews. CSR tests/timing pass, but original formal reference optimizes unique selectors differently for conflicting inputs. Independent review reproduces a priority-preserving analysis-copy proof and recommends explicit baseline approval; original failure retained, no gate/decision changed, no commit/push. [Investigation](../../hw/ip/perf_core/CSR-PRIORITY-INVESTIGATION.md).

- 2026-11-15: T11 in progress, Codex; approved registered execution passes induction, production-binding equivalence, fault rejection, completion covers, simulation and independently reproduced timing. Independent review approved this scope; decoder/core work continues and whole-core acceptance remains open. No gate or decision changed.

- 2026-11-15: T11 blocked -> in progress, Codex; user approved registered execution boundaries, extra ALU/divide cycles and necessary pipeline-control changes, with transaction/refinement and retirement checks. Timing limits and other acceptance requirements remain unchanged.

- 2026-11-14: T11 in progress -> blocked, Codex; approved iterative multiplier implemented and independently reviewed; all 21 simulations, 13 configured equivalence checks and new arithmetic/division proofs pass. Revised local gate exits 1 on unchanged 24.96 ns limit: multdiv 25.093014 ns and EX 25.975801 ns. Awaiting explicit ALU/divide retiming decision; whole core incomplete, no commit/push. [Report](tasks/reports/T11.md).

- 2026-11-14: T11 in progress, Codex; user approved iterative multiplier state/latency change with reviewed arithmetic/transaction refinement and whole-core retirement comparison. Faithful baseline and unchanged-module exact proofs retained; no timing limit waived. Local CI checkpoint passed before redesign.

- 2026-11-14: T11 in progress, Codex; qualified explicit combinational buffering/sizing and electrical-limit rejection without changing STA constraints. ALU, counters, register file, compressed decoder, fetch FIFO and prefetch parent pass leaf proofs/timing with independent review. Multiplier/divider structural equivalence passes including sign-fault rejection; its timing fails and is under investigation. Full-core acceptance remains open.

- 2026-11-14: T11 blocked -> in progress, Codex; user approved combinational repairs for measured timing failures throughout T11 after retaining each faithful baseline proof. Ports, state, reset, cycle behavior, timing budgets and verification checks remain unchanged.

- 2026-11-14: T11 in progress -> blocked, Codex; authorized counter repair passes equivalence, simulation, timing and independent review. Continued with faithful ALU, which proves equivalent but fails unchanged timing budget; independent review confirms path and stateless timing-mode checks. Awaiting decision on broader same-state combinational repairs; no whole-core acceptance or commit claimed.

- 2026-11-14: T11 blocked -> in progress, Codex; user approved localized combinational counter increment restructuring, preserving registers, ports, reset, cycle behavior, timing budget and all verification checks.

- 2026-11-14: T11 in progress -> blocked, Codex; configured CSR/counter leaf proofs and simulations pass, but mapped 64-bit mcycle timing fails the unchanged T09 budget. Stopped before structural improvements; measured evidence and proposed next decision in report. No full-core or CI acceptance claimed.

- 2026-11-14: T11 blocked -> in progress, Codex; user approved preserving inherited combinational boundaries for the faithful baseline, necessary production-isolation/gated-clock timing support and core timing-ledger entries. Timing budgets and acceptance checks remain unchanged.

- 2026-11-14: T11 readiness rechecked after T10 completion, Codex; comparison interfaces are available. Registered-output/no-retiming conflict and production timing/isolation scope remain unresolved; report refreshed, no RTL started.

- 2026-11-14: T10 continuation in progress -> done, Codex; all-module and whole-core unbounded self-equivalence, candidate formal/lockstep paths and real source-fault rejection, pinned architectural/flight suites, and required divide stress pass. Full local gate and final independent review pass; limitations and measured runtimes recorded in the report/ledger. No Chisel conversion started and no gate checked.

- 2026-11-14: T10 done -> in progress, Codex; user assigned harness completion after review found T11 acceptance interfaces missing. Sequential/whole-core self-equivalence is the first required checkpoint; no Chisel conversion authorized in this continuation.

- 2026-11-14: T11 not started -> in progress -> blocked, Codex; independent readiness review confirmed the inherited combinational-output conflict and required verification/timing scope extensions. Concrete clarification in [report](tasks/reports/T11.md); no RTL or acceptance changes, no gate checked.

- 2026-11-14: T10 in progress -> done, Codex; revised D44 acceptance passes: 66 original bounded partitions and four bounded/arithmetic-abstracted ALTOPS partitions with covers and both multiply faults, integer lemmas, required real-arithmetic stress, physical isolation and full local gate. Independent review reproduced checks and found no actionable issues. Optional C failed frontend feasibility without a valid model; raw arithmetic remains unresolved as approved. See report. No physical/verification gate checked.

- 2026-11-14: T10 blocked -> in progress, Codex; user assigned implementation of D44 with revised acceptance, independent review and commit/push on completion.

- 2026-11-14: Plan change, Claude at user's direction; D44 approves splitting the multiply instruction check (ALTOPS integration check, integer lemma, required stress simulation; unabstracted check kept as non-gating diagnostic). T10 and T11 briefs and the formal plan updated; K22 added. The T10 brief's May change list now includes the reference-rejection guard in tools/timing/check.py, which its step 3 already required. T10 stays blocked until the split is implemented and its checks pass. No gate checked.

- 2026-11-14: T10 remains blocked, Codex; user explicitly authorized commit/push of the incomplete checkpoint so another agent can review. This does not approve task completion or change any acceptance check.

- 2026-11-14: T10 in progress -> blocked, Codex; investigation favors arithmetic solver complexity: the unchanged MUL property also times out at a separate 1,800-second diagnostic limit. Fixed the independently reviewed QEMU shutdown-trace boundary bug; 17,680 multiplication products pass independent comparison, all 66 non-multiply partitions have bounded/cover/fault evidence across runs, and nonzero-destination multiply faults are detected. Normal acceptance remains unchanged and unsuccessful; no commit/push. See report and investigation note.

- 2026-11-14: T10 blocked -> in progress, Codex; user requested investigation of bug versus insufficient proof time. Running isolated extended-time diagnostics and independent multiplication checks; acceptance limits remain unchanged.

- 2026-11-14: T10 in progress -> blocked, Codex; exact adaptation documented and reviewed, both frontends/equivalence/retirement checks pass. Corrected reference formal run completed 46 bounded/covered partitions with rejected faults, then MUL/MULH/MULHSU reached the unchanged 600-second solver limit. Full CI did not pass. Physical ingress hook awaits scope approval; no commit/push. See report and core formal ledger.

- 2026-11-14: T10 blocked -> in progress, Codex; user authorized removing the exact unused declaration in the generated analysis copy and requested a durable bug-triage note. Originals remain byte-exact; adaptation hash/bytes/reversal recorded in dv/core/ADAPTATIONS.md and adaptations.json. All acceptance checks and independent review still required.

- 2026-11-14: T10 not started -> in progress, Codex; user assigned next task with the same checks, independent review and commit/push workflow. Preparing reference pin, front-end elaboration and comparison harnesses; no Chisel core conversion started.
- 2026-11-14: T10 in progress -> blocked, Codex; independently reproduced slang failure on input-dependent unused declaration initialization in Ibex v2.1.0. Sources remain unmodified; no suppression or compatibility patch applied. Awaiting explicit decision under the brief's front-end stop condition; no commit/push.

- 2026-11-14: T09 not started -> in progress, Codex; user assigned the next task with independent review, full local checks, commit and push. Required OpenSTA and pinned GF180 slow-corner libraries are available.
- 2026-11-14: T09 in progress -> blocked, Codex; independent review reproduced RegBlock coverage timing at 44.802906 ns against 24.96 ns. Kept the failing check intact; requested scope to fix core timing, prohibited by T09's current brief. No commit/push.
- 2026-11-14: T09 blocked -> in progress, Codex; user explicitly approved extending T09 to repair RegBlock timing while preserving behavior, budget, all checks and independent review before commit/push.
- 2026-11-14: T09 in progress -> complete, Codex; timing self-test and full local gate passed. Coverage RegBlock measured 19.390715 ns under unchanged 24.96 ns ceiling after authorized decode repair; independent fresh-context review reproduced the result and found no actionable issues. No architecture gate changed.

- 2026-11-14: T05 in progress -> done, Codex; approved partial-write contract implemented; Python/Chisel model comparisons, formal proofs/faults/covers, full local gate and independent verification passed. [Report](tasks/reports/T05.md). No physical gate checked.

- 2026-11-14: T05 blocked -> in progress, Codex; user approved byte-masked rwh writes and complete-field wo writes with transaction-wide error suppression; specification clarified and implementation resumed.

- 2026-11-14: T05 in progress -> blocked, Codex; independent review confirmed unspecified byte-strobe behavior for rwh/wo; concrete clarification submitted to user under the brief's ambiguity stop rule. [Report](tasks/reports/T05.md). No implementation started.

- 2026-11-14: T05 not started -> in progress, Codex; user assigned next task with independent review, commit and push; checking register-map contract before implementation.

- 2026-11-14: T07 in progress -> done, Codex; pinned direct Chisel build, behavioral negative control, native BTOR2 and SymbiYosys induction/fault/cover checks passed; merged-tree local gate and independent verification passed. [Report](tasks/reports/T07.md). Remote D43 plan retained; no gate checked.

- 2026-11-14: Plan change, Claude at user's direction; D43 removes the NoC and restores a whole-chip bus with domain bridge and mailbox. D3/D14 superseded. T03/T04/S2 blocked -> withdrawn. T14 added, unstarted. R-NOC replaced by R-BUS; K8 closed, K14 rewritten, K21 added. No gate checked.

- 2026-11-14: T07 not started -> in progress, Codex; user assigned pinned Chisel build and formal smoke, routine tooling repairs, independent review, commit and push.

- 2026-11-14: T06 in progress -> done, Codex; clean upstream gates/export, mapped area within the original tolerance, exact architectural storage, local gate and independent verification passed. [Report](tasks/reports/T06.md). Remote plan update merged; no gate checked.

- 2026-11-14: Plan change, Claude at user's direction; D2 revised to an equivalence-checked Ibex conversion. T10 split into T10 (reference/harness), T11 (conversion), T12 (FPU), T13 (F integration/improvements); S1 now depends on T13. Risks K19/K20 added. Briefs unstarted; no gate checked.

- 2026-11-14: T06 not started -> in progress, Codex; assigned next unblocked task, Maven preflight passed, pinned baseline checkout prepared.

- 2026-11-14: T02 in progress -> done, Codex; repeated exact QEMU matches, unchanged historical summary, negative controls and local gate passed; independent review verified the fixes. [Report](tasks/reports/T02.md). No gate checked.

- 2026-11-14: T02 blocked -> in progress, Codex; user approved scoped LF enforcement and routine tooling repairs with checks intact, independent review, commit and push.

- 2026-11-14: T02 in progress -> blocked, Codex; baseline shell launch failed on Windows CRLF checkout. Independent review confirmed a scoped LF-attribute fix; awaiting approval under the failed-command stop rule.

- 2026-11-14: T02 not started -> in progress, Codex; user assigned continued plan implementation with independent review and automatic commit/push after verification.

- 2026-11-14: T08 in progress -> done, Codex; immutable image built, clean rebuild reproduced inventory/versions/smoke, local gate passed; [report](tasks/reports/T08.md).
- 2026-11-14: T01 in progress -> done, Codex; scaffold acceptance passed, fresh-context reviewer verified fixes and found no remaining issues; [report](tasks/reports/T01.md). No gate checked.

- 2026-11-14: T01 not started -> in progress, Codex; preparing the assigned scaffold while the T08 image builds; acceptance remains dependent on T08.

- 2026-11-14: T08 blocked -> in progress, Codex; user authorized resolving bootstrap/build failures until built, retaining verification.

- 2026-11-14: T08 in progress -> blocked, Codex; initial Docker build failed on CA trust before package installation; awaiting approval to correct bootstrap. T01 not started.

- 2026-11-14: T08 not started -> in progress, Codex; user assigned T08/T01 with local-only checks and a fresh-context review afterward.

- 2026-11-13: PLAN01 in progress -> done, Codex; documentation checks passed, [report](tasks/reports/PLAN01.md). No implementation started.

- 2026-11-13: PLAN01 not started -> in progress, Codex; user assigned plan/brief reconciliation and authorized commit/push, no implementation.
- 2026-11-13: User decisions D1-D42 reconciled; superseded/deferred items explicitly identified. No gate checked.
- 2026-11-13: T07 brief rewrite removes its stale async blocker; task remains unstarted. T03/T04/S2 record sanitized-source blockers. T08/T09/T10 briefs added, unstarted.
- 2026-11-13: Original tracker created; no implementation task started.

- 2026-11-19: User approved keeping packetData full-rate while applying D58 pre-enable capture to all packet flags. Resumed implementation and strict engine/wrapper equivalence; no consumer or state-match obligation relaxed.

- 2026-11-19: D58 engine relational equivalence is unresolved at the existing 120-second cap. Recorded model statistics and independent proof-tool findings; no unchanged retry. Wrapper proof, cadence/constraints, timing and frozen checks not reached under the explicit stop rule. Candidate remains uncommitted; full tier and post-placement recheck unrun.

- 2026-11-19: User requested continuation after D58 timeout. Resuming proof-guard hardening and exact model simplification under unchanged assertions, assumptions and solver cap; timing remains gated on equivalence.

- 2026-11-19: D59 approved a 15 ns USB single-cycle warning ceiling and continuation. D58 equivalence, cadence/reset proofs and mapped capture certificates pass; measured consume paths close. The 14.726458 ns RX path is now a warning. Continuing unchanged regressions and frozen acceptance; all other obligations remain.

- 2026-11-19: Froze D58/D59 implementation after independent proof/constraint review. Starting unchanged USB aggregate followed by fast CI; existing packet and physical qualification failures remain explicit. Full tier is not run.

- 2026-11-19: First D59 frozen USB run passes all 19 simulations and focused proofs; packet/physical qualification remains failed. Fixed standalone fixture cadence emission binding and re-proved exact engine/wrapper equivalence. Applying the already-approved diagnostic-only standalone SIE option, preserving its failed measurements; final frozen fast tier will repeat the USB aggregate. Full tier unrun.

- 2026-11-19: D58/D59 final frozen fast02 repeats all 19 USB simulations, exact equivalence, focused formal, CDC and timing. No engine/wrapper setup class exceeds its approved failure limit; packet proofs, hold/reset and prior sampling/exception qualification retain failed USB/fast status. Source inventories match; standalone SIE remains a complete failed diagnostic under the approved option. Reporting-only updates follow; full tier/post-placement timing unrun. T19 blocked, no merge.

- 2026-11-19: User resumed the pad/reset boundary contract only. Modeling documented pad/board estimates and synchronized reset-release clock-to-Q, preserving asynchronous assertion, all limits and physical hold checks; no RTL or packet-proof change.

- 2026-11-19: T19 pad/reset contract implemented and independently reviewed. Frozen boundary fast/USB rerun reproduces timing and exact source hashes; all 19 simulations, focused formal and equivalence pass. Conditional AON removal artifact resolved; pad hold, peer RDC/physical qualification, packet and prior sampling obligations remain. USB/fast failed, full tier/post-placement unrun; T19 blocked, no merge.

- 2026-11-19: User assigned packet-proof decomposition under E1/E2/E3, recorded D60-D62. Continue at 20bcb66, preserving the boundary-contract descendant of requested base 33cf251. No assertion/cap change; independent reset-return and assumption review requested.
- 2026-11-19: D60-D62 decomposition reaches its stop: six original claims prove at 16 bytes and four additional claims at eight bytes; IN progress/OUT integrity remain unresolved. Arbitrary later resets retained because the literal reset-return premise is false. E1 closes no additional proof; E2 skipped. Real small covers/faults and independently audited lemma chains pass. Freeze for USB/fast and full-size simulation; no T19 completion or merge.
- 2026-11-19: First packet frozen run passes all 19 full-size simulations but exposes a historical-fixture compile failure from the new proof-only emitter. Reviewed fixture-only exclusion restores engine/wrapper equivalence and every control with exact pinned baseline HDL hashes. Sources refrozen for fast02; no production RTL, assertion, assumption or cap change. Two original packet proofs and existing physical/qualification items remain open.

- 2026-11-19: Final packet snapshot fast02 preserves exact source hashes; all 19 USB simulations, focused formal, CDC, equivalence and fault controls pass. Six original claims prove at full size and four at the small model with full-size simulation; IN progress/OUT integrity remain unresolved. Frozen USB/fast fail packet and existing physical/prior qualification; full tier unrun. Independent review clears an incomplete checkpoint for publication only; no merge.

- 2026-11-19: User authorized focused IN progress/OUT integrity lemma work from b6326d0 and explicitly prohibited CI. Original assertions, resets, environments and caps remain; focused formal checks and independent review only.

- 2026-11-19: Focused IN progress proves at 16 bytes and OUT integrity at eight bytes with authenticated lemma chains and real faults. Original common-reset packet inventory now closes (seven full-size, five small-model plus prior full-size simulation). Focused audits and ten guard tests pass; no production RTL/assertion/environment/cap change. CI/aggregate/timing/simulation not run by user instruction; T19 remains blocked on composition, integration and physical/prior qualification. No merge.

- 2026-11-19: User assigned independent reset/SIE composition closure from b2e9845; no CI. Checking actual producer/reset guarantees and phase-general packet properties, including zero-byte ACK and malformed overlength OUT; no new environment assumption or RTL change authorized.
- 2026-11-19: Independent reset/SIE follow-up from b2e9845: eleven epoch claims qualify (five full-size, six proved at small model and simulated at full size); actual SIE safety, wrapper bindings, four real-traffic/fault tests, two seeded throughput tests and fourteen proof-tool unit tests pass. OUT ownership/integrity remains open after the triage budget; combined-occupancy lemma proposed for an additional approved attempt. No production RTL change, CI tier, USB aggregate or merge.
- 2026-11-20: User approved one additional unchanged-cap OUT occupancy-lemma attempt, then prioritized all non-proof T19 work first. The extra proof is deferred. Completing acceptance evidence plumbing and physical handoff within the standalone USB scope; no CI or solver run.
- 2026-11-20: Non-proof priority follow-up from 8084eb2: fail-closed evidence integration and independent physical handoff review complete. Twelve tooling tests and two unchanged seeded throughput tests pass; audited inventory retains eleven closed claims and unresolved OUT integrity. No production RTL/limits/assertions/assumptions changed; no solver, CI tier or USB aggregate run. Physical hold/RDC/placement and prior proof qualification remain; extra approved proof attempt deferred. Incomplete review checkpoint only, no merge.
- 2026-11-20: User assigned physical hold/RDC/post-placement validation, explicitly without CI. Extending the pinned physical runtime, checking destination reset-release structure, and measuring the unchanged USB wrapper with physical interconnect; no acceptance limit or RTL change authorized.
- 2026-11-20: T19 physical validation measured on d8d51ac plus bound tooling: standalone wrapper place/CTS/route and fifteen PVT/RC cases complete; FP13.691668/12.5ns, FC16.003422/15ns and FF15.516943/15ns fail unchanged ceilings. Local reset-chain timing is positive, boundary hold/removal and physical/RDC signoff remain open. Ten focused fault tests and independent reviews qualify an incomplete diagnostic checkpoint; no RTL changes, CI, aggregate, proof or merge. [Physical report](../spec/usb-physical-validation.md).
- 2026-11-20: D63: user explicitly authorized merging codex/t19-usb-review into main with known issues for collaborative follow-up, superseding prior no-merge instructions. T19 remains incomplete; failed timing/proof/physical obligations and current no-CI instruction remain. Merge handoff records work areas; unrelated uncommitted core/S1 work excluded.
- 2026-11-20: User directed the approved remaining OUT lemma work after D63 merge. On codex/t19-out-occupancy, prove widened non-overlapping pointer occupancy, derive the checker count bound and retry dependent ownership/integrity only with exact-model receipts. Existing reset/environment/assertions/caps remain; no CI or timing-policy change.
- 2026-11-20: OUT occupancy follow-up from 0216c37 proves pointer non-overlap and combined counts, then ownership/data/pipeline and original integrity at eight bytes. Real overflow/data faults and reset/traffic covers qualify; read-only audit accounts for all twelve independent-reset claims (five full-size, seven small-model with source-matched full-size simulation). Independent review is clear; seventeen packet tooling tests and twelve evidence tests pass. No production RTL, original assertion, environment or cap change; no CI, aggregate, timing or simulation rerun. T19 remains blocked on the handoff's physical/timing and prior sampling/exception obligations.
- 2026-11-23: T33 continuation implemented and independently reviewed D85 production threshold tests and passive reset-phase observation; exact production HDL identity preserved. Fresh mapped timing/area checks and paired flight retention pass in their stated scopes. The original 138/139 regression failure and routine oracle/compile/mapping repairs are preserved. Composition proof budgets remain exhausted, CDC/RDC inventory is not qualification, and final regression/CI are unrun; T33 remains in progress, not complete.

- 2026-11-24: PLAN05 Phase2 scoped progress: production dormant/WFI retention,512-word macro tests, lite/QSPI/bridge-reset and migratedI1 eight-case integration pass. Intermediate mapped main worst69.15168ns against75ns; estimated chip12.040010510mm2/headroom0.879989490, larger SRAM options do not fit. SPI positive proof deferred at120s; GPIO retention checker remains unqualified after coalescing diagnostics. Independent scoped review complete; boot/test migrations, phase-end fast checks and T36 remain open. No implementation commit/push.

- 2026-11-24: PLAN05 Phase2 migration: loader/PWM retirement inventories complete, actual OpenOCD reset-halt/32kHz-AON/in-flight reset pass, lite/performance client and watchdog phase tests pass. Both AON strap timing screens have no failures (approved USB warning remains); independently reviewed area/leakage. Final warm-pin SBA matrix and missing-pin control pass. Scoped proof deferrals remain; Phase2 fast and T36 implementation follow.

- 2026-11-24: PLAN05 first frozen Phase2 fast run failed after measured 1,732.076684 s at stale USB build.sbt evidence, following passing active checks through I2C. No USB functional failure or new solver timeout. Refreshing unchanged proof/simulation bindings and the actual buffered bus physical fixture; no acceptance waiver, implementation commit or push.
