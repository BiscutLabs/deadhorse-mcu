# Per-block GF180 timing ledger

## T13 shared integer and floating-point multiplier, 2026-11-18

Measured on `f4155b0` plus the shared MAC and FPU addend reuse. The standard
faithful-F `main-9mhz` fast-tier timing command at 62,500 ps gave 814,627.7440 µm²
and 64.831543 ns, compared with 829,781.2096 µm² and 64.258347 ns on the baseline.
Across five matched targets, the unchanged core varied by 4,897.4912 µm² and
3.240048 ns. The selected run measured 814,597.0112 µm² and 64.751656 ns.
These are pre-layout standard-cell measurements at GF180 SS/125 °C/3.0 V.
[Targets, endpoints, throughput and checks](../plan/tasks/reports/T13-round2.md)

## T13 faithful-F register-file area study, 2026-11-18

Measured on `73c178e` plus eight-bank FP register reads with
`python3 hw/ip/perf_core/check_top_timing.py --emitted build/area-study/fp-read-eight-banks/emit/asic --operating-point main-9mhz --output build/area-study/fp-read-eight-banks/timing`.
The GF180MCU 7t5v0 slow corner at 125 °C and 3.0 V gave 829781.2096 µm² and
64.258347 ns for the complete faithful RV32IMFC core. The same flow measured
841971.1552 µm² and 64.389893 ns on the baseline. Derived reductions were
12189.9456 µm² (1.448%) and 0.131546 ns. Both runs were mapped pre-layout
with ideal clocks and no wire delay. The fast tier reproduced the selected
values. [All five hypotheses and four refinements](../plan/tasks/reports/T13-area-study.md)

## T13 faithful-F pipeline timing study, 2026-11-17

Measured on `d75ce89` plus the parallel operand select, using
`python3 hw/ip/perf_core/check_top_timing.py --emitted build/pipeline-study/h2/emit/asic --operating-point main-9mhz --output build/pipeline-study/h2/timing`.
GF180 7t5v0 SS/125 C/3.0 V, mapped pre-layout with ideal clocks. Baseline
65.726219 ns and 839962.5472 um2; selected 64.389893 ns and 841971.1552 um2.
Worst register path `_64088_/Q` to `_61821_/D`, 80 logic levels, zero
electrical violations. Derived delay improvement 2.033%, mapped area growth
0.239%. Fast CI reproduced both numbers. All five hypotheses and the
higher-frequency trial are in the [study](../plan/tasks/reports/T13-pipeline-timing.md).

## T18 lite I2C recovery loader, 2026-11-17

Measured on base `35738fe` plus T18 changes with the pinned T09 flow,
GF180MCU 7t 5 V SS, 125 C, 3.0 V, ideal clock and no wire delay. Command:
`python3 tools/timing/check.py --top RecoveryLoader --clock clk`, supplying
every SystemVerilog source from the corresponding fresh production emission.
The default assumed allowance is 60% of 41.6 ns, or 24.96 ns.

| Output under build/t18 | Measured delay ns | Mapped cell area (um2) | Electrical violations |
| --- | ---: | ---: | ---: |
| timing-initial | 36.429199 | 96959.7888 | 198 |
| timing-domain-reset | 25.190571 | 98513.9904 | 0 |
| timing-range | 24.589447 | 96577.8240 | 0 |

The initial input path ran from por_n through a redundant local whole-domain
reset net with excessive load. The qualified whole-domain reset supplied by
the reset controller already includes POR. Using that input directly removed
the overload. The remaining BEGIN path included a 32-bit variable comparison.
Rejecting upper bits and comparing aligned word indices over the actual
capacity retained full-width input validation and met the budget. The worst
path in timing-range runs from frame opcode storage to the received-byte
counter. The measurement includes the target, shared input synchronizers,
serializer, read snapshot, CRC, metadata, programming lock and memory-port
logic. Program SRAM, CPU, reset distribution, wake controller and pads are
external.

The standalone acceptance and fast CI replay each reproduced the final delay,
area and electrical count using fresh emissions. Source lists, commands and
library hashes are in the timing receipts under `build/t18/check/timing/`
and `build/t18/ci-fast/fast/i2c-recovery-loader/timing/`.

## T17 I2C controller, 2026-11-17

Measured at base `6764ef8` plus T17 sources, pinned GF180 7t5v0 SS/125C/3.0V,
Yosys `0.71+34 e419c4eef`, OpenSTA `3.2.0`. Command after pinned wrapper:
`python3 tools/timing/check.py --top I2cHost --clock clk`, all emitted sources
from `build/t17/emit-watch-bytes`, output `build/t17/timing-watch-bytes`.
The exact full command is in the [report](../plan/tasks/reports/T17.md).

Measured **47223.1424 um2**, **23.978615 ns**, path `_2705_/Q` to `_2653_/D`,
16 logic stages; zero electrical violations, unchanged 24.96 ns assumed budget.
Mapped pre-layout, ideal clock, no wire delay; excludes pads and reset/clock tree.
Initial **28.143589 ns** failure (`build/t17/timing-initial`) is preserved.
An independently reviewed split-byte watchdog keeps exact timeout arithmetic
and progress-over-expiry priority while shortening the mux/decrement path.

After the independently reviewed repeated-START SDA guard repair, fresh
`EmitI2cHost` output `build/t17/emit-restart-guard` and the same timing command
at output `build/t17/timing-restart-guard` measure **46557.9968 um2** and
**22.349216 ns**, path `_2609_/Q` to `_2557_/D`, 16 logic stages, zero
electrical violations. The exact guard regression passes. Mapping changes
prevent attributing the full area/delay delta to a single gate.

The standalone aggregate `python tools/env/run.py run -- python3
hw/ip/i2c_host/check.py --output build/t17/check` and the final-source aggregate
invoked by fast CI at output `build/t17/ci-fast/fast/i2c-host` reproduce
**46557.9968 um2 / 22.349216 ns**, zero electrical violations. The latter
receipt binds fresh emitted sources, timing-flow/library hashes and the
independently checked worst path at `i2c_host/result.json` beneath that output.

## T16 SPI host, 2026-11-17

Measured at base `ea9f238` plus T16 sources, pinned GF180 7t5v0 SS/125C/3.0V,
Yosys `0.71+34 e419c4eef`, OpenSTA `3.2.0`. Preliminary receipt:
`build/t16/timing-count-fix/result.json`, command `python tools/env/run.py run --
python3 tools/timing/check.py --top SpiHost --clock clk`, every source from
`build/t16/emit-count-fix`, output `build/t16/timing-count-fix`.

SpiHost FIFO 16 measures **63564.2112 um2** and **24.328402 ns**, worst path
`_3260_/Q` to `_3297_/D`, 20 logic stages, zero electrical violations. Passes
the unchanged assumed 24.96 ns budget. Pre-layout mapped cells, ideal clock,
no wire delay; qualified reset input, excluding reset/clock tree and pads.
Initial **26.434401 ns** failure is retained at `build/t16/timing-initial`.
An independently checked Boolean simplification of FIFO count conditions
removed redundant admission logic without changing behavior or the budget.
Aggregate `python tools/env/run.py run -- python3 hw/ip/spi_host/check.py
--output build/t16/check-final` reproduces these exact measurements with fresh
emission; receipt `build/t16/check-final/spi_host/result.json`.
[Report](../plan/tasks/reports/T16.md).

## T15 UART, 2026-11-17

