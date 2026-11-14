# Measurement spikes S1 to S4

These replace assumptions in the plan with measurements before the
architecture freezes at gate G1 ([../09-roadmap.md](../09-roadmap.md)).
Unlike the T-series briefs, most of this work needs design judgement. Each
spike says who should take it. None may be closed by weakening its question.

Common rules: no production RTL; everything a spike builds stays under
`tools/spikes/<name>/` or `build/`; each ends with a ledger entry under
`docs/ledger/` and a report under `reports/`.

## S1 Core

**Owner:** senior engineer or the strongest available model, not a
delegated lesser agent. Diagnosing why a desynchronized design is slow, and
what to change, is the judgement this spike exists for.

**Blocked on:** decisions D1 (dependency or fork) and D2 (Ibex or extended
RISCay core), and T06 (RISCay's full gate runs on a clean machine).

**Question:** can the performance core sustain 5 MIPS desynchronized on
GF180 at the slow corner (R-CPU-1)?

**What is known:**

- RISCay's generated design models a worst recurrence of 358.9 ns at
  SS/125 C/3.0 V without wire delay. RISCay's contract attributes the limit
  to the elapsed-time logic, so that number does not transfer to a
  different core.
- The control loop costs at most 2,171 instructions per iteration, of which
  about 390 are multiplies (measured, `sw/flight/loop-measurement/`).
- 5 MIPS at two to three cycles per instruction needs a 67 to 100 ns
  recurrence.
- Whether RISCay's generator accepts a netlist that did not come from its
  own Chisel export is **unknown**. That is the first thing to find out.

**Method:**

1. Map the candidate core, clocked, to `gf180mcu_fd_sc_mcu7t5v0`; record
   area and critical path at the slow corner.
2. Run the measured loop binary on a cycle-accurate simulation of that core
   for cycles per instruction, with the multiplier option under test.
3. Put the core through RISCay's bank partitioning and delay modelling.
   Record bank count, storage ratio, control share and modelled recurrence
   at all five corners.
4. Repeat steps 1 to 3 for the control case named in D2.
5. Try the SRAM word-access options in
   [../07-peripherals-memory-boot.md](../07-peripherals-memory-boot.md).

**Deliverable:** instructions per second at the slow corner for each
candidate, with the area and ratios against R-PHY-3, and a recommendation
for D2, D12 and D13.

**Gate rule:** at least 5 MIPS, proceed. 2.5 to 5, proceed at 500 Hz and
record the shortfall. Below 2.5, stop and revisit before anything else is
built.

## S2 Interconnect study

Study details have been removed.

## S3 Memory

**Owner:** a capable agent, with review of the conclusions. Needs T02.

**Question:** is 16 KiB of SRAM plus execute-in-place enough (R-MEM-1,
R-MEM-2)?

**Method:**

1. Extend the measured loop into a skeleton firmware: interrupt entry, an
   IMU read stub, the actuator commit, a UART console stub, and a
   placeholder navigation task that uses soft-float. No hardware.
2. Split sections into hot (reachable from the control interrupt) and cold.
   Report the hot-set size for RV32IMC at `-Os` and `-O2`.
3. Model flash fetch cost: random and sequential 32-bit fetches at 12 and
   24 MHz SCLK for a standard QSPI NOR read command. State the command and
   dummy-cycle assumptions.
4. Estimate the cold-code execution rate from the instruction trace of the
   navigation task and the fetch model.

**Deliverable:** hot-set size; cold execution rate; a recommendation for
D12 and whether a prefetch buffer is worth its area.

**Stop and ask:** if the hot set exceeds 12 KiB, report before optimising.

## S4 Latency and test access

**Owner:** senior engineer or the strongest available model. Blocked on S1.

**Questions:** what is pin-to-handler interrupt latency on the chosen core
at the slow corner (R-CPU-4), and what does the latch-enable test override
cost (decision D8)?

**Method:**

1. Simulate the S1 core with slow-corner delays; measure from an input edge
   to the first handler instruction, in the worst case of an interrupted
   multi-cycle instruction.
2. On one bank from S1, add the test-mode override that drives master and
   slave latch enables from two external non-overlapping clocks; confirm
   scan shift and capture in simulation; measure added area as a share of
   control area.

**Deliverable:** a latency bound; added control area; a recommendation for
D8.
