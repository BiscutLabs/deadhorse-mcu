### Validation: target run vs native x86 build of the same sources

FNV-1a hash over all 9 outputs and the 4 quaternion words of every iteration (6000 iterations). Target ELF run in `rvsim` vs the same C compiled natively with hardware float / int arithmetic.

| config | numeric | mode0 | mode1 | mode2 | identical to native |
|---|---|---|---|---|---|
| A | fixed | b7988fa3 | 89989880 | 1889c5d7 | YES |
| B | fixed | b7988fa3 | 89989880 | 1889c5d7 | YES |
| C | fixed | b7988fa3 | 89989880 | 1889c5d7 | YES |
| D | float | 9eea3b6a | cb552449 | fc86ca8f | YES |
| E | fixed | b7988fa3 | 89989880 | 1889c5d7 | YES |
| F | fixed | b7988fa3 | 89989880 | 1889c5d7 | YES |
| PA | fixed | b7988fa3 | 89989880 | 1889c5d7 | YES |
| PD | float | 9eea3b6a | cb552449 | fc86ca8f | YES |

### Dynamic instructions per `control_step` call (entry through `ret`, call overhead excluded)

Iterations per mode: 2000. mean/min/max/p99 are over iterations; breakdown columns are per-call means (they sum to the mean). RVC share = fraction of retired instructions that were 16-bit encodings.


**Config A: fixed, rv32im, -O2**

| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hover | 1737 | 1494 | 1804 | 1772 | 339 | 0.0 | 218 | 114 | 100 | 966 | 52 | 0% |
| fixed-wing | 1768 | 1529 | 1774 | 1774 | 339 | 0.9 | 232 | 126 | 111 | 960 | 67 | 0% |
| transition | 2101 | 1851 | 2171 | 2145 | 391 | 1.0 | 283 | 141 | 140 | 1146 | 76 | 0% |

**Config B: fixed, rv32im, -Os**

| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hover | 1724 | 1482 | 1787 | 1754 | 325 | 0.0 | 213 | 110 | 122 | 954 | 81 | 0% |
| fixed-wing | 1751 | 1514 | 1758 | 1758 | 323 | 0.9 | 224 | 122 | 127 | 954 | 91 | 0% |
| transition | 2100 | 1852 | 2166 | 2139 | 371 | 1.0 | 279 | 138 | 167 | 1145 | 113 | 0% |

**Config C: fixed, rv32i (no M), -O2**

| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hover | 55190 | 35427 | 70689 | 70188 | 0 | 0.0 | 558 | 370 | 12622 | 41640 | 8170 | 0% |
| fixed-wing | 59450 | 36980 | 73125 | 72178 | 0 | 0.0 | 563 | 375 | 13999 | 44513 | 8976 | 0% |
| transition | 66323 | 43684 | 78227 | 74372 | 0 | 0.0 | 661 | 427 | 15414 | 49821 | 9855 | 0% |

**Config D: float (soft-float), rv32im, -O2**

| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hover | 30248 | 21922 | 32154 | 31574 | 584 | 0.1 | 2140 | 1938 | 5587 | 19999 | 3066 | 0% |
| fixed-wing | 30057 | 21739 | 30331 | 30271 | 629 | 3.6 | 2072 | 1865 | 5503 | 19984 | 2960 | 0% |
| transition | 37326 | 28480 | 39194 | 38838 | 746 | 3.9 | 2536 | 2258 | 6959 | 24823 | 3852 | 0% |

**Config E: fixed, rv32imc, -Os**

| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hover | 1728 | 1486 | 1791 | 1758 | 325 | 0.0 | 214 | 111 | 122 | 956 | 81 | 46% |
| fixed-wing | 1752 | 1515 | 1759 | 1759 | 323 | 0.9 | 224 | 122 | 127 | 955 | 91 | 47% |
| transition | 2104 | 1856 | 2170 | 2143 | 371 | 1.0 | 280 | 139 | 167 | 1147 | 113 | 48% |

**Config F: fixed, rv32imc, -O2**

| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hover | 1737 | 1494 | 1804 | 1772 | 339 | 0.0 | 218 | 114 | 100 | 966 | 51 | 41% |
| fixed-wing | 1768 | 1529 | 1774 | 1774 | 339 | 0.9 | 232 | 126 | 111 | 960 | 66 | 39% |
| transition | 2101 | 1851 | 2171 | 2145 | 391 | 1.0 | 283 | 141 | 140 | 1146 | 75 | 39% |