Measured at base `172d4f1d2279bb5cc5c621685ad94923bfd15282` plus T15
source hashes, using `python tools/env/run.py run -- python3 hw/ip/uart/check.py
--output build/t15/check`. Its recorded `tools/timing/check.py` commands consume
all freshly emitted sources for each top, clock `clk`, default operating point.
Receipts: `build/t15/check/{uart,wake,bank}/result.json`.

| Top | Measured area, um2 | Worst delay, ns | Worst path | Logic depth |
| --- | ---: | ---: | --- | ---: |
| Uart, FIFO 8 | 50673.9968 | 20.436308 | `_2653_/Q` to `_2493_/D` | 12 |
| UartWake | 465.3824 | 6.950206 | `_15_/Q` to `_15_/D` | 3 |
| UartBank, three FIFO-8 endpoints | 151679.5392 | 21.398275 | `_8416_/Q` to `_8428_/D` | 14 |

All pass the unchanged assumed 24.96 ns limit with zero capacitance/slew
violations. GF180 `gf180mcu_fd_sc_mcu7t5v0`, SS/125C/3.0V; Yosys
`0.71+34 e419c4eef`, OpenSTA `3.2.0`. Mapped, pre-layout, ideal clock,
no wire delay. HF reset is already domain-qualified; reset-tree buffering and
recovery/removal are physical integration obligations. Bank area excludes AON
monitors; estimated bank plus three monitors is
`151679.5392 + 3 * 465.3824 = 153075.6864 um2`, excluding integration glue/pads.
Historical failed timing receipts remain preserved; no timing limit changed.
[Report](../plan/tasks/reports/T15.md).

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

## T13 faithful F continuation (2026-11-16)

Measured base `d8683936` plus frozen sources, pinned Yosys 0.71+34/OpenSTA 3.2.0,
GF180 7t5v0 SS/125C/3.0V, mapped pre-layout with ideal clocks.
Command: `python tools/env/run.py run -- python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/faithful-f/qualified/emit/asic --operating-point main-9mhz --output build/t13/faithful-f/qualified/timing`.
**FAIL 67.791702 ns / 66.666667 ns**, area **838720.064 um2**, electrical
violations zero. Instruction bit 4 to integer RF bit 350; 80 logic stages.
Derived excess 1.125035 ns. Mapping target remains 62500 ps; no default clock
or allowance changed. Earlier 64.900009 ns emission omitted preservation of
unused interface ports and is not substituted for this final measurement.
Independent review authenticated final source hashes. [Report](../plan/tasks/reports/T13-faithful-f.md).

Fast tier **failed (partial tier run)**, measured 426.823 s to stop; 15 commands passed, failed at integrated-timing. Full tier **not run this continuation**.

The retained registered F profile also fails in this fast run: 25.225288 ns / 24.960000 ns, zero electrical violations (build/t13/faithful-f/ci-fast/fast/timing/result.json). This occurs before the added faithful CI jobs; they were not run by the tier. No default-clock failure was bypassed.

## T13 bus-response ownership repair (2026-11-16)

Measured base91dd5c88 plus frozen working-tree sources, pinned GF1807t5v0
SS/125C/3.0V, Yosys0.71+34/OpenSTA3.2.0, mapped pre-layout/ideal clocks.
`python tools/env/run.py run -- python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/bus-error/emit/asic --operating-point main-9mhz --output build/t13/bus-error/timing`
passes **65.726219 / 66.666667 ns**, cell area **839962.5472 um2**, zero
electrical violations. Fresh fast-tier emission reproduces this passing result.
Retained registered F default check passes **24.947506 / 24.960000 ns**.
Derived margins0.940448ns and0.012494ns respectively; neither is routed signoff.
No timing limit or mapping target changed. Source repair adds two ownership
bits and response qualification; mapping changes prevent attributing the entire
area/delay delta to those bits. Earlier failed receipts remain historical.
Fast tier **PASS**, all 26 commands, measured 824.220 s (13m 44s), including 14 RTL tests. **Full tier not run.**
[Repair report](../plan/tasks/reports/T13-bus-error.md).

## T19 USB selective conversion (2026-11-18)

**Measured**, baseline `a280df4fa17516a2ac8507628a6f12e3c4128895` plus
receipt-bound uncommitted T19 sources. Pinned Yosys 0.71+34/OpenSTA 3.2.0,
GF180 7t5v0 SS/125 C/3.0 V, mapped pre-layout with ideal clocks. These are
component measurements, not integrated wrapper or physical USB signoff.

| Component | Delay ns | Budget ns | Cell area um2 | Result | Receipt under `build/t19/` |
| --- | ---: | ---: | ---: | --- | --- |
| EP0 control | 13.042828 | 12.5 | 42297.1136 | FAIL | `timing-13/control/result.json` |
| IN packet buffer | 11.140153 | 12.5 | 105051.2960 | PASS | `timing-08/in/result.json` |
| OUT packet buffer | 11.820112 | 12.5 | 102331.4432 | PASS | `timing-10/out/result.json` |
| Host resume | 9.333540 | 12.5 | 4361.8624 | PASS | `timing-10/resume/result.json` |
| Combined USB engine | 20.556009 | 12.5 | 283246.6560 | FAIL | `timing-13/engine/result.json` |
| Application registers | 11.202718 | 24.96 | 8365.9072 | PASS | `check-01/timing/registers/result.json` |

Every listed measurement reports zero maximum-slew/capacitance violations.
All passing component emissions were compared by SHA-256 with `emit-13` and
are identical. Engine area includes endpoint buffers/control; do not add those
rows to the engine area. No whole-chip fit is claimed.

Latest control/engine command after `python tools/env/run.py run --`:

```sh
python3 hw/ip/usb/timing.py --emitted build/t19/emit-13 --output build/t19/timing-13 --block control --block engine
```

Earlier passing rows were measured by `scratch/t19_timing08.py`,
`hw/ip/usb/timing.py --emitted build/t19/emit-10 --output build/t19/timing-10
--block control --block out --block resume --block engine`, and
`hw/ip/usb/check.py --output build/t19/check-01`, respectively. Their receipts
record every numerical tool invocation and input hash. The aggregate itself
failed and is not an acceptance pass.

The USB budget is **estimated** as 0.60 × (1000/48 ns) = 12.5 ns, retaining
plan 14's **assumed** margin. USB-only fanout insertion adds actual GF180
buffers, verifies unchanged original pin connectivity and clock nets, and
includes inserted-cell area/delay/electrical loading in STA. No path is waived.
A separate tighter mapper-target diagnostic (`scratch/t19_tighter_map.py`)
also failed: control 12.740618 ns and engine 20.556009 ns. Its 9375 ps ABC
optimization target did not change the 12.5 ns acceptance budget; production
mapping remains unchanged. Prior failed measurements remain preserved.

The [SIE timing proposal](../spec/usb-timing-decision.md) was subsequently
approved as D45 for eligible SIE and EP0 pairs. Later diagnostic runs below
apply draft 4/3 constraints, without accepted qualification. EP0 full-rate closure, packet
sampling-equivalence proof, full wrapper-domain timing and complete T19
acceptance remain open. [Task report](../plan/tasks/reports/T19.md).

### D45 eligibility stop (2026-11-18)

