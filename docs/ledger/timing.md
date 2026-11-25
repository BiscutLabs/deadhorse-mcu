# Per-block GF180 timing ledger

## T32 standalone faithful core timing, 2026-11-23

D80's third mapping candidate and maintained-flow reproduction measure
**65.141479 ns RR**, below unchanged estimated 66.666667 ns at 9 MHz; measured
mapped area **814013.088 um2**. Command: pinned
`python hw/ip/perf_core/check_top_timing.py --emitted build/t32/final-fast03/fast/faithful-float-emit/asic --operating-point main-9mhz --output build/t32/timing-iterations/standard-flow02`,
base main `9b80375109826e41d28cae95b1b80c653bfc34ff` plus local T32 work.
Recipe: 50000 ps ABC goal and DeadhorsePerfCore premapped-JSON reload;
unchanged RTL, SS/125 C/3.0 V Liberty, output loads, 9 MHz STA and 60% limit.
All-state transition/output/clock/reset equivalence and wrong-D control pass.
Measured electrical violations zero, min gate slack +0.704980 ns, min data hold
+0.530017 ns; reset removal -0.975158 ns remains physical-boundary debt.
Loops 1/2 fail at measured 70.402451/73.791389 ns and are rejected.
[Full paths, commands, areas and scope](../plan/tasks/reports/T32-timing-followup.md).
Frozen fast CI `build/t32/timing-fast01` passes all 34 active commands in
measured 3850.781049 s with twelve inherited unproved deferrals, reproducing
65.141479 ns in its faithful-core timing stage. Full tier unrun; no
placement/signoff claim. The separate T32 reset read-data proof stays deferred.

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

## S1 faithful-F baseline, 2026-11-17

Historical task base: `172d4f1d2279bb5cc5c621685ad94923bfd15282`; measurement
receipt revision is qualified below. `python tools/env/run.py run -- python3
hw/ip/perf_core/check_top_timing.py --emitted build/s1/emit/faithful-float/asic
--operating-point main-9mhz --output build/s1/timing` passes **65.726219 /
66.666667 ns**, mapped standard-cell area **839962.5472 um2**, zero electrical
violations. GF1807t5v0 SS/125C/3.0V, Yosys0.71+34/OpenSTA3.2.0; pre-layout,
ideal clocks, no wire delay or SRAM macro views. Derived margin0.940448ns;
ABC target62500ps and the60%rule unchanged. No production clock adoption.
Publication audit: both S1 measurement receipts record commit
`20881a45655db39b9bb8b42d6c3bced83e48f527`, which is unavailable in the local
object store. The historical task base above is not asserted equivalent;
the receipts' exact source hashes identify their measured inputs.

S1 is blocked separately: the ideal-memory hard-float fixture has measured
mean12338.667/worst14233cycles, derived1.090122MIPS at9MHz, below the unchanged
2.5MIPS floor. Independent review confirmed the raw loop windows and
comparisons. No formal or CI tier ran for S1; no latency sweep followed the
stop condition. [Report](../plan/tasks/reports/S1.md).

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


## D52 full-rate follow-up, 2026-11-19

Measured with `python tools/env/run.py run -- python3 scratch/t19_d52_measure.py
d52-timing-05`, baseline acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf plus the
receipt source/flow hashes. Per-block commands are in commands.json. Pinned
GF180 7-track SS 125 C / 3.0 V, Yosys/OpenSTA versions in receipts; mapped,
pre-layout, ideal clocks, no wire parasitics. Existing budgets, IO screening,
electrical and hold/removal checks are unchanged.

Resume count comparisons are kept before the late running qualification;
all-state transition equivalence against pinned D51 passes with a prepared
carry-D fault. Chisel named wires require explicit keep binding to the Slang
specialized module before mapping. Weak positive buffer branches are sized to
buf_4; loaded listed size-1 combinational gates use the same family size-2.
Actual library equality and inverted-output faults prove every used replacement;
restoring cell types exactly recovers all connections/state. Actual clock trees
are excluded. Area is recalculated after sizing.

All delays, area and slack in this table are **measured** by that command;
budgets are the unchanged approved limits. CC_reset is the incompatible S→R
reset group and stays full-rate. Empty classes have no path, not a proof waiver.

| Block | Class | Worst ns | Budget ns | Start | End | Area um² |
| --- | --- | ---: | ---: | --- | --- | ---: |
| control | CC | 13.270474 | 50.00 | _1992_/Q | _1814_/D | 45539.4240 |
| control | CC_reset | 10.573215 | 12.50 | _1963_/Q | _1938_/D | 45539.4240 |
| control | CF | 11.119832 | 12.50 | _1958_/Q | _1823_/D | 45539.4240 |
| control | FC | 8.026012 | 12.50 | _1818_/Q | _1846_/D | 45539.4240 |
| control | FF | 8.186110 | 12.50 | _1865_/Q | _1798_/D | 45539.4240 |
| control | IR | 9.534351 | 12.50 | bitEnable | _2055_/D | 45539.4240 |
| control | RO | 4.142676 | 12.50 | _2039_/Q | configured | 45539.4240 |
| control | IO | — | 12.50 | — | — | 45539.4240 |
| control | RG | — | 12.50 | — | — | 45539.4240 |
| control | IG | — | 12.50 | — | — | 45539.4240 |
| engine | CC | 21.589281 | 50.00 | _9906_/Q | _10181_/D | 294903.1680 |
| engine | CC_reset | 10.810170 | 12.50 | _9673_/Q | _9743_/D | 294903.1680 |
| engine | CF | 13.703803 | 12.50 | _9208_/Q | _10159_/D | 294903.1680 |
| engine | FC | 11.514855 | 12.50 | _10160_/Q | _10111_/D | 294903.1680 |
| engine | FF | 11.222711 | 12.50 | _9457_/Q | _10037_/D | 294903.1680 |
| engine | IR | 4.897140 | 12.50 | rxReady | _8955_/D | 294903.1680 |
| engine | RO | 7.859807 | 12.50 | _9942_/Q | txEnable | 294903.1680 |
| engine | IO | 3.308646 | 12.50 | reset_n | pullup_0 | 294903.1680 |
| engine | RG | — | 12.50 | — | — | 294903.1680 |
| engine | IG | — | 12.50 | — | — | 294903.1680 |
| usb | appClock.CC | — | 99.84 | — | — | 332364.2560 |
| usb | appClock.CC_reset | — | 24.96 | — | — | 332364.2560 |
| usb | appClock.CF | — | 24.96 | — | — | 332364.2560 |
| usb | appClock.FC | — | 24.96 | — | — | 332364.2560 |
| usb | appClock.FF | 10.020551 | 24.96 | _11264_/Q | _11264_/D | 332364.2560 |
| usb | appClock.IR | 8.064628 | 24.96 | bus_bits_origin[1] | _10135_/D | 332364.2560 |
| usb | appClock.RO | 3.964705 | 24.96 | _11470_/Q | bus_gnt | 332364.2560 |
| usb | appClock.IO | 4.400927 | 24.96 | vbus | pullupEnable | 332364.2560 |
| usb | appClock.RG | — | 24.96 | — | — | 332364.2560 |
| usb | appClock.IG | — | 24.96 | — | — | 332364.2560 |
| usb | usbClock.CC | 20.215874 | 50.00 | _10698_/Q | _11329_/D | 332364.2560 |
| usb | usbClock.CC_reset | 11.639993 | 12.50 | _10924_/Q | _10161_/D | 332364.2560 |
| usb | usbClock.CF | 12.707026 | 12.50 | _10717_/Q | _11465_/D | 332364.2560 |
| usb | usbClock.FC | 12.167490 | 12.50 | _11425_/Q | _10821_/D | 332364.2560 |
| usb | usbClock.FF | 11.857990 | 12.50 | _9795_/Q | _10731_/D | 332364.2560 |
| usb | usbClock.IR | 6.191682 | 12.50 | vbus | _9215_/D | 332364.2560 |
| usb | usbClock.RO | 9.574278 | 12.50 | _11405_/Q | pullupEnable | 332364.2560 |
| usb | usbClock.IO | 4.400927 | 12.50 | vbus | pullupEnable | 332364.2560 |
| usb | usbClock.RG | — | 12.50 | — | — | 332364.2560 |
| usb | usbClock.IG | — | 12.50 | — | — | 332364.2560 |
| usb | aonClock.CC | — | 99.84 | — | — | 332364.2560 |
| usb | aonClock.CC_reset | — | 24.96 | — | — | 332364.2560 |
| usb | aonClock.CF | — | 24.96 | — | — | 332364.2560 |
| usb | aonClock.FC | — | 24.96 | — | — | 332364.2560 |
| usb | aonClock.FF | 2.488224 | 24.96 | _11003_/Q | _11004_/D | 332364.2560 |
| usb | aonClock.IR | — | 24.96 | — | — | 332364.2560 |
| usb | aonClock.RO | 3.750224 | 24.96 | _11004_/Q | usbClockRequest | 332364.2560 |
| usb | aonClock.IO | 4.400927 | 24.96 | vbus | pullupEnable | 332364.2560 |
| usb | aonClock.RG | — | 24.96 | — | — | 332364.2560 |
| usb | aonClock.IG | — | 24.96 | — | — | 332364.2560 |


control: measured worst hold 0.938884 ns; removal 0.396825 ns; electrical violations 0.

engine: measured worst hold -0.102503 ns; removal -0.160613 ns; electrical violations 0.

usb: measured worst hold -0.102503 ns; removal -0.975158 ns; electrical violations 0.

Remaining failures: engine configured `_9208_/Q` → IN consume `_10159_/D`,
CF 13.703803 ns; wrapper endpoint `_10717_/Q` → EP0 IN-ready `_11465_/D`,
CF 12.707026 ns. Both retain 12.5 ns. These terminate further restructuring;
no stage was removed or acceptance relaxed. The former resume path is closed
numerically; complete protocol sampling and exception qualification are open.
Pad/board contract and standalone-SIE fixture work remain open at the stop.
Negative hold/removal remains visible as a physical/reset qualification item;
no RTL delay was inserted. Frozen confirmation follows below.

### D52 frozen confirmation and additional blocks

