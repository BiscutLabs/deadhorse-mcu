# Per-block GF180 timing ledger

## T11 final focused acceptance, 2026-11-15

Base `a532304` plus final source/flow hashes: `python tools/env/run.py run --
python3 hw/ip/perf_core/check_top_timing.py --emitted
build/t11/csrfinal1/emit/asic --output build/t11/csrfinal1/top_timing` measures
**24.923273 ns**, **458348.9792 um2**, zero electrical violations, minimum
ICG enable setup/hold slack **0.704980 ns**. Complete core/RF/real-ICG hierarchy;
unchanged assumed 24.96 ns limit and GF180 SS/125C/3.0V pre-layout conditions.

The corresponding standalone CSR command (`tools/timing/check.py --top
ibex_cs_registers --source build/t11/csrfinal1/leaves/cs_registers/ibex_cs_registers.sv
--clock clk_i --output build/t11/csrfinal1/csr_timing`) measures **23.427544 ns**,
**87906.7840 um2**, zero electrical violations. Independent reproduction matches.
The earlier 25.379574 ns CSR failure is retained under
`build/t11/ci-before-csr-fix/timing/cs_registers`; a local mstatus RMW repair
preserves exact state/cycle behavior. Fresh aggregate block timing also passes
at `build/t11/ci/timing`. No constraint changed. Full CI was later stopped at
the user's direction; focused closure is documented in the T11 report.

The following sections preserve earlier measured checkpoints.

2026-11-15 T11 registered execution replacement (base `a532304` plus working
changes): measured **23.112328 ns**, mapped cell area **130017.3056 um2**, zero
electrical violations. Command: `tools/timing/check.py --top ClockedExecute
--clock clk_i` with the four emitted sources under
`build/t11/registered1/emit/clocked_execute`, output
`build/t11/registered1/timing`. Independent fresh emission/reproduction:
`build/t11/registered_review/timing1`. Same qualified alias-aware mapping,
SS/125C/3.0V GF180 library and assumed24.96ns limit. Approved extra execution
cycles; old integrated designs remain strict diagnostic failures through
`check_timing.py --profile pre-registered`. Not whole-core or post-layout signoff.

Decoder/LSU follow-up, same base and constraints: `tools/timing/check.py` for
`ibex_decoder` (combinational, `build/t11/decoder1/emit/decoder/ibex_decoder.sv`)
measures **15.133662 ns**, **8372.4928 um2** at `build/t11/decoder1/timing`.
For `ibex_load_store_unit` (clock `clk_i`, emitted under `build/t11/lsu1/emit`),
it measures **16.342241 ns**, **14874.6752 um2** at `build/t11/lsu1/timing`.
Both have zero electrical violations and fresh independent reproductions under
`build/t11/decoder_review/timing` and `build/t11/lsu_review/timing`.

IF/controller/WB follow-up (same base, corner, recipe and constraints), measured
with `tools/timing/check.py`, commands in T11's report:

| Block | Root receipt | Delay (ns) | Cell area (um2) | Electrical violations |
| --- | --- | --- | --- | --- |
| IF stage, translated children | `build/t11/if1/timing` | 23.411352 | 52581.6256 | 0 |
| Controller | `build/t11/controller1/timing` | 18.369602 | 7966.3808 | 0 |
| WB bypass | `build/t11/wb1/timing` | 6.218218 | 1108.576 | 0 |

Fresh independent reviewers reproduced each at
`build/t11/{if_review,controller_review,wb_review}/timing`. All pass the assumed
24.96 ns budget; no whole-core or post-layout claim. CSR-bank initial mapping
at `build/t11/csrbank1/timing` measures 24.659073 ns, 84921.312 um2 and zero
electrical violations. Fresh mapping at `build/t11/csrbank2/timing` reproduces
those values and passes independent review at `csrbank2/independent-review/timing`.
CSR formal acceptance now uses the explicitly approved priority analysis model;
the original failure remains recorded separately.