Fresh **measured** EP0 result at `38e0bddb691288eeba92cb257d30935a40c15fb6`
plus documentation/unrelated working changes, using the same pinned tools,
library and corner: **13.042828 ns**, **42297.1136 um2**, zero reported
slew/capacitance violations. Command (after `python tools/env/run.py run --`):
`python3 hw/ip/usb/timing.py --emitted build/t19/d45-emit-01 --output build/t19/d45-timing-01 --block control`.
Fresh emission command is in the T19 report. Full-rate budget remains
**estimated** 0.60 × 1000/48 = **12.5 ns**. Start `_1925_/Q` = `header_6[5]`;
end `_2046_/D` = `decodedValid` captured unconditionally by `decodeValidQ`.
The header writes on delayed `headerWrite`, not the common protocol-enable
phase. This path is not eligible for D45. Independent review confirmed the
classification and the user's explicit stop condition. No exception, pipeline
removal or further restructuring was applied. All additional qualification
remains open; receipt `build/t19/d45-timing-01/control/result.json`.

### Approved EP0 header/decode restructuring (2026-11-18)

**Measured** after direct enable-qualified header writes and enable-qualified
descriptor/decode registers, at `38e0bddb691288eeba92cb257d30935a40c15fb6`
plus working changes. Same pinned tools, GF180 SS/125 C/3.0 V library, ideal
clocks and pre-layout scope. Command (after `python tools/env/run.py run --`):
`python3 tools/timing/check.py --top UsbControl --source build/t19/d45-emit-02/control/UsbControl.sv --clock clk --operating-point usb-48mhz --usb-cadence build/t19/d45-cadence-05/result.json --output build/t19/d45-class-control-05`.
Cell area **measured** 42161.0112 um2 for the whole EP0 block, not per path.

| Class | Measured worst ns | Estimated budget ns | Start / end | Numerical result |
| --- | ---: | ---: | --- | --- |
| Certified → certified | 12.774849 | 50 | `_1939_/Q` header_1[6] → `_1993_/D` decodeValueQ[7] | Within budget |
| Certified → full-rate | 9.604959 | 12.5 | `_1902_/Q` header_6[6] → `_1777_/D` state[3] | Within budget |
| Full-rate → certified | 12.649599 | 12.5 | `_1793_/Q` address[4] → `_1797_/D` decodeValidQ | FAIL |
| Full-rate → full-rate | 12.244377 | 12.5 | `_1776_/Q` state[4] → `_1751_/D` writeCount[3] | Within budget |
| Input → register | 10.738379 | 12.5 | outReady → `_1971_/D` committed[6] | Within budget |
| Register → output | 4.053404 | 12.5 | `_1964_/Q` configured → configured | Within budget |
| Input → output / clock gates | none | Existing limits | No such paths/cells in this EP0 top | Not applicable |

Budgets are **estimated** 0.60 × 1000/48 = 12.5 ns and 4 × 12.5 = 50 ns.
Source/mapped enable proofs and reset-spanning cadence pass, with their fault
controls. Zero measured maximum-slew/capacitance violations; hold and reset
recovery/removal report has no negative slack. Independent review reran STA
on the identical `class-control-03` netlist and **measured** a representative
certified pair's setup capture edge at 83.333336 ns and hold edge at 0 ns.
This validates the repaired selectors for that pair, not exhaustive coverage.

Earlier `class-control-02` used rejected Q-pin multicycle starts; it is an
invalid-constraint diagnostic, not accepted timing. Current commands use
certificate-generated CLK pins and reject invalid-start/end warnings.
The current runner keeps D45 numerical passes blocked pending sampling,
measured-cadence binding, exception coverage and per-class negative controls.
Address/reset behavior remains unchanged; the failing full-rate path triggers
the user's stop rule. No SIE/combined-engine/wrapper measurement is claimed
for the changed EP0. All additional qualification remains open.

### D46 address predecode and integrated measurements (2026-11-18)

All delays, areas and path identities below are **measured** at base
`38e0bddb691288eeba92cb257d30935a40c15fb6` plus source hashes in each receipt.
Same pinned GF180 SS/125 C/3.0 V corner, ideal clocks and pre-layout scope.
For each directory below, the measurement commands are
`python tools/env/run.py run -- yosys -Q -T -s build/t19/<directory>/buffer.ys`
(mapped area) and
`python tools/env/run.py run -- sta -no_init -exit build/t19/<directory>/timing.tcl`
(paths). The complete preceding synthesis commands and tool versions are in
that directory's `commands.jsonl` and `result.json`.

Budgets are **estimated**: USB full rate = 0.60 × 1000/48 = 12.5 ns;
certified pairs = 4 × 12.5 = 50 ns; application/AON screening =
0.60 × 41.6 = 24.96 ns. Wrapper application/AON clocks use the conservative
41.6 ns screening assumption. Domain crossings are asynchronous clock groups;
physical crossing skew/MTBF is not qualified. Every non-clock input/output
has zero delay against every clock, a conservative boundary screen rather
than a domain-specific external timing contract.

| Block / receipt directory | Measured area um2 | Numerical result |
| --- | ---: | --- |
| EP0, `d46-control-01` | 42865.6704 | pass |
| IN buffer, `d46-components-01/in` | 105051.2960 | pass |
| OUT buffer, `d46-components-01/out` | 102331.4432 | pass |
| Resume, `d46-components-01/resume` | 4361.8624 | pass |
| Registers, `d46-components-01/registers` | 8365.9072 | pass |
| Combined engine, `d46-engine-05` | 281646.3552 | fail |
| Complete wrapper, `d46-wrapper-03` | 319452.0896 | fail |

Area is the whole named block, not an additive per-path attribution. The
wrapper includes CDC, events and clock-request glue. Standalone SIE results
follow below. See [SRAM estimates](usb-area.md).

| Block | Path class | Measured worst ns | Estimated budget ns | Mapped start → end |
| --- | --- | ---: | ---: | --- |
| EP0 | CC | 12.202253 | 50 | `_1810_/Q` → `_1894_/D` |
| EP0 | CF | 10.110165 | 12.5 | `_1978_/Q` → `_1859_/D` |
| EP0 | FC | 11.774527 | 12.5 | `_2031_/Q` → `_2063_/D` |
| EP0 | FF | 11.947232 | 12.5 | `_1859_/Q` → `_1811_/D` |
| EP0 | IR | 11.765710 | 12.5 | `inRequest` → `_1811_/D` |
| EP0 | RO | 4.126209 | 12.5 | `_2039_/Q` → `configured` |
| IN buffer | RR | 11.140153 | 12.5 | `_3172_/Q` → `_3128_/D` |
| IN buffer | IR | 9.972349 | 12.5 | `reset_n` → `_3299_/D` |
| IN buffer | RO | 3.984604 | 12.5 | `_3098_/Q` → `appReady` |
| OUT buffer | RR | 11.820112 | 12.5 | `_3072_/Q` → `_3039_/D` |
| OUT buffer | IR | 9.609552 | 12.5 | `reset_n` → `_3679_/D` |
| OUT buffer | RO | 4.164564 | 12.5 | `_3716_/Q` → `nak` |
| Resume | RR | 9.333540 | 12.5 | `_202_/Q` → `_201_/D` |
| Resume | IR | 8.076866 | 12.5 | `attached` → `_201_/D` |
| Resume | RO | 4.093227 | 12.5 | `_195_/Q` → `suspended` |
| Registers | RR | 11.202718 | 24.96 | `_453_/Q` → `_454_/D` |
| Registers | IR | 9.328797 | 24.96 | `bus_bits_addr[9]` → `_454_/D` |
| Registers | RO | 4.043431 | 24.96 | `_453_/Q` → `bus_gnt` |
| Combined engine | CC | 21.709534 | 50 | `_9906_/Q` → `_10181_/D` |
| Combined engine | CF | 15.341034 | 12.5 | `_9878_/Q` → `_10183_/D` |
| Combined engine | FC | 20.658268 | 12.5 | `_9208_/Q` → `_10175_/D` |
| Combined engine | FF | 14.978270 | 12.5 | `_9221_/Q` → `_10139_/D` |
| Combined engine | IR | 6.502565 | 12.5 | `rxReady` → `_8955_/D` |
| Combined engine | RO | 9.062789 | 12.5 | `_10121_/Q` → `txEnable` |
| Combined engine | IO | 3.674172 | 12.5 | `reset_n` → `pullup_0` |
| Complete wrapper | appClock.FF | 12.017683 | 24.96 | `_11086_/Q` → `_10558_/D` |
| Complete wrapper | appClock.IR | 9.074254 | 24.96 | `bus_bits_origin[1]` → `_10533_/D` |
| Complete wrapper | appClock.RO | 3.929136 | 24.96 | `_11413_/Q` → `bus_gnt` |
| Complete wrapper | appClock.IO | 6.090249 | 24.96 | `appReset_n` → `pullupEnable` |
| Complete wrapper | usbClock.CC | 20.763855 | 50 | `_10645_/Q` → `_9876_/D` |
| Complete wrapper | usbClock.CF | 16.435688 | 12.5 | `_10663_/Q` → `_10971_/D` |
| Complete wrapper | usbClock.FC | 18.105883 | 12.5 | `_10981_/Q` → `_10673_/D` |
| Complete wrapper | usbClock.FF | 16.435089 | 12.5 | `_10981_/Q` → `_10289_/D` |
| Complete wrapper | usbClock.IR | 13.414976 | 12.5 | `usbReset_n` → `_10289_/D` |
| Complete wrapper | usbClock.RO | 8.632684 | 12.5 | `_10981_/Q` → `txEnable` |
| Complete wrapper | usbClock.IO | 6.090249 | 12.5 | `appReset_n` → `pullupEnable` |
| Complete wrapper | aonClock.FF | 2.488224 | 24.96 | `_10948_/Q` → `_10951_/D` |
| Complete wrapper | aonClock.RO | 3.750224 | 24.96 | `_10951_/Q` → `usbClockRequest` |
| Complete wrapper | aonClock.IO | 6.090249 | 24.96 | `appReset_n` → `pullupEnable` |

