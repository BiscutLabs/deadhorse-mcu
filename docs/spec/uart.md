# UART peripheral contract (T15)

Three identical independent UARTs, 8N1, least-significant data bit first.
One HF clock per UART; all timing is counted in clock enables, never a new
baud clock. A separate AON wake monitor remains clocked when HF is stopped.
This contract describes standalone IP ports, not final SoC addresses/pads.

## Configuration and serial timing

TX/RX FIFO capacity defaults to eight bytes each, parameterized 2..16.
TX and RX use independent 16-bit phase accumulators and one shared configured
increment. Actual average baud = `increment * HF_Hz / 65536`; software rounds
`65536 * baud / HF_Hz` to nearest integer. Legal enabled increment is 1..8192
(at least eight HF edges per bit). Reset disables TX/RX. Inversion applies to
both pins; reset TX is high and its output-enable is false.

Configuration registers are shadows. APPLY copies enable/inversion/baud into
active configuration only when both serial engines and both FIFOs are empty;
otherwise it raises config_error without altering active state. Invalid
enabled baud likewise raises config_error. Software drains/disables RX via
the sleep/quiesce interface before reconfiguration if needed. Changes never
alter an in-flight frame. TX launches queued bytes when enabled and holds
start, eight data and stop bits for their fractional bit periods. RX uses
the shared input synchronizer and samples each bit near its center, rejects
a high false-start sample, and discards bad-stop frames with framing_error.
After a bad stop it waits for idle before accepting another start.

APPLY tests pre-edge empty/idle state: simultaneous POP/flush does not make
an otherwise rejected APPLY succeed. A successful APPLY suppresses new TX
or RX launch on that edge. POP occurs only on a pre-edge valid head; a new
RX byte is not consumed by an empty POP. FIFO flush wins simultaneous enqueue
or POP, including RX completion on that edge, but does not abort an active
serial frame. Error events from rejected operations still latch.

Tests qualify quantization and +/-1% peer-rate mismatch at the maximum target;
larger total oscillator mismatch is not a silicon guarantee. Baud selection,
HF trimming and external-clock tolerances remain system responsibilities.

## Bus, queues, ownership and DMA

Use LocalBus through BusRegAdapter and generated RegBlock. A 256-byte aligned
base is an integration parameter. Every granted access is checked against
the trusted three-bit `owner` input; denied accesses error without a side
effect. The adapter may map the matching origin to its fixed authorized tag
internally, but never accepts an untrusted replacement origin. The external
ownership controller changes owner only after blocking new accesses,
draining bus work and serial/FIFO work. No ownership register lives here.

TX_DATA writes enqueue one byte; full writes drop the offered byte and set
tx_overflow. RX_DATA reads the stable head, zero when empty; RX_POP consumes
one byte, or sets rx_underflow when empty. Reads never consume. RX arriving
to a full FIFO is discarded and sets rx_overflow; a simultaneous successful
pop may make room. FIFO flush commands discard queued data only, not active
serial frames. Each command acts once, regardless of bus latency.

DMA outputs are registered level requests: TX enabled and space available;
RX data available. A later DMA engine services TX_DATA or RX_DATA followed
by RX_POP using ordinary owner-checked bus transactions. Requests are hints,
not credits: acceptance/status determines success. CPU and DMA for one owner
must serialize RX peek/pop; no concurrent consumers or hidden DMA bypass.

| Offset | Register | Fields / semantics |
| --- | --- | --- |
| 0x00 | configuration | RW shadow tx_enable[0], rx_enable[1], invert[2]; reset 0 |
| 0x04 | baud | RW shadow increment[15:0]; reset 0 |
| 0x08 | command | W1P apply[0], rx_pop[1], tx_flush[2], rx_flush[3] |
| 0x0c | tx_data | WO value[7:0]; enqueue on byte-0 strobe |
| 0x10 | rx_data | RO value[7:0]; zero when empty |
| 0x14 | status | RO tx_ready[0], rx_valid[1], tx_busy[2], rx_busy[3], idle[4], tx_count[12:8], rx_count[20:16] |
| 0x18 | events | W1C tx_overflow[0], rx_overflow[1], rx_underflow[2], framing_error[3], config_error[4], tx_done[5]; hardware set wins clear |
| 0x1c | irq_enable | RW rx_valid[0], tx_ready[1], errors[2], tx_done[3]; reset 0 |
| 0x20 | active | RO tx_enable[0], rx_enable[1], invert[2], increment[31:16] |

