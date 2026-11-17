# SPI host (T16)

`SpiHost(json, fifoDepth = 16, base = 0)` implements the authoritative
[SPI contract](../../../docs/spec/spi-host.md). Generated register decode is
from `spi_host.regmap.yaml`. FIFO depth is 2..16 and base is 256-byte aligned.

Inputs: HF `clk`, domain-qualified `reset_n`, `bus: LocalBus`, trusted 3-bit
`owner`, asynchronous `miso`, same-domain `sleepRequest`, `sleepEnable`, and
coherent same-domain 32-bit `timeNow`. Outputs: registered `sclk`, `mosi`,
`cs_n[1:0]`, `pinsEnable`, `irq`, `dmaTxRequest`, `dmaRxRequest`, `clockHold`
and `quiescent`, plus registered bus responses. SCLK drives a pin, never RTL
clock ports. MISO uses the shared CdcSync; qualified reset comes from the
integration's shared ResetRelease. No new crossing implementation exists here.

Modes 0 and 3 use MSB-first full-duplex bytes. Half-period divider 3..255
defines relative HF-edge timing; 4 MHz SCLK derives from assumed 24 MHz HF
at divider 3. The shared two-flop MISO latency requires external data to settle
before the first HF edge following its output launch and remain stable until
sampling. Pad/board delay and metastability remain physical qualifications.
START reserves all TX data and RX space for a bounded transaction, captures
the supplied timestamp at CS assertion, and keeps CS continuous through all
bytes. Final RX is published before done; CS setup/hold/gap are each one
half-period. Sensor-specific idle gaps remain firmware's responsibility.

APPLY uses pre-edge idle/empty state. START conflicts with APPLY or flush;
busy flushes are rejected. RX_POP can coexist with START but cannot make a
pre-edge insufficient RX reservation succeed. Queues use explicit counts;
reads peek, writes enqueue, and sticky hardware events win W1C. Owner transfer
requires an external drain/block protocol. DMA request outputs are hints and
do not grant bus or memory permissions.

Sleep admission is explicit; active transfers always finish and queued TX
retains clock demand. The power controller also checks outstanding bus work
before gating. Reset clears control/queues/events/timestamp, deasserts both
CS pins, drives SCLK/MOSI low and disables pins. Configuration can change
idle SCLK only with no selected device. No state is retained across reset.

Formal claims, assumptions and negative controls are recorded beside the block
and in the [task report](../../../docs/plan/tasks/reports/T16.md). The timing
ledger records measured GF180 pre-layout area and delay; no area estimate is
used for acceptance. Frame checks are bounded, not unbounded protocol proofs.
Physical reset distribution, pads, clock tree, DMA and SoC wiring are excluded.
