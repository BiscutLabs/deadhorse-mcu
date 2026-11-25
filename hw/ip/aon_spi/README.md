# AON SPI

Lite-owned, nominal32kHz, mode0/3, one chip select and eight-byte TX/RX FIFOs.
The production binding runs with OSC_IN stopped and never requests main clocks.
Completion/error IRQ wakes lite. The [integration contract](../../../docs/spec/plan05-integration.md)
and `aon_spi.regmap.yaml` define start validation, FIFO, framing and configuration
rules. New transfers must fit both FIFOs; busy configuration changes error.

`AonSpiSpec` checks serial edges/data against a byte queue in both modes and
supported dividers, concurrent FIFO traffic, ownership/errors and injected
faults. `SocWatcherPathSpec` and `SocDormantSpec` execute the measured RV32E
watcher against an independent radio peer through production pads and buses.

Formal ordering/framing remains deferred after the120-second positive proof
cap. Fault witnesses and covers passed; they are not a substitute for the
unbounded result. See [formal scope](formal/README.md) and the PLAN05 report.
Phase-end acceptance remains open.