Measured by `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output
build/t19/d52-frozen-check-01`, base acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf
plus frozen hashes; same pinned tools/corner and pre-layout limitations above.
The EP0/engine/wrapper table above reproduces exactly. No slew/cap violation
is reported. Remaining negative hold/removal rows: engine 4, wrapper 6, SIE 5;
they remain unresolved, not waived by sizing. No pad-delay contract is claimed.

Additional measured block/class paths (unchanged budgets):

| Block | Class | Worst ns | Budget ns | Start | End | Area um² |
| --- | --- | ---: | ---: | --- | --- | ---: |
| in | RR | 9.369685 | 12.50 | _3202_/Q | _3699_/D | 108636.0576 |
| in | IR | 7.092785 | 12.50 | reset_n | _3299_/D | 108636.0576 |
| in | RO | 4.111012 | 12.50 | _3098_/Q | appReady | 108636.0576 |
| in | IO | — | 12.50 | — | — | 108636.0576 |
| in | RG | — | 12.50 | — | — | 108636.0576 |
| in | IG | — | 12.50 | — | — | 108636.0576 |
| out | RR | 9.349499 | 12.50 | _3072_/Q | _3016_/D | 105938.1568 |
| out | IR | 6.719829 | 12.50 | reset_n | _3199_/D | 105938.1568 |
| out | RO | 4.282614 | 12.50 | _3716_/Q | nak | 105938.1568 |
| out | IO | — | 12.50 | — | — | 105938.1568 |
| out | RG | — | 12.50 | — | — | 105938.1568 |
| out | IG | — | 12.50 | — | — | 105938.1568 |
| resume | RR | 8.028501 | 12.50 | _202_/Q | _207_/D | 4783.3408 |
| resume | IR | 5.062730 | 12.50 | attached | _190_/D | 4783.3408 |
| resume | RO | 4.080467 | 12.50 | _205_/Q | suspended | 4783.3408 |
| resume | IO | — | 12.50 | — | — | 4783.3408 |
| resume | RG | — | 12.50 | — | — | 4783.3408 |
| resume | IG | — | 12.50 | — | — | 4783.3408 |
| registers | RR | 11.202718 | 24.96 | _453_/Q | _454_/D | 8365.9072 |
| registers | IR | 9.328797 | 24.96 | bus_bits_addr[9] | _454_/D | 8365.9072 |
| registers | RO | 4.043431 | 24.96 | _453_/Q | bus_gnt | 8365.9072 |
| registers | IO | — | 24.96 | — | — | 8365.9072 |
| registers | RG | — | 24.96 | — | — | 8365.9072 |
| registers | IG | — | 24.96 | — | — | 8365.9072 |
| sie | CC | 24.453424 | 50.00 | _2779_/Q | _2916_/D | 58611.8400 |
| sie | CC_reset | — | 12.50 | — | — | 58611.8400 |
| sie | CF | 7.714397 | 12.50 | _2812_/Q | _2894_/D | 58611.8400 |
| sie | FC | 9.707932 | 12.50 | _2897_/Q | _2770_/D | 58611.8400 |
| sie | FF | 13.912383 | 12.50 | _2809_/Q | _2801_/D | 58611.8400 |
| sie | IR | 17.865311 | 12.50 | io_in_int_endps_i[10] | _2916_/D | 58611.8400 |
| sie | RO | 21.380751 | 12.50 | _2779_/Q | io_in_ready_o | 58611.8400 |
| sie | IO | 14.792633 | 12.50 | io_in_int_endps_i[10] | io_in_ready_o | 58611.8400 |
| sie | RG | — | 12.50 | — | — | 58611.8400 |
| sie | IG | — | 12.50 | — | — | 58611.8400 |

Standalone SIE failures are FF 13.912383 ns, IR 17.865311 ns, RO 21.380751 ns
and IO 14.792633 ns against 12.5 ns. Its unconstrained endpoint-mask fixture
remains an open boundary issue; integrated engine/wrapper failures remain
independently blocking. Frozen aggregate and fast CI fail; full tier is unrun.
No pipeline was removed, no hold RTL inserted and no further restructuring
performed after the remaining integrated CF stop. Functional sources stayed
frozen; final reporting edits do not turn these failures into acceptance.


## D53 measured candidate, 2026-11-19

Measured command: `python tools/env/run.py run -- python3 hw/ip/usb/check.py
--output build/t19/d53-frozen-check-01`; base
d45e50f457f3576949b8fdbfd6e1bb69652aaa53 plus exact frozen source/flow hashes.
Pinned GF180 7-track SS/125 C/3.0 V, Yosys 0.71+34/OpenSTA 3.2.0, ideal clocks,
mapped pre-layout cell delay/area; no routed/parasitic or board signoff.
Budgets remain estimated 0.60×1000/48=12.5 ns for full-rate USB and
0.60×4×1000/48=50 ns only for certified compatible pairs. Other domain limits,
electrical, reset, hold and gate checks are unchanged. Empty rows mean no path
of that class was reported, not an exception. Fast CI reproduces every row.

Fresh mapped certificate bit counts, measured from the source-bound D52/D53
certificate receipts: EP0 196→196, engine 294→292, wrapper 294→292, SIE 168→166.
The smaller SIE packet counter removes two certified bits; eligibility rules
and all negative controls remain unchanged. Buffer registers retain full-rate
classification. Reset-aware group pairing and copied-enable proofs are reapplied
to the fresh mapped identities, not inherited by name from the older netlist.

| Block | Class | Measured worst ns | Estimated budget ns | Start | End | Measured area um² |
| --- | --- | ---: | ---: | --- | --- | ---: |
| control | CC | 13.395742 | 50.00 | _2031_/Q | _1833_/D | 46165.0560 |
| control | CC_reset | 10.447189 | 12.50 | _1976_/Q | _1924_/D | 46165.0560 |
| control | CF | 11.734216 | 12.50 | _1972_/Q | _1842_/D | 46165.0560 |
| control | FC | 8.128351 | 12.50 | _1832_/Q | _1967_/D | 46165.0560 |
| control | FF | 8.865483 | 12.50 | _1870_/Q | _1811_/D | 46165.0560 |
| control | IR | 10.367253 | 12.50 | busReset | _2016_/D | 46165.0560 |
| control | RO | 4.170210 | 12.50 | _2052_/Q | configured | 46165.0560 |
| control | IO | — | 12.50 | — | — | 46165.0560 |
| control | RG | — | 12.50 | — | — | 46165.0560 |
| control | IG | — | 12.50 | — | — | 46165.0560 |
| in | RR | 9.012933 | 12.50 | _1321_/Q | _1297_/D | 39542.1376 |
| in | IR | 5.089289 | 12.50 | reset_n | _1414_/D | 39542.1376 |
| in | RO | 4.111012 | 12.50 | _1283_/Q | appReady | 39542.1376 |
| in | IO | — | 12.50 | — | — | 39542.1376 |
| in | RG | — | 12.50 | — | — | 39542.1376 |
| in | IG | — | 12.50 | — | — | 39542.1376 |
| out | RR | 9.012933 | 12.50 | _1267_/Q | _1243_/D | 38339.1680 |
| out | IR | 5.085909 | 12.50 | reset_n | _1114_/D | 38339.1680 |
| out | RO | 4.282614 | 12.50 | _1212_/Q | nak | 38339.1680 |
| out | IO | — | 12.50 | — | — | 38339.1680 |
| out | RG | — | 12.50 | — | — | 38339.1680 |
| out | IG | — | 12.50 | — | — | 38339.1680 |
| resume | RR | 8.028501 | 12.50 | _202_/Q | _207_/D | 4783.3408 |
| resume | IR | 5.062730 | 12.50 | attached | _190_/D | 4783.3408 |
| resume | RO | 4.080467 | 12.50 | _205_/Q | suspended | 4783.3408 |
| resume | IO | — | 12.50 | — | — | 4783.3408 |
| resume | RG | — | 12.50 | — | — | 4783.3408 |
| resume | IG | — | 12.50 | — | — | 4783.3408 |
| engine | CC | 20.914219 | 50.00 | _5318_/Q | _5917_/D | 156976.5568 |
| engine | CC_reset | 11.821310 | 12.50 | _5867_/Q | _6247_/D | 156976.5568 |
| engine | CF | 16.720451 | 12.50 | _5318_/Q | _6263_/D | 156976.5568 |
| engine | FC | 12.978483 | 12.50 | _6267_/Q | _5992_/D | 156976.5568 |
| engine | FF | 14.131563 | 12.50 | _6003_/Q | _6059_/D | 156976.5568 |
| engine | IR | 4.680038 | 12.50 | rxReady | _5299_/D | 156976.5568 |
| engine | RO | 8.123858 | 12.50 | _5402_/Q | txEnable | 156976.5568 |
| engine | IO | 3.987964 | 12.50 | reset_n | pullup_0 | 156976.5568 |
| engine | RG | — | 12.50 | — | — | 156976.5568 |
| engine | IG | — | 12.50 | — | — | 156976.5568 |
| registers | RR | 11.202718 | 24.96 | _453_/Q | _454_/D | 8365.9072 |
| registers | IR | 9.328797 | 24.96 | bus_bits_addr[9] | _454_/D | 8365.9072 |
| registers | RO | 4.043431 | 24.96 | _453_/Q | bus_gnt | 8365.9072 |
| registers | IO | — | 24.96 | — | — | 8365.9072 |
| registers | RG | — | 24.96 | — | — | 8365.9072 |
| registers | IG | — | 24.96 | — | — | 8365.9072 |
| usb | appClock.CC | — | 99.84 | — | — | 197043.3472 |
| usb | appClock.CC_reset | — | 24.96 | — | — | 197043.3472 |
| usb | appClock.CF | — | 24.96 | — | — | 197043.3472 |
| usb | appClock.FC | — | 24.96 | — | — | 197043.3472 |
| usb | appClock.FF | 10.022916 | 24.96 | _7484_/Q | _7484_/D | 197043.3472 |
| usb | appClock.IR | 8.064628 | 24.96 | bus_bits_origin[1] | _6376_/D | 197043.3472 |
| usb | appClock.RO | 3.964705 | 24.96 | _7668_/Q | bus_gnt | 197043.3472 |
| usb | appClock.IO | 4.400927 | 24.96 | vbus | pullupEnable | 197043.3472 |
| usb | appClock.RG | — | 24.96 | — | — | 197043.3472 |
| usb | appClock.IG | — | 24.96 | — | — | 197043.3472 |
| usb | usbClock.CC | 20.238413 | 50.00 | _7030_/Q | _6989_/D | 197043.3472 |
| usb | usbClock.CC_reset | 11.922677 | 12.50 | _7288_/Q | _6529_/D | 197043.3472 |
| usb | usbClock.CF | 13.506083 | 12.50 | _7029_/Q | _7397_/D | 197043.3472 |
| usb | usbClock.FC | 11.913838 | 12.50 | _6995_/Q | _7378_/D | 197043.3472 |
| usb | usbClock.FF | 12.062296 | 12.50 | _7093_/Q | _7057_/D | 197043.3472 |
| usb | usbClock.IR | 6.251663 | 12.50 | vbus | _7548_/D | 197043.3472 |
| usb | usbClock.RO | 9.581448 | 12.50 | _7605_/Q | pullupEnable | 197043.3472 |
| usb | usbClock.IO | 4.400927 | 12.50 | vbus | pullupEnable | 197043.3472 |
| usb | usbClock.RG | — | 12.50 | — | — | 197043.3472 |
| usb | usbClock.IG | — | 12.50 | — | — | 197043.3472 |
| usb | aonClock.CC | — | 99.84 | — | — | 197043.3472 |
| usb | aonClock.CC_reset | — | 24.96 | — | — | 197043.3472 |
| usb | aonClock.CF | — | 24.96 | — | — | 197043.3472 |
| usb | aonClock.FC | — | 24.96 | — | — | 197043.3472 |
| usb | aonClock.FF | 2.488224 | 24.96 | _7203_/Q | _7207_/D | 197043.3472 |
| usb | aonClock.IR | — | 24.96 | — | — | 197043.3472 |
| usb | aonClock.RO | 3.750224 | 24.96 | _7207_/Q | usbClockRequest | 197043.3472 |
| usb | aonClock.IO | 4.400927 | 24.96 | vbus | pullupEnable | 197043.3472 |
| usb | aonClock.RG | — | 24.96 | — | — | 197043.3472 |
| usb | aonClock.IG | — | 24.96 | — | — | 197043.3472 |
| sie | CC | 24.667847 | 50.00 | _2825_/Q | _2827_/D | 58260.6080 |
| sie | CC_reset | — | 12.50 | — | — | 58260.6080 |
| sie | CF | 8.328444 | 12.50 | _2857_/Q | _2938_/D | 58260.6080 |
| sie | FC | 9.698649 | 12.50 | _2941_/Q | _2823_/D | 58260.6080 |
| sie | FF | 12.008800 | 12.50 | _2768_/Q | _2936_/D | 58260.6080 |
| sie | IR | 17.718779 | 12.50 | io_in_int_endps_i[7] | _2795_/D | 58260.6080 |
| sie | RO | 20.493279 | 12.50 | _2825_/Q | io_in_ready_o | 58260.6080 |
| sie | IO | 11.862667 | 12.50 | io_in_int_endps_i[7] | io_in_ready_o | 58260.6080 |
| sie | RG | — | 12.50 | — | — | 58260.6080 |
| sie | IG | — | 12.50 | — | — | 58260.6080 |

