# Clock-gate boundary

Status: T11 shared-wrapper addition approved 2026-11-15; scoped digital binding,
phase simulation and mapped pre-layout timing checks pass, independently reviewed.

`ClockGate` has `clk_i`, `en_i`, `test_en_i`, and `clk_o`. All belong to one
clock domain. It performs no CDC or synchronization. The parent supplies
domain-safe controls; the Ibex parent retains its existing busy register and
debug/interrupt wake controls. There is no reset pin or reset state. A low
clock phase establishes the captured enable before clock output is used.

ASIC target instantiates `gf180mcu_fd_sc_mcu7t5v0__icgtp_1`, with E=en_i,
TE=test_en_i, CLK=clk_i and Q=clk_o. It captures either enable while the input
clock is low and holds that decision throughout the high phase. Changes to
either enable during the high phase must neither truncate nor start a pulse.
Test enable opens the gate through the same capture mechanism.

The verification binding uses Chisel's pinned CIRCT ClockGate intrinsic with
explicit compiler flags selecting the immutable reference primitive. It checks
the wrapper's connection and test-enable logic, not an independently generated
CIRCT latch. ASIC pin mapping and pulse behavior are separately checked against
the unchanged, hash-verified GF180 UDP cell model using pinned Icarus. The
primitive's low-phase latch represents the ICG, never general data storage.
No handwritten Verilog is used.
Digital simulation/proof cannot establish analog glitch immunity or setup/hold
signoff at the physical cell.

`FpgaClockEnable` is the explicit FPGA substitution: unchanged input clock and
`enable_o` for consumer register clock-enables. It is a distinct interface so
it cannot silently replace a gated clock while dropping the consumer enable.
Every consumer must use enable_o on all state updates (asynchronous reset
remains independent). No FPGA fabric clock AND is permitted. Board clock
buffer selection belongs in the later board wrapper.

Area estimate: one ICG × 61.4656 um2 = 61.4656 um2, from the pinned SS library
cell's area attribute. This excludes clock-tree buffers and wiring and is not
a mapped core-area measurement. Clock latency and enable setup/hold are checked
separately from data-path timing; do not apply a data-path exception to the core.

Formal contracts: enable capture/hold and output equality to the reference gate,
no assumptions on enable or test-enable, equal captured state as the induction
relation. Negative controls must detect disabled test bypass and inverted enable.
Simulation checks transitions within both clock phases against an independent
phase model and rejects a corrupted observed output. FPGA enable usage is
checked at consumer register boundaries; it is not waveform equivalence of
the ungated FPGA clock to the ASIC gated clock.

FPGA evidence qualifies the example enabled-register consumer only. Core-wide
CE conversion and board mapping must use that contract before claiming FPGA
core equivalence. Dedicated ICG measurement with `clock_gate_timing.py`, base
`a532304` plus working changes, gives 1.896664 ns worst CLK-to-Q propagation,
0.624586 ns minimum enable setup/hold slack, and zero electrical violations
at the pinned SS/125C/3.0V corner, assumed 0.5 ns slew and 0.05 pF load.
Receipts: `build/t11/clock_gate/timing` and independent reproduction at
`build/t11/clock_gate/independent2/timing`. These are single-cell pre-layout
results, not clock-tree or core timing signoff.
