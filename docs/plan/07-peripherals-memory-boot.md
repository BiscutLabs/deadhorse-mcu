# 07 Peripherals, memory, boot and debug

## Peripheral set

Every peripheral is ordinary synchronous logic in the main domain: its
registers and FIFOs sit on the local bus and its bit-level timing counts
`clk_main` directly. There is no crossing inside a peripheral.

| Peripheral | Count | Source | Notes |
| --- | --- | --- | --- |
| UART | 3 | Adopt an open core | 8N1, up to 921,600 baud, RX and TX inversion, 16-byte RX FIFO, start-bit wake |
| SPI controller | 1 | Adopt | Modes 0 and 3, at least 4 MHz, two chip selects, burst read into a FIFO so a 14-byte IMU frame is one command |
| I2C controller | 1 | Adopt | 100 and 400 kHz, clock stretching, bus-stuck recovery |
| I2C target | 1 | RISCay | Host loader, unchanged |
| SPI ADC player | 1 | RISCay | Battery voltage and current, owned by the lite core |
| QSPI flash controller | 1 | Adopt | Execute-in-place read path plus a register path for erase and program. Two chip selects: boot flash and logging flash |
| USB FS device | 1 | Separate implementer; integrated last | CDC-ACM. Its own 48 MHz clock domain. See the reservation below |
| Timers | 4 capture/compare + 1 microsecond timebase | New, small | Counted on `clk_main` |
| Actuator block | 9 channels | New | See below |
| GPIO | Remaining pads | RISCay | Wake on level |
| Interrupt controller | 1 per core | Adopt with the core | Sources: data-ready pin, UART, SPI done, timer, USB |

"Adopt" means: take an existing, verified, permissively licensed clocked
design and put our generated register block in front of it. A Chisel implementation is preferred. A
SystemVerilog one is vendored unmodified behind a Chisel black box. "New"
blocks are written in Chisel.

### Actuator block

The one substantial new peripheral. It exists so the CPU never bit-times an
output.

- **Nine channels**, each with a mode: servo PWM, ESC PWM, DShot, or GPIO.
- **Shared tick** derived from the HF reference: 2.4 MHz gives eight ticks per
  DShot300 bit and 0.42 microsecond PWM resolution. DShot600 needs 4.8 MHz.
- **Shadow registers and one commit.** Firmware writes nine values, then one
  commit register. The block latches all nine at the next frame boundary
  (R-CTL-3).
- **Frame trigger:** free-running at a programmed rate, or a fixed offset
  after the IMU data-ready edge
  ([06-power-clock-reset.md](06-power-clock-reset.md)).
- **DShot frame** built in hardware from an 11-bit throttle and a telemetry
  bit, including the checksum.
- **Failsafe** values and modes per channel, entered autonomously and left
  only by a keyed re-arm.
- Bidirectional DShot (RPM telemetry) is not in the prototype.

### USB reservation

USB is being implemented outside this plan and is the last block integrated.
Everything it needs is reserved at architecture freeze (G1), so it can be
dropped in without moving anything else.

| Reserved | Amount | Status |
| --- | --- | --- |
| Floorplan region | About 0.5 mm2 placed, at a die edge next to its pads, held as a placement blockage | Assumed (0.2 to 0.3 mm2 mapped at 55 percent); replaced by the implementer's figure |
| Pads | D+, D-, pull-up enable | In the pad budget below |
| Clock | 48 MHz from the clock pad, with its own clock tree | Assumed; confirm what the implementation needs |
| Reset | Its own reset domain, released after the main domain | |
| Bus window | One block in the generated register map; one interrupt line to each core's controller | |
| Wake | One wake input for bus resume | |

Integration contract, to be agreed with the implementer in Phase 0:

- **The boundary is the USB clock domain's edge, with one crossing:** transmit and receive
  byte FIFOs with handshakes, a status register, an interrupt and a wake
  line. Nothing else crosses.
- **A stub with the same ports exists from Phase 2.** It reports "not
  attached" and leaves the pads as inputs. Every test runs against the stub
  until the real block arrives; USB tests are added on delivery.
- **Deliverables:** clocked RTL or a hardened macro, a verification suite we
  can run in CI, timing constraints, clock and reset requirements, and area.
- **Late placement is possible** because the block is self-contained in its own clock domain
  logic behind one crossing. It can be hardened separately and placed in the
  reserved region.
- **Until USB is integrated,** the gateway monitor and the firmware console
  use a UART.
- **Proposed cut-off:** if the block is not integrated by the Phase 4
  floorplan freeze, the region is filled, the pads are tied off as inputs and
  the chip tapes out with the UART gateway.

### Flight logging (R-PER-8)

Tuning a VTOL needs high-rate logs of sensor inputs, setpoints and actuator
outputs. At 1 kHz that is about 64 kB/s.

**Plan: a second flash on the QSPI bus, with its own chip select.**

- One extra pad. The boot flash and the logging flash share clock and data
  lines; each has a chip select.
- A page write occupies the bus only while its 256 bytes are shifted in,
  roughly 50 to 100 microseconds at 12 to 24 MHz in quad mode. The chip then
  programs internally for up to a few milliseconds with the bus free, so
  in-place execution from the boot flash continues.
- The controller arbitrates per transaction: execute-in-place reads and log
  writes interleave, and a read never waits longer than one page transfer.