Integrated failures: engine CF `_5318_/Q` (`_sie_endp_o[0]`)→`_6263_/D`
(`in.consume`) 16.720451 ns; FC `_6267_/Q` (`control.outReady`)→`_5992_/D`
(`control.cursor[5]`) 12.978483 ns; FF `_6003_/Q` (`sie.u_phy_rx.nrzi_q[3]`)
→`_6059_/D` (`sie.u_phy_rx.shift_register_q[7]`) 14.131563 ns. Wrapper USB CF
`_7029_/Q` (`engine._sie_endp_o[1]`)→`_7397_/D` (`engine.in.consume`) 13.506083 ns.
Aliases measured with `python tools/env/run.py run -- python3 -m
scratch.t19_d51_paths d53-frozen-check-01/timing` on the mapped netlists.
The unchanged full-rate budget is 12.5 ns. All certified compatible paths fit 50 ns;
EP0 numeric success remains qualification-blocked. No further restructuring or
pipeline removal follows the stop; retained full-rate sampling obligations remain.

No maximum-slew/capacitance violation is reported. Remaining negative checks:

| Block | Check | Start | End | Measured slack ns |
| --- | --- | --- | --- | ---: |
| engine | hold/min_fall | dnRx | _6278_/D | -0.102503 |
| engine | hold/min_fall | dpRx | _6279_/D | -0.102503 |
| usb | hold/min_fall | dpRx | _6326_/D | -0.102503 |
| usb | hold/min_fall | dpRx | _6559_/D | -0.102503 |
| usb | hold/min_fall | dnRx | _7173_/D | -0.102503 |
| usb | hold/min_fall | dnRx | _7531_/D | -0.102503 |
| usb | reset/min_rise | aonReset_n | _7595_/RN | -0.975158 |
| usb | reset/min_rise | aonReset_n | _7598_/RN | -0.975158 |
| sie | hold/min_fall | io_dp_rx_i | _2945_/D | -0.102503 |
| sie | hold/min_fall | io_dn_rx_i | _2968_/D | -0.102503 |

These are the existing zero-delay boundary screens, not a completed pad/board
delay contract. Negative hold remains a physical-flow item; no hold-fix RTL is
added. Wrapper reset-removal remains negative. Standalone SIE input-mask/endpoint
fixture qualification remains open; its IR/RO failures are retained. Integrated
engine/wrapper failures independently block acceptance. Setup/hold exception
coverage, per-class over-budget controls and retained pipeline sampling proof
remain required. The new streaming test additionally exposes an inherited IN
replay defect. Frozen aggregate and fast CI fail; full tier is unrun.


## D54 retry lifecycle, 2026-11-19

Measured by `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d54-frozen-check-03`, base commit `c20e625ea44baaf65c9a523f7a9e12fb070dee22` plus the receipt's exact frozen source hashes. Fast CI independently repeats the same measurements. GF180 7-track SS/125 C/3.0 V, Yosys 0.71+34/OpenSTA 3.2.0, mapped pre-layout cell area/delay and ideal clocks; no routed or board signoff. Budgets remain estimated 0.60×1000/48=12.5 ns full-rate and 0.60×4×1000/48=50 ns for certified compatible pairs; other domains retain existing limits.

Fresh source/mapped certificate counts (measured physical certified cells): EP0 196→196, engine 292→294, wrapper 292→293, standalone SIE 166→182. Read command: `python tools/env/run.py run -- python3 -m scratch.t19_d54_cert_delta`. The new live bulk `in_zlp_pending_q[1]` is B-certified in the engine (`_6255_`) and wrapper (`_7640_`); the standalone fixture retains all sixteen pending bits. Mapping also retains the existing engine eligibility `in_zlp_q[2]` FF (`_6133_`). Unused eligibility bits `[3..15]` merge with an existing compatible disabled-endpoint toggle FF (engine `_6211_`, wrapper `_7603_`); these aliases do not each add a register. Independent review confirms common B reset metadata and fresh mapped hold/reset checks, not a mixed-class alias waiver. New buffer `in.pending` remains full-rate (engine `_6206_`, wrapper `_7703_`). All existing certificate/fanout faults remain; no eligibility rule changes.

