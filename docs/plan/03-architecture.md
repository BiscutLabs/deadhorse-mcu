# 03 Architecture

Deadhorse is an entirely clocked, synchronous design (decision D17,
2026-11-13). The earlier clockless plan, which generated bundled-data logic
from a clocked reference, is abandoned. There are no handshake controllers,
matched delays, mutexes or desynchronized regions in the chip. One contained
exception is allowed later, for the lite core only (decision D18, below).

This is the proposed target. It is not frozen until the Phase 1 spikes report
([09-roadmap.md](09-roadmap.md)) and the decisions in
[10-decisions-and-risks.md](10-decisions-and-risks.md) are approved.

## Block view

## Design language

Deadhorse is written in **Chisel** (decision D16), as RISCay-MCU's clocked
design is. With the clockless plan abandoned, chisel-async is no longer a
dependency.

| Part | Language | Notes |
| --- | --- | --- |
| SoC top, clock and reset control, both domains' logic | Chisel | The RTL that is simulated, prototyped on FPGA and taped out is the same source |
| Lite core, local bus, register blocks, peripherals, actuator block, timers | Chisel | New or carried over from RISCay's clocked Chisel design |
| Clock-domain crossings | Chisel | Two-flop synchronizers and asynchronous FIFOs from one reviewed library block |
| Performance core (if Ibex, decision D2), USB | SystemVerilog | Vendored, unmodified, instantiated through a Chisel `BlackBox` |
| Tools, register-map front end, reference models | Python | No hardware |

## Clock domains

Three clock domains. Everything inside a domain is ordinary synchronous
logic closed with standard static timing analysis.

| Domain | Clock | Contents | Stops when |
| --- | --- | --- | --- |
| **Always-on** | `clk_aon`: the 32 kHz LF oscillator, or a divided HF clock when the lite core asks for speed | Lite core, its SRAM, watchdog, timebase, power, reset and clock control, wake logic | Never |
| **Main** | `clk_main`: the HF reference, 12 to 24 MHz | Performance core, local bus, SRAM, flash controller, all serial peripherals, timers, actuator block, interconnect | Deep sleep: the HF source is stopped |
| **USB** | `clk_usb`: 48 MHz from a pad | USB serial interface engine and endpoint FIFOs | USB not attached |

Within the main domain, clock gates switch off whole subsystems that are
idle: the performance core at `wfi`, each peripheral when disabled.

Rules:

- **Two crossings only.** Always-on to main; main to USB, at the USB block's FIFOs. Each is an asynchronous
  FIFO or a handshake built on two-flop synchronizers, with a stated MTBF.
- **One crossing block.** Every crossing instantiates the same reviewed
  module. No ad hoc synchronizers.
- **Clock switching is glitch-free.** The always-on domain's clock mux and
  every clock gate use the library's integrated clock-gating cell; the HF
  source stops only after a complete final pulse, as RISCay's oscillator
  already does.
- **Peripheral bit timing needs no crossing.** UART, SPI, I2C and the
  actuator generators count `clk_main` directly. The "timed I/O island" of
  the clockless plan no longer exists as a separate thing.

The USB block is being implemented by a separate owner and is the last block
integrated. Until it arrives it is a stub behind the same crossing, and the
gateway runs over a UART
([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)).

## Cores

### Performance core

Proposal: adopt **Ibex** (lowRISC, Apache-2.0, RV32IMC, two-stage) as a
vendored SystemVerilog block behind a Chisel black box. Reasons:

- It already has interrupts, CSRs, `wfi`, a debug interface and an existing
  verification record, none of which RISCay's core has.
- It is a clocked core used as designed. The risk the clockless plan carried,
  that a generator might not accept it, is gone.
- Its instruction and data ports are single-outstanding request/response
  interfaces, close to RISCay's `MemoryRequest`/`MemoryResponse` fabric.

