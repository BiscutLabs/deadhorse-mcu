# 14 Timing design rules

Rules that keep long combinational paths out of the design, and the check
that enforces them. The FPGA prototype cannot do this job: at 12 to 24 MHz a
modern FPGA has so much slack that a path far too long for GF180 passes
without complaint. RISCay's records show the risk is real: its elapsed-time
logic has a data path of about 120 ns at the slow corner, longer than the 83
ns period of a 12 MHz clock.

**GF180 timing is the check. The FPGA is a functional prototype only.**

## The check

Every block is synthesized to the chosen GF180 library and timed at the slow
corner (SS, 125 C, 3.0 V) in CI, on every change.

| Item | Rule |
| --- | --- |
| Clock period | The `clk_main` period fixed at gate G1; until then, 41.6 ns (24 MHz) for main-domain blocks |
| Budget | A block fails if its worst register-to-register, input-to-register or register-to-output path exceeds **60 percent** of the period. The rest is reserved for wires, clock uncertainty and the SRAM's own timing |
| Scope | Each block alone, then each clock domain's top level |
| Record | Worst path per block (delay, start and end points, logic depth) in `docs/ledger/timing.md`, one row per block per change that moves it |
| Exceptions | A path over budget needs a written entry in the block README naming the path and why, and approval. A multi-cycle path is declared in the constraints and proved by a property that the destination is only sampled when valid |

These are pre-layout numbers without wire delay. They catch long logic early;
they are not signoff. Signoff timing is gate 1 in
[08-physical-verification.md](08-physical-verification.md).

The 60 percent figure and the period are assumptions until spike S1 has timed
a real core. S1 uses this same flow.

## Design rules

1. **Register block outputs.** Every output of a block comes straight from a
   flip-flop. Paths then cannot chain through several blocks, and each block
   can be timed alone. An unregistered output needs an exception as above.
2. **Break ready/valid chains.** No back-pressure signal passes
   combinationally through more than one block. Put a register stage (a
   two-entry skid buffer) at each handshake boundary, including bus-to-peripheral interfaces.
3. **Heavy operations are multi-cycle.** Multiply, divide, CRC,
   floating-point and the elapsed-time arithmetic take several cycles, by an
   iterative or pipelined implementation, never one long path. Use the
   cores' multi-cycle multiplier options.
4. **Synchronous memories only.** Design to memories that register their
   read, as the GF180 SRAM macros and FPGA block RAM both do. No register
   arrays read combinationally beyond a small size (32 words), and no logic
   between an SRAM's data output and the next flip-flop beyond a multiplexer.
5. **Bounded decode and arbitration.** Address decode, bus multiplexing and
   arbitration each fit in one cycle with the budget met; if adding a
   peripheral breaks the budget, add a register stage, do not widen the mux.
6. **One RTL for FPGA and ASIC.** The only differences are in a thin
   wrapper: clock generation, memory macros, pads and clock-gate cells. No
   FPGA-specific changes to logic, and no FPGA primitives outside the
   wrapper.
7. **Do not over-pipeline.** At these clock rates most logic meets the
   budget untouched. Add a stage because the check failed or a rule above
   requires it, not as a precaution: every stage costs area and latency.

## Paths to watch

Known candidates in this design: the performance core's multiplier and its required multicycle FPU; address decode plus bus multiplexing into SRAM setup; the elapsed-time and timestamp
arithmetic inherited from RISCay; CRC over a 32-bit word.

## Order of work

1. The per-block timing flow (T09): yosys synthesis to the
   chosen library, static timing with an open timer, a script that applies
   the budget and writes the ledger row. Proven first on RISCay's clocked
   design, whose 120 ns path it should find.
2. Wire it into CI once the Chisel build exists.
3. Spike S1 reuses it for the cores.
