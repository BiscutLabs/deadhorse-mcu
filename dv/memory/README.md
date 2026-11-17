# S3 memory experiment

Run in the pinned environment:

```sh
python3 tools/spikes/s3_memory/memory_models.py --output build/s3-memory
python3 -m unittest dv.memory.test_memory
```

These are Python organization/transaction models, **not SRAM macro or controller
RTL validation**. Formal properties do not apply to this nonhardware experiment.
The receipt records inputs, source hashes, seed, model observations and estimates.

`BankedWords` uses contiguous banks of 32-bit words and byte strobes. An independent
byte-address dictionary checks all 16 masks, every bank boundary, first/last words,
invalid/misaligned accesses, deterministic random writes/reads, configured 1/2/5
edge latencies and held responses under backpressure. Model storage starts zero;
this makes no power-on SRAM-content claim. Actual model faults alias banks, reverse
byte lanes, overwrite disabled bytes or complete early; the normal checker must
reject each. Capacities are the baseline 16 KiB and 3 KiB, with several bank counts.

The flash event scheduler and independent closed-form/scenario oracle use two
**assumed** profiles: SPI at 12 MHz and quad data/address at 24 MHz. No part is
selected. These serial clocks are independent assumptions, not derivations from
the current CPU clock. Opcode, address and mode widths/lanes, dummy cycles, CS gap,
page size, maximum burst, program busy and erase busy are explicit profile fields.
32-bit addresses are assumed because a 24-bit byte address cannot reach 40 MiB.
The serial table is 0x0C four-byte fast read (1-1-1, eight dummy clocks), 0x12
four-byte page program (1-1-1), 0x06 WREN, and 0xDC four-byte block erase.
The quad table changes only read to assumed 0xEC (1-4-4, eight mode bits on four
lanes, six dummy clocks); program remains 0x12 with serial address and data.
These exact hypothetical command tables require part qualification. The model
does not establish support, timing or mode-value requirements on a real device.

Boot/XIP uses one chip select; logging uses another. One priority read may be
outstanding. It waits for at most the remaining current bounded log transaction,
then its own read. Boot is modeled as a serialized synthetic full-SRAM load before
flight; this is not firmware size evidence. All program transfers respect page
boundaries. Each program/erase has a separate WREN transaction, and XIP can
interleave between them. Device busy releases the bus. The experiment assumes
conservative fixed waits after each command of 3 ms program / 400 ms erase,
assumed upper bounds that must be qualified for a selected part. No polling
traffic is modeled. Real status polls, controller overhead and clock/domain
startup need separate bounded budgets.

The assumed producer stages four 64-byte records into 256-byte pages, with eight
queued batches (2048 bytes) plus 256 bytes staging. These buffers must appear in
the firmware allocation; no free-memory assumption is implied. Enqueue never
advances modeled time and drops/counts whole batches on overflow. CPU cost of
copying/enqueueing is outside the experiment. The 600-second flight assumes a
pre-erased logging region. A separate erase stress checks overflow and XIP
isolation, without claiming sustained logging during erase. A queue recurrence
independent of the event scheduler checks drops. All SCLK arrival edges during
WREN, maximum program and erase transfers are checked against the latency bound.
The 600-second flight stimulus injects one 64-byte XIP read per second; this is
an explicit scenario assumption, not a measured firmware access pattern. A
one-second final drain allowance follows the arrivals; the receipt records when
the last program becomes durable under the assumed maximum busy-time wait. A
separate arithmetic service bound includes one 64-byte read per programmed page.
Continuous priority XIP traffic can starve logging: the bounded queue still
drops/counts records and never blocks the loop, but sustained 64 kB/s is not
claimed under arbitrary XIP demand. The hot loop must remain entirely in SRAM.
Fault controls omit dummy clocks, allow an unbounded program burst, or retain
the shared bus through device busy; the normal scenario checker rejects them.

64 bytes × 1000/s × 600 s = 38,400,000 bytes. The existing 40 MiB allowance is
41,943,040 bytes, leaving 3,543,040 bytes before metadata, erase reserve and unusable
sectors. This is arithmetic from assumed inputs, not storage-part qualification.
Area, power, macro latency, retained behavior and physical fit remain unmeasured.
