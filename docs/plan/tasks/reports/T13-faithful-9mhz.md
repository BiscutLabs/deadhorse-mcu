# T13: faithful Chisel core at 9 MHz

## Outcome

Done as a focused timing experiment: a fresh faithful-core mapping passes at 9 MHz, 65.305771 ns against 66.666667 ns; production clock adoption, faithful F integration and full T13 acceptance remain open.

## What changed

- `tools/timing/check.py` adds `main-9mhz`: period 1000/9 ns and the unchanged 60 percent allowance, 200/3 ns. This named trial keeps the tighter **62500 ps ABC optimization target** from the 9.6 MHz mapping. Mapping target and STA acceptance are recorded separately; no arbitrary override is provided.
- Initial mapping at the looser 66666.667 ps target failed. Retaining the earlier target reproduces the better mapping from RTL, without changing RTL behavior. Defaults and other trial targets, the library/hash, IO constraints, electrical rejection, isolation and clock-gate checks are unchanged.
- Existing tests cover the new point and the mapping/acceptance distinction. README, ledger, report and own STATUS row record both the failed and passing experiments. No profile, check or formal bound was removed.

## Checks run

Commands use `python tools/env/run.py run --`. Base `78be66b` plus the trial changes; receipts preserve tools, source/flow/library hashes under `build/t13/faithful9/`. The initial executed flow files are archived under `initial-flow/` so their earlier hashes remain available.

| Command after container prefix | Result / final output |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulCore build/t13/faithful9/emit"` | `[success] Total time: 5 s`; ASIC and model outputs each 17 files byte-identical to the prior trial. |
| `python3 -m unittest tools.timing.test_timing` | Final code: `Ran 16 tests`; `OK`; independently repeated. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted build/t13/faithful9/emit/asic --operating-point main-9mhz --output build/t13/faithful9/tight-mapping` | Exit 0: `PASS DeadhorsePerfCore: 65.305771 ns, budget 66.666667 ns; electrical violations 0`. |
| `python3 tools/timing/check.py --top ClockedElapsedTicks --clock clock --source build/riscay-mcu/build/export/clocked/ClockedElapsedTicks.sv --operating-point main-9mhz --output build/t13/faithful9/negative-tight` | Expected exit 1: `FAIL ClockedElapsedTicks: 71.002609 ns, budget 66.666667 ns; electrical violations 0`. |

Final fast tier: `python3 tools/ci.py --tier fast --output build/t13/faithful9/ci-fast-final`
passed all 21 commands in measured **474.641 s (7m55s)**, ending `PASS fast tier`.
Full tier was **not rerun**; the previous partial failure and 26 unrun commands
remain recorded in T13.md. Only report/ledger/status documentation changed
after the final gate; executable hashes remain unchanged. Structure and diff
checks passed after documentation updates.

Independent review verified the named trial, unchanged default/acceptance limits, source/flow hashes, all eight ICG checks, negative control and report. The reviewer independently passed 16 timing tests and 65 repository tool tests. Fresh `mapped.v`, `mapping.abc` and `mapping.constr` are byte-identical to the earlier 9.6 MHz mapping (`mapping-reproduction.json`). All 34 fresh model/ASIC source hashes match the previous emission (`emission-identity.json`). No additional formal sweep or new proof machinery was introduced; fast CI reruns its existing short formal checks.

### Preserved diagnostic results

- Initial period-only trial, before the mapping-policy adjustment: same core timing command with output `build/t13/faithful9/timing`, ABC target 66666.667 ps, failed **69.336807 ns / 66.666667 ns**, area **429822.3552 um2**. Its negative control also rejected 71.002609 ns (`negative/`). This failure is not relabelled passing.
- Re-import attempt: `python3 tools/timing/check.py --top DeadhorsePerfCore --clock clk_i --source build/t13/faithful9p6/timing/mapped.v --operating-point main-9mhz --output build/t13/faithful9/retained-mapping` stopped at `premap failed (1)` with four undriven aliases. Review traced them to unused alias-buffer cones, with no hardware cell or top-port sink in the original netlist. Original synthesis reported zero problems. No check was disabled to bypass the re-import failure.
- Direct STA diagnostic, `python3 build/t13/faithful9/reanalyze.py`, passed the unchanged prior netlist at 9 MHz. It changed only the generated Tcl period and two report paths, reused the shared analyzer, authenticated inputs and checked boundary, electrical limits and eight ICG paths. All 8,028 data-path rows match the prior analysis (`retained-sta/`). This established the useful mapping target; **acceptance above uses a fresh RTL mapping**, not this diagnostic script.

The existing mapping/STA separation in `tools/timing/check.py` was the relevant implementation pattern: ABC's target guides combinational optimization, while OpenSTA independently applies clock, IO and acceptance constraints. The measured failed and passing mappings justify preserving the tighter heuristic for this named trial. The original fast gate passed 21 commands in measured 481.079 s before that adjustment; it does not substitute for the final gate.

## Numbers

Measured with pinned Yosys 0.71+34 (`e419c4eef`) and OpenSTA 3.2.0, GF180 `gf180mcu_fd_sc_mcu7t5v0`, SS/125C/3.0V. Mapped pre-layout, ideal pre-CTS clocks; no wire parasitics, placement, SRAM or routed signoff.

| Quantity | Provenance and interpretation |
| --- | --- |
| 65.305771 ns worst delay; 439002.6816 um2 mapped cell area | Measured by the final fresh timing command; 0.439003 mm2 cell area, not total die area. |
| 66.666667 ns allowance | Derived: (1000 / 9) * 0.60; default remains 24.96 ns. |
| 1.360896 ns / 2.041344 percent allowance margin | Derived: 66.666667 - 65.305771; margin / allowance * 100. |
| 58 logic stages / 60 path cells | Measured instruction/rs1-address launch `_33260_/Q` to register-file x30[31] capture `_32120_/D`. |
| Zero electrical violations; eight ICG checks; minimum slack 0.704980 ns | Measured in final STA receipt and gate report. |
| Historical mean 3879.791667 / worst 4350 cycles | Previously measured on `ecc5d7e` plus recorded hashes with `python3 dv/core/performance.py --output build/t13/feedback/performance`; not rerun here. |
| Estimated mean 431.088 us / worst 483.333 us at 9 MHz | Historical cycles / 9. Older performance core/CSR emission is not byte-identical to current emission; this is not a fresh throughput measurement. |

The current faithful model matches the newer previously checked baseline as detailed in the 9.6 MHz report. The historical fixture has ideal one-cycle memory without interrupts or external I/O; no MIPS or whole-system 1 kHz qualification is claimed.

## Deviations from the brief

The user approved the 9 MHz follow-up as a focused T13 experiment. A minor, independently reviewed mapping-policy adjustment retains the tighter prior optimization target after fresh remapping regressed timing. The actual clock/60 percent acceptance rule and all other checks remain intact. No architectural repair, production clock adoption, profile retirement or additional ISA sweep was attempted.

## Open issues

- Faithful RV32IMC now has a reproducible 9 MHz pre-layout timing pass. Production adoption still needs an explicit clock/profile decision and physical qualification; the allowance margin is small.
- Full F remains required and has not been integrated into this faithful profile. Integration needs fresh verification, timing and throughput measurements.
- Current flight throughput, the 5 MIPS requirement, whole-system 1 kHz scheduling and routed timing remain unqualified.
- The default clock, registered profiles and prior full-gate failure remain unchanged. Full T13 is not complete.
