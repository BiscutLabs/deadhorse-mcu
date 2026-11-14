# 04 Carry-over from RISCay-MCU

Assessed at RISCay-MCU `4671317`. RISCay describes itself as "a development
design, not ready for fabrication". This document sorts it into what Deadhorse
keeps, adapts and replaces.

## State of RISCay today

| Area | State |
| --- | --- |
| CPU | RV32E, one instruction in flight. No CSRs, interrupts, multiply or compressed instructions. `ecall`, `ebreak` and faults halt the core until reset |
| Memory | 2 KiB program and 1 KiB data SRAM (three 1024x8 macros, 0.466 mm2), four byte accesses per word |
| Bus | Bespoke single-master fabric with hand-written MMIO decode |
| Peripherals | I2C target (host loader only), receive-only SPI ADC player, GPIO. Flash is bit-banged through GPIO by the boot ROM |
| Sleep | Retained clock-stop sleep, always-on LF timebase and watchdog, wake on tick, GPIO level or I2C START |
| Analog | LF oscillator (7.7 Hz), fast RC oscillator (8.6 to 17 MHz), bandgap supply monitor: schematic candidates, no layout |
| Async flow | Generated desynchronization from the clocked netlist: 1.163 times mapped area, ten banks. Worst modelled recurrence 358.9 ns at SS without wires. Two generated-chip tests still fail (`BOOT_NOT_SLEEPING`, `LOADER_COMPLETION_DEADLINE`). Mutex unqualified |
| Physical | Routing study on a 2.35 by 2.53 mm outline. No pad ring, ESD, debug port or production test |

## Keep as is

| Asset | Why |
| --- | --- |
| **Desynchronization generator and its tools** (`tools/`, bank map, primitive registry, timed-graph checks) | This is the main reusable asset. It turns any clocked netlist into bundled-data logic with a measured area ratio |
| **Evidence discipline:** area ledger, one row per commit, negative controls, per-corner delay sizing, distinction between reference and generated-chip passes | Prevents the failure modes the async skill documents |
| **Approved ratio ceilings** (1.17 mapped, 1.20 repaired, 1.25 storage, 5.5 percent control) | Become R-PHY-3 |
| **Boot chain:** generic boot ROM, A/B slots, golden image, CRC and compatibility checks, programming lock, I2C host loader | Verified and application-neutral |
| **Reset sequencing:** supply qualification, 100,000-cycle hold, ordered release, watchdog recovery semantics | Verified digitally; the hard part of reset is already specified |
| **Sleep and wake protocol:** work gate, grace interval, wake sources, host wake probe | Becomes the deep-sleep mode of region M |
| **Firmware conventions:** startup, linker scripts, stack and guard checks, pinned toolchain | Extended, not replaced |
| **GF180 physical scripts:** OpenROAD patches, slew policy, repair flow, bounded capture trees | Reused for regions A and M |

## Adapt

| Asset | Change |
| --- | --- |
| RV32E `ClockedCore` | Becomes the lite core. Add a minimal CSR set, one interrupt input, `wfi` mapped onto the existing WAIT ([03-architecture.md](03-architecture.md)) |
| `ClockedPowerReset`, `ClockedHousekeeping` | Become region A's power, watchdog and timebase block. Timebase re-specified for a 32 kHz source |
| Memory fabric protocol | Kept as the local bus protocol. Decode becomes generated from a register description |
| SRAM wrapper | Byte-serial access was chosen for area with a 1 KiB memory. The performance core needs word access. Re-evaluate the macro choice (1024x8 at 0.155 mm2/KiB, 512x8 at 0.189 mm2/KiB, or a wider macro) |
| SPI ADC player | Kept for battery sensing, owned by the lite core |
| I2C target | Kept for the host loader. The planned register-pointer host interface (RISCay follow-up B) is adopted instead of the framed loader if it lands first |
| LF oscillator | Redesigned for a nominal 32 kHz. The 300 megohm, 0.1 mm2 resistor was sized for a few hertz at minimum power; a faster source needs less resistance |
| Fast RC oscillator | Gains a trim register and becomes the HF reference for island T |
| Always-on / application ownership split (RISCay follow-up A) | Implemented in Deadhorse as regions A and M. This is where that proposal lands |

## Replace

| RISCay item | Replacement |
| --- | --- |
| RV32E core as the only CPU | Ibex RV32IMC as the performance core |
| Bit-banged flash boot | QSPI flash controller with execute-in-place |
| No interrupts, traps halt | Machine-mode interrupts on both cores |
| No debug port | Debug access gateway; JTAG debug module as decision D5 |
| I2C target only | I2C controller added |
| No UART, SPI controller, USB, timers, actuator outputs | Island T and island U ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)) |
| Frozen four-phase BD and two-phase Click hand implementations | Not carried over. Deadhorse has one clocked reference and one generated async design |

## Do not carry over

- The three parallel implementations (clocked, BD, Click). They were a
  research comparison. Deadhorse maintains **one clocked reference SoC** and
  **one generated design**, and every test runs on both.
- The hand-written contract documents for native BD stages
  (receipts, returns, publication slots). The generated flow made them
  historical.
- Groundlark board profile and battery-supervisor assumptions.

## Import method

Decision D1 chooses between two ways to bring RISCay code in.

| Option | How | For | Against |
| --- | --- | --- | --- |
| **A. Dependency** (recommended) | Deadhorse depends on RISCay-MCU at a pinned commit for the desync tools and shared Chisel, the way RISCay pins chisel-async | No fork to keep in sync; fixes flow both ways | RISCay must expose its tools as a library; some refactoring there |
| B. Fork and prune | Copy the kept directories, delete the rest | Fast start, full freedom | Two diverging copies of the generator within weeks |

Under option A, RISCay-MCU remains the open methodology demonstrator and
Deadhorse is the product that consumes it. Changes to the generator are made
upstream and pinned here.

## Problems inherited, which Deadhorse must close

These are open in RISCay and block any product built on it. They head the risk
list in [10-decisions-and-risks.md](10-decisions-and-risks.md).

1. **Throughput.** The generated design's modelled recurrence is 358.9 ns.
   R-CPU-1 needs roughly 70 to 100 ns at two to three cycles per instruction.
2. **Mutex qualification.** Deep sleep stops the main region through a
   filtered mutex whose 1 FIT target is not established.
3. **Generated-chip failures.** Both failing tests are throughput deadlines,
   so they follow from item 1.
4. **No routed timing.** Every async margin so far is zero-wire or
   schematic-level.
5. **Analog has no layout.** Oscillators and supply monitor are schematics.