ID stage with translated decoder/controller, same base and constraints:
`tools/timing/check.py --top ibex_id_stage --clock clk_i`, all three sources
under `build/t11/id1/emit/id_stage`, output `build/t11/id1/timing`, measures
**24.466211 ns**, **29215.9168 um2**, zero electrical violations. Independent
review reproduces those values under `build/t11/id1/independent-priority/timing`.
Fresh root mapping at `build/t11/id2/timing` reproduces these measurements.
Its formal comparison passes with the approved priority analysis normalization;
this block timing pass does not establish overall acceptance or full-core timing.

## T11 buffered/sized mapping qualification

Measured at base `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus working
changes. The new `buffered-sized-combinational-v1` recipe uses explicit ABC
combinational mapping, buffering and sizing, with no retiming. The assumed
mapping driver is the pinned library's `buf_1`, mapping load 50 fF and target
24960 ps. These guide mapping only: final STA retains the original library
hash/corner, 0.5 ns input slew, 0.05 pF output load, ideal clock, zero IO delay
and 24.96 ns budget. All new rows also require zero max-capacitance/max-slew
violations. Earlier rows preserve their original recipe and outcomes; some
area-only mappings exceed library electrical limits and cannot be treated as
clean characterized results or compared directly with these areas.

Primary commands use `python tools/env/run.py run -- python3 tools/timing/check.py`
with the top, emitted sources, clock or combinational mode and output paths in
the table. Exact invocations, source hashes and mapping recipe hashes are in
each output's `commands.jsonl`/`result.json`.

| Top/configuration | Source under build/t11 | Mode | Output under build/t11 | Delay ns | Area um2 | Result |
| --- | --- | --- | --- | ---: | ---: | --- |
| ibex_alu, repaired | alu9/emit/alu/ibex_alu.sv | combinational | alu9/timing_sized | 23.850603 | 43339.8336 | Pass |
| ibex_counter, mcycle | leaves_v2/emit/mcycle/ibex_counter.sv | clk_i | leaves_v2/timing_mcycle | 21.831022 | 10776.2368 | Pass |
| ibex_counter, counter11 minstret | counter11/emit/minstret/ibex_counter.sv | clk_i | counter11/timing_minstret | 19.555578 | 13676.0960 | Pass |
| ibex_register_file_ff | leaves_v2/emit/register_file/ibex_register_file_ff.sv | clk_i | leaves_v2/timing_rf | 14.182172 | 155747.2448 | Pass |
| ibex_compressed_decoder | leaves_v2/emit/compressed_decoder/ibex_compressed_decoder.sv | combinational | leaves_v2/timing_compressed | 13.134775 | 6001.6768 | Pass |
| ibex_fetch_fifo, repaired | fifo2/emit/fetch_fifo/ibex_fetch_fifo.sv | clk_i | fifo2/timing | 19.284517 | 18948.9664 | Pass |
| ibex_prefetch_buffer with Chisel FIFO | prefetch2/emit/prefetch_buffer/{ibex_prefetch_buffer,ibex_fetch_fifo}.sv | clk_i | prefetch2/timing | 19.029213 | 28361.9840 | Pass |

The full timing self-test passed at `build/t11/timing_sized_qualified`: all
existing controls remain, and a real 0.5 pF overload produces measured
14.941490 ns (within budget) but 16 electrical violations, correctly rejected.
Missing/duplicate electrical-report unit controls also pass. Independent review
reproduced ALU, both counters, RF/decoder/FIFO/prefetch proofs and timing; the
reviewer additionally proved the sized ALU gate netlist equivalent and rejected
a fault. These are mapped pre-layout results, not routed or whole-core signoff.

Preserved failures under the corrected flow: original repair6 minstret
25.727716 ns; counter7 29.046221 ns; counter8 39.769947 ns; counter9 minstret
25.951130 ns and mcycle 43.851215 ns; counter10 minstret 25.091261 ns.
Counter11's explicit prefix stages resolve this carry-depth issue. Faithful
FIFO1 measured 27.237787 ns, and prefetch1 with the converted FIFO measured
25.987406 ns; their approved local address increment repairs preserve all state.
The faithful multiplier/divider in `multdiv2/timing` fails at 52.541870 ns;
parallel MAC trial `multdiv3/timing` also fails at 55.642658 ns. Both have zero
electrical violations. Neither failure is waived; multiplier timing remains open.

## T11 authorized counter repair and ALU screen

Measured at `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus uncommitted
T11 changes. Counter commands use `python tools/env/run.py run -- python3
tools/timing/check.py --top ibex_counter --source
build/t11/repair6/emit/<configuration>/ibex_counter.sv --clock clk_i --output
build/t11/repair6/timing_<configuration>`, for `mcycle` and `minstret` (exit 0).
The ALU command is `python tools/env/run.py run -- python3 tools/timing/check.py
--top ibex_alu --source build/t11/alu1/emit/alu/ibex_alu.sv --combinational
--output build/t11/alu1/timing` (exit 1).