| Block | Class | Measured worst ns | Estimated budget ns | Start | End | Measured area um² |
| --- | --- | ---: | ---: | --- | --- | ---: |
| control | CC | 13.395742 | 50.00 | _2031_/Q | _1833_/D | 46165.0560 |
| control | CC_reset | 10.447189 | 12.50 | _1976_/Q | _1924_/D | 46165.0560 |
| control | CF | 11.734216 | 12.50 | _1972_/Q | _1842_/D | 46165.0560 |
| control | FC | 8.128351 | 12.50 | _1832_/Q | _1967_/D | 46165.0560 |
| control | FF | 8.865483 | 12.50 | _1870_/Q | _1811_/D | 46165.0560 |
| control | IR | 10.367253 | 12.50 | busReset | _2016_/D | 46165.0560 |
| control | RO | 4.170210 | 12.50 | _2052_/Q | configured | 46165.0560 |
| control | IO | — | 12.50 | — | — | 46165.0560 |
| control | RG | — | 12.50 | — | — | 46165.0560 |
| control | IG | — | 12.50 | — | — | 46165.0560 |
| in | RR | 9.347021 | 12.50 | _1346_/Q | _1337_/D | 39875.8080 |
| in | IR | 5.141446 | 12.50 | reset_n | _1203_/D | 39875.8080 |
| in | RO | 4.111012 | 12.50 | _1356_/Q | appReady | 39875.8080 |
| in | IO | — | 12.50 | — | — | 39875.8080 |
| in | RG | — | 12.50 | — | — | 39875.8080 |
| in | IG | — | 12.50 | — | — | 39875.8080 |
| out | RR | 9.012933 | 12.50 | _1267_/Q | _1243_/D | 38339.1680 |
| out | IR | 5.085909 | 12.50 | reset_n | _1114_/D | 38339.1680 |
| out | RO | 4.282614 | 12.50 | _1212_/Q | nak | 38339.1680 |
| out | IO | — | 12.50 | — | — | 38339.1680 |
| out | RG | — | 12.50 | — | — | 38339.1680 |
| out | IG | — | 12.50 | — | — | 38339.1680 |
| resume | RR | 8.028501 | 12.50 | _202_/Q | _207_/D | 4783.3408 |
| resume | IR | 5.062730 | 12.50 | attached | _190_/D | 4783.3408 |
| resume | RO | 4.080467 | 12.50 | _205_/Q | suspended | 4783.3408 |
| resume | IO | — | 12.50 | — | — | 4783.3408 |
| resume | RG | — | 12.50 | — | — | 4783.3408 |
| resume | IG | — | 12.50 | — | — | 4783.3408 |
| engine | CC | 18.291136 | 50.00 | _5982_/Q | _5987_/D | 160743.5200 |
| engine | CC_reset | 12.094826 | 12.50 | _6040_/Q | _6318_/D | 160743.5200 |
| engine | CF | 15.562494 | 12.50 | _5982_/Q | _6306_/D | 160743.5200 |
| engine | FC | 13.729841 | 12.50 | usb_enable_replica_0/Q | _5852_/D | 160743.5200 |
| engine | FF | 12.067788 | 12.50 | _6120_/Q | _5455_/D | 160743.5200 |
| engine | IR | 4.680038 | 12.50 | rxReady | _5385_/D | 160743.5200 |
| engine | RO | 7.577746 | 12.50 | _6336_/Q | txEnable | 160743.5200 |
| engine | IO | 3.987964 | 12.50 | reset_n | pullup_0 | 160743.5200 |
| engine | RG | — | 12.50 | — | — | 160743.5200 |
| engine | IG | — | 12.50 | — | — | 160743.5200 |
| registers | RR | 11.202718 | 24.96 | _453_/Q | _454_/D | 8365.9072 |
| registers | IR | 9.328797 | 24.96 | bus_bits_addr[9] | _454_/D | 8365.9072 |
| registers | RO | 4.043431 | 24.96 | _453_/Q | bus_gnt | 8365.9072 |
| registers | IO | — | 24.96 | — | — | 8365.9072 |
| registers | RG | — | 24.96 | — | — | 8365.9072 |
| registers | IG | — | 24.96 | — | — | 8365.9072 |
| usb | appClock.CC | — | 99.84 | — | — | 198496.5696 |
| usb | appClock.CC_reset | — | 24.96 | — | — | 198496.5696 |
| usb | appClock.CF | — | 24.96 | — | — | 198496.5696 |
| usb | appClock.FC | — | 24.96 | — | — | 198496.5696 |
| usb | appClock.FF | 10.028626 | 24.96 | _7750_/Q | _7750_/D | 198496.5696 |
| usb | appClock.IR | 8.064628 | 24.96 | bus_bits_origin[1] | _6421_/D | 198496.5696 |
| usb | appClock.RO | 3.964705 | 24.96 | _7765_/Q | bus_gnt | 198496.5696 |
| usb | appClock.IO | 4.400927 | 24.96 | vbus | pullupEnable | 198496.5696 |
| usb | appClock.RG | — | 24.96 | — | — | 198496.5696 |
| usb | appClock.IG | — | 24.96 | — | — | 198496.5696 |
| usb | usbClock.CC | 20.704672 | 50.00 | _7113_/Q | _6507_/D | 198496.5696 |
| usb | usbClock.CC_reset | 11.327496 | 12.50 | _7385_/Q | _7279_/D | 198496.5696 |
| usb | usbClock.CF | 13.100976 | 12.50 | _7126_/Q | _7503_/D | 198496.5696 |
| usb | usbClock.FC | 11.849917 | 12.50 | _7276_/Q | _7244_/D | 198496.5696 |
| usb | usbClock.FF | 11.898813 | 12.50 | _6472_/Q | _6640_/D | 198496.5696 |
| usb | usbClock.IR | 6.658974 | 12.50 | vbus | _6642_/D | 198496.5696 |
| usb | usbClock.RO | 9.581448 | 12.50 | _7771_/Q | pullupEnable | 198496.5696 |
| usb | usbClock.IO | 4.400927 | 12.50 | vbus | pullupEnable | 198496.5696 |
| usb | usbClock.RG | — | 12.50 | — | — | 198496.5696 |
| usb | usbClock.IG | — | 12.50 | — | — | 198496.5696 |
| usb | aonClock.CC | — | 99.84 | — | — | 198496.5696 |
| usb | aonClock.CC_reset | — | 24.96 | — | — | 198496.5696 |
| usb | aonClock.CF | — | 24.96 | — | — | 198496.5696 |
| usb | aonClock.FC | — | 24.96 | — | — | 198496.5696 |
| usb | aonClock.FF | 2.488224 | 24.96 | _7305_/Q | _7309_/D | 198496.5696 |
| usb | aonClock.IR | — | 24.96 | — | — | 198496.5696 |
| usb | aonClock.RO | 3.750224 | 24.96 | _7309_/Q | usbClockRequest | 198496.5696 |
| usb | aonClock.IO | 4.400927 | 24.96 | vbus | pullupEnable | 198496.5696 |
| usb | aonClock.RG | — | 24.96 | — | — | 198496.5696 |
| usb | aonClock.IG | — | 24.96 | — | — | 198496.5696 |
| sie | CC | 26.335587 | 50.00 | _3167_/Q | _3237_/D | 66591.3920 |
| sie | CC_reset | — | 12.50 | — | — | 66591.3920 |
| sie | CF | 8.284876 | 12.50 | _3199_/Q | _3306_/D | 66591.3920 |
| sie | FC | 10.208137 | 12.50 | usb_enable_replica_0/Q | _3133_/D | 66591.3920 |
| sie | FF | 14.152512 | 12.50 | _3112_/Q | _3189_/D | 66591.3920 |
| sie | IR | 17.250689 | 12.50 | io_in_int_endps_i[6] | _3237_/D | 66591.3920 |
| sie | RO | 22.479979 | 12.50 | _3167_/Q | io_in_ready_o | 66591.3920 |
| sie | IO | 13.395082 | 12.50 | io_in_int_endps_i[6] | io_in_ready_o | 66591.3920 |
| sie | RG | — | 12.50 | — | — | 66591.3920 |
| sie | IG | — | 12.50 | — | — | 66591.3920 |

Remaining over-budget paths:

- engine CF: measured 15.562494 ns, budget 12.50 ns, `_5982_/Q` (_sie_endp_o[2]) → `_6306_/D` (in.consume[0]).
- engine FC: measured 13.729841 ns, budget 12.50 ns, `usb_enable_replica_0/Q` (usb_enable_replica_0_q[0]) → `_5852_/D` (control.header_1[6]).
- usb usbClock.CF: measured 13.100976 ns, budget 12.50 ns, `_7126_/Q` (engine._sie_endp_o[1]) → `_7503_/D` (engine.in.consume[0]).
- sie FF: measured 14.152512 ns, budget 12.50 ns, `_3112_/Q` (sie.u_phy_rx.nrzi_q[3]) → `_3189_/D` (sie.u_phy_rx.shift_register_q[7]).
- sie IR: measured 17.250689 ns, budget 12.50 ns, `io_in_int_endps_i[6]` (io_in_int_endps_i[6]) → `_3237_/D` (sie.in_byte_q[1]).
- sie RO: measured 22.479979 ns, budget 12.50 ns, `_3167_/Q` (io_endp_o[1]) → `io_in_ready_o` (io_in_ready_o).
- sie IO: measured 13.395082 ns, budget 12.50 ns, `io_in_int_endps_i[6]` (io_in_int_endps_i[6]) → `io_in_ready_o` (io_in_ready_o).

| Block | Check | Start | End | Measured slack ns |
| --- | --- | --- | --- | ---: |
| engine | hold/min_fall | dnRx | _6087_/D | -0.102503 |
| engine | hold/min_fall | dpRx | _6317_/D | -0.102503 |
| usb | hold/min_fall | dpRx | _6515_/D | -0.102503 |
| usb | hold/min_fall | dnRx | _6619_/D | -0.102503 |
| usb | hold/min_fall | dpRx | _6620_/D | -0.102503 |
| usb | hold/min_fall | dnRx | _7711_/D | -0.102503 |
| usb | reset/min_rise | aonReset_n | _7697_/RN | -0.975158 |
| usb | reset/min_rise | aonReset_n | _7701_/RN | -0.975158 |
| sie | hold/min_fall | io_dp_rx_i | _3313_/D | -0.102503 |
| sie | hold/min_fall | io_dn_rx_i | _3340_/D | -0.102503 |
| sie | reset/min_rise | reset_n | _3307_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | _3308_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | _3309_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | _3311_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | _3312_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | _3313_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | _3340_/RN | -0.223424 |
| sie | reset/min_rise | reset_n | usb_enable_replica_0/RN | -0.223424 |

No maximum slew/capacitance violation is reported. Hold/reset rows retain the existing zero-delay boundary screen; the pad/board contract remains open. Negative hold is a physical-flow item, not an RTL fix. No unrelated timing restructuring or pipeline removal follows these failures. Standalone SIE fixture, complete multicycle qualification, retained pipeline sampling proofs and original packet proofs remain open. Full tier not run; no acceptance or merge.


## T19 D58/D59 pre-enable capture — 2026-11-19

Measured with `python tools/env/run.py run -- python3 scratch/t19_d58_measure.py engine`
and the same command with `usb`, base099c27f plus exact receipt source/flow hashes,
receipts `build/t19/d59-timing-01/{engine,usb}/result.json`. GF1807-track SS/125C/3.0V,
mapped pre-layout, ideal clocks. D59 approved15ns warning ceiling for eligible USB
single-cycle classes; estimated CP37.5ns/CC50ns and strict FP12.5ns stay unchanged.
Post-placement real-wire recheck remains mandatory. The full per-class/start/end
and area table is in the T19 report.

| Block | Incoming launch class | Before ns | Before target/limit ns | Before start | Before end | After ns | After budget ns | After start | After end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| engine | CP | 15.562494 | 12.500000 (D54 original target) | _5982_/Q (_sie_endp_o[2]) | _6306_/D (in.consume) | 14.305089 | 37.500000 | _6069_/Q (_sie_endp_o[1]) | _6431_/D (in.consume) |
| engine | FP | 13.824021 | 12.500000 (D54 original target) | _6279_/Q (configured) | _6306_/D (in.consume) | 12.361530 | 12.500000 | _6387_/Q (configured) | _6431_/D (in.consume) |
| usb | CP | 13.100976 | 12.500000 (D54 original target) | _7126_/Q (engine._sie_endp_o[1]) | _7503_/D (engine.in.consume) | 12.811203 | 37.500000 | _7057_/Q (engine._sie_endp_o[1]) | _7683_/D (engine.in.consume) |
| usb | FP | 7.958107 | 12.500000 (D54 original target) | _6592_/Q (engine._control_inValid) | _7503_/D (engine.in.consume) | 9.182744 | 12.500000 | _7583_/Q (_engine_configured) | _7683_/D (engine.in.consume) |

All engine/wrapper setup classes pass or warn. Engine FF14.726458ns
(`_6206_/Q`, rx_state_q[1] → `_6197_/D`, shift_register_q[7]) warns under D59;
wrapper FF13.485458ns warns. P endpoints receive setup3/hold2 only from certified
R/B/H launches. Actual CP setup capture62.5ns/hold0 and FP20.833334ns/hold0 are
recorded and checked. Every S launch remains in strict FP.

