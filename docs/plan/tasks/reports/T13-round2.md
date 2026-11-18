# T13 round 2 — faithful-core area and timing

## Outcome

Keep the registered-owner shared multiplier and compatible FPU register reuse. On the unchanged production mapping target of 62,500 ps, area falls from **829,781.2096 to 814,627.7440 µm²** and worst delay moves from **64.258347 to 64.831543 ns**. That leaves 0.335124 ns to the study guard band. The hard-float loop takes **7,778.83 mean / 8,973 worst cycles**, down from **12,338.67 / 14,233**. Fixed-point cycles are unchanged.

| Candidate | Core µm² | Block saving µm² | Best / slowest worst path (ns) | Fixed cycles mean / worst | Hard-float cycles mean / worst | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| Unchanged | 827,891.1 | — | 63.225658 / 66.465706 | 3,879.8 / 4,350 | 12,338.7 / 14,233 | Reference |
| P3 shared MAC | 819,887.4 | +8,120.0 | 66.074554 / 66.555038 | 3,879.8 / 4,350 | 7,778.8 / 8,973 | Misses guard |
| P5 register reuse | 813,602.6 | +8,675.4 | 64.856171 / 66.718857 | 3,879.8 / 4,350 | 12,338.7 / 14,233 | Qualifies alone |
| P3 + compatible P5 | 814,597.0 | +12,486.3 | 64.751656 / 67.296249 | 3,879.8 / 4,350 | 7,778.8 / 8,973 | **Keep** |
| H1 interleaved | 812,522.5 | +16,336.7 | 67.131447 / 67.209984 | 3,879.8 / 4,350 | 12,338.7 / 14,233 | Misses guard and spread |
| H1 four banks of eight | 813,334.8 | +17,100.6 | 66.658653 / 66.658653 | 3,879.8 / 4,350 | 12,338.7 / 14,233 | Misses guard and spread |
| H4 shared adder | 826,264.5 | +1,857.1 | 66.723824 / 66.732292 | 3,879.8 / 4,350 | 12,338.7 / 14,233 | Misses guard, spread and area |
| P5 + four banks | 804,547.4 | +25,528.0 | 66.962448 / 67.057526 | 3,879.8 / 4,350 | 12,338.7 / 14,233 | Misses guard and spread |
| P3 + P5 + four banks | 805,052.3 | +29,641.8 | 68.309135 / 68.309135 | 3,879.8 / 4,350 | 7,778.8 / 8,973 | Misses guard and spread |
| WB1 diagnostic | 850,293.2 | -15,482.7 | 63.752048 / 66.606766 | 3,471.1 / 3,888 | 12,009.0 / 13,863 | Superseded, area grows |
| WB1 corrected | 842,019.4 | -15,129.3 | 67.858757 / 67.858757 | 3,471.1 / 3,888 | 12,009.0 / 13,863 | Reject on timing, area and IRQ |

## What changed

The faithful RV32IMFC core connects the existing signed integer MAC to the FPU. ID holds an FP arithmetic instruction until its response or cancellation. The FPU’s registered busy bit owns the MAC for that transaction. Four unsigned 12-bit partial products replace the serial significand multiply. The accumulator already holds the final product, so only P5’s saved-addend reuse applies. A dedicated shared-multiplier regression joins the regular fast tier. The production parameter enables sharing only on the faithful floating-point profile.

## Checks run

All 33 commands passed in 2195.7 s, including the shared-multiplier regression and production faithful-F STA. 12 inherited, unproved deferrals. Full CI did not run. QEMU lockstep and all 184,380 T12 vectors passed on the retained hardware.

<details>
<summary>Commands, proof scope and negative controls</summary>

Measurements use base `f4155b0e42429040e40ffa8c5e4d4ffe34746762` plus each isolated Chisel variant. The retained emission is identified by the production sources in this commit. Commands below ran in the pinned environment with `python tools/env/run.py run --`. Raw source hashes, commands, netlists, traces and receipts are under `build/r2/<trial>/`.

