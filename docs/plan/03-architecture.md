# 03 Architecture

This is the proposed target. It is not frozen until the Phase 1 spikes report
([09-roadmap.md](09-roadmap.md)) and the decisions in
[10-decisions-and-risks.md](10-decisions-and-risks.md) are approved.

## Block view

## Timing regions

Deadhorse is globally asynchronous. It has two clockless regions and two small
clocked islands. Each clocked island exists because of a written obligation.

| Region | Timing | Contents | Why |
| --- | --- | --- | --- |
| **A, always-on** | Desynchronized bundled data | Lite core, its SRAM, watchdog, low-frequency timebase, power and reset control, wake logic | Must make progress while everything else is stopped |
| **M, main** | Desynchronized bundled data, stoppable | Performance core, local bus, SRAM, flash XIP, peripheral registers, interconnect | Bulk of the logic; stopped in deep sleep |
| **T, timed I/O** | Clocked on the trimmed HF reference, gated when idle | UART, SPI, I2C shifters and bit timers; actuator pulse and DShot generators; capture timers | *Obligation:* these blocks generate and measure absolute time on external pins. A self-timed region has no stable period to count |
| **U, USB** | Clocked at 48 MHz, off unless USB is attached | USB full-speed serial interface engine and endpoint FIFOs | *Obligation:* the host defines the bit clock; recovery needs a 48 MHz reference within 0.25 percent |

Island U is being implemented by a separate owner and is the last block
integrated. Until it arrives it is a stub behind the same crossing, and the
gateway runs over a UART. Its reservation is specified in
[07-peripherals-memory-boot.md](07-peripherals-memory-boot.md).

Rules carried over from RISCay:

- **One crossing per subsystem.** Region M meets island T at one register and
  FIFO boundary per peripheral, not per signal or per message type.
- **Producer and consumer move together.** A block is never split so that
  half is clocked and half is clockless with a bridge and two copies between.
- **Clocked storage is counted per clock on every change.** Islands T and U
  are the only places the count may be non-zero outside the watchdog and
  timebase, and the count has a ceiling set at architecture freeze.
- **Crossings between independently timed regions** (A to M, M to T, M to U)
  are either a blocking handshake, which needs no arbitration, or a
  synchronizer with a stated MTBF. A mutex is used only where a region must
  choose between two independent requests, and only once the mutex is
  qualified ([10-decisions-and-risks.md](10-decisions-and-risks.md), K1).

## Cores

### Performance core

Proposal: adopt **Ibex** (lowRISC, Apache-2.0, RV32IMC, two-stage) in its
clocked form as the reference, and generate the bundled-data version with
RISCay's desynchronization flow. Reasons:

- It already has interrupts, CSRs, `wfi`, a debug interface and an existing
  verification record, none of which RISCay's core has.
- RISCay's flow generates the async netlist from an unchanged clocked netlist,
  so the core's source language should not matter. Spike S1 confirms this.
- Its two instruction and data ports are single-outstanding request/response
  interfaces, close to RISCay's `MemoryRequest`/`MemoryResponse` fabric.

The alternative, growing RISCay's `ClockedCore` to RV32IMC with interrupts,
means writing and verifying a new core. It stays as the fallback if Ibex
desynchronizes badly.

### Lite core

Proposal: RISCay's existing RV32E `ClockedCore`, extended with the minimum
needed to be useful as an always-on supervisor:

- a small CSR set (`mstatus`, `mtvec`, `mepc`, `mcause`) and one external
  interrupt input, so traps no longer halt the core;
- RISCay's existing blocking WAIT kept as the sleep primitive, exposed as
  `wfi`;

This is the one piece of core RTL we expect to write.

## Local bus and register map

The performance core has a private local bus for memory and for the
loop-critical peripherals.

- **Protocol:** single outstanding request and response with byte masks and an
  error bit, as in RISCay. Instruction and data ports are arbitrated onto it.
- **Decode is generated, not hand-written.** RISCay's fabric decodes MMIO
  offsets in a hand-written 334-line module. Deadhorse keeps one register
  description as the single source for RTL decode, the C header and the
  documentation.

### Ownership

Every peripheral has exactly one local owner.

| Resource | Owner | Reachable by |
| --- | --- | --- |
| IMU SPI, actuator block, timers, UART 0-2, I2C controller | Performance core | Lite core, gateway |
| Main SRAM, flash XIP | Performance core | Gateway (debug, programming) |
| Watchdog, LF timebase, power control, wake mask, GPIO wake | Lite core | Performance core |
| Battery ADC player, I2C target (host loader) | Lite core | Performance core, gateway |
| USB | Gateway | Both cores |

The lite core needs to read sensors during deep sleep. Rather than duplicate
SPI and I2C in region A, it requests the HF reference on demand, as RISCay's
restartable service oscillator already allows (startup at most 100
microseconds), and uses the island T peripherals. Whether one
dedicated low-power sensor port in region A is worth its area is decision D7.

## What sleeps

| Mode | Region A | Region M | Island T | Island U | Entered by |
| --- | --- | --- | --- | --- | --- |
| Run | Running | Running | Clocked on demand | On if attached | Default |
| Idle | Running | Quiescent, handshakes at rest | Gated | Suspended | `wfi` on the performance core |
| Deep sleep | Running or waiting | Stopped, retained | HF reference off | Off | Lite core, after the performance core parks |

Details and wake rules are in
[06-power-clock-reset.md](06-power-clock-reset.md).