CC/CF/FC/FF mean certified/full-rate launch and capture. IR/RO/IO are input,
output and combinational boundary paths. No clock-gate cells/paths exist in
these USB tops; gate checks remain implemented in the shared runner.
EP0 has no negative hold/reset slack and zero reported electrical violations.
All measured blocks have zero maximum-slew/capacitance violations.

The engine's worst CC path is `sie.data_q[1]` → `sie.out_toggle_q[0]`, within
50 ns. Its failing CF path ends in PHY TX `nrzi_q`; FC runs from `configured`
to `frame[10]`; FF runs from cadence enable to PHY RX `rx_eop_qq`.
Those paths retain 12.5 ns. The complete wrapper's FC path is PHY TX state
to SIE PHY state. D46's small EP0 allowance does not waive these failures.

Engine raw `dpRx`/`dnRx` hold slack is **measured** −0.102503 ns with zero
input delay. The wrapper has six reported negative hold rows. These remain
failures; no PHY input false path or external timing assumption was added.
Wrapper receipt `d46-wrapper-03` contains a stale single-clock boundary label
although its clock constraints and domain table use all three clocks; the
runner metadata has since been corrected. The receipt is retained as issued.

Source/mapped enable, cadence-step and reset-cone checks now pass, including
targeted reset/cadence/bus-reset faults (`d46-reset-cert-03`). This later
certificate reuses the exact engine05 mapped identities. Exhaustive applied
exception coverage, per-class over-budget faults and protocol sampling
equivalence remain unresolved; numerical EP0 success is not qualification.

### Standalone retained SIE with production cadence

**Measured** at the same base commit and pinned corner, from the exact
production `UsbSie` BlackBox parameters plus `UsbBitEnable`. The fixture
exposes other vendor inputs at full rate; integrated constant endpoint masks
are not imposed. Unused cloned clock/reset/enable interface fields have no
connection to sequential cells. Actual sequential clocks use `clk` and the
certificate binds the internal cadence/reset. Commands:

```sh
python tools/env/run.py run -- python3 tools/sbt.py "runMain deadhorse.usb.EmitUsbSieTiming build/t19/d46-sie-emit-01"
python tools/env/run.py run -- python3 tools/timing/check.py --top UsbSieTiming --source build/t19/d46-sie-emit-01/UsbSieTiming.sv --source build/t19/d46-sie-emit-01/UsbBitEnable.sv --source build/vendor/usb/rtl/sie.v --source build/vendor/usb/rtl/phy_rx.v --source build/vendor/usb/rtl/phy_tx.v --clock clk --operating-point usb-48mhz --usb-cadence build/t19/d46-cadence-final-01/result.json --output build/t19/d46-sie-01
```

Measured mapped area: **54825.1200 um2**, including cadence. Zero electrical
violations. PHY input hold slack is measured −0.102503 ns; reset-removal
slack reaches measured −0.256078 ns under the zero-delay input contract.
Numerical status FAIL. No clock-gate cells/paths occur.

| Class | Measured worst ns | Estimated budget ns | Start → end |
| --- | ---: | ---: | --- |
| CC | 24.721727 | 50 | `_2779_/Q` → `_2916_/D` |
| CF | 24.098761 | 12.5 | `_2779_/Q` → `_2838_/D` |
| FC | 16.159996 | 12.5 | `_2715_/Q` → `_2916_/D` |
| FF | 18.411098 | 12.5 | `_2829_/Q` → `_2714_/D` |
| IR | 18.264446 | 12.5 | `io_in_int_endps_i[14]` → `_2916_/D` |
| RO | 21.622900 | 12.5 | `_2779_/Q` → `io_in_ready_o` |
| IO | 14.955754 | 12.5 | `io_in_int_endps_i[14]` → `io_in_ready_o` |

All source/mapped enable, cadence-step and reset-cone certificates and their
listed faults pass. This does not waive measured full-rate/IO/hold/reset
failures or the remaining global exception/sampling qualification.

## T19 final frozen measurements (2026-11-18)
These final **measured** results supersede the earlier EP0 numerical pass.
Command: `python tools/env/run.py run -- python3 hw/ip/usb/check.py --packet-triage build/t19/d46-sparse-06/result.json --output build/t19/d46-frozen-check-02`.
Baseline `38e0bddb691288eeba92cb257d30935a40c15fb6` plus the frozen source
SHA-256 inventory in that result. Individual timing commands are recorded
in its `commands` array and each timing directory. Yosys 0.71+34 / OpenSTA
3.2.0, pinned GF180 7-track SS/125 C/3.0 V, mapped pre-layout, ideal clocks,
no routed wire delay. All electrical slew/capacitance violation counts are zero.
Budgets are **estimated**: CC = 0.60 × 4 × 1000/48 = 50 ns; other USB
paths = 0.60 × 1000/48 = 12.5 ns; application/AON = 0.60 × 41.6 = 24.96 ns.
Wrapper clocks and conservative IO/CDC screening assumptions remain as above.

