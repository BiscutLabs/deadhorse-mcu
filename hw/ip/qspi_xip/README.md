# Native QSPI read path

T30 extends the T29 command engine in an opt-in profile. XIP uses the native
main-clock local-memory path, not the peripheral fabric, whose response limit
is unchanged. Existing QSPI-only profiles and their map remain unchanged.

Trusted performance-origin1 may read aligned words in0x10000000..0x1fffffff,
independent of the current MMIO owner. Writes, other origins, disabled XIP,
misalignment and unrepresentable addresses return zero with error. Three-byte
address mode rejects offsets>=0x01000000, never aliases them; four-byte mode
supports the complete existing window. Bus reads return little-endian words:
reverse the four byte lanes of the engine's MSB-first assembled RX result.
No cache or speculative flash request is added.

There is one captured native request slot and one captured software command
slot. The T30 START key queues a snapshot if the command slot is free, even
while a read owns the engine; a second command fails. This is an explicit
T30 difference from T29's busy rejection. Arbitration alternates completed
frames when both slots wait; no selected frame or mandatory CS-high gap is
preempted. Native read result is separate from the software command result.
XIP always selects boot CS0. Raw CS0 commands are rejected while XIP is enabled;
raw CS1 commands remain available. This prevents a software program/erase on
the boot flash from overlapping enabled instruction reads.

At most one competing frame precedes a queued request. Estimated conservative
native response bound is2×53299+32=106630 running main edges, including slot,
dispatch and response registers. It assumes a running main clock and the
engine's bounded digital frame; external flash data validity is separate.
No existing128-edge peripheral limit changes. Tests measure actual edges.

## Configuration

The current QSPI MMIO owner controls these additional registers. The canonical
T29 map and this valid extension map are merged and revalidated in build/;
no duplicate hand-written register decoder or new YAML access type exists.

| Offset | Register | Meaning |
| --- | --- | --- |
| 0x100 | xip_configuration | enable bit0; address bytes[3:1], reset3; quad address bit4; quad data bit5; opcode[15:8], reset0x03 |
| 0x104 | xip_timing | half-period[7:0], reset4; dummy clocks[12:8] |
| 0x108 | xip_apply | full-word WO key0x58495021 |
| 0x10c | xip_status | active enabled bit0; pending/active work bit1 |

APPLY validates address bytes3/4 and divider4..255, snapshots settings, and
changes active enable only while both slots, engine, responses and CS gap are
idle. Handoff has the same requirement. Concurrent START or offered native
request prevents either update; rejected actions set the existing command_error.
Shadows may be written while busy. Reset disables XIP; no implicit flash mode
setup or flash-internal ready polling occurs. Firmware must run from ROM/SRAM
while configuring/disabling XIP and must first configure the device and poll
it ready. Empty controller slots do not prove future fetches or flash readiness.

## Reset and integration

Main-service reset asynchronously cancels controller/read slots and disables
pads. Performance/client reset leaves accepted flash work under service reset,
suppresses orphan replies, and holds epochReady until both XIP and any accepted
MMIO drain. A reset pulse must be remembered even if it ends before the reply.
Instruction returns stay ordered: drain earlier local responses before an
XIP instruction grant; block later instruction grants until its response.
Independent data/SRAM/DMA work may proceed during an instruction flash read.
DMA remains SRAM-only. Existing local arbitration/latency is unchanged when
no XIP request is present; no combinational target-grant chain is introduced.

T29 pad/input-settling contracts still apply. Neither this stage nor its
digital checks qualify a flash part, routed hold/RDC, physical timing,
production boot/recovery images or system XIP performance. Mapped controller
and local-memory-control figures belong in the T30 report; no new area allowance
is assumed. The local-memory screen uses the existing audited synchronous
memory cut, preserving all production control logic and excluding macro
delay/area, upstream core paths and physical interconnect. No CI runs here.

Focused acceptance is `python tools/env/run.py run -- python dv/soc/check_xip.py
--output build/t30/<fresh-directory>`. It runs the old command/profile tests,
native pin-model tests, reset/memory arbitration tests and an actual two-core
recovery-loaded firmware example. The example enables XIP from lite firmware,
jumps from boot ROM into flash, performs a flash data load, and signals success
through GPIO. It is test firmware, not the production image ABI or boot policy.
See [formal scope](formal/README.md) for the assumptions and proof boundaries.

The scoped T30 checkpoint passed frozen focused acceptance and independent
review; see the [report](../../../docs/plan/tasks/reports/T30.md). The final
receipt is `build/t30/frozen02/result.json`, with independent audit at
`build/t30/independent-final-review.json`. Neither CI tier ran. Changes remain
local on main with the inherited uncommitted implementation.