| Block/configuration | Worst delay | Start | End | Combinational depth | Cell area (um2) | Budget result |
| --- | ---: | --- | --- | ---: | ---: | --- |
| Repaired mcycle, width 64, update output disabled | 17.448200 ns | _758_/Q | _733_/D | 7 | 10684.0384 | Pass |
| Repaired minstret, width 64, update output enabled | 21.172373 ns | _672_/Q | _724_/D | 7 | 12664.1088 | Pass |
| Faithful RV32BNone ALU | 62.401089 ns | operator_i[1] | result_o[0] | 34 | 16914.0160 | Fail |

All figures are measured, mapped, pre-layout, no wire delay; same pinned
library/hash, slow corner, tools and assumed slew/load/period/budget as the
original counter entry below. The budget remains 24.96 ns. Each result
records its exact source and flow hashes. The counter repair is authorized
same-state combinational restructuring, not a timing waiver. It passed
unbounded equivalence and independent review. Failed intermediate mappings
remain in `build/t11/repair1` through `repair5`; none is relabeled as passing.

The ALU is stateless. Its additional timing route uses a virtual clock and
the existing IO constraints, covers all input-to-output paths, and rejects
sequential cells in both Python and STA. Existing sequential controls and the
new positive XOR/negative wrong-mode controls passed via
`python tools/env/run.py run -- python3 tools/timing/check.py --self-test
--output build/t11/timing_mode_validation_final`. The ALU path includes decode,
operand selection, adder carry, comparison and result selection. It remains
failed in this historical checkpoint. Subsequent user approval and qualified
repairs are recorded above; the original measurement is not relabeled.

