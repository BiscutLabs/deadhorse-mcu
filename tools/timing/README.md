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

The exit codes are 0 for a passing measurement, 1 for an over-budget path or
library max-capacitance/max-slew violation,
and 2 for an unsupported or incomplete analysis. The self-test expects the
historical elapsed-time path to exit 1; it does not waive any production block.
It also checks Hello and the mixed and coverage RegBlock configurations, verifies
nonzero clock-to-Q on a direct register output, rejects an unconstrained clock
in the real timer, and rejects the T06 SRAM synthesis stub before optimization.
The larger RegBlock coverage configuration initially exceeded the budget.
The user-authorized local write/read decode repair now passes with the same
interface, behavior, corner and ceiling; the failing history remains in the ledger.

Inherited stateless core leaves can use `--combinational` instead of `--clock`.
This uses a virtual clock with the same IO constraints and budget. Both the
netlist boundary validator and STA reject sequential cells in this mode.
The self-test includes a pure Chisel XOR positive control and actual sequential
wrong-mode negatives. An electrically overloaded Hello output must fail even
while its data delay meets the budget; missing electrical reports also block.

The qualified `buffered-sized-alias-load-v3` mapping recipe uses ABC
buffering and sizing with an explicit script containing no retiming. Its
`buf_1` driver, output load in fF and target in ps are mapping heuristics,
recorded separately from the unchanged final STA slew/load constraints.
After synthesis, output pins that share a net are counted. ABC uses the maximum
aggregate output load as a conservative global mapping heuristic; constants are
excluded, and any new alias multiplicity introduced by ABC blocks the result.
Final STA still loads each output port with 0.05 pF. The AliasTiming fixture
checks two output pins, 100 fF mapping load and unchanged 50 fF per-port STA.
The historical v1 recipe used one 50 fF mapper load regardless of aliases.
The intermediate v2 recipe reimported a premapped JSON design, perturbing ABC
traversal order even without aliases. V3 uses the premap pass only for alias
discovery and repeats the original frontend/synthesis sequence for mapping.

Synthesis buffers are included in timing and area; physical clock-tree/wire
buffering is still outside this pre-layout screen. Historical area-only
measurements retain their original flow hashes and are not overwritten.

## Supported constraints

[block-timing.json](../../phys/gf180-ws-1x1/block-timing.json) records the plan's
assumed 41.6 ns period and 60% budget (24.96 ns), assumed 0.5 ns input slew and
0.05 pF output load. All nonclock inputs, including reset, have zero external
delay; every output has zero external delay. These isolate the block's data
delay. The clock is ideal with zero latency/uncertainty; no parasitics, wire
delay, placement, clock tree or physical buffering are modeled.

The flow accepts one rising-edge root clock, directly or through the qualified
root-driven `gf180mcu_fd_sc_mcu7t5v0__icgtp_1`. Every sequential pin must report
exactly that root clock by identity; merely counting clocks is insufficient in
OpenSTA. Arbitrary clock logic, cascaded gates, extra clocks, explicit storage
latches, falling-edge clocks, inouts and uncharacterized black boxes are
blockers. SRAM instances require qualified macro timing views and a later
explicit integration; an empty SRAM stub must never be flattened away and
mistaken for timed logic. No false paths, multicycle exceptions, arbitrary
periods, corner substitutions or waiver switches are provided.

For RR, IR, RO, IO and register/input-to-ICG-enable (RG/IG) paths, OpenSTA enumerates every endpoint and both
transition polarities. The budget uses endpoint arrival from the ideal launch
edge (or zero input delay), including clock-to-Q. Subtracting the first listed
point would be wrong because that point may already be a flop's Q output.
Logic depth counts unique combinational instances; cell depth also includes
launch/capture registers. Missing path classes are recorded as `null`.

For each ICG E/TE pin, all rise/fall setup/hold paths must exist and have
nonnegative slack; evidence is in `gate_checks.tsv` and `clock_gate_checks`.
The gated fixture includes actual STA negatives for an alien clock and late
setup/early hold. Clock propagation at a characterized cell load is checked
separately by `hw/lib/formal/clock_gate_timing.py`; ideal pre-CTS top timing
does not imply clock-tree signoff.

This is a **maximum data-path screening check**, not routed timing signoff.
Setup/hold/recovery/removal reports are retained as diagnostics; zero IO timing
assumptions can produce hold/removal violations, and these are not represented
as qualified interface timing. Full physical timing and SRAM/clock integration
remain required by the physical-verification plan.
ICG E/TE setup/hold checks are the explicit mandatory exception to the diagnostic
handling above, because the wrapper must not glitch its clock.

`dv/core/reference_timing.py` supplies only the locked reference configuration
to the shared numeric flow and labels its receipts `reference-benchmark-only`.
It binds the same ASIC gate and omits RVFI in both compared physical profiles.
The production API and CLI always enforce reference-source isolation; a
benchmark result never waives a production timing failure.

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

## User-authorized timing trials

`--operating-point main-12mhz` selects the T13 experiment requested on
2026-11-16. It sets the clock period to 1000/12 ns and preserves the 60 percent
allowance (50 ns), slow-corner library, slew/load, clock-gate and electrical
checks. ABC's mapping target and OpenSTA's clock both use that operating point.
No RTL is changed. The default and all existing CI commands remain at the
pinned 41.6 ns period / 24.96 ns allowance.

```sh
python tools/env/run.py run -- python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/clock12/no-f-emit/asic --operating-point main-12mhz --output build/t13/clock12/no-f-timing
```

Receipts label this `role: operating-point-trial`, with the named operating
point and effective assumptions. A trial pass is not default production
acceptance or physical signoff. The generic timing CLI also accepts this named
point for positive/negative fixtures; `--self-test` remains a default-flow test
and rejects a simultaneous trial selection. Only the explicitly named trial frequencies are accepted.
The global clock decision and cycle-based firmware deadlines are separate from
this pre-layout experiment.

The approved faithful-core trial uses `--operating-point main-9p6mhz`: period
1000/9.6 ns, allowance 62.5 ns. Emit with
`python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulCore build/t13/faithful9p6/emit"`,
then run `hw/ip/perf_core/check_top_timing.py` on its `asic` directory.
This emitter selects the existing faithful RV32IMC hierarchy, with the same
physical ports, flop register file, disabled RVFI and real clock gate as the
registered physical view. Its `model` view retains RVFI for comparison with
the previously qualified faithful candidate. It does not implement F or
adopt a production frequency.

The follow-up `--operating-point main-9mhz` trial uses the same faithful
emitter with period 1000/9 ns and allowance 200/3 ns (66.666667 ns).
Use a separate output directory, such as `build/t13/faithful9/`, to preserve
the failed 9.6 MHz receipt. It is a fresh mapping, not a relabelled result.
The T32 D80 follow-up uses a 50000 ps ABC optimization target; the earlier
62500 ps recipe and its failing receipt remain recorded. This tighter mapping
goal changes synthesis effort, not the clock or acceptance. For DeadhorsePerfCore,
the recipe also reloads the freshly emitted premapped JSON before ABC; its
traversal order is part of the measured improvement. A tighter target alone
did not reproduce it. Other targets retain their existing mapping sequence.
STA still applies the
9 MHz period and 66.666667 ns allowance. Mapping-target provenance is explicit
in the receipt; no arbitrary target override is offered. Default production
timing, other trial targets and all non-period acceptance constraints stay unchanged.
