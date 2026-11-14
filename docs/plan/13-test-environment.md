# 13 Test environment

Deadhorse tests run through the pinned environment. Use one shared file list per block and check behavior against independent models.

What is proved formally is in
[12-formal-verification.md](12-formal-verification.md). Signoff gates are in
[08-physical-verification.md](08-physical-verification.md).

## Local execution policy

User decision 2026-11-14: checks run locally. References to CI mean the local
`tools/ci.py` check entry point; no GitHub Actions or hosted runner is required.
Outputs remain under build/ rather than being uploaded by a service.

## 1. One pinned environment

One pinned Linux container image (D23, established in T08) provides everything: JDK, sbt, firtool, the simulators, the
formal tools, the RISC-V compiler, Python and its packages, yosys and the
PDK fetch. Developers, agents and CI all use it.

- No script may contain a path outside the repository or the environment.
- No per-platform wrapper scripts. Windows and macOS users run the same
  container; Windows uses Docker/WSL. CI uses the same image digest.
- Tool versions are pinned in one place, with hashes where the source allows.
- A task that needs a tool not in the environment adds it to the definition;
  it does not install it ad hoc.

## 2. Block tests in the design language

Block-level tests are ScalaTest suites using Chisel's simulation library, as
in RISCay-MCU.

- Tests live in the block's `src/test/scala/` directory and are part of the block's sbt
  project. There is no separate source list to maintain.
- One file per feature or behaviour. A test file that grows past a few
  hundred lines is split.
- Tests use the block's own Chisel types and bundles, so an interface change
  is a compile error, not a silent mismatch.

## 3. Reference models, not source matching

- Every block is checked against an independent model of its behaviour: a
  small Scala or Python model, the generated register model, or an
  instruction-set simulator for the cores.
- The model is written from the specification, not derived from the RTL.
- **Tests never read or match RTL source text.** A test observes only what a
  user of the block can observe: its ports, its registers, its pins.
- Each test suite has at least one negative control: a deliberate fault the
  suite must catch.

## 4. One test body, four targets

System-level tests are written once and run on four targets.

| Target | What it is | Used for |
| --- | --- | --- |
| RTL simulation | The emitted design in a compiled simulator | The reference; every change |
| Fast model | An instruction-level model of the chip with peripheral models | Firmware development, long scenarios |
| FPGA | The same RTL on the prototype board | Real-time behaviour, real actuators and sensors |
| Silicon | The chip on its bring-up board | Bring-up, characterisation |

How:

- System tests are Python. They talk to the chip only through a small
  **target interface**: reset, register read and write through the gateway
  protocol (`docs/spec/gateway-protocol.md`, to be written by T14),
  load an image, drive and observe named pins, advance or wait time.
- Each target implements that interface: a simulator adapter, the fast
  model, a UART link to the FPGA, a UART or USB link to the board.
- A test declares what it needs (for example cycle-exact pin timing). A
  target that cannot provide it reports the test as not applicable; it is
  never silently skipped or passed.
- A failure on FPGA or silicon is reproduced by running the same test on
  RTL simulation.

Python is chosen for the system layer because the airframe model and the
host tools are Python and the tests must drive real hardware. It means two
test frameworks: ScalaTest for blocks, Python for the system.

## 5. Firmware and airframe in the loop

The system simulation runs the real firmware against models of everything
outside the chip:

- **Sensor and storage models:** BMI270 IMU on SPI with timestamped data-ready acquisition,
  MS5611 barometer and IST8310 compass on I2C (no airspeed sensor),
  Holybro M10 GPS and RP3 V2 CRSF receiver on UART, the boot
  and logging flash on QSPI.
- **Actuator checkers** on the nine outputs. They decode servo and ESC PWM
  and DShot frames, check pulse width, bit timing, frame checksum and that
  publication is atomic and each channel updates at its own frame boundary, and feed the decoded commands to the
  airframe model.
- **Airframe model:** rigid-body dynamics of the Stallion tilt-rotor with
  motor, tilt-servo and surface responses, closing the loop from actuator
  commands back to sensor readings.
- **Scenarios** as tests: arm, hover, transition out, forward flight,
  transition back, land; sensor dropouts; brownout and watchdog reset in
  flight, checking the failsafe outputs.

The same models and scenarios drive the FPGA in hardware-in-the-loop, and
the same checkers decode captured signals from the board.

## 6. Results are artifacts

- Logs, waveforms, coverage data, captured hardware traces, bitstreams and
  model files are written under `build/` and uploaded by CI as artifacts.
  None is committed.
- A result worth keeping becomes a ledger row: the commit, the command, the
  number.
- Large fixed inputs that tests need (for example a recorded flight log) are
  stored outside the repository and fetched by hash.

## Where things live

| Path | Contents |
| --- | --- |
| `hw/ip/<block>/src/test/scala/` | Block tests and local reference models; Python models may live under block `dv/` |
| `dv/system/` | System tests, written against the target interface |
| `dv/targets/` | The four target adapters |
| `dv/models/` | Sensor, storage and actuator models, the airframe model |
| `sw/host/` | The gateway client the adapters share with the host tools |

## Order of work

1. T08 pinned Linux environment, then T07 Chisel build/formal smoke test.
2. The target interface and the RTL-simulation adapter, with the first
   system test (boot and read an identity register).
3. Actuator checkers, with the actuator block.
4. Sensor models and the airframe model, in parallel with the flight
   firmware.
5. The fast model, once the register map is stable.
6. The FPGA adapter at prototype bring-up; the silicon adapter at board
   bring-up.

## Approved-contract regressions

The revised system tests must cover mixed actuator rates and timeout/reset
independence; timer-driven sampling with stale/missing sensor data; UART receive,
wake-only and disabled modes; sleep-time SPI/I2C and HF requests; DMA ownership
violations and bounded arbitration; both-core JTAG wake/debug; external clock
selection; and selectable monitor thresholds/qualified reset release in mixed
signal tests. No early-warning detector or external die-link test is required.
