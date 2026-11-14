# Measurement spikes S1 to S4

These replace assumptions in the plan with measurements before the
architecture freezes at gate G1 ([../09-roadmap.md](../09-roadmap.md)).
Unlike the T-series briefs, most of this work needs design judgement. Each
spike says who should take it. None may be closed by weakening its question.

Common rules: no production RTL; everything a spike builds stays under
`tools/spikes/<name>/` or `build/`; each ends with a ledger entry under
`docs/ledger/` and a report under `reports/`.

## S1 Core

**Owner:** a capable agent, with review of the conclusions. With the design
entirely clocked (decision D17) this is ordinary synthesis and timing work.

**Blocked on:** decision D2 (which candidates to measure) and T07 (the
Chisel build, for the RISCay-core control case).

**Question:** how fast and how large is the performance core on GF180, and
does it sustain 5 MIPS at the slow corner (R-CPU-1)?

**What is known:**

- The control loop costs at most 2,171 instructions per iteration, of which
  about 390 are multiplies (measured, `sw/flight/loop-measurement/`).
- 5 MIPS at two cycles per instruction needs a 10 MHz clock.
- RISCay's clocked design states a 20 MHz maximum for its own work clock;
  that is a different core and is not a measurement of this one.
- No core has been mapped or timed for this project.

**Method:**

1. Map the candidate core to `gf180mcu_fd_sc_mcu7t5v0` with yosys; record
   area and cell count.
2. Run static timing at SS/125 C/3.0 V and at the typical corner with a
   wire-load allowance; record the maximum clock frequency and the critical
   path. State the allowance used.
3. Run the measured loop binary on a cycle-accurate simulation of the core
   (Verilator or Icarus) for cycles per instruction, with each multiplier
   option.
4. Repeat steps 1 to 3 for the control case named in D2, and for one
   FPU-capable core with and without its FPU (decision D19). For that core
   also run the float build of the loop (`-DNUM_FLOAT`, hard-float ABI).
5. Try the SRAM word-access options in
   [../07-peripherals-memory-boot.md](../07-peripherals-memory-boot.md) and
   report their effect on cycles per instruction.

**Deliverable:** for each candidate: area, maximum frequency, cycles per
instruction, and instructions per second at the slow corner. A
recommendation for D2, D12, D13 and the `clk_main` frequency (12 or 24 MHz).

**Gate rule:** at least 5 MIPS, proceed. 2.5 to 5, proceed at 500 Hz and
record the shortfall. Below 2.5, stop and revisit the core choice.

**Stop and ask:** if timing analysis cannot be run with the open tools on
this library, report what failed; do not substitute an estimate.

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

**Owner:** a capable agent, with review. Needs S1.

**Questions:** what is pin-to-handler interrupt latency on the chosen core
(R-CPU-4), and what does scan cost and cover in the open flow (decision D8)?

**Method:**

1. Simulate the S1 core; measure, in clock cycles, from an input edge to the
   first handler instruction, in the worst case of an interrupted
   multi-cycle instruction. Convert to time at the S1 frequency.
2. On one block (the lite core is a good size), replace flip-flops with the
   library's scan flip-flops, stitch one chain, and confirm shift and
   capture in gate-level simulation. Record added area.
3. Find out which open pattern generator works on that netlist and what
   stuck-at coverage it reports. If none does, say so.

**Deliverable:** a latency bound; scan area overhead; achieved coverage or a
clear statement that the open flow cannot generate patterns; a
recommendation for D8.