Both overall timing statuses remain failed: engine2/wrapper6 hold/reset negatives
persist (pad hold−0.102503ns; wrapper AON removal−0.975158ns), together with prior
qualification obligations. Boundary/physical work is not hidden by the setup
warning policy. No additional RTL restructuring, clock gating or SRAM swap.

The final frozen fast02 USB command (`python3 hw/ip/usb/check.py --output build/t19/d59-frozen-fast-02/fast/usb`, invoked by the pinned fast tier) reproduces every engine/wrapper class and area above exactly. Source inventories match; the complete fresh block/class and hold/reset identities are in the T19 report. The standalone SIE fixture preserves the exact full cadence emission and has a passing source/mapped certificate, but remains numeric-failed diagnostic-only under the approved step 1b option: IR 16.586666 ns and RO 22.734825 ns. No binding/tool error remains. Overall USB/fast acceptance still fails original packet and physical/prior qualification obligations; full tier and post-placement recheck unrun.

## T19 pad/reset boundary contract, 2026-11-19

The approved boundary follow-up changes only timing collateral, not RTL.
Measured by `python tools/env/run.py run -- python3 scratch/t19_boundary_measure.py engine`
and the same command with `usb`, at base `33cf251` plus exact flow/source hashes
in `build/t19/boundary-timing-01/{engine,usb}/result.json`. Pinned Yosys
0.71+34/e419c4eef, OpenSTA 3.2.0, GF180 7t5v0 SS/125 C/3.0 V; mapped pre-layout,
no routed wires. Both overall results remain failed; setup warnings only,
no over-limit setup class or electrical violation. All output setup/hold
polarities pass under the estimated contract.

| Boundary diagnostic | Engine measured slack (ns) | Wrapper measured slack (ns) |
| --- | --- | --- |
| Worst pad hold | -0.102503, dpRx/dnRx to sampler D; 2 paths | -0.102503, dpRx/dnRx to sampler D; 4 paths |
| Worst removal | +0.559058, vbus to _6355_/RN | +0.961138, vbus to _6357_/RN |
| Former AON removal | n/a | raw -0.975158 to conditional +1.143400, aonReset_n to _7632_/RN and _7699_/RN |
| Worst recovery | +10.616619, _6372_/Q to _5690_/RN | +11.605783, _6357_/Q to _6438_/SETN |
| Worst contracted output setup/hold | +3.530727, reset_n to pullup_0 | +3.514510, vbus to txEnable |
| Mapped area (um2) | 160227.6480, unchanged | 197379.2128, unchanged |

Estimated digital pad/board reserve is 0..1+0..1=0..2 ns; asynchronous input
minimum remains zero. Reset rising release uses estimated upstream dffrnq_1
CLK-to-Q 2.420..3.882109 ns from the actual pinned library over assumed clock
slew 0.02..0.5 ns and load 0.001..0.05 pF; estimated rise slew is 2.4 ns.
Falling assertion remains asynchronous with zero-phase diagnostics. No delay
is added to internal release flops. Source-cell assumptions require eventual
integration validation and are not fast-corner hold bounds.

Identical-netlist zero-delay reference reproduces the old engine2/wrapper6
negatives. Real output-delay faults and zero-CQ reset-release fault are
rejected. Four wrapper peer-domain reset sink rows remain RDC-unqualified.
Negative pad hold remains a physical-flow item and is not waived. Actual
pads/board, reset implementation, fast corner, CTS and routed timing remain open.
The core's historical identical -0.975158 ns is the same zero-arrival minus
library-removal artifact (`build/s1/timing/sta.log`, receipt commit20881a4,
`sta -no_init -exit /work/build/s1/timing/timing.tcl`); core timing was inspected,
not rerun. See T19 report for full provenance, identities and commands.

Independent boundary review found no blocking defect. `boundary.sdc` records
the boundary setup before later multicycle commands; the driver/protocol TCL
and edge audits retain that later context. Existing IO domain labels are
repeated query buckets, not ownership claims. Frozen USB/fast rerun follows;
full tier and physical timing remain unrun.

Frozen follow-up: `python tools/env/run.py run -- python3 tools/ci.py --tier fast --output build/t19/boundary-frozen-fast-01` invokes fresh `python3 hw/ip/usb/check.py --output build/t19/boundary-frozen-fast-01/fast/usb`. Measured elapsed times are 2923.629 s (fast) and 1321.439 s (USB). `python scratch/t19_boundary_final_audit.py` confirms exact source inventories and reproduction of every engine/wrapper class, area and hold/reset row above. All 19 simulations, 16 focused formal cases, equivalence and byte CDC pass; output/reset boundary faults are rejected. USB/fast remain failed for unchanged positive packet proof, physical hold and prior sampling/exception qualification obligations. Only reporting files change after the audit. Full tier/post-placement unrun; no merge.


## T19 routed standalone physical diagnostic, 2026-11-20

**Measured** on `d8d51aca578b8353a582d05129c01624c915dc6a` plus the sealed
physical tooling, using unchanged production/mapped sources. Exact commands,
all class rows and source/artifact bindings are in
[the physical validation report](../spec/usb-physical-validation.md).
`tools/physical/` pins the companion OpenROAD runtime and existing GF180 views.
The wrapper completed place/CTS/detail-route, three OpenRCX extractions and
fifteen PVT/RC STA cases. No CI, USB aggregate or proof solver ran.

| Reported class | Measured worst observed delay (ns) | Approved failure ceiling (ns) | Start → end |
| --- | ---: | ---: | --- |
| USB FP | 13.691668 | 12.5 | `_7583_/Q` → `_7709_/D` |
| USB FC | 16.003422 | 15 | `_6520_/Q` → `_7435_/D` |
| USB FF | 15.516943 | 15 | `_6398_/Q` → `_7362_/D` |

All three fail; no further restructuring. Values remove actual launch-clock
insertion but retain CLK-to-Q and routed data delay. Endpoint selection makes
these worst observed delays, not exhaustive data-order maxima. Measured raw
period setup minimum is +3.296796 ns; it does not override the project budgets.
Worst measured boundary hold is −3.828268 ns (`dnRx` → `_7547_/D`), removal
−2.508364 ns (`vbus` → `_6357_/RN`); no negative internal register-origin row
was reported. Directed local reset-chain interstage setup/hold and downstream
recovery/removal are positive across all cases. Raw-reset topology qualifies
only the destination release structure; upstream pulse/phase, analog
metastability and full RDC remain unqualified.

Measured routed Liberty cell-area sum is 217149.1840 µm². The floorplan and
pad/reset envelope are assumed/estimated standalone inputs. Missing PDN/pads,
unsupported LEF58 enclosure rules, foundry DRC/LVS and actual boundary
implementation prevent physical signoff. Effective-SDC, graph and annotation
audits and ten focused fault tests pass after independent review. Status stays
failed-validation; neither T19 nor merge is accepted.

## T20 I0 reset distribution and core mapping, 2026-11-20

**Measured**, `72bcfac` plus receipt-bound working tree. Commands and complete
receipts are in [T20](../plan/tasks/reports/T20.md), especially
`hw/top/reference/timing/logic_timing.py --mapped-dir build/t20/core-map-balanced-reset --output build/t20/physical-final-timing`
through the pinned environment. GF180 7t5v0 SS125C/3.0V, ideal clocks and no
wire delay; existing assumed 0.5 ns input slew, 0.05 pF output loads and zero
IO delays. This is observation-enabled I0 logic with five synchronous memory
boundaries exposed, excluding macro timing/area and physical signoff.

| Path class | Measured worst ns | Start -> end | Estimated 8 / 9 MHz budget ns |
| --- | ---: | --- | ---: |
| RR, entire instrumented top | 70.011482 | `_93597_/Q` -> `_91493_/D` (instruction decode bit 31 -> RVFI data bit 30) | 75 / 66.666667 |
| Integer RF diagnostic subset | 69.443718 | `_93597_/Q` -> `_90069_/D` (x20[31]) | 75 / 66.666667 |
| IR | 19.960014 | `memcut_3_RW0_rdata[16]` -> `_91851_/D` | 75 / 66.666667 |
| RO | 57.486359 | `_93585_/Q` -> `memcut_4_RW0_wmode` | 75 / 66.666667 |
| RG | 5.975131 | `_90366_/Q` -> `core.core_clock_gate_i.cell_0/E` | 75 / 66.666667 |

Budget arithmetic: `0.60 x 1000 / MHz`. Full-top screening passes at 8 MHz
and fails at 9 MHz; no RVFI path is excluded from acceptance. The integer RF
subset covers 1,984 rows, all 31 x 32 bits and both polarities; it also fails
9 MHz. The inherited standalone core's trace-off boundary is not substituted.

591 verified reset buffers reduce direct release-flop loads from 2,582 / 280
to eight each. Measured electrical violations fall from 2,866 to zero. All
2,869 RN/SETN endpoints receive applicable release checks. Minimum measured
hold slack +0.724836 ns, removal +0.490473 ns, recovery +116.902161 / +103.013268 ns
at 8 / 9 MHz. Dynamic ICG setup/hold checks pass; TE is literal zero.

Mapped logic area is measured 1,103,439.232 um2 including reset buffers and
excluding memories. XOR balancing is a combinational mapping change only;
state/clock/reset boundaries are preserved. Stronger buffer/hot-gate sizing
trials worsened timing and are rejected; a tighter 60000 ps mapping target gave
the same netlist and was not retimed. Independent review verified the evidence.
No core RTL changes or CI runs occurred in that mapping study. D66 subsequently
authorizes the focused MAC carry-network experiment below; T20 remains incomplete.

### T20 D66 MAC carry experiment (rejected candidate)

Measured on `72bcfac` plus the D65 working tree and D66 candidate, using fresh
`EmitSocTiming`, `scratch/t20_timing_prepare.py --output
build/t20/mac-prefix/prep`, the unchanged balanced ABC recipe in
`build/t20/mac-prefix/map/synth.ys`, `buffer_resets.py --mapped
build/t20/mac-prefix/map/mapped.json --output build/t20/mac-prefix/reset`, and
`hw/top/reference/timing/logic_timing.py --mapped-dir
build/t20/mac-prefix/reset --output build/t20/mac-prefix/timing`, all through
the pinned `python tools/env/run.py run --` wrapper. Same GF180 7t5v0
SS/125 C/3.0 V, ideal clocks, no wires, synchronous memory-interface cuts,
0.5 ns input transition, 0.05 pF output load and zero IO delays as the baseline.