| Block | Class | Measured worst ns | Estimated budget ns | Start → end | Measured block area um2 |
| --- | --- | ---: | ---: | --- | ---: |
| control | CC | 13.306602 | 50 | `_1992_/Q` → `_1814_/D` | 42922.7456 |
| control | CF | 12.580610 | 12.5 | `_1985_/Q` → `_1964_/D` | 42922.7456 |
| control | FC | 13.370109 | 12.5 | `_1963_/Q` → `_1990_/D` | 42922.7456 |
| control | FF | 12.721625 | 12.5 | `_1963_/Q` → `_1848_/D` | 42922.7456 |
| control | IR | 11.261580 | 12.5 | `busReset` → `_1846_/D` | 42922.7456 |
| control | RO | 4.142676 | 12.5 | `_2039_/Q` → `configured` | 42922.7456 |
| in | RR | 11.140153 | 12.5 | `_3172_/Q` → `_3128_/D` | 105051.2960 |
| in | IR | 9.972349 | 12.5 | `reset_n` → `_3299_/D` | 105051.2960 |
| in | RO | 3.984604 | 12.5 | `_3098_/Q` → `appReady` | 105051.2960 |
| out | RR | 11.820112 | 12.5 | `_3072_/Q` → `_3039_/D` | 102331.4432 |
| out | IR | 9.609552 | 12.5 | `reset_n` → `_3679_/D` | 102331.4432 |
| out | RO | 4.164564 | 12.5 | `_3716_/Q` → `nak` | 102331.4432 |
| resume | RR | 9.333540 | 12.5 | `_202_/Q` → `_201_/D` | 4361.8624 |
| resume | IR | 8.076866 | 12.5 | `attached` → `_201_/D` | 4361.8624 |
| resume | RO | 4.093227 | 12.5 | `_195_/Q` → `suspended` | 4361.8624 |
| registers | RR | 11.202718 | 24.96 | `_453_/Q` → `_454_/D` | 8365.9072 |
| registers | IR | 9.328797 | 24.96 | `bus_bits_addr[9]` → `_454_/D` | 8365.9072 |
| registers | RO | 4.043431 | 24.96 | `_453_/Q` → `bus_gnt` | 8365.9072 |
| engine | CC | 21.709534 | 50 | `_9906_/Q` → `_10181_/D` | 281646.3552 |
| engine | CF | 15.341034 | 12.5 | `_9878_/Q` → `_10183_/D` | 281646.3552 |
| engine | FC | 20.658268 | 12.5 | `_9208_/Q` → `_10175_/D` | 281646.3552 |
| engine | FF | 14.978270 | 12.5 | `_9221_/Q` → `_10139_/D` | 281646.3552 |
| engine | IR | 6.502565 | 12.5 | `rxReady` → `_8955_/D` | 281646.3552 |
| engine | RO | 9.062789 | 12.5 | `_10121_/Q` → `txEnable` | 281646.3552 |
| engine | IO | 3.674172 | 12.5 | `reset_n` → `pullup_0` | 281646.3552 |
| usb | appClock.FF | 12.017683 | 24.96 | `_11086_/Q` → `_10558_/D` | 319452.0896 |
| usb | appClock.IR | 9.074254 | 24.96 | `bus_bits_origin[1]` → `_10533_/D` | 319452.0896 |
| usb | appClock.RO | 3.929136 | 24.96 | `_11413_/Q` → `bus_gnt` | 319452.0896 |
| usb | appClock.IO | 6.090249 | 24.96 | `appReset_n` → `pullupEnable` | 319452.0896 |
| usb | usbClock.CC | 20.763855 | 50 | `_10645_/Q` → `_9876_/D` | 319452.0896 |
| usb | usbClock.CF | 16.435688 | 12.5 | `_10663_/Q` → `_10971_/D` | 319452.0896 |
| usb | usbClock.FC | 18.105883 | 12.5 | `_10981_/Q` → `_10673_/D` | 319452.0896 |
| usb | usbClock.FF | 16.435089 | 12.5 | `_10981_/Q` → `_10289_/D` | 319452.0896 |
| usb | usbClock.IR | 13.414976 | 12.5 | `usbReset_n` → `_10289_/D` | 319452.0896 |
| usb | usbClock.RO | 8.632684 | 12.5 | `_10981_/Q` → `txEnable` | 319452.0896 |
| usb | usbClock.IO | 6.090249 | 12.5 | `appReset_n` → `pullupEnable` | 319452.0896 |
| usb | aonClock.FF | 2.488224 | 24.96 | `_10948_/Q` → `_10951_/D` | 319452.0896 |
| usb | aonClock.RO | 3.750224 | 24.96 | `_10951_/Q` → `usbClockRequest` | 319452.0896 |
| usb | aonClock.IO | 6.090249 | 24.96 | `appReset_n` → `pullupEnable` | 319452.0896 |
| sie | CC | 24.721727 | 50 | `_2779_/Q` → `_2916_/D` | 54825.1200 |
| sie | CF | 24.098761 | 12.5 | `_2779_/Q` → `_2838_/D` | 54825.1200 |
| sie | FC | 16.159996 | 12.5 | `_2715_/Q` → `_2916_/D` | 54825.1200 |
| sie | FF | 18.411098 | 12.5 | `_2829_/Q` → `_2714_/D` | 54825.1200 |
| sie | IR | 18.264446 | 12.5 | `io_in_int_endps_i[14]` → `_2916_/D` | 54825.1200 |
| sie | RO | 21.622900 | 12.5 | `_2779_/Q` → `io_in_ready_o` | 54825.1200 |
| sie | IO | 14.955754 | 12.5 | `io_in_int_endps_i[14]` → `io_in_ready_o` | 54825.1200 |

A block area is repeated for traceability; rows are not additive. Empty
classes have no paths. No clock-gate paths occur in these tops; RG/IG checks
remain enabled. Hold/reset-removal checks are retained: engine raw-PHY hold
slack is measured −0.102503 ns; wrapper has six negative rows; standalone
SIE reaches measured −0.256078 ns reset-removal slack and −0.102503 ns hold
slack. EP0 has no negative hold/reset slack.

Final EP0 FC path is `_1963_/Q` state[5] → `_1990_/D` header_5[6].
State has a synchronous busReset override outside the protocol enable, so
this is correctly full-rate-to-certified and cannot receive 4/3. Final
EP0 mapping uses `synth -nofsm` to preserve certificate identities; the
earlier `d46-control-01` did not. Independent review verified identical
emitted source SHA-256
`c772e4c749448130391c26e51864269ce2473d29c7255a861b8c039af3fe71ab`
and otherwise matching mapping targets. The earlier 11.947232 ns full-rate
pass and 42865.6704 um2 area are historical, not final qualification.
The explicit user stop applies; no further RTL or mapping restructuring
was performed. D46's prior address-path allowance does not waive this path.

Source/mapped enable and reset/cadence certificates pass their targeted
fault controls on the final snapshot. Exhaustive applied-exception coverage,
actual over-budget faults per class, direct header/decode producer-spacing
and retained-pipeline sampling equivalence remain unresolved. Final USB
aggregate and fast CI fail; full CI was not run.

## D48-D50 post-step-4 stop (2026-11-18)

**Measured** at `15161bf897d1b4b4cba69030154daf89ee19ca12` plus receipt-bound
working sources. Command: `python tools/env/run.py run -- python3 scratch/t19_d48_measure.py`
(engine/wrapper, final `build/t19/d48-timing-05`); EP0 is the first invocation
`build/t19/d48-timing-01/control`. Individual `tools/timing/check.py` commands
are in `commands.json` and the child receipts. Pinned Yosys 0.71+34 / OpenSTA
3.2.0, GF180 7-track SS/125 C/3.0 V; mapped pre-layout, ideal clocks.
No routed wires, physical reset skew or board qualification is claimed.

Budgets are **estimated**: CC = 0.60 × 4 × 1000/48 = 50 ns; other USB
classes = 0.60 × 1000/48 = 12.5 ns; application/AON = 0.60 × 41.6 = 24.96 ns.
Zero-delay IO screening remains; the pad contract was not reached after the
explicit stop condition. No delay, electrical or hold requirement was waived.

