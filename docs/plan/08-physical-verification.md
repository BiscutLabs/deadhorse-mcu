# 08 Physical implementation and verification

## Process and slot

| Item | Value | Source |
| --- | --- | --- |
| Process | GF180MCU, 3.3 V devices and I/O | RISCay, Coldfoot |
| Cells | 7-track. RISCay pins `gf180mcu_fd_sc_mcu7t5v0`; Coldfoot uses `gf180mcu_as_sc_mcu7t3v3`. One must be chosen (decision D15) | RISCay, Coldfoot |
| SRAM | `gf180mcu_ocd_ip_sram` 1024x8 (155,414 um2) and 512x8 (96,985 um2) | Coldfoot `tile_pkg.sv`, RISCay |
| Slot | wafer.space 1x1: die 3.932 by 5.122 mm, core 12.92 mm2 | Coldfoot slot file |
| Pad ring | 40 bidirectional, 12 input-only, 2 analog, clock and reset pads | Coldfoot pad document |

Both source projects already target this process, and Coldfoot has a pad ring,
slot template and LibreLane configuration for this shuttle. Deadhorse reuses
those for the chip level and RISCay's OpenROAD scripts for the clockless
regions (decision D9).

## Area budget

The following component estimates do not establish whole-chip fit.

| Block | Mapped (mm2) | Basis |
| --- | --- | --- |
| Region A: lite core, power, timebase, loader | 0.55 to 0.65 | RISCay clocked reference is 0.532 mm2 for its whole MCU |
| Performance core | 0.6 to 1.0 | Assumed two to three times RISCay's CPU; S1 measures it |
| Local bus, flash controller, register front ends | 0.2 to 0.3 | Assumed |
| SRAM: 16 KiB + 3 KiB | 2.96 | Macro footprints |
| Analog macros: two oscillators, supply monitor | 0.3 to 0.5 | Assumed; RISCay's LF resistor alone is about 0.13 mm2 today |

USB is integrated last. The floorplan reserves its region, pads and clock
route from G1, and the region stays a placement blockage until the block
arrives ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)).

## Analog and mixed-signal deliverables

None of these has a layout today.

| Macro | Starting point | Work |
| --- | --- | --- |
| LF oscillator, 32 kHz, trimmable | RISCay schematic (7.7 Hz) | Redesign, trim DAC, layout, extraction, mismatch and noise, corner campaign |
| HF reference, trimmable, restartable | RISCay schematic | Trim DAC, layout, extraction, stop and start glitch-freedom at the extracted level |
| Supply monitor and reset hold | RISCay schematic | Threshold review against the board rail, layout, slow-ramp behaviour |
| Mutex | chisel-async GF180 schematic and RISCay's experimental layout | Metastability characterisation to a defensible failure rate |
| C-elements, matched-delay cells | RISCay primitive registry | Layout or mapping to library cells, per-corner characterisation |
| Crystal driver, 32 kHz (if D6) | None | New |
| USB pad arrangement | Standard 3.3 V bidirectional pads with external series resistors and pull-up | With the USB implementer: validate drive, slew and input thresholds against the full-speed electrical spec |
| Pad ring, ESD, power pads | Coldfoot's wafer.space ring | Re-assign per the pad budget |

RISCay's LF design requires the GF180 high-resistance poly option. Confirm the
shuttle includes it before investing in the redesign (open question Q5).

## Verification strategy

### One reference, one generated design

Deadhorse maintains a **clocked reference SoC** and the **generated
bundled-data SoC**. Every test body runs on both with the same oracle. A pass
on the reference is never reported as a pass on the generated chip. This is
RISCay's rule; Deadhorse drops RISCay's other two hand-built variants.

### Layers

| Layer | What | Source |
| --- | --- | --- |
| Adopted IP | Each adopted block keeps its upstream suite, run in our CI | Ibex, serial cores; USB from its implementer |
| ISA | RISC-V architectural tests; lockstep comparison with an instruction-set simulator for both cores | Standard suites |
| SoC, directed | Boot, both images, sleep and wake from every source, reset during every committed operation | RISCay chip-test bodies extended |
| SoC, firmware | The real flight firmware against a simulated airframe and sensor models | New |
| Async-specific | Transfer checks against original register semantics, marked-graph conformance, randomised delays within stated bounds, per-corner recurrence against every external deadline | RISCay tools |
| Negative controls | Shorten a matched delay, bypass a guard, break a crossing: a check must fire | RISCay practice |
| Formal | Check clock crossings and actuator failsafe entry | Project harnesses |
| FPGA | Clocked reference on an FPGA board, flying a hardware-in-the-loop simulation, then driving real ESCs, servos and sensors on the bench | Coldfoot's FPGA flow |

### Throughput budgets

RISCay's two open failures are both deadlines missed at slow-corner speed.
Deadhorse states every external deadline up front and checks it with
worst-corner delays:

| Deadline | Budget |
| --- | --- |
| Control loop complete before the actuator latch offset | Under 800 microseconds at 1 kHz |
| IMU frame read | Under 150 microseconds |
| UART receive service before FIFO overflow at 921,600 baud | 16 bytes, about 170 microseconds |
| I2C target sampling at 400 kHz | Handled in island T, no longer a region-speed constraint |
| USB endpoint response | Handled in island U; region M must service FIFOs within the host's retry tolerance |
| Watchdog service | Counted on the LF timebase, not on region cycles |

Moving bit-level sampling into island T removes the class of failure where a
slow async cycle misses a bus sampling window.

## Production test (R-PHY-4)

Clockless logic has no scan clock, so this needs a decision early (D8).

Proposal: use the fact that the design is **desynchronized**. Every register
is a master and slave latch pair under a local controller. In test mode the
controllers are bypassed and the latch enables are driven from two
non-overlapping test clocks on pads, which turns regions A and M back into an
ordinary level-sensitive scan design that standard pattern generation can
target. Controllers, matched delays and the mutex are then covered by
functional tests at speed. Islands T and U take ordinary scan.

SRAM is tested by a march routine run by the lite core from ROM, with results
readable through the gateway.

Spike S4 checks that the test-mode override fits inside the control-area
ceiling and does not add a per-bit cost.

## Signoff gates

From RISCay's contract and the async design rules. None may be waived without
written approval.

1. Electrical repair (slew, capacitance) clean at every corner before any
   timing number is trusted.
2. Relative timing closed per bank at every corner with routed min and max
   RC: bundling as max-delay, hold as min-delay including capture-tree spread.
3. Composed paths checked (launch, capture, acknowledge, re-open), not only
   local stages.
4. Every capture-enable tree bounded (at most 16 loads per branch, equal
   depth); every clock sink in the islands enumerated independently of the
   tree tool.
5. Reset distribution: assertion, release order and quiescence shown on the
   routed design.
6. Mutex and every synchronizer with a stated failure rate.
7. Ratios against the clocked reference within R-PHY-3.
8. DRC, LVS, antenna clean on the full chip including analog macros and ring.
9. Generated-chip suite fully passing at the slow corner with no weakened
   assertion or deadline.
10. Deep-sleep current from extracted leakage within R-PWR-3, or the
    requirement formally revised.