| Class | Measured worst ns | Start | End | Budget at 8 / 9 MHz, ns |
| --- | ---: | --- | --- | ---: |
| RR | 79.044106 | `_91641_/Q` (instruction decode bit 30) | `_90132_/D` (`rvfi_rd_wdata[31]`) | 75 / 66.666667: fail both |
| IR | 18.657497 | `memcut_3_RW0_rdata[16]` | `_90471_/D` | 75 / 66.666667 |
| RO | 60.655823 | `_91632_/Q` | `memcut_4_RW0_wmode` | 75 / 66.666667 |
| RG | 5.965534 | `_88777_/Q` | `core.core_clock_gate_i.cell_0/E` | 75 / 66.666667, gate checks also pass |

Measured mapped logic area including the same 591 reset buffers is
1,107,004.2368 um2, versus 1,103,439.232 um2 before. Memory area remains excluded.
Electrical violations remain zero; minimum hold +0.747969 ns, removal
+0.490473 ns, recovery +116.902161 / +103.013268 ns at 8 / 9 MHz.
These are pre-layout screening results, not physical signoff.

The explicit grouped carry network prevents the original fused multiply-add
compression: Yosys now maps the signed product separately from the accumulator.
Independent review confirmed this in both synthesis logs and the failing path.
The candidate worsens RR from 70.011482 to 79.044106 ns and is rejected. No
timing limit, clock choice or observation-state exclusion changes; no CI.

### T20 D67 isolated MAC mapping and unchanged control

Measured on `72bcfac` plus the source-hashed D65/D67 tree with fresh emission,
`hw/top/reference/timing/map_fused_mac.py`, the unchanged balanced ABC recipe,
`buffer_resets.py` and `logic_timing.py`; exact commands and receipts are in
the T20 report and `build/t20/fused-mac/{control,fa,42}`. Same GF180 SS/125 C/3 V,
ideal clocks, no wires, memory-interface cuts, IO loads/delays and RVFI boundary
as above. No production RTL or cycle change; no CI.

| Variant | Class | Measured worst ns | Start | End |
| --- | --- | ---: | --- | --- |
| Original MAC control | RR | 66.563103 | `_92911_/Q` | `_90260_/D` (`rvfi_rd_wdata[31]`) |
| Original MAC control | IR | 20.810877 | `memcut_3_RW0_rdata[24]` | `_92893_/D` |
| Original MAC control | RO | 55.245838 | `_92902_/Q` | `memcut_3_RW0_wmode` |
| Original MAC control | RG | 5.571865 | `_88190_/Q` | `core.core_clock_gate_i.cell_0/E` |
| FA + prefix | RR | 66.426033 | `_90394_/Q` | `_89424_/D` (integer RF) |
| FA + prefix | IR | 19.094036 | `memcut_3_RW0_rdata[25]` | `_90782_/D` |
| FA + prefix | RO | 56.231403 | `_90795_/Q` | `memcut_3_RW0_wmode` |
| FA + prefix | RG | 5.905660 | `_86124_/Q` | `core.core_clock_gate_i.cell_0/E` |
| 4:2 + prefix | RR | 69.822578 | `_90327_/Q` | `_87726_/D` |
| 4:2 + prefix | IR | 20.093237 | `memcut_3_RW0_rdata[25]` | `_90314_/D` |
| 4:2 + prefix | RO | 53.731461 | `_90329_/Q` | `memcut_1_RW0_wmode` |
| 4:2 + prefix | RG | 5.583239 | `_85656_/Q` | `core.core_clock_gate_i.cell_0/E` |

All classes retain estimated budgets `0.60 * 1000 / MHz` = 75 / 66.666667 ns
at 8 / 9 MHz. Original control and FA pass both; 4:2 fails 9 MHz RR. Measured
area including 591 reset buffers is respectively 1,112,314.4256,
1,113,078.3552 and 1,109,047.9680 um2, excluding memories. All three have zero
electrical and hold/reset violations, with all 2,869 applicable reset endpoints
covered. Control minimum measured hold +0.814248 ns, removal +0.490473 ns,
recovery +116.902161 / +103.013268 ns, and clock-gate hold +4.729134 ns.

Retain the original-MAC control flow: exact graph restoration and reversible
private renaming preserve its arithmetic. The isolated FA transformation gains
only estimated 0.137070 ns over that control; it is not accepted without its
arithmetic proof. The control's improvement from historical 70.011482 ns is
primarily a synthesis-order effect, not evidence of a better compressor.
Independent review verifies the control graph, scripts, hashes and measured
timing. Its estimated +0.103564 ns margin at the 9 MHz screening budget is not
routed or macro-inclusive timing closure; Q15/Q16 remain open.

## T21 functional I/O block screens — 2026-11-21

Measured on main HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus the
uncommitted T21 source-bound emissions. Commands inside the pinned environment:
`python3 dv/soc/check_io_timing.py` and
`python3 hw/ip/gpio/timing/buffer_reset.py`. Slow GF180 125°C/3.0V, mapped
pre-layout cells, no physical wire/pad timing. Existing main-9MHz trial budget
is estimated0.60×1000/9=66.666667ns, conservative for main8 and AON profiles.

| Block | Class | Measured ns | Budget ns | Start → end | Mapped area µm² |
| --- | --- | --- | --- | --- | --- |
| main8 | RR | 51.976086 | 66.666667 | `_5681_/Q` → `_5757_/D` | 98246.1760 |
| main8 | IR | 9.365267 | 66.666667 | `bus_bits_addr[19]` → `_5385_/D` | 98246.1760 |
| main8 | RO | 4.395018 | 66.666667 | `_5720_/Q` → `timeNow[26]` | 98246.1760 |
| main9 | RR | 58.302357 | 66.666667 | `_5624_/Q` → `_5771_/D` | 98226.4192 |
| main9 | IR | 9.365267 | 66.666667 | `bus_bits_addr[19]` → `_5405_/D` | 98226.4192 |
| main9 | RO | 4.346962 | 66.666667 | `_5746_/Q` → `timeNow[31]` | 98226.4192 |
| aon | RR | 25.904716 | 66.666667 | `_3240_/Q` → `_3242_/D` | 54730.7264 |
| aon | IR | 9.365267 | 66.666667 | `bus_bits_addr[19]` → `_3141_/D` | 54730.7264 |
| aon | RO | 4.073875 | 66.666667 | `_3307_/Q` → `bus_gnt` | 54730.7264 |
| adc | RR | 41.680973 | 66.666667 | `_2569_/Q` → `_2595_/D` | 50974.7392 |
| adc | IR | 9.365267 | 66.666667 | `bus_bits_addr[19]` → `_2838_/D` | 50974.7392 |
| adc | RO | 4.071314 | 66.666667 | `_2870_/Q` → `bus_gnt` | 50974.7392 |
| GPIO buffered | IR | 7.124507 | 66.666667 | `bus_bits_addr[19]` → `_784_/D` | 17017.1904 |
| GPIO buffered | RO | 4.094893 | 66.666667 | `_736_/Q` → `clockHold` | 17017.1904 |
| GPIO buffered | RR | 10.907675 | 66.666667 | `_754_/Q` → `_738_/D` | 17017.1904 |

Raw GPIO screen failed65 electrical violations on reset-release fanout; its
receipt remains failed. Verified mapped-only insertion of eight non-inverting
buffers clears all electrical violations, preserves every original pin/clock
and rejects a buffer-cycle fault. Corrected GPIO receipt:
`build/t21/timing-gpio-buffered/result.json`; other block receipts:
`build/t21/timing-first/<block>/timing/result.json`. Independent review verified
original and exported connectivity. Production RTL hashes still match; later
timer formal/test edits do not change the measured production emission.

GPIO fixture ties clocks for a conservative all-cone logic screen, not CDC/RDC
signoff. No gate/IO paths exist in these fixtures. Corrected GPIO ideal-boundary
measured hold−0.102503ns and reset-removal−0.975158ns remain unqualified
physical-flow items. No RTL delay padding or acceptance-limit change. Full
SoC placement/pad/clock qualification and CI are not claimed; see T21 report.

## T22 generic PWM block screen — 2026-11-21

Measured command: `python tools/env/run.py run -- python3 hw/ip/pwm/check_timing.py --output build/t22/timing-first`.
Dirty main based on `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47`; receipt
`build/t22/timing-first/result.json` binds production sources, emitted modules
and flow inputs. GF180 `gf180mcu_fd_sc_mcu7t5v0`, SS/125 C/3.0 V; existing
main-9MHz operating-point trial. Budget estimated 0.60 x 1000/9 = 66.666667 ns,
conservative for the unchanged 8/9 MHz functional profiles. Mapped, ideal clocks,
zero boundary delays and no placed-wire parasitics; this is not chip signoff.

| Class | Measured worst ns | Budget ns | Start | End | Measured area um2 |
| --- | --- | --- | --- | --- | --- |
| RR | 34.134335 | 66.666667 | `_16288_/Q` | `_16771_/D` | 271822.8352 |
| IR | 9.952121 | 66.666667 | `bus_bits_addr[19]` | `_17400_/D` | same block |
| RO | 4.211749 | 66.666667 | `_17510_/Q` | `pinsEnable[4]` | same block |

No IO or clock-gate paths exist in this block. Measured capacitance/slew
violations: zero. Setup/electrical screen passes without RTL timing exceptions
or added buffer repair. Hold/reset-removal were not measured by this screen;
RDC, physical pads and routed timing remain open. No CI tier ran.

## T23 DMA and native-memory control screen — 2026-11-21

Measured commands (pinned environment, uncommitted `main` on `72bcfac`):

```
python tools/env/run.py run -- python3 hw/ip/dma/check_timing.py --output build/t23/timing-first
python tools/env/run.py run -- python3 hw/ip/dma/check_memory_timing.py --output build/t23/memory-timing-first
```