- The part is a 64 MiB or larger SPI NAND or NOR, for 10 minutes at full
  rate with margin. NAND is cheaper per byte and writes faster; it needs
  bad-block handling in firmware.
- Firmware keeps a ring buffer of about 2 KiB in SRAM and writes whole pages
  from a low-priority task. The control loop only copies a record into the
  buffer. If the buffer fills, records are dropped and counted, never
  blocked on.
- Logs are read back on the ground through the gateway.

**Next best, and the fallback: stream over a UART.** At 921,600 baud a UART
carries about 92 kB/s, enough for the full record. It needs no chip change,
but it takes one of the three UARTs or shares the telemetry link at a
reduced rate, and it needs an external logger or a ground station in range.
The FPGA prototype uses this first, since it needs nothing new.

Not chosen: an SD card in SPI mode (write stalls of tens to hundreds of
milliseconds and a large buffer), a logging flash on the IMU's SPI bus (it
would contend with the 1 kHz sensor read), and logging to the boot flash
itself (an erase there would stall in-place execution).

## Memory

| Memory | Size | Area (estimated from the 1024x8 macro at 0.155 mm2/KiB) | Retained in deep sleep |
| --- | --- | --- | --- |
| Performance SRAM | 16 KiB baseline, 32 KiB option | 2.49 mm2, 4.97 mm2 | Yes |
| Lite program + data SRAM | 2 + 1 KiB | 0.47 mm2 | Yes |
| Boot ROM | A few hundred bytes of logic | Small | n/a |
| External QSPI NOR flash | 2 MiB or more | Off-chip | n/a |

Why 16 KiB is plausible: the measured control loop is 3.8 to 5.6 KiB of code
with 780 bytes of state. The hot set also needs the interrupt handlers, the
IMU and actuator drivers and the estimator's helper tables. The remainder of
the firmware (USB stack, configuration, navigation, telemetry formatting)
runs in place from flash.

### Execute in place

A random 32-bit fetch over QSPI costs a command, address and dummy phase
before data: on the order of 20 or more SCLK cycles, so roughly 1 to 2
microseconds at 12 to 24 MHz. Sequential fetches streamed under one command
are several times cheaper. Cold code therefore runs at well under 1 MIPS,
which is acceptable only for code outside the control loop. Spike S3 measures
this with the real firmware split and decides whether a small prefetch buffer
or a larger SRAM is the better use of area.

The linker script assigns sections: `.hot` (copied to SRAM at boot), `.text`
(in place), `.data`/`.bss` (SRAM). A build check fails if anything reachable
from the control-loop interrupt lies outside `.hot`.

### SRAM macro choice

RISCay's wrapper reads a 32-bit word as four byte accesses, which was the
right trade for 1 KiB. For the performance core it would quadruple load and
fetch time. Options, decided in spike S1 alongside the core:

1. Four byte-wide macros in parallel per bank (word access, same macro).
2. A wider macro if one is available and qualified for the shuttle.
3. Keep byte-serial access and accept four clock cycles per word, if S1
   shows the clock is fast enough to afford it.

## Boot

RISCay's chain, with two changes.

1. Reset, supply qualification, ordered release (unchanged).
2. **Lite core boots first** from the boot ROM: validates its own image in
   flash (A/B, golden fallback, CRC, compatibility), loads it to lite SRAM.
3. Lite core loads trim words for both oscillators from flash.
4. **Lite core releases the performance core**, whose ROM stub validates the
   main image, copies `.hot` to SRAM and jumps.
5. If no valid image exists, the I2C host loader and the gateway both
   accept a programming session.

Changes from RISCay: the QSPI controller replaces GPIO bit-banging, and there
are two images. The programming lock and its reset semantics are unchanged.

CRC gives integrity, not authenticity. Signed images are out of scope for the
prototype and noted as open question Q7.

## Debug

| Path | Capability | Cost | Status |
| --- | --- | --- | --- |
| **Gateway monitor** | Register and memory access for bring-up | | Planned for the prototype |
| **JTAG debug module** | Standard RISC-V external debug: GDB, breakpoints, single-step | Four pads, a small TCK clock domain, the debug module, core debug support | Decision D5 |

The gateway monitor is enough to bring up silicon. A product that third parties program needs
the JTAG path. Ibex already supports the standard debug module, so the cost
is mostly pads and a small extra clock domain.

## Pad budget

Against the wafer.space 1x1 ring (40 bidirectional, 12 input-only, 2 analog,
plus clock and reset pads).

| Function | Bidirectional | Input-only |
| --- | --- | --- |
| Actuators | 9 | |
| UART x3 | 3 (TX) | 3 (RX) |
| SPI controller (SCLK, MOSI, CS0, CS1 / MISO) | 4 | 1 |
| I2C controller | 2 | |
| I2C target (SDA / SCL) | 1 | 1 |
| ADC player (CS, SCLK / MISO) | 2 | 1 |
| QSPI flash (boot), plus one chip select for the logging flash | 7 | |
| USB (D+, D-, pull-up enable) | 3 | |
| IMU data-ready | | 1 |
| JTAG (TDO / TCK, TMS, TDI) | 1 | 3 |

The 48 MHz input uses the clock pad; the 32 kHz crystal option uses the two
analog pads. The pad budget must be reviewed against the board design.
