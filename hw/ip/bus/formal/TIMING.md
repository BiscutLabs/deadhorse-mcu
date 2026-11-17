# T14 area and timing measurement

Run from the pinned environment:

```sh
python3 hw/ip/bus/formal/timing.py --output build/t14/timing
```

The output directory must be fresh. The driver emits production modules,
runs the unchanged T09 single-clock checker on each, records source hashes,
and rejects changed inputs or any failing component. No clock is tied to
another clock for measurement. The default slow-corner library and 24.96 ns
budget apply to every module, including those intended for the slower AON
clock. Individual receipts retain path endpoints, logic depth, area, tool
versions, constraints and commands.

The measured configurations are:

- `BusFabric`: three masters; two aligned 4 KiB regions at 0x1000 and
  0x2000; watchdog limits 128 and 131080 cycles.
- `BridgeSource`: 131072-cycle watchdog; `BridgeTarget`: production defaults.
- `DirectionArbiter`: the real AON state machine used by `DirectionPermit`.
- `MailboxEndpoint`: generated mailbox register description, owners 0 and 1.
- `CdcWrite` and `CdcRead`: depth two, widths 32, 33 and 72, including each
  half's internal pointer synchronizer.
- `ResetRelease` and `CdcSync`: production primitives; sync widths one and two.

`component_sum` is an **estimate from measured module areas**, not a
measurement of an integrated SoC. It adds two of the representative fabrics,
two one-way bridges, one direction arbiter and one two-way mailbox. Each
bridge adds a source, target, 72-bit request FIFO, 33-bit response FIFO,
eight reset-release instances and two one-bit synchronizers. The mailbox
adds its two endpoints, two 32-bit FIFOs and six reset-release instances.
The direction-permit wrapper adds two reset-release instances and three
one-bit synchronizers. This totals 24 reset-release and seven external
one-bit synchronizer instances. FIFO synchronizers are already included
in the FIFO halves and are not counted again.

The sum excludes combinational reset glue and integrated synthesis
optimization. The actual address map, master count and domain top-level
timing remain integration work. Measurements are mapped, pre-layout, with
no wire delay. They do not qualify Gray-pointer skew, CDC payload settling,
metastability MTBF, reset recovery/removal or routed timing. Those physical
crossing constraints remain required at integration and signoff.
