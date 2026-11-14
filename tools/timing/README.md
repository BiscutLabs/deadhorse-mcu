# GF180 block timing

Run inside the pinned Linux environment. T06's exported RISCay design and
its pinned merged slow-corner Liberty must already be present in `build/`.
Missing inputs are blockers; this tool does not download substitutes.

```sh
python tools/env/run.py run -- python3 tools/timing/check.py --self-test --output build/t09
python tools/env/run.py run -- python3 tools/timing/check.py --top Hello --clock clock --source build/emit/hello/Hello.sv --output build/timing/hello
```

Repeat `--source` for additional emitted files. `--liberty` may point to another
repository-local copy, but its bytes must match the pinned SS/125 C/3.0 V hash.
All paths must remain inside this repository; outputs must be below `build/`.
Paths containing whitespace or Tcl/Yosys metacharacters are rejected.

The exit codes are 0 for a passing measurement, 1 for an over-budget path,
and 2 for an unsupported or incomplete analysis. The self-test expects the
historical elapsed-time path to exit 1; it does not waive any production block.
It also checks Hello and the mixed and coverage RegBlock configurations, verifies
nonzero clock-to-Q on a direct register output, rejects an unconstrained clock
in the real timer, and rejects the T06 SRAM synthesis stub before optimization.
The larger RegBlock coverage configuration initially exceeded the budget.
The user-authorized local write/read decode repair now passes with the same
interface, behavior, corner and ceiling; the failing history remains in the ledger.

## Supported constraints

[block-timing.json](../../phys/gf180-ws-1x1/block-timing.json) records the plan's
assumed 41.6 ns period and 60% budget (24.96 ns), assumed 0.5 ns input slew and
0.05 pF output load. All nonclock inputs, including reset, have zero external
delay; every output has zero external delay. These isolate the block's data
delay. The clock is ideal with zero latency/uncertainty; no parasitics, wire
delay, placement, clock tree or physical buffering are modeled.

This first flow accepts a single direct rising-edge clock. Latches, non-root
clock connections, falling-edge clocks, inouts and uncharacterized black boxes
are blockers. SRAM instances require qualified macro timing views and a later
explicit integration; an empty SRAM stub must never be flattened away and
mistaken for timed logic. No false paths, multicycle exceptions, alternate
periods, corner substitutions or waiver switches are provided.

For RR, IR, RO and IO paths, OpenSTA enumerates every endpoint and both
transition polarities. The budget uses endpoint arrival from the ideal launch
edge (or zero input delay), including clock-to-Q. Subtracting the first listed
point would be wrong because that point may already be a flop's Q output.
Logic depth counts unique combinational instances; cell depth also includes
launch/capture registers. Missing path classes are recorded as `null`.

This is a **maximum data-path screening check**, not routed timing signoff.
Setup/hold/recovery/removal reports are retained as diagnostics; zero IO timing
assumptions can produce hold/removal violations, and these are not represented
as qualified interface timing. Full physical timing and SRAM/clock integration
remain required by the physical-verification plan.

## Evidence

Each measurement writes `result.json`, `paths.tsv` (including per-point arrival
times), `ledger-row.md`, `commands.jsonl`, exact synthesis/Tcl scripts, mapped
JSON/Verilog and tool logs. Results record source/flow/library hashes, tool
versions, base Git commit and dirty state. Old success is invalidated at entry.
Only a successful self-test writes a passing `self-test.json`.

The self-test emits production Chisel without modifying it. Its Scala entry
point is loaded for that invocation only. The local gate includes the timing
check after the existing simulation/formal checks, which remain intact.
See the [timing ledger](../../docs/ledger/timing.md) for measured results.
