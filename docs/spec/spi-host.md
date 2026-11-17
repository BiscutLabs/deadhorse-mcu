# SPI host contract (T16)

One HF-domain full-duplex host, MSB-first eight-bit words, SPI modes 0 and 3,
two active-low chip selects. SCLK is a registered output, never an internal
clock. All state advances on HF. Ports use the T14 LocalBus convention.

## Transfers and timing

TX/RX FIFOs default to 16 bytes, parameterized 2..16. A START command accepts
only if enabled, idle, sleep admission permits, length is 1..FIFO depth, TX
contains the whole transfer, and RX has room for every result. It reserves
the selected length; no queued descriptor or mid-transfer starvation/stall.
Rejected START itself changes no transfer/queue state and latches command_error;
an independently requested RX_POP still follows its own rules below.
Every transmitted byte generates one RX byte, including command/dummy bytes.
Software handles BMI270 command and dummy-byte conventions and parses payload.

The configured half-period H is an integer 3..255 HF edges. SCLK frequency
is HF/(2H): 4 MHz at 24 MHz with H=3, 2 MHz at 12 MHz, 1.5 MHz at 9 MHz.
These are derived digital rates using assumed clocks, not physical guarantees.
MISO passes through shared CdcSync before sampling. The external device must
present each bit after its launch edge with enough delay margin to settle by
the first following HF edge, and hold through the sampling edge. Three-edge
half-periods accommodate the shared synchronizer pipeline. Pads/flight time,
metastability, setup/hold, duty cycle and board load need later qualification.

START asserts exactly one CS, captures the first TX byte and the acquisition
timestamp, and waits H edges before the first SCLK edge. Mode 0 idles low,
preloads MOSI at CS assertion, samples MISO on leading rising edges and changes
MOSI on trailing falling edges. Mode 3 idles high, drives MOSI on leading
falling edges and samples on trailing rising edges. Each half-period lasts H
edges; bytes are contiguous under one CS. After the last trailing edge CS
remains asserted for H more edges, then is released and done latches. A final
H-edge deselected gap precedes idle/admission. Busy includes setup, clocking,
hold and the deselected gap; done can be set while busy is still high.
Thus CS-low time is
`(16 * length + 1) * H` HF edges. For length 16 (command, dummy, 14 payload)
and H=3 this is 771 edges, derived 85.667 us at assumed 9 MHz, below 150 us.
Measurement starts at accepted START/CS assertion; bus loading/service and
firmware scheduling are separately reported, not silently included in this bound.
The fixed hardware gap is not a sensor-specific intertransaction delay.
Firmware must honor the attached device's read/write/power-state idle intervals
and initial SPI-selection procedure; for BMI270 these may exceed this gap.
Final RX enqueue occurs at the final trailing edge, before done/CS release.

## Register programming and ownership

Use generated RegBlock and BusRegAdapter at a configurable 256-byte-aligned
base. Trusted three-bit `owner` is checked on every accepted access. The
external controller blocks new requests and drains transactions/FIFOs before
changing ownership; no software origin override or ownership register exists.

Configuration is shadowed. APPLY succeeds only idle with both FIFOs empty;
enabled configurations require H>=3. Disabled configurations retain all eight
divider bits. APPLY updates idle SCLK and output enables. It never changes
an active transfer. Transfer length is snapshotted on START. START cannot
combine with APPLY or FIFO flush; the entire conflicting command (including
POP/APPLY/flush) is rejected, with only command_error set. Admission uses
pre-edge TX/RX counts: simultaneous RX_POP cannot rescue insufficient space.
APPLY
tests pre-edge FIFO state even with flush/pop on the same command.
Flush is legal only while idle, and wins enqueue/pop on that edge; flush
during a transfer/gap latches command_error and changes no queued bytes.
RX_POP acts only on a pre-edge valid head; an empty pop cannot consume a new
arrival. TX/RX operations otherwise may run during a transfer. Simultaneous
pop/arrival can use the freed RX slot; a full TX write may use a slot consumed
on the same edge. Full writes drop only the offered byte and set tx_overflow.
RX overflow is flagged and drops that byte (normal admitted transfers reserve
sufficient capacity). Empty RX_POP sets rx_underflow. Reads never pop.

