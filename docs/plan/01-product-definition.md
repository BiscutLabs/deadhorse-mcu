# 01 Product definition

## What Deadhorse is

A clocked, synchronous RISC-V microcontroller with two
cores, retained deep sleep, standard serial peripherals, a nine-channel
actuator output block.

The architecture is modelled on two commercial parts, for structure and not
for speed:

- **STM32 H7 class:** a fast application core, a full peripheral set, several
  low-power modes, a debug port.
- **STM32 N6 class (later):** the same MCU with an on-chip accelerator. The accelerator is outside the prototype scope.

GF180MCU at 3.3 V cannot reach the clock rates of either part. Deadhorse
targets single-digit to low-double-digit MIPS, which the flight-loop
measurement shows is enough for the target application
([02-requirements.md](02-requirements.md), R-CPU-1).

## First application: Flightory Stallion VTOL

| Property | Value | Provenance |
| --- | --- | --- |
| Airframe | Tilt-rotor tricopter VTOL, two tilting front motors, one fixed rear motor | Product page |
| Size | 1340 mm span, 2 to 3 kg all-up | Product page |
| Motors and ESCs | Three, BLHeli_S 45 A or similar, 7 inch props | Product page |
| Servos | Two tilt servos, plus control surfaces on the base airframe | Product page; surface count assumed |
| Actuator outputs | Nine: 3 ESC, 2 tilt, 4 surfaces | **Assumed** split; confirm against the wiring PDF |
| Battery | 4S | Product page |

The flight controller needs, beyond the nine outputs: an IMU on SPI, a
barometer, compass and airspeed sensor on I2C, GPS, RC receiver and telemetry
radio on three UARTs, battery voltage and current sensing, and USB for ground
configuration.

## Role of each core

| Core | Role | When it runs |
| --- | --- | --- |
| Performance core | Flight control loop, navigation, estimator, USB and telemetry stacks | Armed and in flight; woken on demand otherwise |
| Lite core | Battery and arming supervision, RC-link presence, periodic sensor polling, deciding when to wake the performance core, later feeding the neuromorphic IP | Always, including deep sleep |

In flight the motors draw far more power than the MCU, so deep sleep and the
lite core matter for ground standby and armed-idle time. They are in scope
because they are the architectural groundwork for the heterogeneous product,
not because this airframe needs them.

## In scope for the GF180 prototype

1. Performance core, lite core, local memories and bus.
2. Retained deep sleep with an always-on low-frequency oscillator and watchdog.
3. UART (three), SPI controller, I2C controller and target, USB full-speed
   device, GPIO, timers, nine-channel actuator block. USB is being
   implemented separately and is integrated last; the plan reserves its
   space, pads, clock and bus window from the start.
4. Provision for later integration.
5. Boot from external QSPI NOR flash, with the RISCay A/B and golden-image
   scheme.
6. Pad ring, ESD, power-on reset and brownout, production test access.

## Out of scope for this plan

- Neuromorphic IP is outside the scope of this prototype.
- Embedded flash, on-chip ADC, on-chip regulator, hardware floating point.
- USB high speed or host mode.
- Power-gated standby with isolation and retention cells. Measured first,
  decided later ([06-power-clock-reset.md](06-power-clock-reset.md)).
- Porting PX4, ArduPilot or Betaflight. They assume an FPU and hundreds of KiB
  of flash. Deadhorse runs its own fixed-point flight firmware.
- A node shrink. The prototype tapes out on GF180; the architecture should not
  depend on anything GF180-specific above the cell and macro level.

## Definition of done for the prototype

Packaged silicon on a bring-up board, running our fixed-point firmware, holds
a Stallion VTOL in a stable hover, transitions to forward flight and back, and
enters and leaves retained deep sleep on the ground with the lite core
running. Intermediate milestones are in [09-roadmap.md](09-roadmap.md).