| Block | Class | Measured worst ns | Estimated budget ns | Mapped start → end | Measured block area um2 |
| --- | --- | ---: | ---: | --- | ---: |
| EP0 | CC | 4.986572 | 50 | `_2060_/Q` → `_2060_/D` | 42922.7456 |
| EP0 | CF | 13.306602 | 12.5 | `_1992_/Q` → `_1814_/D` | 42922.7456 |
| EP0 | FC | 13.370109 | 12.5 | `_1963_/Q` → `_1990_/D` | 42922.7456 |
| EP0 | FF | 12.721625 | 12.5 | `_1963_/Q` → `_1848_/D` | 42922.7456 |
| EP0 | IR | 11.261580 | 12.5 | `busReset` → `_1846_/D` | 42922.7456 |
| EP0 | RO | 4.142676 | 12.5 | `_2039_/Q` → `configured` | 42922.7456 |
| Engine | CC | 4.346316 | 50 | `_10109_/Q` → `_10109_/D` | 282348.8192 |
| Engine | CF | 12.777115 | 12.5 | `_9811_/Q` → `_10101_/D` | 282348.8192 |
| Engine | FC | 13.556070 | 12.5 | `_9673_/Q` → `_10111_/D` | 282348.8192 |
| Engine | FF | 21.709534 | 12.5 | `_9906_/Q` → `_10181_/D` | 282348.8192 |
| Engine | IR | 6.502565 | 12.5 | `rxReady` → `_8955_/D` | 282348.8192 |
| Engine | RO | 9.062789 | 12.5 | `_10121_/Q` → `txEnable` | 282348.8192 |
| Engine | IO | 3.674172 | 12.5 | `reset_n` → `pullup_0` | 282348.8192 |
| Wrapper | appClock.FF | 12.017683 | 24.96 | `_11078_/Q` → `_10550_/D` | 319285.2544 |
| Wrapper | appClock.IR | 9.074254 | 24.96 | `bus_bits_origin[1]` → `_10525_/D` | 319285.2544 |
| Wrapper | appClock.RO | 3.929136 | 24.96 | `_11405_/Q` → `bus_gnt` | 319285.2544 |
| Wrapper | appClock.IO | 4.683438 | 24.96 | `vbus` → `pullupEnable` | 319285.2544 |
| Wrapper | usbClock.CC | 5.355806 | 50 | `_11279_/Q` → `_11279_/D` | 319285.2544 |
| Wrapper | usbClock.CF | 13.388058 | 12.5 | `_10783_/Q` → `_11284_/D` | 319285.2544 |
| Wrapper | usbClock.FC | 14.811282 | 12.5 | `_10860_/Q` → `_10745_/D` | 319285.2544 |
| Wrapper | usbClock.FF | 22.338293 | 12.5 | `_10637_/Q` → `_10662_/D` | 319285.2544 |
| Wrapper | usbClock.IR | 12.100127 | 12.5 | `vbus` → `_10281_/D` | 319285.2544 |
| Wrapper | usbClock.RO | 9.848157 | 12.5 | `_11342_/Q` → `pullupEnable` | 319285.2544 |
| Wrapper | usbClock.IO | 4.683438 | 12.5 | `vbus` → `pullupEnable` | 319285.2544 |
| Wrapper | aonClock.FF | 2.488224 | 24.96 | `_10940_/Q` → `_10943_/D` | 319285.2544 |
| Wrapper | aonClock.RO | 3.750224 | 24.96 | `_10943_/Q` → `usbClockRequest` | 319285.2544 |
| Wrapper | aonClock.IO | 4.683438 | 24.96 | `vbus` → `pullupEnable` | 319285.2544 |

Area is repeated per block and is not additive. Empty classes have no paths.
There are no clock-gate paths in these tops; electrical slew/capacitance
violations are zero. EP0 has no negative hold/reset slack; engine has two
and wrapper six negative hold rows under the unchanged zero-delay contract.

Mapped certified FF counts are **measured** from the certificate inventories:

| Scope | Previous D45 | Literal D48 subset |
| --- | ---: | ---: |
| Standalone EP0 | 87 | 64 unreset header bits |
| Integrated EP0 | 87 | 64 unreset header bits |
| Retained SIE | 85 | 0 |
| Retained PHY | 0 | 0 |
| Engine / wrapper total | 172 each | 64 each |

The old certificates proved enables/reset cones, not the new reset-inclusive
value invariant. No resettable register is promoted without that stronger
proof. This is a sound conservative subset, not exhaustive reachable-state
certification. All source/mapped proofs and old/new targeted faults pass for
the retained subset. Full exception-coverage and per-class over-budget controls
remain unqualified, and the runner still fails closed.

Requested classifications: SIE → PHY TX nrzi_q is now FF; EP0 configured →
SIE frame[10] is FF. EP0 header → state is CF, state → header is FC and
state → address is FF. They do not become CC under literal D48. The prior
SIE data → out_toggle path is also FF and is the engine worst above.

The authorized fanout transformation inserts eight parallel enable FFs in
the engine and three in the wrapper, one per additional first-branch load
group; all share the original next-state, clock and asynchronous reset.
Actual library-FF equality proves by induction; wrong-data/reset controls fail.
Exact substitution recovers original connections, including copied leading
buffer/inverter prefixes. Independent review caught and resolved unused-net
bit-allocation and JSON cell/net naming collisions before final measurement.

The engine enable → PHY RX rx_eop_qq path is **measured** 13.296519 ns from
`usb_enable_replica_1/Q` to `_10139_/D`, FF, still over 12.5 ns. The former
14.978270 ns result is historical. Further restructuring stops here.
The wrapper raw-reset worst input path is removed by sourcing engine reset-data
from shared usbUp; the new worst USB IR is vbus → resume carries at
12.100127 ns. Asynchronous assertion is retained by the shared primitive.
Reset-data equivalence and cadence proofs/covers/faults pass at
`build/t19/d48-formal-02`; all eleven wire/MMIO/resume tests pass at fresh
`d48-emit-01`. Sampled digital formal is not physical reset-skew signoff.

No further pipeline removal, pad delay contract, standalone SIE fixture
change or SRAM swap followed the stop. The small-model packet attempt is
ineligible without forbidden buffer restructuring; no solver job/time box
was started. Frozen acceptance failures are recorded below and in the task report.

### D48 final frozen confirmation

**Measured** on the final frozen source inventory at base
`15161bf897d1b4b4cba69030154daf89ee19ca12`:
`python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d48-frozen-check-01`.
The final EP0/engine/wrapper class delays and areas exactly match the table
above. Local certificates and all applicable old/new fault controls pass;
the new retained-pin fault is explicitly recorded in this frozen receipt.
The aggregate and fast CI fail, with no source-change error. Full tier was
not run. Other freshly measured block results follow; budgets use the same
arithmetic and corner stated above.

