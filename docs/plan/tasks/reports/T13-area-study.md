# T13 faithful RV32IMFC core area study

## Outcome

Eight-bank floating-point register reads reduced mapped whole-core area by 1.448% and shortened the worst path by 0.131546 ns, meeting the strict zero-regression timing criterion.

## What changed

`FloatExecution.scala` now splits each faithful-F read address into a two-bit word select and a three-bit bank select. Each bank contains four interleaved words. The word select feeds a one-hot mux across the four words, and the bank select chooses the result. All three read ports feed their existing operand registers. `IbexCore.scala` enables this organization for the faithful-F profile. The core README, timing ledger and T13 tracker link this study.

The pinned Ibex register file supports indexed and one-hot reads. OpenHW documents the cost of a flip-flop register file with multiple read ports and a floating-point bank. Chisel's `Mux1H` lets a word enable select every bit of a word when exactly one enable is asserted. These motivated experiments on selection logic while retaining each storage bit, port and read cycle. [Pinned Ibex register file](https://github.com/lowRISC/ibex/blob/38c070939183cc10940b66c8e9e04eeca6b65470/rtl/ibex_register_file_ff.sv) · [CV32E40P register file](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/latest/register_file.html) · [Chisel muxes](https://www.chisel-lang.org/docs/explanations/muxes-and-input-selection)

