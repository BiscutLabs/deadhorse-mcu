# DMA (T23, T40)

Four channels share one main-clock transfer engine and
service ready channels round-robin after each retired bus transaction, at most
one item before reconsidering peers. Readiness waits do not occupy the shared
engine. Fairness is in serviced transactions, not a wall-time guarantee while
a peripheral is unready or a bus response is stalled.
Counts are finite except for optional UART RX circular receive (T40/D102);
there are no linked descriptors or application protocols.
The initial SoC binding uses performance-owned SRAM, existing serial/PWM
endpoints and IRQ8 at the reserved 0x40011000 control window.

## Transfer contract

A channel snapshots its memory address, item count and endpoint selector on
START. Shadow writes do not change active work. Zero count, invalid selector,
word misalignment, out-of-range/overflowing memory span, duplicate active
endpoint or START while busy rejects and sets config-error. For simultaneous
START requests selecting the same endpoint, the lower channel number wins.
UART/SPI items are packed bytes; PWM items are aligned 32-bit words. Memory
addresses advance by the item size. Only the low 256-byte control window decodes.

The endpoint table is supplied from the validated SoC map:

| Selectors | Direction and sequence |
| --- | --- |
| 0..5 | UART0/1/2 TX,RX pairs: TX memory read then FIFO write; RX FIFO peek, memory write, then POP |
| 6,7 | SPI TX,RX, with the same byte sequence; firmware configures/starts SPI transactions |
| 8..16 | PWM0..8: memory word read, read/validate shadow period, high-time shadow write, poll for no queued update, then APPLY and request acknowledgement |

PWM words with any bit above bit16 set, or with high-time greater than the
shadow period plus one, stop with a data error before changing the peripheral.
Only valid, nonbusy APPLY is issued. Exclusive configuration ownership and
the absence of another active channel for that selector preserve these checks
through pulse consumption. Completion means queued/start configuration accepted,
not a completed waveform. Pending-status polling yields to other channels after
each read, so it does not monopolize the engine.

Requests are registered readiness hints, not reserved credits. The engine
rechecks readiness before the data-side operation. Firmware must not concurrently
change a DMA-owned FIFO, flush/configure its endpoint, or mutate its active
memory buffer. Ordinary status/event reads and SPI START are allowed. This
software concurrency contract does not grant DMA any additional permissions;
every outgoing access retains the hardware-checked initiating owner.

One bus transaction is outstanding at a time. Request payload stays stable
until grant; retirement waits for the corresponding response. An item counts
as completed only after all its required side effects succeed. A bus error stops
the channel and records the failed phase; previous writes may already have
occurred (RX memory write before a failed POP, for example). Software must inspect
the endpoint before retrying. No failed transaction is automatically replayed.

ABORT stops a channel before its first offer immediately; an already offered
item finishes its sequence before reporting aborted, even if grant has not
arrived. It never withdraws an offered transaction or reuses its response slot.
ABORT wins simultaneous START. A transfer error wins abort reporting; otherwise
abort suppresses the final done event. A successfully retired item still advances
current/decrements remaining before aborted is reported. Error leaves current
at the partially completed item and remaining unchanged for that item.
Peripheral fabric quarantine/drain
remains authoritative on a timeout; the engine does not manufacture success.
Cold/warm reset cancels all channels jointly with their bus endpoints under
T41. A fixture's local memory-client hold does not reset the DMA service.

Clock demand remains asserted for active/waiting work. Completion, transfer
error, configuration error and abort events are sticky W1C with set winning
clear; IRQ is registered and masked. A byte copied to a TX FIFO is complete
when accepted by that FIFO, not when its final wire bit leaves the peripheral.

## Memory and permissions

Dedicated memory and peripheral LocalBus master ports use registered offers.
The memory port accesses only the performance owner's SRAM region. It shares
the existing native memory service with CPU instruction/data requests; the
arbiter alternates a requesting DMA with CPU service, retaining the original
instruction/data preference when DMA is idle. Invalid memory accesses return
errors without effects. Byte accesses use aligned word addresses and byte
strobes; words use all lanes. The peripheral port reaches only the fixed table
of endpoint registers. Software cannot program arbitrary peripheral addresses
or origin tags. Owner changes require external idle/drain, as for serial IP;
the initial profile fixes the owner to performance.

## Register layout

### UART RX circular receive (D102)

Endpoint bit5 enables circular receive only for selectors1,3,5 (UART0/1/2 RX),
with count at least2. All existing range/alignment/duplicate/owner checks apply.
The mode is captured on START. A completed lap reloads current/count from the
existing shadow registers, keeps busy asserted and sets wrap instead of done.
No second base/count copy is stored. Half fires on the successful item leaving
floor(count/2) items; odd counts therefore report after ceil(count/2) items.

While an active circular channel is busy, nonzero-strobe writes to address,
count or the complete endpoint/circular register are ignored and set its
config-error event. Reads and zero-strobe writes retain their normal behavior.
The same lock covers a pending circular START, even if START will be rejected;
ABORT wins START. A terminating item still rejects a same-edge shadow write
using pre-edge busy. Once abort/fault has completed, writes are accepted.
An active non-circular channel keeps its original writable-shadow behavior,
including writing a circular bit for its next START.

