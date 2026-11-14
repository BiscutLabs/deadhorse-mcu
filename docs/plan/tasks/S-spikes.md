# Measurement spikes S1 to S4

These replace assumptions with evidence for G1. D2/D19 select the Chisel
Ibex-derived core and FPU: **no alternative-core evaluation**. Measurements
qualify the selected implementation, not whether to include F.

## Common contract

Read AGENTS.md, requirements, architecture, decisions, formal/test/timing plans
and the relevant prerequisite reports before work. Use T08's pinned environment.
Changes: Chisel measurement harnesses and scripts under tools/spikes, independent
models/test inputs under dv, measurement firmware under sw/flight outside the
historical loop source, ledger and task report. Emitted RTL/results go to build/.
No new handwritten SystemVerilog. Production core changes belong to T10;
promoting other prototypes to production requires their own integration brief.

The executable interfaces below are deliverables to create in the assigned
spike, **not tools already implemented or commands verified by PLAN01**. Each
check must exercise independent behavior and reject a negative control. Record
exact tool commands, commit, inputs, corners and limits; no bounded proof may
be called unbounded. Missing required tools or failed limits block completion.

## S1 Core

**Requires:** T10 selected core/FPU, T09 timing, T02 historical workload, S3
memory model where available. No D2 selection blocker remains.

**Question:** area, achievable frequency, latency and throughput of the selected
RV32IMFC implementation on GF180 at the specified corners.

1. Map/time the core plus multicycle FPU and word-wide byte-enabled memory
   interface using gf180mcu_fd_sc_mcu7t5v0. Record area, critical paths and allowance.
2. Measure cycle-accurate fixed-point reference workload and a separate hard-float
   workload (full selected ISA/ABI). Include interrupt/FPU stall behavior; the
   historical instruction count is not a cycle count or full flight workload.
3. Measure banking/access latency and improvement hypotheses without a competing
   core bakeoff. Do not remove F to hit a target. Choose feasible main frequency
   from existing 12/24 MHz targets based on evidence.
4. Report total hot-loop deadline margin and excluded work; no fitted instruction
   average may stand in for worst-case completion evidence.

**Acceptance:**

```sh
python3 tools/spikes/s1_core/check.py --output build/s1
python3 tools/ci.py
```

Require report of area/timing/CPI and independent correctness results. Existing
gate target is at least 5 MIPS; 2.5-5 MIPS requires the documented 500 Hz fallback
and actual loop validation. Below 2.5 MIPS stop and report; do not switch cores
or lower limits. These are plan targets, not results. Final routed timing is G3.

## S2 Interconnect study

Study details have been removed.

## S3 Memory

**Requires:** T02/T07/T08; collaborate through reports with T10/S1, not circular
completion dependencies. Memory modeling can start before core cycle measurement.

1. Build separate representative firmware including interrupts, BMI270 streaming
   initialization/driver buffers, timestamped acquisition, DMA descriptors,
   actuator publication, FPU helpers and navigation. No new fixed-point-only
   constraint and no edits to historical benchmark outputs to disguise growth.
2. Report hot/cold code, stack, state and buffers for RV32IMFC at size/speed
   settings, against 16 KiB performance and 3 KiB retained lite SRAM.
3. Model boot/XIP/logging arbitration with exact flash-command/dummy-cycle and
   write-stall assumptions. Bound interference with loop work; UART/logging
   allocation and exact flash part remain board/firmware questions.
4. Validate word-wide banked access with byte enables. Report area/power evidence
   where available; no one-cycle or power-saving assertion from organization alone.

**Acceptance:**

```sh
python3 tools/spikes/s3_memory/check.py --output build/s3
python3 tools/ci.py
```

Deliver allocation/stack evidence and explicit XIP latency model. Existing
stop threshold: hot set above 12 KiB requires review before optimization.
Recommend growth only with supporting physical evidence; capacity is already
chosen as a baseline, not reopened by this spike.

## S4 Latency and test access

**Requires:** S1 and T08/T09. Test architecture approved by D8/D41; implementation
coverage and overhead remain to be measured.

1. Measure worst-case pin-to-handler latency including multicycle integer/FPU
   operations, ownership/DMA contention, and CDC. Check R-CPU-4 without weakening it.
2. Insert scan in a representative clocked block with the selected library;
   gate-level shift/capture checks, stuck-at pattern generation and coverage.
3. Exercise SRAM self-test detection with injected faults against an independent
   memory model; document algorithm and access. Plan analog calibration/test
   connectivity and explicit test-mode entry without permanent debug locks.
4. Check performance-reset containment and actuator fault signaling; whole-chip
   reset still disables outputs. No early-warning comparator assumed.

**Acceptance:**

```sh
python3 tools/spikes/s4_test/check.py --output build/s4
python3 tools/ci.py
```

Deliver latency bound, scan overhead, achieved coverage, SRAM fault-detection
results and analog test-access contract. If pattern generation cannot run,
report blocked coverage rather than calling functional tests production scan.