| Check | Measured result |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulFloatCore <emit>"`, then `python3 scratch/r2_measure.py <trial> <target>` and `python3 scratch/r2hier.py <trial>` | 55 flat and 55 hierarchical maps. All 55 flat STAs reported zero slew/capacitance violations and passed all eight clock-gate checks. |
| `python3 scratch/r2_owner.py <trial>` and the integrated ownership monitors | Before changing RTL, 43,003 FP issues and 18,720 integer claim edges over 1,504,427 hard-float clock samples had zero collisions. An injected collision failed. With the shared MAC, the same FP requests produced 109,436 MAC partials. |
| `python3 scratch/r2_mac_equiv.py`, `python3 scratch/r2_p5_proof.py base p5` and `python3 scratch/r2_p5_proof.py p3 p3p5` | Integer MAC outputs and next state proved equal with FP owner low and remaining inputs free. Three faults rejected. The FPU register reuses passed unbounded phase-dependent induction with arbitrary input, cancel and reset. Corrupt next-sum faults failed. |
| `python3 dv/core/revision_equiv.py --before <reference> --after <candidate> --output <revision>` | Both bank layouts, H4 and both bank combinations passed whole-top cycle equivalence to their respective parents, including the fault controls. |
| `python3 dv/core/lockstep.py --candidate <candidate> --isa rv32imfc --suite arch,random,flight-float --output <out>` | Both shared-MAC variants passed 57 arch cases, two seeded streams, the 191,201-retirement flight case and eight fault controls. Fresh QEMU trace generation used a repository-relative RAM mount to meet the original timeout. |
| T12 `dv/fpu/sim.cpp` on the actual coupled MAC/FPU and original vectors, plus ownership, cancel and reset tests | Both shared-MAC variants passed **184,380** result/flags/backpressure vectors. Add/sub/mul/fused maximum fell from 38 to 18 cycles. The integrated core passed reset and NMI at all four partials and the held-response and integer-resumption checks passed. |
| `python3 tools/spikes/s1_core/performance.py --candidate <candidate> --output <out>` | The existing workspace S1 script (SHA-256 70db65017b05720b4a341fd460f7a3e64807a43cd81dcb6e1d72a346d4584d84) measured 120 iterations per workload. The accepted core's fixed and hard-float architectural comparisons and negative controls passed. Hard-float throughput rose from 1.090122 to 1.729135 MIPS at 9 MHz and remains below S1’s 2.5 MIPS floor. |
| `python3 dv/core/equiv.py --unchanged-since t11-baseline --candidate <candidate> --output <out>` | PASS unchanged modules: 10 proved with fault controls. Changed-module obligations remain separate. |
| `python3 tools/ci.py --tier fast --output build/r2/ci-fast` | All 33 commands passed in 2195.7 s, including the shared-multiplier regression and production faithful-F STA. 12 inherited, unproved deferrals. |

The normal production emitter reproduced all 26 ASIC files and all 26 model files byte-for-byte. The registered integer and registered floating-point profiles reproduced their previous ASIC and model outputs. Independent review checked production source identity, MAC arithmetic and owner timing, all area/delay receipts, loop windows, QEMU comparisons and fault controls.

</details>

## Numbers

All areas and paths above are measured pre-layout on GF180 7t5v0, SS/125 °C/3.0 V with ideal clocks and wires. The same five ABC targets were applied to every variant. No independent seed is exposed. The worst path is the maximum over six path classes at each target. The baseline’s 63.225658–66.465706 ns spread was **3.240048 ns**. Its 824,883.7184–829,781.2096 µm² area spread was **4,897.4912 µm²**.

The selection uses the fastest run in each set, then smaller area and lower target to break ties. The selected combination saves **13,294.1312 µm²** in the flat core and **12,486.2976 µm²** in changed blocks. The FPU and FloatExecution save 14,742.9632 and 105.3696 µm² respectively, while the integer MAC grows by 2,362.0352 µm². Its 1.525998 ns increase is within the baseline spread, and 64.751656 ns meets the 65.166667 ns guard. Local block area sums exclude child instances and compare the same target on each side. The baseline local spread was 140.4928 µm² for the shared-MAC group and zero for standalone P5, either bank or H4. P5 alone saves another 994.4256 µm² versus the retained combination, but keeps the original hard-float cycle count.

<details>
<summary>Every mapping run, with area in µm² and worst delay in ns</summary>

