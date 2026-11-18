# T13 ten-proposal optimization study

## Outcome

Study complete. None of the ten proposals demonstrated both lower whole-core area and shorter whole-core delay. The eight-bank production implementation remains the measured baseline.

## What changed

The study started from the faithful RV32IMFC eight-bank core at `2e5bc00545f4002ab4540bce61762e6a770af1a1`. This report and its entry in `docs/plan/STATUS.md` record the decision. Candidate sources and raw measurements are available locally under `build/ten-study`. The comparison required both a strictly smaller whole-core mapped area and a strictly shorter whole-core worst path than the fresh baseline. Standalone FPU timing and functional requirements continued to apply.

| Proposal | First implementation | Researched refinement |
| --- | --- | --- |
| 1. Unity bypass for add/sub | Form the exact product by shifting the significand | Seed the existing final multiply iteration, avoiding the second wide select |
| 2. Two-bit significand multiply | Select 0, A, 2A or 3A | Compress the two partials and accumulator before final carry propagation |
| 3. Reuse the integer multiplier | Four unsigned 12-bit partial products on the existing signed 17-bit MAC | Move ownership into the idle integer-state decode |
| 4. Overlap preparation | Start the first two product iterations during alignment | Start multiply after operand capture and capture metadata on its second iteration |
| 5. Reuse product and addend registers | Shift both working registers during the three chunk additions | Keep operands stationary and select a 17-bit slice by phase |
| 6. Change one FPU adder | Let synthesis map the multiplier's unsigned addition | Six four-bit groups with a sparse Brent–Kung carry network |
| 7. Static IF predecode | Carry four opcode class bits with a reset-safe raw fallback | Carry a single recognition bit for the substitute instruction mux |
| 8. Isolate unused FPU operands | Zero the three pre-multiply inputs during unrelated operations | Hold the recoded C operand stationary when its datapath is unused |
| 9. SRAM banking | Replay both real address streams with common acceptance and response policies | Test code/data coloring and select a zero-padding pair of bank-index bits from the trace, then repeat cycle-accurate simulation |
| 10. Buffering | Reproduce original whole-core STA and isolate a high-fan-out buffer on its longest path | Compare local load splits, drive changes and the smaller-cell option at the same corner |

