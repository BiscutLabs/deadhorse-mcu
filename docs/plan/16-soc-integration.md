# 16 SoC integration

Written 2026-11-20, after T05–T19 delivered the first set of blocks. This
document is the plan for putting them together into one chip. It does not
start implementation, freeze the architecture or mark a gate complete.
[03-architecture.md](03-architecture.md) remains the architectural authority;
this document says how the top level is assembled, verified and measured.

## Where the blocks stand

| Block | Task | State on 2026-11-20 | Mapped area (pre-layout) |
| --- | --- | --- | --- |
| Performance core, RV32IMFC faithful profile | T10–T13 | Built; T13 blocked on one integration proof | 0.815 mm2 measured (T13 round 2) |
| Bus fabric, domain bridge, mailbox | T14 | Done, four approved unproved deferrals | 0.251 mm2 estimated from measured parts |
| Three UARTs and wake monitors | T15 | Done | 0.153 mm2 estimated from measured parts |
| SPI host | T16 | Done | 0.064 mm2 measured |
| I2C controller | T17 | Done, eight approved unproved deferrals | 0.047 mm2 measured |
| Lite I2C recovery loader | T18 | Done | 0.097 mm2 measured |
| USB CDC-ACM | T19 | Merged with open timing, physical and proof items | 0.198 mm2 measured (wrapper) |
| Memory sizing | S3 | Done | 16 KiB + 3 KiB SRAM; macro footprint estimated 2.96 mm2 |
| Timers and timebase | none | Not briefed | |
| Actuator block | none | Not briefed; draft spec only | |
| GPIO and pin mux | none | Not briefed | |
| Interrupt routing | none | Not briefed | |
| DMA | none | Not briefed | |
| Boot ROM, QSPI flash and XIP | none | Not briefed | |
| JTAG debug, both cores | none | Not briefed | |
| Lite core (RISCay adoption) | none | Not briefed | |
| Power, clock and reset control, watchdogs | none | Not briefed | |
| Analog: oscillators, supply monitor | none | Not briefed | |

The logic measured so far sums to about 1.62 mm2 mapped (estimated: a sum of
separate block measurements, not an integrated result). The chip-level
budget in [08-physical-verification.md](08-physical-verification.md) predates
the FPU and must be rebuilt by T20.

## Approach: a growing chip, never a big-bang merge

1. **One top, built early.** T20 creates the reference SoC in
   `hw/top/reference/` now, with the blocks that exist. Blocks that do not
   exist yet appear as **stubs with their final ports**: they answer their
   address window with bus errors, drive interrupts and wake requests
   inactive, and hold outputs in their reset-safe state.
2. **Each later block brief replaces its own stub.** The last deliverable of
   every new block brief is: remove the stub, connect the block in the
   reference SoC, and pass the SoC system tests. T20 does not wait for them.
3. **Firmware runs end to end at every stage.** Each stage boots a program in
   simulation and exercises the connected blocks through the four-target
   test interface of [13-test-environment.md](13-test-environment.md).
4. **One source of truth for the map.** Addresses, interrupt numbers, clock
   and reset domains, bus masters and pins live in one machine-readable file,
   `hw/top/reference/soc.yaml`, described by `docs/spec/soc.md`. Address
   decode, the interrupt map and firmware headers are generated from it;
   nothing restates it by hand.
5. **Measure the chip, not just blocks.** Whole-SoC area, per-domain timing
   and flight-loop cycles on the integrated bus are reported at every stage.

## Integration stages

| Stage | Contents | Exit evidence | Owner |
| --- | --- | --- | --- |
| I0 Skeleton | Performance core, boot ROM model, SRAM model with the macro interface, local memory path, main fabric, UART | Program boots from ROM, prints over UART in simulation; ISA lockstep still passes inside the SoC | T20 |
| I1 Existing peripherals | SPI, I2C, mailbox and domain bridge, AON bus with retained-SRAM model and recovery loader, USB (stub by default, real block as a build variant), stubs for everything else | SPI IMU and I2C barometer models read by firmware; mailbox round trip to a lite-core stand-in; recovery load over I2C; USB loopback on the real-USB variant | T20 |
| I2 Flight I/O | Timers, actuator block, interrupt routing, GPIO and pin mux | Timer-driven control loop closes against the airframe model in simulation, with actuator outputs checked by the independent checker | Block briefs, then T20 checks |
| I3 Always-on domain | Lite core, power/clock/reset control, watchdogs, sleep and wake | Lite boots first and releases the performance core; reset containment and sleep/wake tests from 06 | Block briefs |
| I4 Boot and debug | Boot ROM content, QSPI flash and XIP, DMA, JTAG for both cores | Two-image boot and recovery; debug halt/step/memory access; DMA with ownership checks | Block briefs |
| I5 Chip | Pad wrapper, test mode and scan, analog macro views, FPGA build | Pad-level simulation; FPGA bring-up of the I2 flight loop | Physical and analog briefs |