| ABC target (ps) | 60000 | 61250 | 62500 | 63750 | 65000 |
| --- | --- | --- | --- | --- | --- |
| Unchanged | 827891.1424 / 63.225658 | 827891.1424 / 63.225658 | 829781.2096 / 64.258347 | 825731.0656 / 65.140976 | 824883.7184 / 66.465706 |
| P3 shared MAC | 819887.4432 / 66.074554 | 819887.4432 / 66.074554 | 819887.4432 / 66.074554 | 819887.4432 / 66.074554 | 816985.3888 / 66.555038 |
| P5 register reuse | 813602.5856 / 64.856171 | 813602.5856 / 64.856171 | 813602.5856 / 64.856171 | 821489.9392 / 65.574730 | 814366.5152 / 66.718857 |
| P3 + compatible P5 | 814597.0112 / 64.751656 | 814597.0112 / 64.751656 | 814627.7440 / 64.831543 | 812689.3824 / 65.522522 | 811328.3584 / 67.296249 |
| H1 interleaved | 814594.8160 / 67.209984 | 814594.8160 / 67.209984 | 814594.8160 / 67.209984 | 814594.8160 / 67.209984 | 812522.5472 / 67.131447 |
| H1 four banks of eight | 813334.7712 / 66.658653 | 813334.7712 / 66.658653 | 813334.7712 / 66.658653 | 813334.7712 / 66.658653 | 813334.7712 / 66.658653 |
| H4 shared adder | 825948.3904 / 66.732292 | 825948.3904 / 66.732292 | 825948.3904 / 66.732292 | 825948.3904 / 66.732292 | 826264.4992 / 66.723824 |
| P5 + four banks | 804547.3856 / 66.962448 | 804547.3856 / 66.962448 | 804547.3856 / 66.962448 | 804547.3856 / 66.962448 | 806125.7344 / 67.057526 |
| P3 + P5 + four banks | 805052.2816 / 68.309135 | 805052.2816 / 68.309135 | 805052.2816 / 68.309135 | 805052.2816 / 68.309135 | 805052.2816 / 68.309135 |
| WB1 diagnostic | 850293.1584 / 63.752048 | 850293.1584 / 63.752048 | 848923.3536 / 64.226868 | 845061.9968 / 65.535294 | 844236.6016 / 66.606766 |
| WB1 corrected | 842019.4496 / 67.858757 | 842019.4496 / 67.858757 | 842019.4496 / 67.858757 | 842019.4496 / 67.858757 | 842019.4496 / 67.858757 |

The WB1 diagnostic preceded a correction to the debug CSR write strobe. WB1 corrected is the version that passed reference equivalence. Each entry uses the production timing flow with only `tools.timing.check.mapping_target_ps` set to the column value. To reproduce on the retained design, emit the faithful ASIC view and call the following inside the pinned environment.

```python
from pathlib import Path
from unittest.mock import patch
from tools.timing import check

sources = sorted(str(p) for p in Path("build/r2/ci-fast/fast/faithful-float-emit/asic").glob("*.sv"))
for target in (60000, 61250, 62500, 63750, 65000):
    with patch.object(check, "mapping_target_ps", return_value=float(target)):
        check.measure("DeadhorsePerfCore", sources, "clk_i", f"build/recheck/{target}",
                      operating_point="main-9mhz")
```

Hierarchical maps use the same Liberty, constraints and ABC script with `read_slang --keep-hierarchy` and `stat -liberty`. A hierarchy-preserving map supplies block attribution. Flat top-level mapping supplies the acceptance area.

</details>

<details>
<summary>Path classes and endpoints</summary>

All worst paths were register-to-register (RR). The launch column names the fetched instruction register as instruction. The class codes IR, RO, IO, RG and IG mean input-to-register, register-to-output, input-to-output, register-to-gate and input-to-gate. Register captures are labelled with the Q net of the destination flop. Each comparison uses the baseline at the same target.

| Candidate | Target (ps) | RR launch → capture | Logic stages | Classes with a different launch or capture |
| --- | --- | --- | --- | --- |
| Unchanged | 60000 | instruction[0] → integer RF[669] | 66 | Reference |
| P3 shared MAC | 60000 | instruction[28] → integer RF[351] | 74 | RR, IR, RO, IO, RG, IG |
| P5 register reuse | 60000 | instruction[30] → integer RF[863] | 68 | RR, RO, IO |
| P3 + compatible P5 | 60000 | instruction[2] → integer RF[862] | 62 | RR, IR, RO, IO |
| H1 interleaved | 65000 | instruction[1] → x31[31] | 77 | RR, IR, RO, IO |
| H1 four banks of eight | 60000 | instruction[0] → x1[29] | 62 | RR, IR, RO, IO, RG, IG |
| H4 shared adder | 65000 | instruction[0] → integer RF[767] | 73 | RR, IR, RO, IO, RG |
| P5 + four banks | 60000 | instruction[1] → x30[31] | 71 | RR, IR, RO, IO, RG |
| P3 + P5 + four banks | 60000 | instruction[0] → x30[31] | 74 | RR, RO, IO |
| WB1 diagnostic | 60000 | instruction[31] → WB forward[31] | 71 | RR, IR, RO, IO, RG, IG |
| WB1 corrected | 60000 | instruction[27] → ID intermediate[65] | 79 | RR, IR, RO, IO, RG |

