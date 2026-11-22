# Status

Single progress tracker. Last updated: 2026-11-21.
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

## Tasks

| | ID | Item | Owner | Depends on | Report |
| --- | --- | --- | --- | --- | --- |
| [x] | PLAN01 | [Reconcile decisions](tasks/PLAN01-reconcile.md) | Codex | User approvals | [Report](tasks/reports/PLAN01.md); documentation only |
| [x] | PLAN02 | [General-purpose MCU scope](tasks/PLAN02-general-mcu.md) | Codex | User direction D69 | [Report](tasks/reports/PLAN02.md); documentation checks and independent review pass; no RTL or CI |
| [~] | PLAN03 | [SoC consolidation and tape-out planning](tasks/PLAN03-soc-consolidation.md) | Codex | D72–D76; existing T20–T30 evidence | B2 consolidation verified/reviewed; separate ADC retirement and B3 fast CI next. [Report](tasks/reports/PLAN03.md). No new block work |
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
| [!] | T19 | [USB CDC-ACM](tasks/T19-usb.md) | Codex | T05, T07, T08, T09, T14 | [Report](tasks/reports/T19.md): all twelve independent-reset packet claims qualify (five full-size, seven small-model with full-size simulation). Routed setup, hold/RDC, physical signoff and sampling/exception obligations remain. Acceptance incomplete; no CI |
| [!] | T20 | [Reference SoC integration, I0–I1](tasks/T20-soc-integration.md) | Codex | T05, T07, T09, T13, T14–T19, S3 | [Pin-contract checkpoint](tasks/reports/T20.md#gpio-adc-timer-contract-continuation-2026-11-21): GPIO/ADC/timer logical contracts and safe I1 bindings complete; focused simulations/map tests, pad proofs/faults and both top emissions pass with independent review. Physical pin fit, system/CDC and I1 timing/area remain; local main changes, no CI |
| [x] | T21 | [GPIO, timers and retained ADC](tasks/T21-flight-io.md) | Codex | T05, T07, T09, T14, T20 interfaces | [Report](tasks/reports/T21.md): functional GPIO/ADC/D68 split timers and SoC profile complete; frozen focused checks and independent review pass; CI unrun by user instruction, physical/T20 qualification separate |
| [x] | T22 | [General-purpose PWM](tasks/T22-pwm.md) | Codex | D69, T21, T20 interfaces | [Report](tasks/reports/T22.md): generic PWM and SoC profile implemented; frozen focused simulations, scoped proofs, setup/electrical timing and independent review pass. DMA controller, physical qualification and CI remain open |
| [!] | T23 | [Basic DMA controller](tasks/T23-dma.md) | Codex | D25, D69, T22, T20 interfaces | [Report](tasks/reports/T23.md): RTL, frozen 62 tests/four top emissions and block timing pass; one range proof unresolved; helper approval pending; no CI |
| [x] | T24 | [Limited GPIO output pin mux](tasks/T24-pinmux.md) | Codex | D39, D69, T21–T23 interfaces | [Report](tasks/reports/T24.md): functional RTL, frozen 71 tests/four top emissions, 18 assertions and timing pass; independently reviewed; no CI; physical qualification separate |
| [!] | T25 | [Clocked lite core adoption](tasks/T25-lite-core.md) | Codex | D1, T06, T14, T18, T20/T24 interfaces | [Report](tasks/reports/T25.md): real AON hart/loader binding, 28 frozen tests/four top emissions, baseline/control proofs and mapped timing pass; independent review clear. Full ISA/machine formal open after capped ADDI triage; no CI |
| [!] | T26 | [Digital watchdog/reset supervision](tasks/T26-watchdog.md) | Codex | D70, T20/T22/T24/T25 interfaces | [Report](tasks/reports/T26.md): D70 RTL, frozen functional/top checks, output-disable proofs and corrected mapped setup/electrical screens pass; independent review clear. Full-width watchdog proof unresolved; physical qualification and CI open; uncommitted on main |
| [x] | T27 | [Raw ADC acquisition](tasks/T27-adc-raw.md) | Codex | D69, D71, T21 | [Report](tasks/reports/T27.md): raw production ADC and retired0x14 ABI complete; frozen focused tests, component proofs, wrapper timing and four whole tops independently verified. No CI; physical qualification separate; local main changes |
| [x] | T28 | [Lite-first performance release](tasks/T28-boot-release.md) | Codex | T25/T26/T27 interfaces, plans07/16 | [Scoped digital handoff verified](tasks/reports/T28.md); production boot/physical qualification open, no CI |
| [x] | T29 | [Bounded QSPI command interface](tasks/T29-qspi-command.md) | Codex | Plans04/07, T28 interfaces | [Command-mode RTL verified](tasks/reports/T29.md); frozen focused checks and independent review pass; XIP/boot/physical open, no CI |
| [x] | T30 | [Native QSPI read path](tasks/T30-qspi-xip.md) | Codex | Plans03/07, T29 interfaces | [Native flash RTL verified](tasks/reports/T30.md); frozen focused checks and independent review pass; production boot/physical open, no CI |
| [-] | T31 | [Retained locked-image restart](tasks/T31-retained-loader-restart.md) | n/a | D73 | Withdrawn; loader frozen at existing feature set and reset policy. [Historical proposal](tasks/reports/T31.md) |
| [-] | S2 | Interconnect study | n/a | n/a | Withdrawn by D43 |
| [x] | S3 | [Memory](tasks/S-spikes.md#s3-memory) | Codex | T02, T07, T08 | [Report](tasks/reports/S3.md): representative allocations/model checks and independent review pass; fast 29/29 with inherited T14 deferrals, full not run |
| [ ] | S4 | [Latency/test](tasks/S-spikes.md#s4-latency-and-test-access) | unassigned | S1, T08, T09 | |

Former P0-f/P0-g now have briefs T08/T09. P0-a actuator split and P0-b parts
are approved decisions D26-D33, not bench qualification. P0-c USB boundary is
approved; implementer delivery/sizing remains open. P0-d die-link agreement is
deferred. P0-e analog work has not started and still needs an assigned brief.

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