Registered IRQ ORs the selected queue levels and sticky events. Hardware
events remain latched regardless of masking. Unmapped/misaligned accesses
error; zero strobes have no bus-induced effect; byte strobes follow RegBlock.

## Sleep/wake and integration boundary

The HF endpoint has same-domain `sleepRequest` and two-bit `sleepMode` inputs
from the future power controller: 0 disabled, 1 wake-only, 2 receive, 3 treated
as disabled. Run ignores sleepMode. Receive retains full RX and requests HF
continuously while RX is enabled. Other sleep modes stop accepting new RX
frames; an existing frame and queued TX finish. Unread RX bytes are retained.
No sleep transition silently cancels a frame or queued TX byte.

`clockHold` is registered and stays asserted for TX work, an active RX frame,
or enabled continuous receive. `quiescent` reports drained serial engines and
TX queue; RX data may remain retained. The power controller also collects
bus/bridge demand: UART clockHold alone is not authorization to gate while a
bus transaction or register command is pending. Disabled TX with queued data
must retain clock demand until software flushes it.
Because APPLY requires empty FIFOs, a disabled TX with queued bytes must be
flushed before it can be enabled; no automatic enabling path is implied.

`UartWake` uses its own AON clock, shared ResetRelease/CdcSync, an AON-domain
`armed`, `invert`, and `clear`, and exports a sticky registered `wake`/HF
request. It captures the synchronized active RX level while armed; capture
wins clear. Arming/configuration belongs to the AON power controller after
the UART is quiescent and before HF gating; disarming does not erase pending
wake. Disabled mode leaves it unarmed. A same-edge wake must prevent gating.
Synchronize the normalized active level (reset value inactive), so an idle
pin cannot trigger wake during synchronizer initialization. Change inversion
only while disarmed and allow four AON edges before arming with the new
polarity. The preamble bound assumes reset release and this settling complete.
Cross-domain mode/config handoff is a later power-controller responsibility,
not independent bit synchronization of a bus payload.

Wake-only sender contract: hold the active level for at least four AON clock
periods, then allow HF startup and a full idle bit before retrying the data.
At nominal32kHz this preamble is a derived125us, not a guaranteed physical
startup time. Short ordinary high-baud start bits may be missed; the first
byte is not retained while HF is stopped. No analog edge-capture latch is
introduced. Receive mode is required for unsolicited lossless reception.

The HF endpoint and bank accept an already-qualified `reset_n`: integration
must supply asynchronous assertion and synchronous HF-domain release through
the shared ResetRelease primitive. Simulation wrappers instantiate that
primitive. UartWake includes its own small AON-domain release synchronizer.
Standalone UART timing excludes the shared reset distribution tree; its
buffering, electrical loading and recovery/removal remain physical integration
obligations. Reset aborts local bus/serial work, empties queues, masks IRQ,
disables output and clears wake. Performance-core reset is not wired here;
the later SoC must preserve this shared peripheral when its owner survives.

## Verification and references

Independent tests decode real TX pins and drive mathematical 8N1 RX frames,
with FIFO list models, fractional rates, errors, reset/sleep and denial.
Formal claims are scoped per property and include actual negative controls;
timeouts remain deferred/unproved. GF180 default SS timing is required.

Primary reference consulted: [OpenTitan UART theory of operation](https://opentitan.org/book/hw/ip/uart/doc/theory_of_operation.html)
documents fractional baud generation and FIFO/serial separation. T15 reuses
those general techniques, not OpenTitan RTL or its 16x-oversampling formula;
our accumulator emits bit-period events with RX half-bit alignment.