### Ratios of mean instructions per call (vs config A)

| config | hover | fixed-wing | transition |
|---|---:|---:|---:|
| A (fixed, rv32im, -O2) | 1.00x | 1.00x | 1.00x |
| B (fixed, rv32im, -Os) | 0.99x | 0.99x | 1.00x |
| C (fixed, rv32i (no M), -O2) | 31.78x | 33.62x | 31.56x |
| D (float (soft-float), rv32im, -O2) | 17.42x | 17.00x | 17.76x |
| E (fixed, rv32imc, -Os) | 1.00x | 0.99x | 1.00x |
| F (fixed, rv32imc, -O2) | 1.00x | 1.00x | 1.00x |

### Per-stage mean instructions per call: Config A (fixed, rv32im, -O2) with stages forced `noinline`

Stage = instructions executed inside the stage function; libgcc helpers (soft-mul/soft-float) are charged to the calling stage. `glue` = `control_step` body itself (call setup, zero-init, branches).

| stage | hover | fixed-wing | transition | hover (mul) | transition (mul) |
|---|---:|---:|---:|---:|---:|
| imu_scale | 57 | 57 | 57 | 6 | 6 |
| filters | 339 | 339 | 339 | 66 | 66 |
| estimator | 438 | 438 | 438 | 119 | 119 |
| attitude | 218 | 218 | 218 | 44 | 44 |
| rate_hover | 214 | 0 | 214 | 30 | 30 |
| hover_mix | 143 | 0 | 144 | 22 | 22 |
| fw | 0 | 365 | 365 | 0 | 52 |
| tilt_sched | 33 | 31 | 33 | 4 | 4 |
| blend | 102 | 102 | 102 | 22 | 22 |
| output | 251 | 251 | 251 | 18 | 18 |
| glue | 94 | 86 | 99 | 0 | 0 |
| **total** | **1890** | **1888** | **2261** | | |
| (non-profiled config A mean, stages inlined) | 1737 | 1768 | 2101 | | |

### Per-stage mean instructions per call: Config D (float soft-float, rv32im, -O2) with stages forced `noinline`

Stage = instructions executed inside the stage function; libgcc helpers (soft-mul/soft-float) are charged to the calling stage. `glue` = `control_step` body itself (call setup, zero-init, branches).

| stage | hover | fixed-wing | transition | hover (mul) | transition (mul) |
|---|---:|---:|---:|---:|---:|
| imu_scale | 968 | 968 | 967 | 24 | 24 |
| filters | 6076 | 6077 | 6075 | 132 | 132 |
| estimator | 9336 | 9342 | 9338 | 228 | 228 |
| attitude | 4082 | 4276 | 4261 | 76 | 88 |
| rate_hover | 3716 | 0 | 3710 | 52 | 52 |
| hover_mix | 2615 | 0 | 3023 | 37 | 41 |
| fw | 0 | 5579 | 5612 | 0 | 94 |
| tilt_sched | 411 | 479 | 590 | 0 | 8 |
| blend | 1364 | 1410 | 1802 | 20 | 44 |
| output | 1803 | 2013 | 2097 | 16 | 36 |
| glue | 141 | 139 | 152 | 0 | 0 |
| **total** | **30512** | **30283** | **37627** | | |
| (non-profiled config D mean, stages inlined) | 30248 | 30057 | 37326 | | |

### Static size (loop + helpers only; harness, init and scenario data excluded)

Method: link `control_step.o` alone with `-Wl,-e,control_step --gc-sections -lgcc`, so only reachable code (including libgcc helpers) is counted.

| config | .text (bytes) | of which libgcc helpers | .rodata | undefined libgcc symbols pulled in |
|---|---:|---:|---:|---|
| A (fixed, rv32im, -O2) | 5636 | 0 | 4 | - |
| B (fixed, rv32im, -Os) | 4928 | 0 | 4 | - |
| C (fixed, rv32i (no M), -O2) | 8376 | 356 | 4 | __mulsi3, __muldi3, __divsi3, __hidden___udivsi3, __udivsi3, __umodsi3, __modsi3 |
| D (float (soft-float), rv32im, -O2) | 10944 | 4536 | 352 | __addsf3, __divsf3, __gesf2, __gtsf2, __lesf2, __ltsf2, __mulsf3, __subsf3, __fixsfsi, __floatsisf, __clzsi2 |
| E (fixed, rv32imc, -Os) | 3810 | 0 | 4 | - |
| F (fixed, rv32imc, -O2) | 4512 | 0 | 4 | - |

