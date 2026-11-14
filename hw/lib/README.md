# lib

Shared Chisel bundles, bus interfaces and register-block support.

## Hello build fixture

`deadhorse.lib.Hello` is the T07 clocked build/verification fixture. Ports:
`clock` (rising edge), `reset_n` (active-low asynchronous reset), `in` and `out`
(unsigned eight-bit). Each rising edge captures the successor of `in` modulo
256. `out` is registered and resets to zero, including between clock edges.
Reset release must meet the caller's clock-domain reset contract; this fixture
does not implement a reset synchronizer or a CDC. It uses the supplied single
clock, with one edge of latency and no combinational input-to-output path.
The caller must assert reset before relying on the output.

Area is not measured: estimated storage is eight resettable flip-flops, plus
an eight-bit incrementer. GF180 area/timing qualification belongs to T09; this
build fixture makes no timing claim. There are no software-visible registers.

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
