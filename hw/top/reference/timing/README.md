# I0 mapped-logic diagnostics

These focused tools do not run CI. They consume a previously authenticated
GF180-mapped I0 netlist with the five synchronous memory interfaces exposed.
They do not implement memory macro mapping or establish whole-chip signoff.
The current I0 top includes RVFI observation logic; retain that scope in reports.

- `buffer_resets.py --mapped build/.../mapped.json --output build/...` inserts
  the existing characterized non-inverting buffer trees only on the two named
  release nets. Every original pin and clock must restore exactly through the
  buffers. A real production-netlist feedback fault must be rejected.
- `size_path.py --netlist build/.../mapped.v --output build/... --cell instance=cell`
  accepts explicit same-family combinational sizing choices. Actual Liberty
  function equality is proved for every input, with a polarity negative per
  cell pair. No state, connection or clock-topology change is allowed.
- `logic_timing.py --mapped-dir build/... --output build/...` times the same
  netlist at the brief's 8 and 9 MHz trial clocks with unchanged 60% budgets,
  electrical assumptions and pinned slow-corner library. All dynamic ICG and
  applicable RN/SETN release checks remain; literal-zero TE is recorded.
  Negative electrical, setup, hold or reset slack fails the result. Reset
  endpoint coverage, finite results and rejecting checker controls are required.

Outputs must be new directories under `build/`. Run via
`python tools/env/run.py run -- python3 <script> ...`.
The T20 report lists exact measured commands and rejected experiments.
Passing this logic-only screen does not qualify macro delays, board/pad
boundaries, routed parasitics, clock/reset distribution or RDC signoff.
