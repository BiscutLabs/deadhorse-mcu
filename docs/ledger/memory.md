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