Both receipts bind source, generated netlist and flow hashes. GF180 7t5v0
SS/125C/3.0V; existing main-9MHz screen, estimated budget
`0.60 * 1000 / 9 = 66.666667 ns`. Mapped pre-layout with ideal clocks, assumed
zero boundary delays, 0.5ns input slew and 0.05pF output load.

| Block | Class | Measured worst ns | Start | End | Measured area um² |
| --- | --- | ---: | --- | --- | ---: |
| DMA | RR | 43.368591 | `_10546_/Q` | `_11172_/D` | 159020.288 |
| DMA | IR | 27.404062 | `requests[14]` | `_11057_/D` | same block |
| DMA | RO | 4.603601 | `_11049_/Q` | `memory_bits_addr[10]` | same block |
| Memory control | RR | 20.955997 | `_1503_/Q` | `_1405_/D` | 22920.0832 |
| Memory control | IR | 17.464502 | `instruction_req` | `_1405_/D` | same block |
| Memory control | RO | 21.502474 | `_1503_/Q` | `memcut_1_RW0_wmode` | same block |
| Memory control | IO | 18.010981 | `instruction_req` | `memcut_1_RW0_wmode` | same block |

All classes pass the unchanged budget; measured electrical violations zero.
The memory projection audits synchronous read boundaries and exposes five
memory interfaces; reinstating removed cells restores the exact original graph.
Macro timing/area, upstream core paths, physical hold/reset-removal and placed
wire delays are excluded. No complete-SoC timing claim; no CI tier ran.

## T24 limited GPIO output pin mux — 2026-11-21

Measured command on `72bcfac` plus receipt-bound local sources:

```sh
python tools/env/run.py run -- python3 hw/ip/pinmux/check_timing.py --output build/t24/timing-frozen
```

Receipt PASS, 45 source and 31 artifact hashes independently verified. GF180
7t5v0 SS/125C/3.0V, existing main-9MHz screen. Estimated budget
`0.60 * 1000 / 9 = 66.666667 ns`, unchanged for every class. Assumed ideal
clocks, zero input/output delay, 0.5ns input transition, 0.05pF output load.

| Class | Measured worst ns | Start | End |
| --- | ---: | --- | --- |
| RR | 9.887082 | `_357_/Q` | `_366_/D` |
| IR | 7.962392 | `bus_bits_origin[0]` | `_351_/D` |
| RO | 3.976222 | `_365_/Q` | `bus_gnt` |

Measured standard-cell area6475.84 um²; electrical violations0. No IO or
clock-gate paths. Mapped pre-layout block screening only: pad loads/delays,
physical wiring, hold/reset-removal, actual pad fit and full-SoC qualification
remain separate. No CI tier ran.

## T25 lite-core mapped screen, 2026-11-21

Measured command (pinned environment):
`python hw/ip/lite_core/check_timing.py --output build/t25/timing-frozen`.
Commit `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus receipt source hashes;
current-source **PASS**, mapped pre-layout only. Independent contract review
retained the conservative existing main-9MHz screen for this externally clocked
AON block; no domain-frequency decision or budget relaxation. Estimated logic
budget `0.60 × 1000 / 9 = 66.666667 ns`; ideal clock, no wire parasitics.

| Class | Measured ns | Start → end |
| --- | ---: | --- |
| RR | 63.398540 | `_21186_/Q` → `_20414_/D` |
| IR | 11.444583 | `irq` → `_21321_/D` |
| RO | 6.308051 | `_21202_/Q` → `rvfi_ixl[0]` |
| IO, clock gates | No path | Hart has no internal clock gate |

Measured standalone area **302742.2272 µm²**, electrical violations **0**.
The standalone hart includes exposed trace/RVFI state and output loads; area
is not the integrated top with unused instrumentation trimmed. Library is
the pinned GF180 `ss_125C_3v00` corner. Physical pad/hold/removal/routed timing
and full SoC qualification remain separate. No CI tier ran. See the
[T25 report](../plan/tasks/reports/T25.md) for functional/proof scope.

## T26 watchdog reset distribution (2026-11-21)

Measured on main HEAD `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus receipt-bound
local sources. Commands:

```
python tools/env/run.py run -- python dv/soc/check_watchdog.py --output build/t26/frozen01
python tools/env/run.py run -- python dv/soc/check_watchdog_review.py --output build/t26/review02
```

The first run's Watchdog/Pwm screens failed electrical limits on internal
combined reset nets (134/1227 measured violations); those failures remain in
frozen01. Pinmux passed there. The reviewed, default-off reset-fanout hook
selects unique internal RN/SETN drivers, rejects clock/ambiguous nets, excludes
primary inputs and reuses the existing all-pin-verified noninverting buffer
trees. Fresh Watchdog/Pwm measurements include all added buffer delays and
area; no RTL, limit, load, slew or library change. Final production bytes are
identical to the functional snapshot.

GF180 7t5v0 slow corner (125°C, 3.0V); Yosys 0.71+34, OpenSTA 3.2.0; mapped pre-layout,
ideal clocks, no real interconnect. Budget estimated 0.60×1000/9=66.666667ns
for every present class, using the unchanged conservative 9MHz screen without
selecting AON frequency. Figures below are measured by the commands above.

| Block | Class | Delay ns | Start | End | Area µm² |
| --- | --- | ---: | --- | --- | ---: |
| Watchdog | RR | 42.001823 | _4095_/Q | _3910_/D | 67530.9376 |
| Watchdog | IR | 16.358051 | por_n | _3910_/D | — |
| Watchdog | RO | 6.129250 | _3914_/Q | resetHold | — |
| PWM, watchdog profile | RR | 33.290840 | _16758_/Q | _17593_/D | 288763.1936 |
| PWM, watchdog profile | IR | 9.952121 | bus_bits_addr[19] | _18010_/D | — |
| PWM, watchdog profile | RO | 4.268188 | _18116_/Q | pinsEnable[3] | — |
| Pinmux, watchdog profile | RR | 9.741008 | _393_/Q | _401_/D | 7257.3312 |
| Pinmux, watchdog profile | IR | 7.962392 | bus_bits_origin[2] | _385_/D | — |
| Pinmux, watchdog profile | RO | 4.808930 | _412_/Q | pinsEnable[0] | — |

All final electrical counts are measured 0. Watchdog/PWM add measured 57/520
buffers and 1751.7696/15981.0560µm² versus their raw failed mappings. No IO/RG/IG
paths were reported. Hold/removal/RDC and whole-SoC physical timing are not
qualified by these block screens; four successful complete top emissions
are structural build evidence only. No CI or gate completion claim.

Final selector audit: the opt-in reset selector conservatively rejects any
non-primary clock tree, including an indirect buffer/inverter ancestry.
`python tools/env/run.py run -- python dv/soc/check_watchdog_review.py --output build/t26/guard03 --guard-only`
checks unchanged archived transforms and all earlier evidence, then reruns the
33 focused flow tests. It does not rerun or reinterpret STA. The measured
Watchdog/PWM graphs have only the primary clock, so their actual buffer trees,
netlists, constraints, area and timing remain identical.


## T27 staged raw ADC engine, 2026-11-21

Measured by `python tools/env/run.py run -- python hw/ip/adc/check_raw_timing.py --output build/t27/timing02`
on main72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus receipt-bound local sources.
GF1807t5v0 slow ss_125C_3v00, Yosys0.71+34/OpenSTA3.2.0; asynchronous-reset
standalone engine, manual-start, default half-period5. Ideal boundary and
no placed wires. Existing budget estimated0.60*1000/9=66.666667ns for every
class. This does not select the AON frequency or qualify pads/hold/RDC.

| Variant | Class | Measured ns | Start | End | Measured area um2 |
| --- | --- | ---: | --- | --- | ---: |
| Legacy | RR | 42.517971 | _733_/Q | _789_/D | 11652.1216 |
| Legacy | IR | 6.359634 | io_start | _742_/D | 11652.1216 |
| Legacy | RO | 41.066444 | _733_/Q | io_result_bits_value[30] | 11652.1216 |
| Legacy | IO | 3.940379 | io_start | io_launched | 11652.1216 |
| Raw | RR | 11.264398 | _262_/Q | _251_/D | 4519.9168 |
| Raw | IR | 5.760346 | io_allow | _233_/D | 4519.9168 |
| Raw | RO | 7.349518 | _260_/Q | io_launched | 4519.9168 |
| Raw | IO | 4.071531 | io_allow | io_launched | 4519.9168 |

RG/IG have no paths; measured electrical violations0. Repeated area is not
additive. Estimated engine area difference11652.1216-4519.9168=7132.2048um2;
At that staged checkpoint, production had not switched, so no integrated
saving was claimed. The
inherited combinational launched signal is local to the engine, not exposed
through the registered Adc pad boundary. Timing01's synchronous-reset fixture
is preserved but superseded by timing02. See the T27 report for scope.


## T27 D71 raw production ADC wrapper, 2026-11-21

Measured command: `python tools/env/run.py run -- python hw/ip/adc/check_raw_timing.py --wrapper-only --output build/t27/wrapper01`.
Main72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus receipt-bound local
sources. Same GF1807t5v0 ss_125C_3v00, Yosys0.71+34/OpenSTA3.2.0 and
conservative9MHz screen; budget estimated0.60*1000/9=66.666667ns.
Full production Adc with MMIO, shared MISO synchronizer, registered pads and
sample publication; no scaler instantiated. Mapped pre-layout, ideal clocks,
assumed zero boundary delays; no real wire or physical hold/RDC qualification.

| Class | Measured ns | Start | End | Measured area um2 |
| --- | ---: | --- | --- | ---: |
| RR | 34.922482 | _1822_/Q | _1837_/D | 39676.0448 |
| IR | 9.365267 | bus_bits_addr[19] | _2004_/D | 39676.0448 |
| RO | 4.072706 | _2036_/Q | bus_gnt | 39676.0448 |

IO/RG/IG have no paths. Measured electrical violations0; area repeats per
class, not additive. Relative to historical T21 wrapper area50974.7392um2
(measured by its report command), estimated difference is
50974.7392-39676.0448=11298.6944um2. The old wrapper was not remapped in this
continuation; this is a historical comparison, not a fresh A/B area result.
No whole-chip area/timing or physical signoff is claimed.

## T28 lite-first release block — 2026-11-21

