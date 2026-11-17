# T13: faithful Chisel core at 9.6 MHz

## Outcome

Failed timing trial: the faithful RV32IMC Chisel core measures 65.305771 ns against the unchanged 60 percent allowance of 62.5 ns at 9.6 MHz; T13 remains blocked and the production clock/profile are unchanged.

## What changed

- `tools/timing/check.py` adds the explicitly approved `main-9p6mhz` trial. Period is 1000/9.6 ns and ABC target is 62500 ps. Default configuration, 60 percent fraction, SS library/hash, IO load/slew, electrical rejection, source isolation and clock-gate checks remain unchanged.
- `EmitFaithfulCore.scala` emits the existing `IbexTop` with `RegisteredExecution=false` and `WithF=false`. The ASIC view uses the same physical ports, flop register file, real ICG and disabled RVFI as the registered physical view. The model retains RVFI. This is an emission entry point, not a datapath or control change.
- Existing operating-point tests now exercise both named trials. Timing README, ledger, report and own STATUS row record the failure; no acceptance check or profile was retired.

## Checks run

Commands use `python tools/env/run.py run --`. Base commit `ec736f2fbf299c2a2f2344dd413da3113b447d9b` plus these changes; each timing receipt records emitted source/flow/library hashes and tools. Outputs are under `build/t13/faithful9p6/`.

| Command after container prefix | Result / final output |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulCore build/t13/faithful9p6/emit"` | `[success] Total time: 8 s`; fresh model and ASIC emission. |
| `python3 -m unittest tools.timing.test_timing` | `Ran 15 tests`; `OK`. Independently repeated. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/faithful9p6/emit/asic --operating-point main-9p6mhz --output build/t13/faithful9p6/timing` | CLI exit 1: `FAIL DeadhorsePerfCore: 65.305771 ns, budget 62.500000 ns; electrical violations 0`. |
| `python3 tools/timing/check.py --top ClockedElapsedTicks --clock clock --source build/riscay-mcu/build/export/clocked/ClockedElapsedTicks.sv --operating-point main-9p6mhz --output build/t13/faithful9p6/negative` | Expected CLI exit 1: `FAIL ClockedElapsedTicks: 71.002609 ns, budget 62.500000 ns; electrical violations 0`. |

Fast tier: `python3 tools/ci.py --tier fast --output build/t13/faithful9p6/ci-fast`
passed all 21 commands in measured **475.169 s (7m55s)**, ending `PASS fast tier`.
This checks the existing default configuration; it does not qualify the failed
9.6 MHz experiment. Full tier was **not rerun**; the earlier 53m37s partial
failure and 26 unrun commands remain recorded in T13.md. Only report/ledger/
status documentation changed after the gate, with executable source hashes unchanged.

Independent review authenticated the trial configuration, profile selection,
17 ASIC source and six flow hashes, critical path, all eight ICG checks and the
rejected negative control. The reviewer independently repeated the 15 timing
unit tests and repository tool discovery suite (64 tests), both passing.
Review accepts this as a documented failed experiment, not timing closure.

The 17 fresh emitted model files are byte-identical to their counterparts in the faithful package used by the earlier full gate (`build/t13/feedback/ci-full/legacy-t11/baseline`); `profile-binding.json` records hashes. That package additionally carries standalone csr/counter files not emitted in the top hierarchy. Initial broad manifest comparison recorded this difference in `model-identity.json`; it is not an RTL mismatch. This is provenance checking, not a new equivalence proof.

The older performance package (`build/t11/ci/baseline`) differs in emitted core/CSR files, so its cycle counts below remain explicitly historical and are not claimed as freshly measured or byte-identical current performance. No additional formal sweep or new induction, monitor or composition machinery was introduced; the fast tier reran its existing short formal checks.

## Numbers

Measured with pinned Yosys 0.71+34 (`e419c4eef`) and OpenSTA 3.2.0, GF180 `gf180mcu_fd_sc_mcu7t5v0`, SS/125C/3.0V. Mapped, pre-layout, ideal pre-CTS clocks, no wire parasitics or SRAM timing.

| Quantity | Provenance / interpretation |
| --- | --- |
| Worst path 65.305771 ns; mapped cell area 439002.6816 um2 | Measured by the faithful timing command above. Cell area is 0.439003 mm2, not placed or total-chip area. |
| Allowance 62.5 ns | Derived from the approved trial: (1000 / 9.6) * 0.60. Default remains 24.96 ns. |
| Over allowance by 2.805771 ns / 4.489234 percent | Derived: 65.305771 - 62.5; excess / 62.5 * 100. |
| 58 logic stages, 60 path cells | Measured path from `_33260_/Q` (instruction/rs1 address bit, `rf_raddr_a_o[0]`) to `_32120_/D` (register-file x30 bit31). Capture Q is `gen_regfile_ff_register_file_i._GEN_0[991]`. |
| Zero electrical violations; eight ICG setup/hold checks; minimum slack 0.704980 ns | Measured by OpenSTA and retained in `timing/result.json` and `gate_checks.tsv`. |
| 9.187549 MHz limiting frequency for this mapped path under the 60 percent rule | Estimate: 600 / 65.305771. Not a measured closure result at another frequency; remapping and F integration can change the path. |
| Historical faithful fixed-point mean 3879.791667 / worst 4350 cycles | Previously measured with `python3 dv/core/performance.py --output build/t13/feedback/performance` on `ecc5d7e` plus recorded input hashes; not rerun here. |
| Mean 404.145 us / worst 453.125 us at 9.6 MHz | Estimates from historical cycles / 9.6; the failed timing trial does not qualify operation at this clock. |
| Worst 483.333 us at 9 MHz; 66.666667 ns allowance | Estimates: 4350 / 9 and 600 / 9. A fresh 9 MHz trial is recommended, not performed or accepted here. |

The critical path begins at an instruction/address register and ends at a register-file write bit; it is a full core path. This run does not isolate which individual operator dominates it. The reference's historical 61.667374 ns result was mapped at a different target and is not a substitute for this Chisel measurement. No MIPS result or whole-system 1 kHz qualification is claimed.

## Deviations from the brief

The user approved this focused lower-clock trial as a T13 continuation. The named operating point is explicit, rather than a silent limit change; the 60 percent margin and all other timing checks remain intact. No RTL repair or profile retirement was attempted after failure. Full T13 acceptance is not claimed.

## Open issues

- The faithful core fails the 9.6 MHz trial. Recommend a separately measured 9 MHz trial before choosing the production clock; its estimated allowance margin on this netlist is only 1.360896 ns.
- Full F remains required. The faithful profile has no F integration; reusing the standalone FPU needs fresh integration verification and timing.
- Current faithful flight throughput, routed timing, clocks/SRAM/peripheral overhead and the 5 MIPS requirement still need qualification. The historical fixture used ideal one-cycle memory without interrupts or external I/O.
- Registered profiles, prior default-clock failures and the unfinished full gate remain intact. This trial does not retire them or change G1.
