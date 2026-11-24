# Memory measurement ledger

S3 base commit `e6aa266` plus authenticated working sources. Executed in the
pinned environment with `python3 tools/spikes/s3_memory/check.py --output build/s3`:
**PASS, measured 72.288 s**. Exact commands and child receipts are in
`build/s3/result.json`. Independent review completed. Final local fast tier
`python3 tools/ci.py --tier fast --output build/s3-ci-fast-01` passed all 29 jobs
in measured 1187.791 s, with the four inherited T14 proofs explicitly deferred
and unproved. Full tier not run. The aggregate was followed only by README
placement/padding clarification; executable inputs stayed unchanged, and final
CI includes that documentation.

| Evidence | Result | Qualification |
| --- | --- | --- |
| Main RV32IMFC `-Os` | Measured hot code 4,828 B, constants 964 B, mutable 3,696 B; estimated stack 688 B and SRAM 10,176 B | Representative workload; excludes 152 B sensor-model RAM, retains model/observer code; real HAL/full firmware absent |
| Main RV32IMFC `-O2` | Measured hot code 5,324 B, constants 964 B, mutable 3,688 B; estimated stack 640 B and SRAM 10,616 B | Same scope; both below 12 KiB review threshold; baseline 16 KiB unchanged |
| Lite RV32E size/speed | Estimated SRAM 648/664 B from measured code/state and stack evidence | CRC/chunk/wake subset only; not complete retained image |
| BMI270 init | Measured 8,192 B cold payload, 128 x 64 B upload, actual driver init/enable/read paths | Unmodified pinned Bosch source/config; modeled SPI device, not bench validation |
| Firmware faults | Four compiled faults rejected for intended config/sample/publication/CRC reasons | Independent observable-value/publication checker; control dynamics not requalified |
| Word banks | 18 configurations, 17,406 measured model transactions, all 16 masks; 4 faults rejected | Proposed organization only; assumed 1/2/5-edge latency; no RTL/macro qualification |
| Flash interference | Estimated 221 us serial / 93.5 us quad bound equals exhaustive modeled arrival-edge maximum | Assumed command table/SCLK; max 256 B nonpreemptible transfer; no silicon bound |
| Logging | Modeled 38.4 MB/no drops over 600 s arrival stream plus final drain; erase stress 372 counted drops | Pre-erased region, 64 B at 1 kHz, four-record page batching, one 64 B XIP read/s; priority XIP can starve logs |
| Flash faults | Missing dummy, unbounded burst, busy-bus hold rejected | Arithmetic/scenario oracle independent of event scheduler |
| Physical SRAM | No new area/power/timing evidence | Inherited footprint estimate only; no macro/signoff claims |

Hot code is a sum of reachable ELF function sizes, not a placed hot section;
alignment padding and actual SRAM/XIP relocation remain integration work.
Candidate working set = hot code + conservative constants + mutable bytes +
reserved stack. Stack reserves a conservative hot call chain and one full
trap/handler with main live; observed main peak 448 B is not a universal bound.
Cold initialization error paths, nesting and complete firmware remain open.

The shared logging model/firmware allocation is 2,048 B queue plus 256 B staging.
The aggregate rejects missing/read-only buffer symbols, inconsistent sums,
changed capacity baselines and unreported threshold exceedance. No formal
proof, hardware timing or flight qualification is claimed by these models.
See the [report](../plan/tasks/reports/S3.md) for assumptions and detailed numbers.

## T35 production SRAM and destructive self-test

Base `ad3bb201` plus receipt-hashed T35 sources; pinned-environment commands
and full limitations are in [T35](../plan/tasks/reports/T35.md).
D90 restricts verification to SRAM/BIST and affected integration, with no CI
tier and explicit deferral of expensive timeout proofs.

The production binding uses sixteen byte macros for performance SRAM and four
for retained SRAM, with only 768 retained words exposed. Logical capacities,
normal bus/register maps and latency stay unchanged. Canonical pinned views
include five paired timing corners; vendor models are functional-only and
their initialization is never relied upon.

| Evidence | Result | Qualification |
| --- | --- | --- |
| Independent arrays, all rows/masks, full March traversal and five cell/address fault models | 12 SRAM/BIST Scala cases pass in `campaign02/unit.log` | Full 4096/768-word operation oracles; five full-size read-path faults return correct DMI address/data/phase, including all four performance banks and retained RAM |
| Affected integration and production TAP | 31 Scala cases and all four TAP scenarios pass | Memory/boot/sleep plus BIST, ordinary debug, independent reset and in-flight reset; final source/evidence binding in `build/t35/publication-audit.json` |
| ASIC byte/address/control input wiring | Unbounded pin proof, covers and wrong-lane fault pass | One physical word-bank binding; not macro Q behavior or full-SoC bank selection |
| Eight-word March control | Unbounded proof, early-completion fault and good/bad completion covers pass | Full production sizes are separately simulated; no unrestricted full-size formal claim |
| Full-depth data/latency | Unresolved at measured 121.131 s / 120 s solver cap | D90 deferred; full/partial write/read covers pass; no unchanged retry |
| Full-size independent-clock BIST ownership | Unresolved at measured 121.129 s / 120 s solver cap | D90 deferred; missing-reset-hold fault rejected, main and remote covers reached; whole-top mux/CDC/RDC remains simulation-backed |
| Fixed and hard-float production workloads before/after deep wake | PASS, exactly unchanged T39 cycles | Fresh DUT/model simulation with authenticated target-checksum references; not silicon or full ISA qualification |
| Five-corner production mapping/timing | Measured worst main 69.186501 ns / 75 ns; zero slew/cap and gate-enable violations in both strap modes | Verified 140 non-inverting SRAM-load buffers; physical clock pulse/hold/reset/rail closure remains open |
| Chip area | Estimated 12.699799240 mm2 / 12.92 mm2, headroom 0.220200760 mm2 | Measured standard-cell areas, pinned LEF dimensions and named unchanged allowances; not placed fit |

Always-powered normal-rail sleep relies on the pinned vendor's CEN-high
standby-state guarantee and operating limits. No reduced-voltage, power-off or
brownout data retention is promised. Physical qualification, scan and pad-level
validation remain signoff work; this ledger closes no I5 gate.
