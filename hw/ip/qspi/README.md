# Bounded QSPI command interface

T29 is a command-mode subset of plans04/07, using new clocked Chisel because
the pinned RISCay baseline bit-bangs flash and has no QSPI controller. Adopt
shared CdcSync, ResetRelease, RegBlock and BusRegAdapter unchanged. No vendor
source is imported. XIP remains an error stub; no complete boot/logging claim.

## Ports and wire contract

Main-domain clk/reset_n and LocalBus; dqIn[3:0]; registered dqOut/dqEnable,
sclk/sclkEnable, cs_n[1:0]/csEnable, clockHold. Qualified service reset clears
everything, owner to lite0, outputs disabled, clock low and CS inactive.
Performance core reset and AON service reset do not reset a surviving transfer.
Existing profile requires running external clocks; demand is not permission
to stop the domain or proof of a completed clock controller.

Mode0, MSB first. A command snapshots all settings and emits serial8-bit opcode,
optional0..4 address bytes (single/quad),0..31 dummy SCLK cycles and optional
0..4 payload bytes (single/quad, TX or RX). Low N bytes of address/TX are sent
MSB first; RX is right-aligned and zero-extended. Opcode uses DQ0; serial RX
uses DQ1. Serial phases hold DQ2/3 high; TX enables0xd, RX enables0xc. Quad TX
enables all lanes; quad RX and dummy clocks release all lanes. Firmware must
configure the selected flash's quad mode and qualify dummy/pull-up requirements.
No part/opcode is implicitly selected, no flash busy-poll loop runs in RTL.
Phase/direction changes occur only while SCLK is low. Controller reset aborts
the pin transaction; it cannot cancel a flash-internal program/erase already
accepted by the external device.

Half-period H is4..255 main edges. CS setup before first rise, hold after last
fall, and high gap are each H edges. Busy includes the gap, so idle handoff
cannot shorten it. Longest serial frame has8+32+31+32=103 SCLK cycles;
estimated conservative command bound is(2×103+3)×255+4=53299 main edges.
Tests use that bound; it is not a measured payload throughput.
START enables CS/SCLK pads until reset, with both CS high when idle. DQ output
enable follows the phase and releases at completion; reset disables all pads
asynchronously. Board pull-ups must keep deselected flashes safe during reset.

DQ inputs use shared two-flop CdcSync as an oversampled source-synchronous
bus: each lane must settle before the first main edge following the flash's
falling-edge launch, and remain stable through sampling. H>=4 provides settling
for that digital contract. This is not an arbitrary multibit CDC guarantee.
Pad/board delays and metastability remain physical qualification obligations.

## Registers and ownership

Window0x40013000..0x40013fff. One outstanding adapter transaction; origin is
checked at endpoint acceptance. Current owner alone can read/write. Reset
owner0(lite); keyed idle handoff accepts0(lite) or1(performance). A handoff
updates only when its generated pulse is consumed; subsequent old-origin
requests are rejected at admission. This opt-in override does not change
fixed ownership in earlier profiles. No interrupt/DMA route is introduced.
Handoff preserves shadows, result and sticky events. Its registered response
returns to the old requester even though later old-origin admissions fail.

| Offset | Register | Contract |
| --- | --- | --- |
| 0x00 | configuration | CS bit0, address bytes[3:1], payload bytes[6:4], read bit7, quad address bit8, quad data bit9 |
| 0x04 | timing | half-period[7:0], reset4; dummy clocks[12:8] |
| 0x08 | opcode | low8 bits |
| 0x0c | address | 32-bit shadow |
| 0x10 | tx_data | 32-bit shadow |
| 0x14 | launch | full-word WO key0x51535049, reads zero |
| 0x18 | rx_data | read-only last completed RX word; TX/no-data completes with zero |
| 0x1c | status | busy bit0, owner[3:1] |
| 0x20 | events | done bit0, command_error bit1; W1C, set wins |
| 0x24 | handoff | full-word WO0x4f574e00|owner, reads zero |

Shadow writes during busy affect only the next command. Invalid lengths,
divider, key, busy launch/handoff or simultaneous launch/handoff set error
without changing active transfer or owner. Partial WO writes bus-error;
zero-strobe writes do nothing. All other invalid addresses/origins error.
Result changes only on completion, remains until next completion/reset;
events are sticky and never implicitly cleared by START. Software consumes
the previous result before launching another read.

Measured standalone mapped area is75372.192µm² and worst register delay is
18.435669ns, by pinned `python hw/ip/qspi/check_timing.py --output
build/t29/frozen01/timing`, main HEAD72bcfacc plus receipt-hashed local sources.
Estimated conservative budget is0.60×1000/9=66.666667ns; measured electrical
violations0. This is pre-layout screening, not whole-chip area or physical
qualification. No new area allowance is assumed. Tests, formal scope and
physical limitations are in formal/ and the T29 report. Neither CI tier ran.

T30 optionally adds a shared native read scheduler and extension registers;
see [native QSPI contract](../qspi_xip/README.md). The default command-only
profile retains this register map and busy-rejection behavior.