Note: for rv32imc builds (E, F) any libgcc helpers come from the toolchain's non-compressed `rv32im` multilib, so they are not compressed; fixed-point E/F pull in none.

### Static RAM (same for fixed and float: every field is 32-bit or smaller)

| object | bytes |
|---|---:|
| `state_t` total (params + dynamic state) | 780 |
| of which `params_t` (tunables; flash-initialised, runtime-writable) | 548 |
| of which dynamic filter/estimator/PID state | 232 |
| `inputs_t` | 52 |
| `outputs_t` | 18 |

### Stack

`-fstack-usage` frame of `control_step` (callee frames of helpers that were not inlined added separately), and peak stack depth observed by the simulator during any measured call (SP at entry minus lowest SP, includes libgcc helper frames).

| config | control_step frame (static) | other non-inlined frames in control_step.c | static upper bound (control_step + largest callee) | observed peak, hover / fw / transition |
|---|---:|---|---:|---|
| A | 208 | - | 208 (+ libgcc leaf frames, see observed) | 208 / 208 / 208 |
| B | 208 | lut16:0, pid_axis:0 | 208 (+ libgcc leaf frames, see observed) | 208 / 208 / 208 |
| C | 304 | - | 304 (+ libgcc leaf frames, see observed) | 320 / 320 / 320 |
| D | 256 | - | 256 (+ libgcc leaf frames, see observed) | 288 / 288 / 288 |
| E | 208 | lut16:0, pid_axis:0 | 208 (+ libgcc leaf frames, see observed) | 208 / 208 / 208 |
| F | 208 | - | 208 (+ libgcc leaf frames, see observed) | 208 / 208 / 208 |

Frames with stages kept separate (PA build): stage_imu_scale:0, stage_estimator:48, stage_attitude:48, stage_output:32, stage_fw.constprop.isra:48, stage_blend.isra:0, stage_filters:48, stage_tilt_sched:0, stage_rate_hover.constprop:16, stage_hover_mix.constprop:16, control_step:192

### Required MIPS for config A (fixed-point, rv32im, -O2)

MIPS = instructions per iteration x loop rate / 1e6. This is *instruction* throughput; see the CPI note in the report.

| basis | instr/iter | 500 Hz raw | 500 Hz x2 | 1 kHz raw | 1 kHz x2 |
|---|---:|---:|---:|---:|---:|
| worst-mode mean (transition) | 2101 | 1.05 | 2.10 | 2.10 | 4.20 |
| worst-mode p99 (transition) | 2145 | 1.07 | 2.15 | 2.15 | 4.29 |
| absolute max single iteration (transition) | 2171 | 1.09 | 2.17 | 2.17 | 4.34 |

Same for the other configs, worst-mode mean and absolute max (raw, 1 kHz / 500 Hz):

| config | worst mean | 500 Hz MIPS | 1 kHz MIPS | worst max | 500 Hz MIPS | 1 kHz MIPS |
|---|---:|---:|---:|---:|---:|---:|
| A | 2101 | 1.05 | 2.10 | 2171 | 1.09 | 2.17 |
| B | 2100 | 1.05 | 2.10 | 2166 | 1.08 | 2.17 |
| C | 66323 | 33.16 | 66.32 | 78227 | 39.11 | 78.23 |
| D | 37326 | 18.66 | 37.33 | 39194 | 19.60 | 39.19 |
| E | 2104 | 1.05 | 2.10 | 2170 | 1.08 | 2.17 |
| F | 2101 | 1.05 | 2.10 | 2171 | 1.09 | 2.17 |

### Cycle sensitivity (ASSUMPTION-BASED illustration, not measured)

The simulator counts instructions, not cycles. If the CPU is not single-cycle-per-instruction, the clock needed is higher than the MIPS above. Illustrative CPI models applied to config A's measured category counts (worst mode mean):

| model | cycles/iter | 1 kHz MHz needed | 500 Hz MHz needed |
|---|---:|---:|---:|
| ideal: every instruction 1 cycle | 2101 | 2.10 | 1.05 |
| mul 3, div 34, load 2, taken branch/jump +2 | 3350 | 3.35 | 1.67 |
| mul 1, div 34, load 2, taken branch/jump +2 | 2568 | 2.57 | 1.28 |