## Rules the top level must follow

- **The performance core does not fetch through the fabric.** The fabric in
  [../spec/bus.md](../spec/bus.md) registers request, grant and response and
  admits one transaction at a time. Instruction fetch and performance-SRAM
  data accesses use a local memory path with Ibex's native one-cycle grant
  (boot ROM, performance SRAM, later XIP). Only peripheral and remote windows
  go through the fabric. S1's cycle counts were measured with ideal memory,
  so T20 must re-measure the flight loop on the integrated memory path and
  report the difference.
- **Every crossing uses the shared CDC primitives** in `hw/lib`, and a
  structural check enumerates crossings and rejects any other kind.
- **Resets follow 06**: asynchronous assertion, per-domain synchronous release
  through the shared reset-release block, and the endpoint-quiescent
  handshake required by the bus contract wherever a target can keep work
  across reset.
- **Stubs are honest.** A stub never returns success for an access it cannot
  perform, and the SoC tests list which windows are still stubbed.
- **The block's own verification stays with the block.** SoC-level formal
  covers connectivity, address decode, interrupt wiring and reset sequencing,
  not re-proofs of block internals.

## Clock plan (open: Q15)

| Domain | Frequency | Source | State |
| --- | --- | --- | --- |
| Main (performance core, fabric, peripherals) | about 8–9 MHz | Open | The faithful core meets timing at 9 MHz (T13); 9 MHz is not an integer division of 48 MHz |
| USB | 48 MHz | External clock, ±0.25% required by full-speed USB | Required by T19 |
| AON | nominal 32 kHz | Internal LF oscillator | Not designed |
| JTAG | TCK | External | Not designed |

Q15 must be decided before G1: either derive main from the 48 MHz input
(48 / 6 = 8 MHz, one external source), or keep a separate source for main
(internal HF or a second input) and run at 9 MHz. T20 parameterizes the main
frequency, reports timing and loop time at both 8 and 9 MHz, and does not
choose. The loop-rate target is related (Q16): measured worst control-step
cycles are 4,350 fixed point and 8,973 hard float on the faithful core, so
1 kHz with hard float leaves almost no time for the rest of the firmware.

## Interrupts (provisional)

Ibex provides machine timer, software, external, non-maskable and fifteen fast
interrupt inputs. T20 assigns peripheral interrupts to fast inputs in
`soc.yaml`, reserves the D43 future-bridge interrupt, and routes the
performance watchdog pre-warning (when it exists) to the non-maskable input.
The map is provisional until G1.

## Pins (provisional)

T20 records the provisional pin list in `soc.yaml` from the budget in
[07-peripherals-memory-boot.md](07-peripherals-memory-boot.md): three UARTs,
SPI with two chip selects, I2C, QSPI with boot and logging selects, nine
actuator outputs, USB D+/D-, JTAG, external clock and reset, remaining GPIO.
It checks that all baseline interfaces can be used at the same time. The
exact map is frozen at G1, not by T20.

## Block briefs still needed

These are required before stages I2–I5 can complete. Write each from the
approved contracts; each ends by replacing its stub in the reference SoC.

| Order | Brief | Stage | Notes |
| --- | --- | --- | --- |
| 1 | Timers and microsecond timebase | I2 | Loop tick, capture for sensor timestamps |
| 2 | Actuator block | I2 | From the [actuator draft](../spec/actuator-block.md); timeout and publication policy questions (Q13) stay open and must be parameters |
| 3 | Interrupt routing and GPIO/pin mux | I2 | Pin mux reset-disabled outputs (D39) |
| 4 | Lite core adoption from RISCay | I3 | D1; boot order and retained SRAM |
| 5 | Power, clock and reset controller, watchdogs | I3 | D37 containment, glitch-free clock selection (D35), wake capture |
| 6 | Boot ROM, QSPI flash controller and XIP | I4 | Two images, CRC, recovery (D34) |
| 7 | JTAG debug for both cores | I4 | D5, D41 |
| 8 | DMA | I4 | D25 |
| 9 | Analog macros and supply monitor | I5 | Long lead; start early in parallel |
| 10 | Physical flow and pad ring | I5 | Coldfoot flow restructured (D9) |

## Measurement the SoC must report

- Mapped area per block and whole SoC, and the rebuilt chip budget against
  the 12.92 mm2 core area, with unbuilt blocks as named allowances.
- Worst path per clock domain against the existing 60% rule, and the USB
  routed-timing status carried from T19.
- Flight-loop cycles per iteration (mean and worst, fixed and hard float) on
  the integrated memory path, compared with S1/T13.
- The list of stubbed windows and every deferred proof inherited from blocks.