1. **Integer register reads.** Decode parts of each address once per port and combine four eight-word groups. This could reduce duplicated select gates on both 32-bit read ports.
2. **Floating-point register reads.** For each of the three ports, share one-hot word enables across the data bits before the existing operand register. Register `f0` remains writable.
3. **Shifts.** Use a single right barrel for both directions, with sign fill for arithmetic right shifts and bit reversal for left shifts. Ibex uses this structure to share shifter hardware.
4. **Add and subtract.** Select the second operand's polarity and carry-in before one adder. Ibex uses an input-complement scheme. The experiment kept the separate multiply/divide input path.
5. **Floating-point write enables.** Decode load and arithmetic destinations separately, then combine their qualified enables per register. Moving destination selection out of the address mux could simplify the write logic. Load priority and cancellation are part of the existing interface. [Pinned Ibex ALU](https://github.com/lowRISC/ibex/blob/38c070939183cc10940b66c8e9e04eeca6b65470/rtl/ibex_alu.sv)

The follow-ups changed the order of the address-bit groups in H1 and H2, the number of FP banks, and which FP ports used the grouped read. All refinements used the same comparison rule.

## Checks run

Commands use the pinned prefix `python tools/env/run.py run --`. Here `$B` is `build/area-study` and `$W` is `$B/fp-read-eight-banks`. The fresh baseline was commit `73c178e8898a5cfbcf622b4bea545d871ae08b2c`. Its measured area, delay and production emission hashes matched the previous study's fast CI. The trials substituted isolated Scala sources for the corresponding files during elaboration. Each trial retains its Scala snapshot under `$B/<trial>/source`, emitted files under `emit`, and the mapped netlist, `paths.tsv`, synthesis log and `result.json` under `timing`. Final production elaboration reproduced the winning trial byte for byte in all 26 ASIC files and all 26 RVFI model files.

| Command after the pinned prefix | Result |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulFloatCore $B/selected/emit"` | Production ASIC and model emission succeeded. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted $B/<trial>/emit/asic --operating-point main-9mhz --output $B/<trial>/timing` | Baseline plus nine implementation trials measured. Three exceeded the 66.666667 ns T09 allowance. Eight exceeded the tighter 64.389893 ns comparison cutoff. Winner output: `PASS DeadhorsePerfCore: 64.258347 ns, budget 66.666667 ns; electrical violations 0`. |
| `python3 hw/ip/perf_core/formal/package_candidate.py --float --top $W/emit/model --leaves build/pipeline-study/ci-fast/fast/leaves --core build/pipeline-study/ci-fast/fast/core --output $W/candidate` | Authenticated faithful-F candidate. The baseline packaged against its own model matched the earlier fast-tier manifest. |
| `python3 dv/core/revision_equiv.py --before $B/base/candidate --after $W/candidate --output $W/revision` | `PASS revision equivalence: whole top, no added assumptions, all fault controls rejected`. All four injected faults were detected. |
| `python3 dv/core/equiv.py --unchanged-since t11-baseline --candidate $W/candidate --output $W/unchanged` | 12 unchanged modules proved. |
| `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"` | 60 core tests. `All tests passed.` |
| `python3 dv/core/lockstep.py --candidate $W/candidate --isa rv32imfc --suite arch,random,flight-float --output $W/lockstep` | `PASS selected F lockstep suites`, including the hard-float flight workload. |
| `python3 tools/spikes/s1_core/performance.py --candidate $W/candidate --output $W/performance` | `blocked_throughput_floor`, exit 1. The workload binaries, retirement-cycle hashes, architectural results and all 240 sampled loop iterations matched the existing S1 baseline. |
| `python3 tools/ci.py --tier fast --output $B/ci-fast` | All 33 active commands returned zero. The receipt lists 12 inherited T14/T17 deferrals as unproved. |

Fast CI independently re-emitted, packaged and measured the production core. The registered-F profile reproduced its archived area of 872958.5984 µm² and delay of 24.947506 ns. Independent review checked synthesis area, raw STA paths, the library and flow hashes, source identity, and all eight clock-gate checks. An independent proof against a direct indexed-read oracle covered all three read ports, every 32-bit word and all 32768 simultaneous address combinations. Swapping f0 and f8 was detected. The extracted data cones read the old register values, including on same-edge writes. See `$B/review/functional/result.json`. The retained local receipts include `$B/review/screen.json`, `$W/revision/result.json` and `$B/ci-fast/result.json`.

## Numbers

Area and delay are measured using the command above at GF180MCU 7t5v0 SS, 125 °C, 3.0 V, in the production faithful RV32IMFC ASIC view. The T09 flow used Yosys 0.71+34 (`e419c4eef`) and OpenSTA 3.2.0. These are mapped pre-layout results with ideal clocks and no wire delay. Area is whole-core standard-cell area. Delay is the maximum across the reported path classes. Area change is derived as 100 × (trial area / baseline area − 1), and delay change is trial minus baseline. Decisions use the recorded values before rounding. Each completed run had zero reported capacitance and slew violations.

| Implementation | Area (µm²) | Area change | Worst delay (ns) | Delay change (ns) | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Committed baseline | 841,971.1552 | +0.000% | 64.389893 | +0.000000 | Baseline |
| H1. Four banks of eight integer registers | 819,490.1120 | -2.670% | 65.537796 | +1.147903 | Reject |
| H2. Flat floating-point word selects | 809,602.9312 | -3.844% | 68.113907 | +3.724014 | Reject |
| H3. One bidirectional barrel shifter | 827,239.1680 | -1.750% | 68.986275 | +4.596382 | Reject |
| H4. One adder for integer add and subtract | 837,565.3888 | -0.523% | 64.552025 | +0.162132 | Reject |
| H5. Per-word floating-point write enables | 840,162.3104 | -0.215% | 68.820847 | +4.430954 | Reject |
| H1 refinement. Interleaved integer banks | 822,396.5568 | -2.325% | 65.504036 | +1.114143 | Reject |
| H2 refinement. Four interleaved FP banks | 824,716.8832 | -2.049% | 65.607437 | +1.217544 | Reject |
| H2 refinement. Eight interleaved FP banks | 829,781.2096 | -1.448% | 64.258347 | -0.131546 | Qualifies |
| H2 refinement. Bank only FP ports 1 and 2 | 825,281.0496 | -1.982% | 65.237885 | +0.847992 | Reject |

The flat FP read saved the most area, 3.844%, but increased delay by 3.724014 ns. Four interleaved FP banks reduced that penalty to 1.217544 ns. Eight interleaved banks shortened delay by 0.131546 ns and saved 12189.9456 µm². Whole-core mapping determined the selection. Every variant used the same 9 MHz operating point, ABC mapping target and STA constraints.

The selection criterion uses the whole-core worst delay. Register-to-register remained the limiting class. The full six-class comparison, measured in ns, shows where delays moved.

| Path class | Baseline | Eight banks |
| --- | ---: | ---: |
| Register to register | 64.389893 | 64.258347 |
| Input to register | 29.406412 | 29.640278 |
| Register to output | 47.016392 | 47.973759 |
| Input to output | 26.926514 | 25.728605 |
| Register to clock gate | 16.594126 | 17.322472 |
| Input to clock gate | 14.556479 | 15.284134 |

## Deviations from the brief

This is a user-assigned optimization within T13. Four follow-up implementations explored the two register-read hypotheses after the first layouts missed timing. The complete ISA sweep and standard full CI tier were outside the area study.

## Open issues

S1's hard-float throughput floor and the earlier T13 integration formal obligations remain open. Routed timing and whole-chip die area require physical implementation.
