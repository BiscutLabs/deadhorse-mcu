# Per-block GF180 timing ledger

Measured with `python tools/env/run.py run -- python3 tools/timing/check.py
--self-test --output build/t09`, based on commit
`19b7664881ded9c4f7900f79f01cf0c874de26a0` plus the uncommitted T09 changes.
Per-result flow/source hashes identify the exact candidate. Tools: pinned native
Yosys 0.71+34 with slang, OpenSTA 3.2.0; library
`gf180mcu_fd_sc_mcu7t5v0`, SS/125 C/3.0 V, SHA-256
`5d2f37ba6f43e33aeba26dc1da55c96394a862eeec4148043f1d48bdf65ccea6`.

The period is **assumed** 41.6 ns and budget fraction **assumed** 60% per plan 14;
the budget is **calculated** as 41.6 x 0.60 = 24.96 ns. Input slew is **assumed**
0.5 ns and output load **assumed** 0.05 pF. IO delay and ideal-clock latency are
**assumed** zero. All figures below are **measured, mapped, pre-layout, no wire
delay**. Cell area is raw standard-cell area, not placed or total die area.

| Block/configuration | Worst delay | Start | End | Combinational depth | Cell area (um2) | Budget result |
| --- | ---: | --- | --- | ---: | ---: | --- |
| Hello | 3.880023 ns | in[0] | _29_/D | 3 | 897.8368 | Pass |
| RISCay ClockedElapsedTicks, negative control | 121.539406 ns | _3512_/Q | _3254_/D | 4 | 46902.6432 | Expected fail |
| RegBlock, mixed fixture, before repair | 15.123760 ns | _281_/Q | _263_/D | 4 | 7015.8592 | Pass |
| RegBlock, coverage fixture, before repair | 44.802906 ns | bus_req_addr[1] | _1679_/D | 7 | 37963.7888 | Fail; repaired below |

RISCay's unmodified T06 elapsed-time export produces a path consistent with the
historical approximately 120 ns warning. This is an isolated block mapped by
the current pinned tool, not an exact rerun of the historical whole-chip mapping.
No historical measurement was replaced or tolerance relaxed. An intermediate
implementation incorrectly subtracted clock-to-Q and reported 100.022171 ns;
independent review found that error. The corrected 121.539406 ns includes the
measured 21.517235 ns launch clock-to-Q. The direct-output self-test protects
against that omission.

The coverage fixture exercises the actual RegBlock implementation with its
existing format-coverage register map; it is not an actuator ABI. Both its
input-to-register path (44.802906 ns) and register-to-register path (31.208696 ns)
exceeded the same budget before repair. The failing address-decode/write-enable
path and per-cell arrivals are preserved in `build/t09/coverage/timing/paths.tsv`.
Neither the fixture nor its check was removed. The user explicitly authorized
extending T09 to repair RegBlock while keeping behavior, budget and checks intact.

## Authorized RegBlock repair

Measured with `python tools/env/run.py run -- python3 tools/timing/check.py
--self-test --output build/t09/repair2`, same base commit plus the reviewed RTL
repair. The environment, synthesis recipe, library and constraints above are
unchanged. Each row's emitted source hash is in its `result.json`.

| Block/configuration | Worst delay | Start | End | Combinational depth | Cell area (um2) | Budget result |
| --- | ---: | --- | --- | ---: | ---: | --- |
| RegBlock, mixed fixture, repaired | 12.011798 ns | _319_/Q | _301_/D | 4 | 7121.2288 | Pass |
| RegBlock, coverage fixture, repaired | 19.390715 ns | bus_req_addr[1] | _1964_/D | 6 | 38312.8256 | Pass |

Writes now use full address hits and command qualification local to that
address. Reads rely on the one-hot read mux's existing zero on a missing hit,
so the global response-error decode no longer fans out into data storage.
No port, latency, reset, access policy or hardware priority changed. The
intermediate local-write-only repair measured 25.511124 ns and still failed;
`build/t09/repair1/` retains that result. The complete repair passes the original
ceiling without adding a pipeline stage or changing the mapping recipe.

Independent agent `t09_repair_review` reproduced the repaired coverage result
using `python tools/env/run.py run -- python3 tools/timing/check.py --top RegBlock
--source build/t09/repair2/coverage/emit/RegBlock.sv --clock clk
--output build/t09/reviewer-repair-coverage` (exit 0). All figures remain mapped,
pre-layout screening measurements, not routed signoff.

Exact synthesis and timer invocations are in each measurement's
`commands.jsonl`: `yosys -Q -T -s <output>/elaborate.ys`,
`yosys -Q -T -s <output>/synth.ys`, and
`sta -no_init -exit <output>/timing.tcl`. The generated scripts record every
input path and constraint. See [T09's report](../plan/tasks/reports/T09.md).
