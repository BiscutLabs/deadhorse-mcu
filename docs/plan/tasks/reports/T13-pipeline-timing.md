# T13 performance-core pipeline timing study

## Outcome

The faithful RV32IMFC core's worst mapped path fell from 65.726219 to
64.389893 ns with 0.239% more whole-core cell area. The selected change
parallelizes ALU operand selection in the existing decode/execute stage.
Every instruction retains its previous cycle behavior.

## What changed

`hw/ip/perf_core/src/main/scala/deadhorse/perf_core/IbexIdStage.scala`
computes the condition for each ALU data source directly. Previously an LSU
increment modified multiple encoded selectors, one selected an immediate, and a
later mux chose between the immediate and the register operand. The faithful-F
implementation now combines mutually exclusive choices in one select per
operand. A split memory access still selects the last LSU address and an
increment of four. Instruction length still selects two or four for a PC
increment. The other core configurations retain their existing datapaths.

### Research and five hypotheses

The pinned Ibex places register reads, decode, execution and register writeback
in one stage. Its documentation identifies stalls on multicycle instructions
and redirects. OpenHW's four-stage CV32E40P uses forwarding to avoid stalls on immediate arithmetic
dependencies. An immediate consumer of a load can still stall. The RISC-V encoding keeps register indices in fixed locations to
shorten operand decode and supports sign extension in parallel with decode.
These observations suggested moving or simplifying selects before adding a
new pipeline stage. [Ibex pipeline](https://github.com/lowRISC/ibex/blob/38c070939183cc10940b66c8e9e04eeca6b65470/doc/03_reference/pipeline_details.rst)
[CV32E40P pipeline and hazards](https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/latest/pipeline.html)
[RISC-V base instruction formats](https://docs.riscv.org/reference/isa/v20240411/unpriv/rv32.html)

1. Decode the integer register-file read address into one word select per
   register. Sharing those selects across the bits of a word could reduce
   the cost of two indexed reads and shorten operand access.
2. Decode register, immediate, PC and split-LSU operand sources in parallel.
   This could remove serial control muxes in the ID-to-ALU path. The select
   conditions must remain exclusive and cover reserved immediate encodings.
3. Translate a decompressed FP instruction to the integer-shaped instruction
   in IF and capture it alongside the raw word. This could shift static work
   out of ID. Rounding and FS checks must use live architectural state in ID.
4. Keep translation in ID but select raw fields, register indices and the
   replacement opcode independently. This could avoid a wide late mux while
   preserving compressed and illegal instruction behavior.
5. Decode FLW and FSW directly from opcode, width and FS. This could remove
   unrelated arithmetic legality from the memory and operand selection paths.

## Checks run

Measurements used base `d75ce89` and the production ASIC and RVFI model views
of each individually emitted Chisel variant. Commands below run with the
pinned prefix `python tools/env/run.py run --`. Paths beginning with `$B`
refer to `build/pipeline-study`. Receipts and the experimental Scala
snapshots are retained there. The workload replay used the pre-existing
local S1 measurement script and baseline receipt. The unmodified core's
model manifest also matched the archived T18 fast run.

| Command after the pinned prefix | Result or final output |
| --- | --- |
| `python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitFaithfulFloatCore $B/<trial>/emit"` | Fresh ASIC and model views for baseline and each trial. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted $B/<trial>/emit/asic --operating-point main-9mhz --output $B/<trial>/timing` | Baseline and all five isolated trials passed. Selected output: `PASS DeadhorsePerfCore: 64.389893 ns, budget 66.666667 ns; electrical violations 0`. |
| `python3 hw/ip/perf_core/formal/package_candidate.py --float --top $B/h2/emit/model --leaves build/t18/ci-fast/fast/leaves --core build/t18/ci-fast/fast/core --output $B/h2/candidate` | `PASS packaged Chisel candidate: rv32imfc-faithful-v1; inactive alternatives explicitly listed`. Baseline packaged with the same arguments against its own model. |
| `python3 dv/core/revision_equiv.py --before $B/baseline/candidate --after $B/h2/candidate --output $B/h2/revision` | `PASS revision equivalence: whole top, no added assumptions, all fault controls rejected`. Whole-top named-state induction includes every output and next state. |
| `python3 dv/core/equiv.py --unchanged-since t11-baseline --candidate $B/h2/candidate --output $B/h2/unchanged` | Exit zero, 12 unchanged modules proved with fault controls. |
| `python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.*"` | 60 core tests; `All tests passed.` |
| `python3 dv/core/lockstep.py --candidate $B/h2/candidate --isa rv32imfc --suite arch,random,flight-float --output $B/h2/lockstep` | `PASS selected F lockstep suites`. Includes seeded mixed-ISA streams and 191201 hard-float workload retirements against QEMU. |
| `python3 tools/spikes/s1_core/performance.py --candidate $B/h2/candidate --output $B/h2/performance-replay` | `blocked_throughput_floor`, exit 1. Both workload binaries, full retirement cycle streams, per-iteration results and architectural comparisons match the previous S1 result. An earlier attempt timed out in QEMU while concurrent jobs were running; preserved under `$B/h2/performance`. |
| `python3 hw/ip/perf_core/check_top_timing.py --emitted $B/h2/emit/asic --operating-point main-9p6mhz --output $B/h2/timing-9p6` | FAIL at 64.389893 ns against the 62.500000 ns budget. |
| `python3 tools/ci.py --tier fast --output $B/ci-fast` | `PASS fast tier active checks; 12 deferred, unproved (see receipt)`. All 33 commands returned zero. The four T14 and eight T17 deferrals remain recorded. |

The selected model digest is `86810b0f4e6c7a07ba3a2a6972ccaffc7b6fa83c64ae60ab2256a08339d33a89`.
An independent check of the two emitted ALU operand cones compared both
32-bit outputs over all 256 selector combinations and arbitrary source data,
preserving the bit aliases in the emitted design. It rejected
a stuck operand bit. Fast CI independently emitted the same candidate and
reproduced its mapped delay and area. The archived verification receipts
include `$B/h2-review/result.json` and `$B/ci-fast/result.json`.

## Numbers

Measured pre-layout with GF180MCU 7t5v0 at SS, 125 C and 3.0 V, pinned
Yosys 0.71+34 and OpenSTA 3.2.0. All rows use the same faithful core,
integer and FP register files, multicycle FPU, ASIC gate, ideal clock and
mapping constraints. SRAM macros, placement and wire delay are outside
this measurement. The assumed 9 MHz trial gives a 66.666667 ns budget
under the 60% rule. The comparison uses the worst path over all checked
path classes. The 5% area ceiling is derived as 839962.5472 x 1.05 =
881960.6746 um2.

| Trial | Measured worst delay (ns) | Mapped cell area (um2) | Derived area change |
| --- | ---: | ---: | ---: |
| Original faithful RV32IMFC | 65.726219 | 839962.5472 | +0.000% |
| 1. Decode register-file word selects in parallel | 64.477959 | 814050.4064 | -3.085% |
| 2. Select ALU operands in parallel | 64.389893 | 841971.1552 | +0.239% |
| 3. Translate FP instructions before the IF/ID register | 64.100388 | 841431.1360 | +0.175% |
| 4. Translate independent instruction fields in parallel within ID | 64.552521 | 848951.8912 | +1.070% |
| 5. Decode FP memory operations separately from arithmetic legality | 65.302170 | 840752.8192 | +0.094% |

The selected path runs from IF instruction bit 22 to integer register-file
bit 991 (`_64088_/Q` to `_61821_/D`). The derived reduction is
65.726219 - 64.389893 = 1.336326 ns, or 2.033%. The one-hot RF read is
an area-saving alternative, 0.088066 ns slower than the selection. Its
whole-top revision proof passed. An additional comparison of its integrated
RF leaf with the standalone Ibex reference found a port-inventory mismatch.
A separate standalone RF diagnostic was stopped during SAT and remains
unproved. Neither leaf check is evidence for the selected operand change.

Pairing register-file read selection with hypotheses 2, 3, 4 and 5
measured 68.806030, 69.317017,
67.471382 and 68.225632 ns respectively. Each missed the 9 MHz
allowance. Changes in the mapped worst path make isolated gains
nonadditive. The faster single IF retiming has equivalent transitions once
the first instruction is captured. An independent SAT witness found its
unreset translation payload can change three externally visible address or
data outputs before first fetch while both bus requests are low. The
selected change preserves these outputs as well.

## Deviations from the brief

This is the assigned timing improvement within T13. The comparison retains
the approved 9 MHz trial and the existing area and timing methodology.
Earlier T13 formal deferrals remain open. The complete ISA sweep and
standard full CI tier were outside this timing study.

## Open issues

The hard-float S1 baseline still achieves a derived 1.090122 MIPS at the
assumed 9 MHz trial against the 2.5 MIPS floor. Its ideal-memory worst loop
still takes 14233 cycles; the fixed-point worst loop takes 4350 cycles.
Closing at a higher clock or reducing FPU instruction latency is separate
work. Production frequency requires routed timing and memory integration.