At 60,000 ps the retained design’s RR depth went from 66 to 62 stages. The IR path from fast IRQ[0] moved from fetch-address word 15 bit 0 to word 13 bit 3 (29.650494 → 29.638685 ns). RO moved from instruction bit 0 → address bit 24 to bit 5 → bit 30 (47.475586 → 48.299740 ns). IO moved from IRQ[0] → address bit 3 to bit 14 (25.728605 → 24.230520 ns). RG and IG still ran from MIE[0] and IRQ[0] respectively to the core clock-gate enable (17.322472 → 14.952568 ns and 15.284134 → 12.958228 ns). Registering ownership removes the fetched opcode from the MAC owner select. Ordinary decode still launches the longest path to the integer register file.

</details>

**Writeback pipeline.** Only `WritebackStage` changed in the isolated reference configuration (SHA-256 `18a5ffc165b10f0e83e5d0e8b3f88f05fc2f5f1a59d6c82ffe8d42895eea21ff`). T10/T11 named-state induction proved the integrated integer core against unmodified Ibex, including RVFI, 226 state elements and four rejected faults. The faithful-F ASIC matches the proved-source emission. The corrected design’s 79-stage worst path crosses the operand-B forwarding mux from instruction bit 27 through FP source selection and integer multiply to ID intermediate bit 65. Its mux input/output arrived at 17.727768/19.050474 ns. At the same 60,000 ps target, the integer RF-to-operand/result cone lengthened from 58.397888 to 58.672245 ns. The extra writeback stage saved cycles on both loops but increased area and missed guard and allowance at all targets.

WB1 passed arch, flight-float, all T12 vectors, and directed integer/FP multiply, cancel and reset. The mixed seed `dead1301` diverged at retirement 268 after an interrupt-triggering store. One extra younger instruction retired before the handler. A directed FDIV timer case saved PC 0xB8 instead of 0xB4. Upstream Ibex WB1 reproduced the interrupt ordering. We stopped the pipeline experiment at this point.

**FP register and load/store area.** On the unchanged baseline, at all five targets the measured FP bank with common write and three registered reads is **163,764.1152 µm²**, including 1,024 bank bits and 96 read-stage bits. With FLW write selection it measures **164,690.4896 µm²**. The ID load-commit predicate is **46.0992 µm²**. Matched core shells measure **6,041.1904 − 4,713.0944 = 1,328.0960 µm²** attributable to FP memory decode, substitution and routing. The estimated subtotal is **166,064.6848 µm²** (164,690.4896 + 46.0992 + 1,328.0960). The shared integer LSU is excluded. Zfinx and no-F need their own netlists to establish actual savings.

## Deviations from the brief

P1b’s optional unity bypass seeded the last iteration of the retired serial multiplier. It has no corresponding iteration in the four-part MAC. H4 missed the delay-spread veto and its area gain is inside whole-core noise, so the bank combinations omit it.

## Open issues

The original 62,500 ps minimum-delay report shows **−0.975158 ns** removal slack from rising `rst_ni` to `_59052_/RN` on the DCSR cause flop `u_ibex_core.cs_registers_i._GEN_13[6]`. Its gated clock pin is `_59052_/CLK`. Arrival is 0 ns and required release is 0.975158 ns. Existing gates enforce the six maximum-delay classes, clock-gate enable/test-enable setup and hold, and electrical limits. Reset removal is printed without a pass criterion. Closure needs a specified release relationship for each clock domain, an implemented async-assert/synchronized-release scheme with a running clock, and reset-tree recovery/removal checks across corners with post-CTS delays. T13’s deferred formal acceptance and the S1 throughput floor remain open.