The alternative, growing RISCay's Chisel `ClockedCore` to RV32IMC with
interrupts, keeps the whole design in Chisel at the cost of writing and
verifying a core. Spike S1 measures both.

Speed: R-CPU-1 needs 5 MIPS. At about two cycles per instruction that is a
10 MHz clock, which a two-stage core on GF180 should reach with margin. This
is an expectation, not a measurement; S1 replaces it.

### Lite core

Proposal: RISCay's existing RV32E `ClockedCore`, extended with the minimum
needed to be useful as an always-on supervisor:

- a small CSR set (`mstatus`, `mtvec`, `mepc`, `mcause`) and one external
  interrupt input, so traps no longer halt the core;
- RISCay's existing blocking WAIT kept as the sleep primitive, exposed as
  `wfi`, which gates the core's clock;

On the 32 kHz clock it executes a few thousand instructions per second,
enough to supervise. For bursts of real work it requests a divided HF clock.

#### Option: a coarse Click pipeline (decision D18)

The lite core is implemented clocked first. Once the design is stable, a
clockless version may be built as a drop-in replacement: a coarse Click
pipeline (two-phase bundled data, flip-flop storage, two or three stages),
using chisel-async and RISCay's frozen Click design as the reference. It is
the one place in the chip where a clockless block is allowed.

What it would buy: the core runs at its own speed on demand, with no
oscillator needed for bursts of work and no switching when idle. What it
costs: matched delays to size across corners, an arbiter at the wake-merge
point, and a second physical and test treatment for one block.

To keep the option open, the clocked lite core is built under these rules:

- **A fixed boundary.** The core meets the rest of the always-on domain only
  through its bus port, one interrupt input and
  one wake request. A Click version must fit the same ports.
- **Few stages.** The core keeps one instruction in flight and a small number
  of well-defined register groups, so it maps onto two or three handshake
  stages without restructuring.
- **One wake-merge point.** All wake sources are combined in one place
  outside the core.
- **Shared tests.** The lite core's test bodies do not assume a clock period,
  so the same bodies run on either version, as RISCay's do.
- **Floorplan margin.** The always-on domain's region is sized for the
  larger of the two.

The watchdog, timebase, power and clock control stay clocked in either case.

## Local bus and register map

The performance core has a private local bus for memory and for the
loop-critical peripherals.

- **Protocol:** single outstanding request and response with byte masks and an
  error bit, as in RISCay. Instruction and data ports are arbitrated onto it.
- **Decode is generated, not hand-written.** One register description is the
  single source for the Chisel register block, the C header and the
  documentation.

### Ownership

Every peripheral has exactly one local owner.

| Resource | Owner | Reachable by |
| --- | --- | --- |
| IMU SPI, actuator block, timers, UART 0-2, I2C controller | Performance core | Lite core, gateway |
| Main SRAM, flash XIP | Performance core | Gateway (debug, programming) |
| Watchdog, LF timebase, power and clock control, wake mask, GPIO wake | Lite core | Performance core |
| Battery ADC player, I2C target (host loader) | Lite core | Performance core, gateway |
| USB | Gateway | Both cores |

The lite core needs to read sensors during deep sleep. Rather than duplicate
SPI and I2C in the always-on domain, it restarts the HF source on demand
(startup at most 100 microseconds, as RISCay's service oscillator allows) and
uses the main-domain peripherals. Whether one dedicated
low-power sensor port in the always-on domain is worth its area is decision
D7.

## What sleeps

| Mode | Always-on domain | Main domain | USB domain | Entered by |
| --- | --- | --- | --- | --- |
| Run | Clocked | Clocked; idle subsystems gated | On if attached | Default |
| Idle | Clocked | Performance core gated; peripherals clocked as needed | Suspended | `wfi` on the performance core |
| Deep sleep | Clocked at 32 kHz | HF source stopped; all state retained | Off | Lite core, after the performance core parks |

Details and wake rules are in
[06-power-clock-reset.md](06-power-clock-reset.md).
