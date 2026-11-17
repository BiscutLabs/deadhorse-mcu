# I2C controller (T17)

`I2cHost(json, base = 0)` implements the [controller contract](../../../docs/spec/i2c-host.md).
Generated registers come from `i2c_host.regmap.yaml`; base is 256-byte aligned.
HF clock `clk` and shared domain-qualified `reset_n` drive all state. Inputs:
LocalBus, trusted three-bit owner, resolved asynchronous sclIn/sdaIn and coherent
sleepRequest/sleepEnable. Registered outputs sclLow/sdaLow only pull low or
release; pinsEnable, irq, clockHold, quiescent and bus responses are registered.

Shared CdcSync receives each pin; three stable synchronized samples qualify a
level. No new synchronizer, clock, latch or target controller is implemented.
Firmware sequences byte commands: START/restart, WRITE, READ with ACK/NACK,
STOP, or explicit nine-clock recovery. Timeouts release abandoned ownership.
Reset disables pins, releases both lines and clears control/data/status. Data
is retained through sleep, not reset. AON must start HF before a bus request.

Timing values count relative HF edges. Physical pull-ups, pads, rise/fall,
metastability and reset/clock distribution remain unqualified. The digital
controller targets one-controller sensor buses, not full multi-controller
interoperability. The separate RISCay loader is untouched. No area estimate
is used for acceptance; measured GF180 area/delay and scoped formal evidence
are recorded in the [task report](../../../docs/plan/tasks/reports/T17.md).
Bounded protocol checks are not unbounded proofs or physical qualification.