Independent reviewer `t11_readiness_review` reproduced both repaired counter
passes under `build/t11/review/repair6_final/` and the ALU failure under
`build/t11/review/alu1/`, with matching emitted bytes and constraints.
No complete-core physical result exists. See [T11's report](../plan/tasks/reports/T11.md).

## T11 initial counter: historical failure, repaired above

Measured at `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus uncommitted
T11 leaf translations, using
`python tools/env/run.py run -- python3 tools/timing/check.py --top ibex_counter
--source build/emit/perf_core_leaves/mcycle/ibex_counter.sv --clock clk_i
--output build/t11/timing/mcycle` (exit 1).

| Block/configuration | Worst delay | Start | End | Combinational depth | Cell area (um2) | Budget result |
| --- | ---: | --- | --- | ---: | ---: | --- |
| Chisel ibex_counter, width 64, ProvideValUpd false (mcycle) | 41.118233 ns | _788_/Q (bit 2) | _845_/D (bit 61) | 23 | 11015.5136 | Fail; budget 24.960000 ns |

All row values are measured, mapped, pre-layout, no wire delay. This is an
actual instance configuration of the pinned core. The long path passes through
the counter increment and write-selection logic. Tool versions are Yosys
0.71+34 and OpenSTA 3.2.0; library `gf180mcu_fd_sc_mcu7t5v0`, SS/125 C/3.0 V,
SHA-256 `5d2f37ba6f43e33aeba26dc1da55c96394a862eeec4148043f1d48bdf65ccea6`.
Assumed period 41.6 ns and budget fraction 0.60 give the unchanged 24.96 ns
limit. Assumed input slew is 0.5 ns, output load 0.05 pF, ideal clock and
zero IO delay. Exact flow/source hashes and paths are in the result directory.
The emitted source hash is
`99a98772761e41c0b69f53f873420ce30fd764099d7cc3d93fa11f7c135642b2`.
Independent reviewer `t11_readiness_review` reran the same command with output
`build/t11/review/mcycle`, reproducing exit 1 and the same delay, source/flow
hashes and assumptions. T11 stopped on this failure. At that checkpoint no full-core physical result,
repair or waiver was claimed. See the [T11 report](../plan/tasks/reports/T11.md).

## Historical T09 measurements

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


T11 iterative multiplier (measured at base a532304 plus working changes):
unchanged buffered-sized-combinational-v1, GF180 7t5 SS125C/3.0V, 41.6ns
period/24.96ns budget, 0.5ns slew/0.05pF load, ideal clock, no wire delay.
`tools/timing/check.py` at `build/t11/iterative1/timing`: standalone
23.659555ns, zero electrical violations, pass. Integrated multdiv at
`build/t11/iterative2/timing`: 23.376678ns, 55393.6768 square micrometres,
zero electrical violations, pass. Independent reviewer reproduced both under
`build/t11/iterative_review/`. These are not whole-core timing results.


Final alias-load recipe (`buffered-sized-alias-load-v3`, original frontend
preserved): measured with `python3 hw/ip/perf_core/check_timing.py --emitted
build/t11/approved_checkpoint/emit --output build/t11/approved_checkpoint/timing`,
base a532304 plus working changes. Eleven implemented blocks pass; standalone
multiplier 23.659555ns, integrated multdiv 25.093014ns (fail), EX 25.975801ns
(fail), unchanged 24.96 ns budget and zero electrical violations throughout.
Areas respectively 29066.6432, 61603.8976, 132306.8992 square micrometres.
The prior v1 integrated pass is historical; it is not a pass of final flow.

T11 registered whole-domain top, measured 2026-11-15 at base `a532304` plus
the frozen `integrated23` source hashes:

```
python tools/env/run.py run -- python3 hw/ip/perf_core/check_top_timing.py --emitted build/t11/integrated23/emit/asic --output build/t11/integrated23/top_timing
PASS DeadhorsePerfCore: 24.592239 ns, budget 24.960000 ns; electrical violations 0
```

Mapped area **458891.1936 um2**, minimum ICG E/TE setup/hold slack
**0.704980 ns** (all eight checks present and nonnegative). Includes core,
register file and the real GF180 ICG. Same `buffered-sized-alias-load-v3`,
slow corner, period/slew/load and ideal pre-CTS convention; no wire delay,
placement or CTS claim. RG/IG enable paths use the same budget. Explicit
sequential-clock identity check and alien-clock/setup/hold fault controls were
independently verified. Failed intermediate snapshots remain in the T11 report.

Comparison-only locked reference, measured with
`python tools/env/run.py run -- python3 dv/core/reference_timing.py --output
build/t11/reference_timing`: **61.667374 ns**, **399653.7216 um2**, zero electrical
violations, strict **FAIL** against 24.96 ns. Both physical profiles omit RVFI
and use the same ASIC gate binding. Independent review confirmed identical
constraints, tools, mapping recipes, loads and interface widths. Benchmark
receipts are explicitly reference-only and do not count as production acceptance.

## T12 standalone FPU

Measured 2026-11-15 with `python tools/env/run.py run -- python3
hw/ip/fpu/check_timing.py`, base `3dfa92ea25cea14f3fde0ee0b3f318c849815285`
plus the T12 working tree. Receipt: `build/t12/timing/result.json`; exact
emitted-source, flow and library hashes are retained there. Fresh emission
after canonical upstream-byte restoration is byte-identical, qualified in
`build/t12/provenance/result.json`.

| Block | Worst path | Start | End | Cell / logic depth | Mapped area (um2) | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Fpu, standalone | 24.402643 ns (RR) | _16400_/Q | _16585_/D | 30 / 28 | 217553.1008 | Pass; zero electrical violations |

Same `buffered-sized-alias-load-v3` flow and unchanged 24.96 ns allowance
(assumed 41.6 ns period times 0.60), GF180 7t5v0 SS/125C/3.0V, assumed
0.5 ns input slew and 0.05 pF output load, zero IO delay and ideal clock.
No multicycle exception, retiming or wire-delay assumption is used to repair
timing. This is mapped pre-layout screening, not routed signoff or chip fit.
Named emission must preserve the prefix-adder keep attributes. See the
[T12 report](../plan/tasks/reports/T12.md) for arithmetic/protocol qualification
and remaining T13/S1 integration work.


## T13 approved exponent timing repair (2026-11-15)

Measured on base `11c72b3` plus the T13 working tree, pinned GF180 7t5v0
SS/125C/3.0V using the unchanged flow and 24.96 ns budget. Commands (after
`python tools/env/run.py run --`):
`python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/exponent/emit/asic --output build/t13/timing-exponent`
and `python3 hw/ip/fpu/check_timing.py` (through the complete T12 regression).

| Block | Worst path | Mapped area (um2) | Result |
| --- | --- | --- | --- |
| Integrated DeadhorsePerfCore, RV32IMFC | 24.698816 ns | 875676.2560 | Pass; zero electrical violations |
| Standalone Fpu after exponent repair | 24.421045 ns | 218211.6608 | Pass; zero electrical violations |

Same registers and latency: exact whole-top revision equivalence passes with
all four fault controls; signed-subtraction and prefix-adder proofs pass. No
upstream source edits or budget change. Pre-layout only, no SRAM/peripherals or
chip-fit claim. T13 ISA/refinement acceptance remains incomplete.


## T13 user-authorized 12 MHz trial (2026-11-16)

Measured on `9d7520d` plus the recorded timing-tool working tree, pinned Yosys
0.71+34 / OpenSTA 3.2.0, GF180 7t5v0 SS/125C/3.0V. The named
`main-12mhz` trial changes only the operating period (1000/12 ns), preserving
the 60 percent fraction (50 ns), IO/slew/load, electrical and clock-gate checks.
Default production/CI remains 41.6 ns / 24.96 ns; no RTL was changed.
Commands, hashes and independent review: [T13 12 MHz report](../plan/tasks/reports/T13-12mhz.md).

| Core profile | Worst path (measured) | Mapped area (measured, um2) | Trial result |
| --- | ---: | ---: | --- |
| Registered no-F | 27.500998 ns | 453539.296 | Pass; electrical violations 0 |
| F-integrated | 30.671665 ns | 872504.192 | Pass; electrical violations 0 |

Each has all eight ICG setup/hold checks, minimum slack 0.704980 ns. Both
fresh emitted designs are byte-identical to their earlier timing inputs; cell
mapping was redone at the slower target. Negative ClockedElapsedTicks still
fails at 71.002609 ns with CLI exit 1. Default-flow self-tests pass unchanged.
Pre-layout only, no wire/SRAM/CTS signoff. Derived hard-float loop worst case
at 12 MHz is 1959.083 us, so this does not establish the 1 kHz system target.

The trial continuation fast tier passes all 21 commands in measured 460.822 s:
`python tools/env/run.py run -- python3 tools/ci.py --tier fast --output build/t13/clock12/ci-fast`.
Its default F-integrated timing remains 24.698816 ns / 24.96 ns. Full tier was
not rerun; previous default-clock failure and outstanding checks remain open.

## T13 faithful Chisel 9.6 MHz trial (2026-11-16)

Measured on `ec736f2` plus the approved trial changes, with exact source/flow
hashes under `build/t13/faithful9p6/timing/result.json`. Pinned Yosys 0.71+34,
OpenSTA 3.2.0, GF180 7t5v0 SS/125C/3.0V; mapped pre-layout, ideal clocks,
no wire/SRAM timing. [Report](../plan/tasks/reports/T13-faithful-9p6mhz.md).

Command (after `python tools/env/run.py run --`):
`python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/faithful9p6/emit/asic --operating-point main-9p6mhz --output build/t13/faithful9p6/timing`.

| Profile | Worst path | Allowance | Mapped area | Result |
| --- | ---: | ---: | ---: | --- |
| Faithful Chisel RV32IMC | 65.305771 ns | 62.5 ns | 439002.6816 um2 | FAIL, CLI exit 1 |

Worst path: instruction/rs1-address flop `_33260_/Q` to register-file x30[31]
`_32120_/D`, 58 logic stages. Over budget by derived 2.805771 ns (4.489234%).
Zero electrical violations; all eight ICG checks pass, minimum slack 0.704980 ns.
The negative fixture rejects 71.002609 ns at the same 62.5 ns allowance.
Default 41.6 ns / 24.96 ns and all checks remain unchanged; 9.6 MHz is not adopted.
Estimated frequency ceiling for this mapped path is 600/65.305771 = 9.187549 MHz;
a fresh 9 MHz trial is recommended but not run. No F integration or routed
signoff is claimed. Fast tier passes 21 commands in measured 475.169 s; full
not rerun. Independent review accepts the failed measurement and provenance.

## T13 faithful Chisel 9 MHz trial (2026-11-16)

Measured on `78be66b` plus trial changes, pinned Yosys 0.71+34 / OpenSTA 3.2.0,
GF180 7t5v0 SS/125C/3.0V. Mapped pre-layout, ideal clocks, no wire/SRAM signoff.
[Report](../plan/tasks/reports/T13-faithful-9mhz.md); receipts under
`build/t13/faithful9/`. All acceptance checks retain their original semantics.

| Experiment | ABC optimization target | STA allowance | Worst delay | Cell area (um2) | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Initial fresh mapping | 66666.667 ps | 66.666667 ns | 69.336807 ns | 429822.3552 | FAIL |
| Final fresh mapping | 62500 ps | 66.666667 ns | 65.305771 ns | 439002.6816 | PASS |

Final command after `python tools/env/run.py run --`:
`python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/faithful9/emit/asic --operating-point main-9mhz --output build/t13/faithful9/tight-mapping`.
The named 9 MHz trial keeps the measured tighter mapping target; its freshly
produced netlist is byte-identical to the previous 9.6 MHz mapping. No RTL,
default clock, other trial target or acceptance limit changed. Derived margin:
1.360896 ns / 2.041344% of allowance. Worst path remains instruction/rs1 address
to x30[31], 58 logic stages; zero electrical violations, eight passing ICG
checks, minimum slack 0.704980 ns. Negative fixture rejects 71.002609 ns.

A retained-netlist STA diagnostic also passes; the blocked mapped-Verilog
re-import and initial fresh-mapping failure are preserved in the report.
Independent review accepts the reproducible fresh 9 MHz experiment. Final
fast tier passes 21 commands in measured 474.641 s; full not rerun. This is
RV32IMC pre-layout evidence, not faithful-F integration or production adoption.
