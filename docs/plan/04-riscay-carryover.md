# 04 Carry-over from RISCay-MCU

Assessed at RISCay-MCU `4671317`. With the clockless plan abandoned
(decision D17), Deadhorse takes RISCay's **clocked** design and its
supporting pieces, and none of its asynchronous work.

## State of RISCay today

| Area | State |
| --- | --- |
| Clocked design (`designs/clocked/`) | A complete synchronous implementation of the MCU in Chisel: RV32E core, fabric, loader, GPIO, events, housekeeping, I2C target, SPI ADC player, gated work clock, LF watchdog, retained sleep, coordinated reset. Mapped at 0.532 mm2 with 2,977 architectural bits. Passes RISCay's shared test bodies |
| CPU | RV32E, one instruction in flight. No CSRs, interrupts, multiply or compressed instructions. Faults halt the core until reset |
| Memory | 2 KiB program and 1 KiB data SRAM (three 1024x8 macros, 0.466 mm2), four byte accesses per word |
| Bus | Bespoke single-master fabric with hand-written MMIO decode |
| Peripherals | I2C target (host loader only), receive-only SPI ADC player, GPIO. Flash is bit-banged through GPIO by the boot ROM |
| Sleep | Retained clock-stop sleep, always-on LF timebase and watchdog, wake on tick, GPIO level or I2C START |
| Analog | LF oscillator (7.7 Hz), fast RC oscillator (8.6 to 17 MHz), bandgap supply monitor: schematic candidates, no layout |
| Async work | Native four-phase and two-phase designs (frozen), and a generated desynchronized design (active). **Not used by Deadhorse** |
| Physical | No pad ring, ESD, debug port or production test. RISCay's own note on its clocked variant: clock tree, related-clock constraints, CDC, SRAM timing and routed setup and hold all remain to be done |

## Keep

| Asset | Why |
| --- | --- |
| **Clocked SoC design** in Chisel | The starting point for Deadhorse's always-on domain and for its clock, sleep and reset control |
| **Sleep and wake design:** gated work clock, two-flop demand synchronization, grace interval, restartable HF source, asynchronous wake-event logic, host wake probe | Already a clocked design; becomes Deadhorse's deep sleep |
| **Reset sequencing:** supply qualification, 100,000-cycle hold, ordered release, watchdog recovery semantics | Verified digitally and independent of the async work |
| **Boot chain:** generic boot ROM, A/B slots, golden image, CRC and compatibility checks, programming lock, I2C host loader | Verified and application-neutral |
| **Shared test bodies and oracles** | RISCay runs the same tests on every variant; the clocked suites carry over |
| **Firmware conventions:** startup, linker scripts, stack and guard checks, pinned toolchain | Extended, not replaced |
| **Build:** pinned Scala, Chisel, firtool and simulator versions; the run-receipt habit | One toolchain, already proven for this design |
| **Evidence habits:** area ledger with one row per commit, negative controls, measured-versus-estimated labelling | Useful regardless of timing style |

## Adapt

| Asset | Change |
| --- | --- |
| RV32E `ClockedCore` | Becomes the lite core. Add a minimal CSR set, one interrupt input, `wfi` mapped onto the existing WAIT |
| `ClockedPowerReset`, `ClockedHousekeeping` | Become the always-on domain's power, clock, watchdog and timebase block. Timebase re-specified for a 32 kHz source; a second clock domain and a glitch-free clock mux added |
| Memory fabric protocol | Kept as the local bus protocol. Decode becomes generated from a register description |
| SRAM wrapper | Replace performance access with word-wide byte-enabled configurable banks; qualify the macro arrangement (D36) |
| SPI ADC player, I2C target | Kept; owned by the lite core |
| LF oscillator | Redesigned for a nominal 32 kHz |
| Fast RC oscillator | Gains a trim register and becomes the HF reference |

## Replace

| RISCay item | Replacement |
| --- | --- |
| RV32E core as the only CPU | Equivalence-checked Ibex conversion to Chisel, extended to full RV32IMFC and multicycle FPU (D2/D19/D20) |
| Bit-banged flash boot | QSPI flash controller with execute-in-place |
| No interrupts, traps halt | Machine-mode interrupts on both cores |
| No debug port | Unlocked gateway and JTAG debug for both cores (D5/D41) |
| I2C target only | I2C controller added |
| No UART, SPI controller, USB, timers, actuator outputs | New peripherals ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)) |

## Do not carry over

- The desynchronization generator, its bank maps, primitive registry, timed
  graph checks and area-ratio ceilings.
- The native four-phase design and the contract documents of both native
  designs. RISCay's two-phase Click design is kept as a reference only, for
  the optional Click lite core (decision D18).
- The mutex and C-elements. chisel-async and matched-delay cells return
  only if the Click lite core option is exercised.
- RISCay's custom OpenROAD scripts for protected async primitives.
- The Groundlark board profile and battery-supervisor assumptions.

## Import method

D1 approved: one-time pinned import of the clocked design and required support
at RISCay commit `4671317186003740ceb61360ba08c59bbdf10136`. Restructure into
Deadhorse packages/directories/conventions, preserving licences and a provenance
manifest mapping original files to adapted files. No live RISCay/chisel-async
dependency in the new build. T06 reproduces the old baseline in an isolated
checkout; it is not the import task and does not authorize async integration.

Reset behavior is adapted to D37/D69, not copied unchanged: performance reset
preserves AON and peripherals serving surviving owners; lite watchdog resets
the MCU. Generic PWM uses an explicit reset/output-disable contract, without
dedicated actuator failsafe state; current stub reset wiring is unchanged.
Supply monitor gains selectable thresholds/safe startup (D38); old threshold
and hold-cycle values are not frozen. Shared peripheral ownership, DMA and
sleep access are new work with their own tests.

## Problems inherited, which Deadhorse must close

1. **The clocked design has never been through physical implementation.**
   RISCay mapped it for area only.
2. **Analog has no layout.** Oscillators and supply monitor are schematics.
3. **RISCay's full test gate has not been run on a clean machine by this
   project.** Task T06.

The clockless plan's three largest inherited risks (generated-design
throughput, mutex qualification, routed async timing) no longer apply.