| Offset | Register | Fields and access |
| --- | --- | --- |
| 0x00 | configuration | RW enable[0], mode3[1], chip_select[2]; reset 0 |
| 0x04 | divider | RW half_period[7:0]; reset 3 |
| 0x08 | length | RW bytes[4:0]; reset 1 |
| 0x0c | command | W1P apply[0], start[1], rx_pop[2], tx_flush[3], rx_flush[4] |
| 0x10 | tx_data | WO value[7:0], enqueue on byte-zero strobe |
| 0x14 | rx_data | RO value[7:0], zero when empty |
| 0x18 | status | RO tx_ready[0], rx_valid[1], busy[2], tx_count[12:8], rx_count[20:16] |
| 0x1c | events | W1C tx_overflow[0], rx_overflow[1], rx_underflow[2], command_error[3], done[4] |
| 0x20 | irq_enable | RW rx_valid[0], tx_ready[1], errors[2], done[3]; reset 0 |
| 0x24 | active | RO enable[0], mode3[1], chip_select[2], half_period[15:8] |
| 0x28 | timestamp | RO value[31:0], HF-domain input captured on accepted START |

Timestamp is one coherent register, reset zero, held until next accepted START;
software associates it with that transfer's RX bytes before starting another.
Existing RX contents remain earlier data: software tracks byte counts or drains
the FIFO to maintain boundaries. There is no timestamp per FIFO entry.
It marks acquisition initiation, not the sensor's internal sample or DRDY edge.
The future timebase supplies units/wrap semantics and a coherent HF-domain value.
No bitwise timestamp CDC is permitted. Timer/DRDY triggering remains firmware/
later integration policy. Hardware event set wins W1C. Reserved bits read zero;
misalignment/unmapped addresses error; byte strobes follow RegBlock.

## Sleep, reset and external ports

`sleepRequest` and `sleepEnable` are same-HF-domain policy inputs. Sleep blocks
new START unless sleepEnable is true; accepted work always drains. Queues are
retained and queued TX requests HF until explicitly flushed/consumed. Registered
`clockHold` covers active work and queued/new TX, and `quiescent` reports idle
with no TX queued; unread RX can be retained. Power control also collects bus
demand and accounts for pending commands before gating. A later bus request
wakes HF through the existing bridge/controller path. There is no asynchronous
SPI wake detector or automatic sensor poll in this block.

DMA requests are registered hints: TX enabled with room; RX nonempty. CPU/DMA
must serialize RX peek/pop and use ordinary checked bus transactions. DMA
permissions, burst engine and memory ownership are later work.

Pins `sclk`, `mosi`, `cs_n[1:0]`, output `pinsEnable`, `irq`, DMA requests,
clockHold and quiescent are registered. Reset asynchronously clears all
control, queues, events, timestamp and bus work, drives CS inactive, SCLK/MOSI
low, and disables pins. `reset_n` is already qualified by shared ResetRelease
at integration; performance-core reset must not inadvertently clear this shared
peripheral. External device state after mid-transfer reset is a driver concern.
Physical reset distribution/recovery/removal and clock-tree design remain open.

## References and qualification boundary

Protocol convention checked against [OpenTitan SPI host theory](https://opentitan.org/book/hw/ip/spi_host/doc/theory_of_operation.html)
and [Bosch BMI270 data sheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi270-ds000.pdf).
No external RTL is imported. Independent pin/queue models test both modes,
full-duplex payloads and deadline; formal claims state their configuration and
bound. GF180 timing is pre-layout screening, not physical serial signoff.