| Block | Class | Measured worst ns | Estimated budget ns | Mapped start → end | Measured block area um2 |
| --- | --- | ---: | ---: | --- | ---: |
| in | RR | 11.140153 | 12.5 | `_3172_/Q` → `_3128_/D` | 105051.2960 |
| in | IR | 9.972349 | 12.5 | `reset_n` → `_3299_/D` | 105051.2960 |
| in | RO | 3.984604 | 12.5 | `_3098_/Q` → `appReady` | 105051.2960 |
| out | RR | 11.820112 | 12.5 | `_3072_/Q` → `_3039_/D` | 102331.4432 |
| out | IR | 9.609552 | 12.5 | `reset_n` → `_3679_/D` | 102331.4432 |
| out | RO | 4.164564 | 12.5 | `_3716_/Q` → `nak` | 102331.4432 |
| resume | RR | 9.333540 | 12.5 | `_202_/Q` → `_201_/D` | 4361.8624 |
| resume | IR | 8.076866 | 12.5 | `attached` → `_201_/D` | 4361.8624 |
| resume | RO | 4.093227 | 12.5 | `_195_/Q` → `suspended` | 4361.8624 |
| registers | RR | 11.202718 | 24.96 | `_453_/Q` → `_454_/D` | 8365.9072 |
| registers | IR | 9.328797 | 24.96 | `bus_bits_addr[9]` → `_454_/D` | 8365.9072 |
| registers | RO | 4.043431 | 24.96 | `_453_/Q` → `bus_gnt` | 8365.9072 |
| sie | FF | 24.721727 | 12.5 | `_2779_/Q` → `_2916_/D` | 55049.0304 |
| sie | IR | 18.264446 | 12.5 | `io_in_int_endps_i[14]` → `_2916_/D` | 55049.0304 |
| sie | RO | 21.622900 | 12.5 | `_2779_/Q` → `io_in_ready_o` | 55049.0304 |
| sie | IO | 14.955754 | 12.5 | `io_in_int_endps_i[14]` → `io_in_ready_o` | 55049.0304 |

The integrated-SIE count in the table above is 85 previous D45 bits → zero
under literal D48. The external-mask standalone fixture has 125 previous
bits → zero, plus three enable replicas, and five negative hold/reset rows;
it has not been tied to integrated constants because step 6 was not reached.
No electrical slew/capacitance violation is reported in any measured block.

The canonical previously certified EP0 registers were `header_0` through
`header_7`, `descriptorLength`, `decodeValidQ`, `decodeReplyQ`, `decodeLengthQ`,
`decodePendingQ` and `decodeValueQ`. Only the eight headers remain certified.
Integrated SIE previously included `addr_q`, `crc16_q`, `data_q`, `delay_cnt_q`,
`endp_q`, `frame_q`, `in_ack_pending_q`, `in_byte_q`, `in_data_ack_q`, `in_req_q`,
`in_toggle_q`, `in_zlp_q`, `out_eop_q`, `out_err_q`, `out_toggle_q`, `phy_state_q`
and `pid_q`; none is certified under the stronger literal-reset condition.
PHY RX and TX were previously uncertified and remain uncertified. Receipts
enumerate exact scalar mapped identities, aliases and optimized unused bits.

The worst engine FF is `sie.data_q[1]` → `sie.out_toggle_q[0]`; the worst
wrapper USB FF is `engine.sie.data_q[0]` → `engine.sie.pid_q[2]`. The stopped
EP0 FC remains `state[5]` → `header_5[6]`. None is reported closed.

`python tools/env/run.py run -- python3 scratch/t19_d48_reset_cone.py` finds
zero combinational raw-usbReset_n-to-D endpoints and four asynchronous RN
endpoints in the mapped wrapper (receipt `build/t19/d48-reset-data-cone.json`).
These are measured structural counts, not physical reset-delay/skew results.

## D51 reset-compatible classes and enable sizing, 2026-11-18

**Measured**, baseline `269fa0f7fe1b0560d58dd62c44ef01340e84b06b` plus the source/flow inventories:
`python tools/env/run.py run -- python3 scratch/t19_d51_measure.py d51-timing-01`.
Exact per-block commands are in `build/t19/d51-timing-01/commands.json`.
Production RTL is unchanged from D48; the diagnostic uses its frozen emission.
Yosys 0.71+34/OpenSTA 3.2.0, pinned GF180 7-track SS/125 C/3.0 V,
mapped pre-layout, ideal clocks, no wire parasitics. These diagnostic results
are followed by fresh frozen emission/checks, not substituted for them.
Estimated budgets remain 0.60 × 1000/48 = 12.5 ns, 0.60 × 4 × 1000/48 =
50 ns for proved compatible pairs, and 0.60 × 41.6 = 24.96 ns for app/AON.

R is root-reset protocol state; B is protocol state reset by root and bus reset;
H is header state with bus-reset write suppression; S is EP0 state with a
synchronous bus-reset constant override. S→R is **CC_reset**, single-cycle.
All other proved group pairs are CC. PHY bus_reset_q stays full-rate because
it drives next-sample synchronous reset data. PHY rx_en_q and the sampler/
clock-recovery registers stay full-rate. Neither approval nor reset-value
idempotence alone establishes a compatible capture pair.

| Block | Class | Measured worst ns | Estimated budget ns | Mapped start → end | Measured area um2 |
| --- | --- | ---: | ---: | --- | ---: |
| control | CC | 13.370109 | 50 | `_1963_/Q` → `_1990_/D` | 42922.7456 |
| control | CC_reset | 11.621190 | 12.5 | `_1963_/Q` → `_1854_/D` | 42922.7456 |
| control | CF | 11.557283 | 12.5 | `_1958_/Q` → `_1823_/D` | 42922.7456 |
| control | FC | 9.330946 | 12.5 | `_1818_/Q` → `_1846_/D` | 42922.7456 |
| control | FF | 10.059363 | 12.5 | `_1865_/Q` → `_1798_/D` | 42922.7456 |
| control | IR | 11.261580 | 12.5 | `busReset` → `_1846_/D` | 42922.7456 |
| control | RO | 4.142676 | 12.5 | `_2039_/Q` → `configured` | 42922.7456 |
| engine | CC | 21.709534 | 50 | `_9906_/Q` → `_10181_/D` | 282454.1888 |
| engine | CC_reset | 12.409761 | 12.5 | `_9673_/Q` → `_9720_/D` | 282454.1888 |
| engine | CF | 14.038514 | 12.5 | `_9880_/Q` → `_10159_/D` | 282454.1888 |
| engine | FC | 13.719343 | 12.5 | `_10192_/Q` → `_9208_/D` | 282454.1888 |
| engine | FF | 14.122969 | 12.5 | `_9457_/Q` → `_10037_/D` | 282454.1888 |
| engine | IR | 6.502565 | 12.5 | `rxReady` → `_8955_/D` | 282454.1888 |
| engine | RO | 9.062789 | 12.5 | `_10121_/Q` → `txEnable` | 282454.1888 |
| engine | IO | 3.674172 | 12.5 | `reset_n` → `pullup_0` | 282454.1888 |
| usb | appClock.FF | 12.017683 | 24.96 | `_11078_/Q` → `_10550_/D` | 319390.6240 |
| usb | appClock.IR | 9.074254 | 24.96 | `bus_bits_origin[1]` → `_10525_/D` | 319390.6240 |
| usb | appClock.RO | 3.929136 | 24.96 | `_11405_/Q` → `bus_gnt` | 319390.6240 |
| usb | appClock.IO | 4.683438 | 24.96 | `vbus` → `pullupEnable` | 319390.6240 |
| usb | usbClock.CC | 22.338293 | 50 | `_10637_/Q` → `_10662_/D` | 319390.6240 |
| usb | usbClock.CC_reset | 12.927523 | 12.5 | `_10860_/Q` → `_9284_/D` | 319390.6240 |
| usb | usbClock.CF | 16.453081 | 12.5 | `_10973_/Q` → `_10281_/D` | 319390.6240 |
| usb | usbClock.FC | 14.488053 | 12.5 | `_9893_/Q` → `_10745_/D` | 319390.6240 |
| usb | usbClock.FF | 16.038822 | 12.5 | `_11342_/Q` → `_10281_/D` | 319390.6240 |
| usb | usbClock.IR | 12.100127 | 12.5 | `vbus` → `_10281_/D` | 319390.6240 |
| usb | usbClock.RO | 9.848157 | 12.5 | `_11342_/Q` → `pullupEnable` | 319390.6240 |
| usb | usbClock.IO | 4.683438 | 12.5 | `vbus` → `pullupEnable` | 319390.6240 |
| usb | aonClock.FF | 2.488224 | 24.96 | `_10940_/Q` → `_10943_/D` | 319390.6240 |
| usb | aonClock.RO | 3.750224 | 24.96 | `_10943_/Q` → `usbClockRequest` | 319390.6240 |
| usb | aonClock.IO | 4.683438 | 24.96 | `vbus` → `pullupEnable` | 319390.6240 |