Successful-item half is reported even when that item completes an ABORT.
ABORT/fault suppress reload and wrap; fault suppresses item advancement and
half. The existing non-circular done/error/abort ordering is unchanged.
Events are registered pulses feeding sticky W1C status; hardware set wins clear.

Current is one coherent register snapshot, published only after a successful
RX POP response, which follows the committed SRAM write. At wrap it becomes
the base immediately. While running it is a modulo write position, not a lap
counter. ABORT retains normal post-item advancement, possibly one past the
buffer end; fault leaves the partially completed item's cursor. Software must
check busy/error/abort before interpreting a running-ring snapshot. Firmware
must poll/consume before a complete lap passes unseen; equal positions cannot
distinguish empty from overwritten data. No hardware overrun detection exists.

The approved increment cap is 0.010 mm² across all four channels. Final
measurement and qualifications are recorded in the T40 report. No new clock,
reset or CDC is introduced.

All writable fields reset zero. Address/selector/count arrays have four entries.

| Offset | Register | Fields |
| --- | --- | --- |
| 0x00 | start | w1p channel mask 3:0 |
| 0x04 | abort | w1p channel mask 3:0 |
| 0x08 | busy | ro channel mask |
| 0x0c | events | w1c done3:0, error7:4, config_error11:8, aborted15:12, half19:16, wrap23:20 |
| 0x10 | irq_enable | rw event mask23:0 |
| 0x20..0x2c | address[4] | rw memory byte address |
| 0x30..0x3c | count[4] | rw item count15:0 |
| 0x40..0x4c | endpoint[4] | rw selector4:0, circular5 |
| 0x50..0x5c | remaining[4] | ro items not fully completed |
| 0x60..0x6c | current[4] | ro current memory byte address |
| 0x70..0x7c | fault[4] | ro failed transfer phase |

Fault codes: 0 none; 1 initial source read; 2 TX FIFO write; 3 RX SRAM write;
4 RX POP; 5 PWM period read; 6 PWM shadow write; 7 PWM pending read;
8 PWM APPLY; 9 invalid PWM value. START accepted clears that channel's fault.

## Integration and verification

The production SoC binds this controller and its third native
memory master. IRQ8 and clock demand are connected. `check_soc_map.py` derives
endpoint addresses and command masks from the peripheral register maps and
checks field widths/access types.

Focused commands (prefix each with `python tools/env/run.py run --`):

```
python3 dv/soc/prepare_dma.py
python dv/soc/prepare_dma_circular.py
python tools/sbt.py "hw/testOnly deadhorse.dma.* deadhorse.top.SocDmaSpec deadhorse.top.SocDmaCircularSpec"
python sw/hal/tests/test_dma_ring.py
python hw/ip/dma/formal/circular.py --output build/t40/<fresh-formal>
python hw/ip/dma/formal/check.py --cases denied --output build/t40/<fresh-denied>
python hw/ip/dma/check_timing.py --output build/t40/<fresh-timing>
```

The transaction oracle covers packed bytes, stalls, partial errors, all
offered/waiting abort phases, terminal collisions, invalid descriptors/PWM
words and an actual data-corruption fault. SoC tests use real SRAM, fabrics,
UART/SPI digital pin loopbacks and PWM duration checks, including the T41
qualification/reset contract. Memory tests compare idle-DMA CPU traces against the original
profile and check competing fetch/data/DMA at the tested latencies.

Formal scope and open items: [formal/README.md](formal/README.md).
Measured initial pre-layout GF180 results (timing commands above, receipts
`build/t23/timing-first/result.json` and `build/t23/memory-timing-first/result.json`):
DMA worst path 43.368591 ns, area 159020.288 um²; memory-control worst path
21.502474 ns, area 22920.0832 um². Both pass the existing main-9MHz
66.666667 ns budget, with zero electrical violations. Memory macro area/delay,
upstream core paths, physical hold and reset timing are excluded. Source
hashes identify the uncommitted snapshot on `72bcfac`.

CI remains off by user instruction. Status and frozen-check evidence:
[T23 report](../../../docs/plan/tasks/reports/T23.md).

## Circular receive software

`sw/hal/dma_ring.h` starts a channel/UART/ring, snapshots the coherent current
register, computes available bytes relative to a software read position, and
advances that position after consumption. It rejects stopped/error channels.
The `fence ir,r` orders the device cursor read before SRAM data reads. ABORT
must drain (`busy=0`) before storage or descriptors are reused. Caller owns
channel, FIFO and buffer; this API does not arbitrate concurrent software.
`dma_ring_example.c` consumes an illustrative variable-length stream once per
loop, including split-at-end frames; it implements no device protocol.

Estimated service interval at an assumed 420 kbaud, 8-N-1 is strictly less
than `length * 10 / 420000` seconds: a 256-byte ring gives approximately
6.095 ms, before reserving scheduling margin. Consume promptly after taking
the snapshot; the producer can overwrite unread bytes if the caller falls
behind. Equal modulo positions do not detect a missed complete lap.
