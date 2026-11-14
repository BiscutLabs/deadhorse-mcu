# lib

Shared Chisel bundles, bus interfaces and register-block support.

## RegBlock timing structure

`RegBlock` keeps the register-map bus, asynchronous active-low reset and
hardware priority contract in [the register-map specification](../../docs/spec/regmap-format.md).
Each write is qualified by its own full address hit and the partial-command
check for fields at that address. A full hit already implies a mapped,
word-aligned address. A partial command suppresses all software updates at
that address; hardware updates continue. Response error generation remains
global. The one-hot read mux already returns zero on a missing full address
hit, so read data does not traverse the response-error reduction either.
This avoids routing a global mapped-address reduction into every
storage enable without adding latency, changing ports or changing clocks.
The existing independent-model simulations and formal properties check the
same externally visible behavior. GF180 measurements are recorded in the
[timing ledger](../../docs/ledger/timing.md).

## Hello build fixture

`deadhorse.lib.Hello` is the T07 clocked build/verification fixture. Ports:
`clock` (rising edge), `reset_n` (active-low asynchronous reset), `in` and `out`
(unsigned eight-bit). Each rising edge captures the successor of `in` modulo
256. `out` is registered and resets to zero, including between clock edges.
Reset release must meet the caller's clock-domain reset contract; this fixture
does not implement a reset synchronizer or a CDC. It uses the supplied single
clock, with one edge of latency and no combinational input-to-output path.
The caller must assert reset before relying on the output.

T09 measured 897.8368 um2 mapped cell area and a 3.880023 ns worst path at the
GF180 slow corner; the [timing ledger](../../docs/ledger/timing.md) records the
command, base commit and assumptions. This is pre-layout screening, not
physical signoff. There are no software-visible registers.

Use `python3 tools/sbt.py "hw/test"` inside T08 for ChiselSim/Verilator tests.
The independent model enumerates the cyclic byte alphabet. Tests check every
input, output stability before an edge, asynchronous reset between edges, and
recovery after reset. A wrong-increment implementation must be detected by the
same checker. Formal contracts and assumptions are in [formal/README.md](formal/README.md).

The build reads dependency versions from T08's lock, discovers only lib, IP
and top source/test directories, and excludes vendor/template owners. The
launcher mirrors only the build definition under `build/sbt/definitions/<hash>` so
sbt's meta-build artifacts cannot leak into `project/`. No upstream source
library is a dependency. Status: simulation/formal build fixture, not physically
qualified IP.

The complete local gate is `python tools/env/run.py run -- python3 tools/ci.py`.
For a first dependency download, use `python tools/env/run.py --network bridge
run -- python3 tools/ci.py`. No hosted CI service is required.
