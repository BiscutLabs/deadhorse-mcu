# PLAN05 reference watcher

Phase1 feasibility workload, not a qualified radio driver. RV32E/Zicsr, no
fast AON clock, no main-domain accesses. Firmware waits in WFI for the
GPIO4 individually enabled external interrupt; global interrupt dispatch is
disabled, so the sticky event is handled synchronously after WFI. GPIO5
enables radio power. A valid request is sent through the existing mailbox.

Assumed reference radio contract, fixed before measurement: one pending
eight-byte request, SPI mode0, MSB first, SCK=AON/2, one continuous active-low
CS per packet. Bytes0–1 are address0x4844, byte2 command1, byte3 sequence,
bytes4–5 payload, bytes6–7 big-endian CRC16/CCITT-FALSE over bytes0–5 (poly
0x1021, initial0xffff, no reflection/final xor). The radio keeps the packet
until all bytes have been clocked, with no additional command/dummy cycles.
This models an independent simple radio interface; it makes no claim about
an unselected commercial radio's command protocol or power draw. No auth.

Proposed AON register contract, awaiting Phase1 review and B6 implementation:

| Block/base | Offsets (bytes) |
| --- | --- |
| SPI 0x40020000 | 0 control(enable bit0, mode3 bit1); 4 status(busy bit0); 8 TX push; 12 RX pop; 16 half-period divider; 20 packet length; 24 start pulse; 28 completion W1C |
| GPIO 0x40020100 | 0 input; 4 output; 8 output-enable; 12 sticky events; 16 event enable; 20 event W1C |
| Mailbox 0x40001000 | Existing register contract unchanged |

SPI has eight-entry byte FIFOs. Start requires the complete configured
packet available in TX and enough RX capacity, so CS never pauses mid-byte.
Divider must be nonzero; zero is rejected. The independent model clocks each
bit on two AON half-period edges and supplies the received bytes only after
the final edge. Completion IRQ is available but this workload polls busy;
radio GPIO is its wake source. Invalid address/CRC must never push mailbox.

Initial measurement link layout is a candidate 1 KiB program + 1 KiB data;
E5 selection requires measured sizes and conservative stack with 25% margin.
All firmware, including startup, constants and diagnostic counters, counts.
Phase1 core-cycle results use existing LiteHart plus modeled memory/MMIO;
they are not production peripheral or whole-SoC measurements. B11 must replay
the same workload through the production blocks with OSC_IN stopped.

The `--routed` measurement composes the existing lite core, production debug
router and AON bus fabric. Its leaf targets still grant immediately and respond
after one, two or four edges, without competing-master traffic. These are
optimistic target timings, not production memory/peripheral qualification.
It reports IRQ-to-mailbox publication and IRQ-to-return-to-WFI separately.
No main-domain access is permitted by the independent bus oracle.

Run in the pinned environment, with a fresh output directory:
`python sw/lite/watcher/measure.py --routed --output build/plan05/watcher-routed02`.
The receipt hashes sources before/after, emitted RTL, firmware and executable;
the deliberately corrupted mailbox-payload firmware must fail the oracle.
