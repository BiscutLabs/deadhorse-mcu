---
name: "reference-model-testing"
description: "Use when writing or reviewing tests for the Deadhorse MCU: block tests in ScalaTest, system tests against the four-target interface, reference models, actuator checkers and negative controls."
---

# Reference-model testing (Deadhorse)

The rules are in `docs/plan/13-test-environment.md`; read it and the task
brief first. This skill is about writing tests that can fail for the right
reason and that run unchanged on simulation, the fast model, the FPGA and
silicon.

## Two layers

| Layer | Language | Where | Checks |
| --- | --- | --- | --- |
| Block | ScalaTest with Chisel's simulation library | `hw/ip/<block>/dv/` | One block against its reference model |
| System | Python | `dv/system/` | The whole chip through the target interface |

## Rules that are never broken

1. **A test observes only what a user of the block can observe:** ports,
   registers, pins. It never reads, greps or matches RTL source text, and
   never peeks at internal signals to decide pass or fail.
2. **Expected values come from an independent reference model** written from
   the specification. Never compute the expectation with the same expression
   the RTL uses, and never copy an expected value out of a simulation run.
3. **Every suite has a negative control:** a deliberate fault that the suite
   must catch. A test that cannot fail proves nothing.
4. **Never weaken a test to make it pass.** No loosened tolerance, no longer
   timeout, no skip, no expected-fail, no deleted assertion. Report the
   failure.
5. **Only tools from the pinned environment,** and no path outside the
   repository.
6. **Nothing generated is committed.** Logs, waveforms and traces go under
   `build/`.

## Writing a block test

1. Read the block README contract and its register description. List the
   behaviours a user relies on. Each becomes a test.
2. Write or reuse the reference model. Keep it simple and obviously right:
   a queue is a list, a register block is a dictionary plus the access
   rules. For generated register blocks use the generated JSON model.
3. Drive the block and the model with the same stimulus. Compare every
   output on every cycle the protocol says it is valid, not only at the end.
4. Include the awkward cases: back-pressure on every cycle pattern, reset
   in the middle of a transaction, simultaneous set and clear, full and
   empty boundaries, maximum and minimum values, illegal inputs.
5. One file per feature. Split a file that passes a few hundred lines.
6. Random stimulus uses a fixed seed that the test prints, so any failure
   can be rerun.
7. Add the negative control. Typical faults: drop one item, swap two byte
   strobes, delay a response by a cycle, invert one status bit. Assert that
   the comparison fails, then make sure the fault is not left in.

## Writing a system test

System tests talk to the chip only through the **target interface**:

- reset the chip;
- read and write registers through the gateway protocol;
- load an image;
- drive and observe named pins;
- advance or wait time.

Rules:

- Do not import a simulator, reach into a hierarchy or assume a clock
  period. If the test needs something the interface lacks, stop and ask;
  do not bypass it.
- **Declare what the test needs** (for example cycle-exact pin timing). A
  target that cannot provide it reports the test as not applicable. Never
  let it pass silently or skip silently.
- Express time in real units and tolerances taken from the specification,
  so the same test holds on simulation and on hardware.
- A failure seen on the FPGA or on silicon is reproduced by running the same
  test on RTL simulation before anything is changed.

## Checking the actuator outputs

Decode the pins; do not compare raw waveforms.

- **PWM:** measure pulse width and period in ticks. At the 2.4 MHz reference
  tick, 1.000 ms is 2400 ticks and 2.000 ms is 4800.
- **DShot300:** bit period 8 ticks; a 1 is high for 6 ticks, a 0 for 3. A
  frame is 16 bits, most significant first: 11 bits of throttle, 1 telemetry
  bit, 4 bits of checksum. The checksum is the exclusive-or of the three
  nibbles of the upper 12 bits. Known answer: throttle 1046 with telemetry
  clear is `0x82C6`.
- **Atomic update:** after nine value writes and one commit, all nine
  channels change in the same frame; without the commit, none change.
- **Failsafe:** from armed, a watchdog expiry, brownout or fault flag puts
  failsafe values on the pins within one frame while the bus is in reset.

## Firmware and airframe in the loop

- Sensor models answer on the real buses: IMU on SPI with a data-ready pin,
  barometer, compass and airspeed on I2C, GPS and receiver on UART, boot and
  logging flash on QSPI.
- The actuator checkers feed decoded commands to the airframe model, which
  produces the next sensor readings.
- Scenarios are tests with pass criteria stated up front: attitude error
  bounds, no actuator saturation longer than a stated time, failsafe within
  one frame.
- Do not tune the airframe model or the pass criteria to make a failing
  scenario pass.

## Reporting

For each test added: what behaviour it checks, the reference it is checked
against, the seed, the negative control used and that it was seen to fail.
State which targets you ran it on and which you could not.

## Status of this skill

The target interface, the models and the Chisel build did not exist when
this was written. The rules and the DShot and PWM figures come from the
project plan and the actuator specification; framework calls must be checked
against the pinned versions.