The enable sizing change replaces only weak positive buffers in the proved
cadence tree after fanout insertion. Actual Liberty functions are proved
equivalent; a wrong-polarity replacement fails. Exact type restoration
recovers every original pin and connection. **Measured** engine enable→
rx_eop_qq worst over both transitions is 9.351625 ns, from usb_enable_replica_1/Q to _10139_/D, versus
the historical D48 13.296519 ns. Worst measured enable-launch delay is
11.768248 ns. This is cell sizing, not placement closure.

Remaining measured failures trigger the stop on further restructuring:

- engine CF: endpoint decode `_9880_/Q` → packet-stage `in.consume`
  `_10159_/D`, 14.038514 ns;
- engine FC: packet-stage `control.inRequest` `_10192_/Q` → configured
  `_9208_/D`, 13.719343 ns;
- engine FF: OUT reset release `_9457_/Q` → packet RAM `_10037_/D`, 14.122969 ns;
- wrapper CC_reset: EP0 state[4] `_10860_/Q` → writeCount[0] `_9284_/D`, 12.927523 ns;
- wrapper CF: PHY TX state[0] `_10973_/Q` → resume.carries_3 `_10281_/D`, 16.453081 ns;
- wrapper FC: PHY bus-reset `_9893_/Q` → header_4[6] `_10745_/D`, 14.488053 ns;
- wrapper FF: usbUp release `_11342_/Q` → resume.carries_3 `_10281_/D`, 16.038822 ns.

Each has the unchanged estimated 12.5 ns budget. Standalone EP0 has a numerical
pass, but remains blocked by sampling/exception qualification. No stage was
removed: packet-boundary stages are still full-rate and reset-incompatible
pairs remain. Boundary-delay contract, standalone-fixture adjustment and
additional pipeline changes are not reached after this stop. Existing zero-
delay IO screening/negative hold remains unqualified physical-flow evidence,
not pad/board signoff. No pre-CTS hold RTL or packet-buffer changes were made.

### D51 frozen confirmation

**Measured**, baseline `269fa0f7fe1b0560d58dd62c44ef01340e84b06b` plus frozen
inventories, using `python tools/env/run.py run -- python3 hw/ip/usb/check.py
--output build/t19/d51-frozen-check-01`. Fresh production emission reproduces
every EP0/engine/wrapper class delay and area in the D51 table. All source
hashes match before reporting edits. Final exact-member/pin guards and
execution-dependent fault inventories are exercised in this run. No earlier
diagnostic is retroactively claimed to have tested those final corrections.
Aggregate and fast CI fail; full tier was not run.

Requested original paths are now measured CC: SIE→PHY TX nrzi_q is
15.341034 ns (`_9878_/Q` → `_10183_/D`), and EP0 configured→SIE frame[10]
is 20.658268 ns (`_9208_/Q` → `_10175_/D`), both in the engine. These fit
the estimated 50 ns budget. The former EP0 state[5]→header_5[6] FC path is
now compatible CC because the actual header capture is bus-reset-suppressed.
Incompatible S→R paths retain the original single-cycle budget.

| Block | Group R | Group B | Group H | Group S | Full-rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| control | 60 | 0 | 64 | 72 | 68 |
| engine | 85 | 102 | 64 | 43 | 1625 |
| usb | 85 | 102 | 64 | 43 | 1924 |
| sie | 26 | 142 | 0 | 0 | 46 |

Counts above are measured from exact mapped certificate inventories.

| Block | Class | Measured ns | Estimated budget ns | Mapped start → end | Measured area um2 |
| --- | --- | ---: | ---: | --- | ---: |
| in | RR | 11.140153 | 12.5 | `_3172_/Q` → `_3128_/D` | 105051.2960 |
| in | IR | 9.972349 | 12.5 | `reset_n` → `_3299_/D` | 105051.2960 |
| in | RO | 3.984604 | 12.5 | `_3098_/Q` → `appReady` | 105051.2960 |
| out | RR | 11.820112 | 12.5 | `_3072_/Q` → `_3039_/D` | 102331.4432 |
| out | IR | 9.609552 | 12.5 | `reset_n` → `_3679_/D` | 102331.4432 |
| out | RO | 4.164564 | 12.5 | `_3716_/Q` → `nak` | 102331.4432 |
| resume | RR | 9.333540 | 12.5 | `_202_/Q` → `_201_/D` | 4361.8624 |
| resume | IR | 8.076866 | 12.5 | `attached` → `_201_/D` | 4361.8624 |
| resume | RO | 4.093227 | 12.5 | `_195_/Q` → `suspended` | 4361.8624 |
| registers | RR | 11.202718 | 24.96 | `_453_/Q` → `_454_/D` | 8365.9072 |
| registers | IR | 9.328797 | 24.96 | `bus_bits_addr[9]` → `_454_/D` | 8365.9072 |
| registers | RO | 4.043431 | 24.96 | `_453_/Q` → `bus_gnt` | 8365.9072 |
| sie | CC | 24.721727 | 50 | `_2779_/Q` → `_2916_/D` | 55171.9616 |
| sie | CF | 8.469969 | 12.5 | `_2844_/Q` → `_2893_/D` | 55171.9616 |
| sie | FC | 11.308363 | 12.5 | `_2720_/Q` → `_2718_/D` | 55171.9616 |
| sie | FF | 15.381041 | 12.5 | `_2830_/Q` → `_2801_/D` | 55171.9616 |
| sie | IR | 18.264446 | 12.5 | `io_in_int_endps_i[14]` → `_2916_/D` | 55171.9616 |
| sie | RO | 21.622900 | 12.5 | `_2779_/Q` → `io_in_ready_o` | 55171.9616 |
| sie | IO | 14.955754 | 12.5 | `io_in_int_endps_i[14]` → `io_in_ready_o` | 55171.9616 |

No electrical slew/capacitance violation is reported. Hold/reset checks are retained, including SETN.

| Block | Measured worst hold slack ns | Measured worst reset-check slack ns | Negative rows |
| --- | ---: | ---: | ---: |
| control | 1.175274 | 0.396825 | 0 |
| engine | -0.102503 | 0.100245 | 2 |
| usb | -0.102503 | -0.975158 | 6 |
| sie | -0.102503 | -0.396361 | 5 |

These use the unchanged zero-delay screening boundary, not a completed pad/
board contract. Negative hold remains a physical-flow item and still fails
the current gate; no RTL was added to repair pre-CTS hold.

Independent read-only diagnosis identifies possible next scoped work:
size weak reset/decode buffers before adding RTL, and refactor the resume
running/count carry predicates combinationally without adding latency.
These are unmeasured proposals; no repair or timing closure is claimed.
