# Register-map tooling and RegBlock contract

The [format](../../docs/spec/regmap-format.md) is normative. Run
`python3 hw/regmap/regmap.py <description> --out build/regmap/<block>` inside
the pinned environment. JSON, headers and tables are generated artifacts.
JSON schema version 1 expands arrays, stores offsets as exact decimal strings
(avoiding floating-point rounding in JSON readers), and records numeric `lsb`, `msb`, `width`,
`reset` (stored fields only), access and descriptions; it is the sole input to
the Chisel block and the independent Python model.

`RegBlock` has explicit `clk` and asynchronous active-low `rst_n`. Instantiate
it in one clock domain; all hardware inputs must already belong to that domain.
Reset release is the caller's synchronized domain reset. No crossing is built
here. `RegBus` is target-oriented; `Flipped(new RegBus(width))` is its initiator
view. The hardware `Record` uses the format's `<reg>_<field>_<suffix>` names.

All outputs are registered. A request accepted at a rising edge produces its
response and any command pulse immediately after that edge. While that response
is pending, request ready stays low; accepting the response restores ready for
the following cycle. There is no combinational ready path. Reset clears pending
responses and pulses, restores stored-field reset values and sets ready high.
The response captures live `ro` inputs at request acceptance. Read and write
responses are stable under backpressure. `wo` data is zero outside its pulse
(only pulse-qualified data is contractual). Hardware updates run every edge,
including during stalled responses and rejected requests.

The Python model offers `drive`, `outputs`, `reset`, `idle` and atomic `request`.
`request` represents one accepted-request edge; `idle` represents an edge without
an accepted request. Trace generation adds protocol timing separately.

Status: implemented and verified against the T05 format fixtures. GF180 area/timing is unmeasured;
the reusable timing flow is T09. Estimated storage is the sum of stored-field
widths, pulse/data-output widths, and 35 response/ready bits. This excludes
decode/next-state logic and is not an area estimate in square millimetres.
Formal assumptions and commands are in
[the register proof contract](../lib/formal/regblock.md). No actuator ABI is
defined by these fixtures.