**Measured** by pinned `python hw/ip/boot_control/check_timing.py --output
build/t28/frozen01/timing`, called from the frozen T28 focused runner on
main HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus source-hashed changes.
Receipt PASS; neither CI tier run. Conservative main9MHz operating point:
estimated budget0.60×1000/9=66.666667ns. Assumed SS125°C/3.00V, ideal clocks,
zero I/O delays,0.5ns input slew,0.05pF output load; no routed wire delay.

| Class | Measured ns | Start | End | Measured area µm² |
| --- | --- | --- | --- | --- |
| RR | 11.160238 | _521_/Q | _492_/D | 10793.7984 |
| IR | 6.549746 | bus_req | _439_/D | 10793.7984 |
| RO | 3.976222 | _478_/Q | bus_gnt | 10793.7984 |

IO/RG/IG have no paths. Measured electrical violations0; repeated area is not
additive. This is the standalone controller including adapter/generated MMIO
and internal reset buffers, not an integrated area delta. Hold/removal arrays
are empty in this block screen and do not certify physical reset/RDC/hold.
Four complete top emissions prove elaboration/binding only; routed timing,
clock/reset trees and the whole-chip area budget remain separate work.

## T29 QSPI command controller — 2026-11-21

**Measured** by pinned `python hw/ip/qspi/check_timing.py --output
build/t29/frozen01/timing`, from the T29 frozen focused runner, main
HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus source-hashed local changes.
Receipt PASS. Conservative9MHz profile: estimated budget0.60×1000/9=
66.666667ns. Assumed SS125°C/3.00V, ideal clock, zero I/O delays,0.5ns input
slew and0.05pF output load; no routed interconnect delays.

| Class | Measured ns | Start | End | Measured area µm² |
| --- | --- | --- | --- | --- |
| RR | 18.435669 | _4697_/Q | _4863_/D | 75372.192 |
| IR | 9.502041 | bus_bits_addr[15] | _4846_/D | 75372.192 |
| RO | 6.308051 | _4701_/Q | csEnable[0] | 75372.192 |

IO/RG/IG have no paths. Measured electrical violations0. Area repeats per
class, not additive; it includes engine, shared synchronizers, generated
MMIO/adapter and internal reset buffers. No integrated SoC area delta is
claimed. Empty hold/removal arrays do not qualify physical reset/RDC/hold.
Four complete tops emit; this does not close physical pin timing, flash-part
compatibility, XIP or production boot. Neither CI tier ran.

## T30 native flash controller and local memory control — 2026-11-21

**Measured** by pinned `python hw/ip/qspi_xip/check_timing.py --output
build/t30/frozen02/timing` and `python hw/ip/dma/check_memory_timing.py --xip
--output build/t30/frozen02/memory-timing`, from the frozen focused T30 runner.
Main HEAD72bcfacc0916b6c00d54f5c4518ab16aa46c5a47 plus source-hashed local
changes; both receipts PASS. Estimated budget 0.60 × 1000/9 = 66.666667 ns.
Assumed SS125°C/3.00V, ideal clock, zero I/O delays, 0.5 ns input slew and
0.05 pF output load; no routed wire delays.

| Block | Class | Measured ns | Logic depth | Start | End |
| --- | --- | --- | --- | --- | --- |
| QSPI + native scheduler | RR | 18.405830 | 15 | _7186_/Q | _7154_/D |
| QSPI + native scheduler | IR | 12.391415 | 7 | xip_bits_addr[29] | _6965_/D |
| QSPI + native scheduler | RO | 6.308051 | 0 | _6756_/Q | csEnable[0] |
| Local memory control | RR | 32.613579 | 23 | _2464_/Q | _2614_/D |
| Local memory control | IR | 27.776915 | 21 | data_bits_addr[30] | _2614_/D |
| Local memory control | RO | 31.134016 | 23 | _2464_/Q | memcut_3_RW0_wmode |
| Local memory control | IO | 26.297356 | 21 | data_bits_addr[30] | memcut_3_RW0_wmode |

QSPI IO/RG/IG and memory-control RG/IG have no paths. Measured electrical
violations zero. Measured area is 121987.264 µm² for the combined controller
and 38982.3616 µm² for local-memory control. The memory projection audits five
synchronous boundaries and restores the original graph exactly after
reinstating the cut cells; all production decode/arbitration/drain/response
logic remains. Macro area/delay, upstream core paths and integrated paths are
excluded. No whole-chip area/timing or physical hold/reset qualification follows;
the hold/removal arrays are empty. All complete profiles emit. Neither CI tier ran.

## T41 shared reset distribution — 2026-11-25

Measured on `3f11e32` plus receipt-hashed working sources, pinned SS125 GF180
libraries and existing constraints. Fresh production emission has 278 files;
the `consolidated-timing02`, `03` and `04` copies are byte-identical. Commands
run through `python tools/env/run.py run -- python`:

```text
hw/top/reference/measurements/plan04_map.py --base build/t41/consolidated-timing04 --usb-reference build/t33/pre-fast03/fast/usb/timing/usb --stability-reference build/t41/block-timing02/stability --threshold-control --sram --rom-image build/t36/rom/rom.hex
hw/top/reference/measurements/plan04_screen.py --base build/t41/consolidated-timing04 --usb-reference build/t33/pre-fast03/fast/usb/timing/usb --screen-name ss125b --sram-corner ss_125C_3v00
hw/top/reference/measurements/t35_budget.py --base build/t41/consolidated-timing04
```

Measured maxima are identical in both frozen AON source modes. Prefix `U.` in
the table means `digital.subsystem.usb.`; no path exceptions were broadened.

| Class | Measured ns | Budget ns | Start → end |
| --- | ---: | ---: | --- |
| AON FF | 2.488224 | 18750 | U._7236_/Q → U._7237_/D |
| AON RR | 67.492126 | 18750 | _228618_/Q → _228772_/D |
| Main FF | 10.045056 | 75 | U._7477_/Q → U._7310_/D |
| Main RR | 69.784782 | 75 | _221603_/Q → _220714_/D |
| TCK RR | 17.620693 | 6000 | _236522_/Q → _217676_/D |
| USB CC | 20.921200 | 50 | U._7042_/Q → U._7596_/D |
| USB CC reset | 12.001124 | 12.5 | U._7280_/Q → U._6543_/D |
| USB CF | 10.944381 | 12.5 | U._7254_/Q → U._6522_/D |
| USB CP | 12.811203 | 37.5 | U._7057_/Q → U._7683_/D |
| USB FC | 11.993650 | 12.5 | U._7609_/Q → U._7435_/D |
| USB FF | 13.485458 | 12.5; approved warning ceiling 15 | U._6398_/Q → U._7356_/D |
| USB FP | 9.182744 | 12.5 | U._7583_/Q → U._7683_/D |
| OSC_IN RR | 12.126913 | 12.5 | clocks.executor.counter._194_/Q → clocks.executor.counter._186_/D |

The source counter first failed at measured 13.009707 ns. Removing synchronous
zeroing of its inactive remaining count reduced it to 12.126913 ns; active,
ready and request still clear, and activation reloads before use. Unbounded
stable-output equivalence and its clear-ready negative pass in
`build/t41/stability-clear-proof01`. Counter area is measured 4274.0544 µm²,
down from 5288.2368 µm² in the retained failing attempt. No timing budget changed.

Mapped whole logic is measured 3.5510477184 mm². The T35 method estimates
11.3344345975 mm² including macros/unchanged allowances and 0.55 utilization,
leaving estimated 1.5855654025 mm² against 12.92 mm². Isolated controller area
increases from measured 0.0687404928 to 0.0713242432 mm² for explicit clear/ack
control, including the new sibling reset root; sharing releases saves state
elsewhere. See the T41 report for exact before/after boundaries.

Electrical and gate-violation counts are measured zero in both modes. Each
mode retains 13645 reported raw hold/recovery/removal/pulse violation rows and 12 absent
reset-endpoint paths. Reported endpoint minimum slack +1.87561 ns does not
qualify those missing checks. This is pre-layout setup evidence, not routed
hold, reset-tree, RDC or analog signoff. No aggregate CI ran.

## T42 local main-to-AON grant, 2026-11-25

Measured on mainf534b34 plus authenticated D108 sources. Exact EmitSoc,
plan04_map, plan04_screen, plan04_area and t35_budget commands and every class's
start/end are in [T42](../plan/tasks/reports/T42.md); receipts in
`build/t42/timing01`. SS125, same clocks/budgets, both AON source straps.

| Quantity | Measured result |
| --- | --- |
| LocalPermit area / flops | 74.6368um2 /1 |
| Authenticated old bound DirectionPermit area / flops | 794.6624um2 /9 |
| Isolated area difference | -720.0256um2, not additive to whole-map area |
| LocalPermit worst | 3.750224ns, `_0_/Q` to `permit`, budget75ns |
| Whole mapped logic | 3.5594355776mm2 |
| Main RR worst | 67.515236ns, `_222057_/Q` to `_221651_/D`, budget75ns |
| AON RR worst | 65.482735ns, `_229206_/Q` to `_236296_/D`, budget18750ns |
| TCK RR worst | 17.974028ns, `_235935_/Q` to `_218467_/D`, budget6000ns |
| USB FF worst | 13.485458ns, inherited warning against12.5ns/approved ceiling15ns |
| OSC_IN stability RR worst | 12.126913ns against12.5ns |

Isolated commands: `python hw/ip/bus_bridge/measurements/local_permit_area.py
--baseline build/t42/baseline02 --proof build/t42/local-proof01 --output
build/t42/grant-area04` and `python tools/timing/check.py --top LocalPermit
--source build/t42/local-proof01/emit/block/LocalPermit.sv --clock clk
--operating-point main-8mhz --output build/t42/local-timing01` (pinned environment).
The comparator binds requestAon low/permitAon unused exactly as old production,
authenticates emitted inputs/library/config and requires known cells and drivers.

Electrical and clock-gate violations are measured zero. Both modes retain
13,676 raw hold/recovery/removal/pulse violation rows and missing reset endpoint
checks. CROSS rows are diagnostics. No routed hold/reset/RDC signoff or new
physical exception is claimed. T35 method estimates11.3505473655mm2 total and
1.5694526345mm2 headroom with unchanged macros/allowances. No aggregate CI ran.