The FPU refinements follow the pinned HardFloat pre-multiply stage’s actual signal availability and fused rounding interface. The two-bit multiplier refinement reduces consecutive carry-propagating additions. The sparse adder explores carry fan-out without sharing add and subtract. The IF refinements preserve the original reset-visible raw data before the first accepted instruction. [HardFloat arithmetic](https://www.jhauser.us/arithmetic/HardFloat-1/doc/HardFloat-Verilog.html) · [MIT multiplier architecture](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2017/pages/c8/c8s1/) · [Brent and Kung](https://maths-people.anu.edu.au/brent/pub/pub060.html) · [OpenROAD timing repair](https://openroad.readthedocs.io/en/latest/main/openroad/rsz/README.html)

## Checks run

Commands below use `python tools/env/run.py run --` and paths under `$B=build/ten-study`. The experimental Scala snapshots in each `source/` directory replaced only their named counterparts via sbt's `hw / Compile / unmanagedSources` setting. For example, `p5/source/Fpu.scala` replaced production `Fpu.scala`. The baseline used ordinary production elaboration. `scratch/ten_run.py` records the complete sbt source override.

| Command after the pinned prefix | Result |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulFloatCore $B/<trial>/emit"` | Fresh ASIC/model views. The baseline ASIC source hashes, all six path classes, and area matched the preceding study’s production CI. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted $B/<trial>/emit/asic --operating-point main-9mhz --output $B/<trial>/timing` | Each hardware variant completed mapping and STA. The table uses final receipts. |
| `python3 tools/sbt.py "hw/runMain deadhorse.fpu.EmitFpu $B/<trial>/fpu"`, followed by `python3 tools/timing/check.py --top Fpu --clock clock --source <each emitted file> --output $B/<trial>/fpu-timing` | Standalone FPU results use the unchanged 24.96 ns limit. |
| `python3 scratch/ten_vector_inside.py $B/<trial>` | Unmodified `dv/fpu/sim.cpp`, `build/t12/vectors.txt`, and the trial's standalone RTL. Results appear below. |
| `python3 scratch/ten_cached_iss.py --candidate $B/<trial>/candidate --output $B/<trial>/performance-cached` | Measured both 120-iteration loops with the normal S1 RTL simulator and pinned QEMU reference. Fresh QEMU generation under concurrent jobs hit the existing 30 s timeout. Replays verified the ELF, binary and archived QEMU trace digests before reuse and ran the original architectural comparison and its fault controls. |
| `python3 scratch/ten3_sim.py` and `python3 scratch/ten3b_sim.py` | Both shared-MAC configurations passed all arithmetic vectors using the actual emitted integer MAC, plus directed checks for ownership, cancellation and reset. |
| `python3 scratch/ten_adder_proof.py` and `python3 scratch/ten7_if_proof.py <p7 or p7b>` | The extracted P6b carry network matched P6's emitted unsigned-adder reference on all 25 output bits for 49 free input bits. A dropped-carry control failed. Both IF class invariants held from reset with arbitrary stalls and later resets, and each incorrect-class control failed. |
| `python3 scratch/ten7_switch.py <trial>` and `python3 scratch/ten7_fixed.py <trial>` | Cycle samples of HardFloat pre-multiply ports plus full architectural and cycle trace digests for each workload. |
| `python3 scratch/ten_bank_close.py` and `python3 scratch/ten_physical_close.py` | Verified the SRAM simulation and replay evidence and the buffer trials against their references. |
| `python3 scratch/ten_screen.py` and independent `python3 scratch/ten7_review_screens.py` | Checked raw synthesis area, all reported path delays, operating point, gates, electrical checks and source/flow digests for the baseline and all 16 variants. |
| `python3 tools/ci.py --tier fast --output build/ten-study/baseline-ci` | All 33 active jobs returned zero on the production RTL. The receipt records 12 inherited, unproved deferrals (4 T14 and 8 T17). Full tier unrun. |

A concurrent preparation of the ignored HardFloat build copy failed during one P2 refinement emission. The failing log was retained and the outer build lock serialized preparation on retry. The checked-in vendor lock and patches stayed intact. The measurement audit checked emitted source hashes against disk, shared flow parameters, and expected module differences against the fresh baseline.

## Numbers

Measured with Yosys 0.71+34 and OpenSTA 3.2.0 at GF180 7t5v0 SS/125 °C/3.0 V, mapped pre-layout at the same 9 MHz operating point, ideal clocks with no wire delay. The table uses the worst across all six whole-core timing path classes. The final column is the measured standalone FPU worst delay when that implementation changes. The project’s 9 MHz operating point allows 66.666667 ns for this block. The study required a shorter path than the measured 64.258347 ns baseline as well as lower cell area. ASIC standard-cell area excludes SRAM macros, wiring and pads.

| Trial | Core area (µm²) | Worst (ns) | Area change (µm²) | Delay change (ns) | FPU (ns) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 829,781.2096 | 64.258347 | 0 | 0 | — |
| p1 | 829,432.1728 | 68.452499 | -349.0368 | +4.194152 | 24.184332 |
| p1b | 834,272.5888 | 65.151344 | +4,491.3792 | +0.892997 | 25.214830 |
| p2 | 829,765.8432 | 67.312309 | -15.3664 | +3.053962 | 32.675449 |
| p2b | 827,798.9440 | 64.854836 | -1,982.2656 | +0.596489 | 24.661316 |
| p3 | 820,363.8016 | 66.081337 | -9,417.4080 | +1.822990 | — |
| p3b | 817,123.6864 | 71.406059 | -12,657.5232 | +7.147712 | — |
| p4 | 831,552.7360 | 64.897575 | +1,771.5264 | +0.639228 | 25.205715 |
| p4b | 826,558.6560 | 65.516876 | -3,222.5536 | +1.258529 | 24.814766 |
| p5 | 813,602.5856 | 64.856171 | -16,178.6240 | +0.597824 | 24.491375 |
| p5b | 832,755.7056 | 64.480736 | +2,974.4960 | +0.222389 | 26.970633 |
| p6 | 828,938.2528 | 65.551140 | -842.9568 | +1.292793 | 28.862011 |
| p6b | 826,637.6832 | 64.971664 | -3,143.5264 | +0.713317 | 26.930790 |
| p7 | 827,074.5280 | 69.915253 | -2,706.6816 | +5.656906 | — |
| p7b | 828,172.1280 | 69.155167 | -1,609.0816 | +4.896820 | — |
| p8 | 830,946.8608 | 64.662712 | +1,165.6512 | +0.404365 | 25.192141 |
| p8b | 826,775.9808 | 68.607330 | -3,005.2288 | +4.348983 | 24.323368 |

The suffix `b` identifies the single refinement for that proposal. P3 used the actual shared integer unit in the integrated core. Its default standalone configuration uses its local multiplier, so standalone timing cannot qualify this change.

| Throughput trial | Hard-float loop cycles, 120 iterations | Worst iteration (cycles) | Derived MIPS at assumed 9 MHz |
| --- | ---: | ---: | ---: |
| Baseline | 1,480,640 | 14,233 | 1.090122 |
| p1 | 1,343,144 | 12,745 | 1.201716 |
| p1b | 1,348,873 | 12,807 | 1.196612 |
| p2 | 1,152,332 | 11,077 | 1.400706 |
| p2b | 1,152,332 | 11,077 | 1.400706 |
| p3 | 933,460 | 8,973 | 1.729135 |
| p3b | 933,460 | 8,973 | 1.729135 |
| p4 | 1,425,922 | 13,707 | 1.131954 |
| p4b | 1,425,922 | 13,707 | 1.131954 |

**Area and throughput.** P5 saved 16,178.6240 µm² (1.950% of baseline), the largest area reduction. The fixed and hard-float architectural and cycle traces matched, but the worst path grew by 0.597824 ns. Keeping the data stationary in P5b reduced that delay penalty to 0.222389 ns and lost the area saving. P2b brought the standalone FPU back inside its 24.96 ns limit, but the whole core was still 0.596489 ns slower. All twelve standalone arithmetic variants passed the same 184,380 result/flag vectors and backpressure checks.

**Shared multiplier.** Both P3 trials cut the sampled add, subtract, multiply and fused result latency from 38 cycles to 18. They also cut the measured hard-float loop from 1,480,640 to 933,460 cycles. At an assumed 9 MHz the worst iteration projects to 997 µs (8,973 cycles ÷ 9 cycles/µs), and aggregate throughput projects to 1.729135 MIPS, below the separate 2.5 MIPS requirement. P3b took opcode arbitration off the direct multiplier steering path. Its longest path still ran from the fetched opcode into the integer register file. All eight cycle-changing trials took the baseline 465,575 cycles on the fixed-point loop.

**Operand isolation.** The hard-float run sampled 1,413,429 bit changes on the three baseline pre-multiply operand ports. P8 reduced that count to 1,342,672 (5.01%) and P8b to 1,308,311 (7.44%). On the three selected arithmetic outputs, P8 reduced transitions by 11.48% while P8b increased them by 3.17%. All three fixed-point runs saw zero operand transitions. Both workloads preserved their architectural and cycle traces. These counts describe settled port activity sampled once per cycle. They exclude glitches, capacitance and chip power.

**SRAM.** The model used four single-port 4 KiB SRAM banks. The two unchanged firmware images ran in 38 simulations, each over 120 iterations. QEMU comparison covered all distinct architectural traces (283,490 fixed-point and 191,201 hard-float retirements per run). At the assumed one-edge response, every tested policy and layout used 465,575 fixed-point or 1,480,640 hard-float loop cycles. With one system-wide outstanding request, bank selection cannot admit a second access. The refinement selected byte address bits 13 and 11 out of 66 tested bit pairs without requiring image padding. Relative to contiguous banks, simultaneous same-bank demands within the loops fell from 320 to zero for fixed-point and from 2,635 to 1,394 for hard-float. Under a hypothetical one-credit-per-bank policy and five-edge response, the measured hard-float cycle count fell from 1,983,349 to 1,978,045. Padding the code/data layout eliminated loop conflicts on both fixtures and reduced the five-edge hard-float count to 1,972,254 at the cost of image space. The current protocol and base latency produced no measured throughput gain from either refinement.

**Pre-layout buffering.** The unmodified mapped netlist reproduced the 64.258347 ns baseline. The table shows measured OpenSTA delays and estimated area deltas computed by adding or subtracting the relevant GF180 Liberty cell areas. The net had ten loads. A same-drive control reproduced the baseline.

| Change to the baseline x4 buffer | Worst delay (ns) | Estimated area change (µm²) |
| --- | ---: | ---: |
| Clone and split loads evenly | 64.406326 | +30.7328 |
| Add x2 branch buffer | 64.905739 | +17.5616 |
| Increase drive to x8 | 64.402420 | +26.3424 |
| Clone for the critical sink alone | 64.406326 | +30.7328 |
| Reduce drive to x2 | 64.450829 | −13.1712 |

The eight enable/test-enable setup and hold checks passed, with minimum slack of +0.704980 ns. The slew and capacitance checks reported zero violations. The existing asynchronous reset-removal slack was −0.975158 ns and the ordinary clock-group hold slack was +0.103031 ns. These ideal-clock, ideal-wire checks do not establish routed hold margins.

## Deviations from the brief

The user selected pre-layout evidence for proposal 10. The pinned environment provides OpenSTA and lacks a placed design, approved GF180 technology LEF/floorplan bundle and OpenROAD executable. No placed, CTS or routed measurement is claimed. Proposal 9 compares timing models with explicit resource and memory assumptions. It does not measure physical SRAM area.

## Open issues

The S1 hard-float throughput floor and earlier T13 formal obligations remain open. The standard full CI tier was outside the study. The baseline does not qualify the actual SRAM, complete firmware workload, or routed silicon frequency.
