# 03 Architecture

The initial MCU is entirely clocked Chisel. The approved choices are in
[10-decisions-and-risks.md](10-decisions-and-risks.md); physical feasibility
and clock frequency remain subject to measurement. No neuromorphic IP or
chip-to-chip link is included.

## Block view

## Cores and memories

The performance core is a Chisel conversion of a pinned Ibex revision, with
full RV32IMFC, machine-mode CSRs, vectored interrupts, `wfi`, debug and an RVFI
verification path. The unmodified Ibex SystemVerilog is kept under
`hw/vendor/ibex_ref/` as a reference only: the conversion is first proved
equivalent to it module by module as RV32IMC with no changes (T10/T11), and
only then is F integrated and anything improved (T12/T13). The chip does not
contain an Ibex SystemVerilog BlackBox and no alternative-core selection is
requested. Improvements should target GF180 area, timing and clock gating
without reducing ISA correctness. Their benefits must be measured.

The FPU is area-focused and multicycle, selectively reusing pinned HardFloat
Chisel components. Full F semantics include rounding modes, flags, fused
operations, subnormals, special values, comparisons and conversions. D is
excluded. Ibex has no F extension, so the FPU and its integration are new
design outside the equivalence proof and need their own verification.

RISCay's clocked RV32E core becomes the lite core with minimal interrupts/CSRs,
`wfi`, debug and local peripheral access. The historical D18 Click option is deferred
to a separate explicitly authorized brief; no async dependency enters this build.

Performance SRAM baseline is 16 KiB with word-wide access, byte-write enables
and configurable banks. Lite SRAM baseline is 3 KiB retained. Macro access
latency and any capacity increase require measurement; word-wide does not imply
single-cycle access. Cold code uses QSPI XIP; loop-critical code stays in SRAM.

## Buses and ownership

Local request/response buses retain byte masks and explicit errors. Decode is
generated from register descriptions.

| Resource | Access policy |
| --- | --- |
| Performance SRAM, XIP and actuator registers | Performance-local; authorized debug/programming access |
| Lite SRAM, wake, clock and reset control | AON-local; checked remote access |
| SPI, I2C controller, UARTs | One programmable owner at a time; ownership checked at the endpoint for local, remote and DMA requests |
| ADC player and I2C loader | Lite/AON baseline, checked remote access |
| USB FIFO interface | Gateway subsystem, checked access from both cores |

Ownership transfer must drain or cancel outstanding transfers before granting
the next owner. DMA inherits the requesting owner's peripheral and memory
permissions; it cannot bypass private-memory checks. DMA serves SPI/UART using
bounded bursts and completion/error interrupts; no linked descriptors initially.

## Clock, reset and sleep boundaries

Logical clock domains include AON, main/HF, optional USB, and JTAG TCK.
Shared peripherals can remain clocked while the performance core sleeps;
actuator reset is independent of performance reset. Final domain partitioning
must be documented at G1. Do not assert an artificial total of two crossings:
all asynchronous crossings instantiate the same reviewed CDC implementation.

The AON source is the internal nominal 32 kHz oscillator, with divided-HF
selection for bursts. Main clock comes from trimmed HF or the approved external
input through a divider and glitch-free source selection. USB has its own
external-clock-derived domain. No seamless automatic failover is implied.

Retained sleep gates the performance core. Selected SPI/I2C/UART operations may
request HF without waking it; stop HF only after all consumers release their
requests and transactions drain. UART receive mode can keep HF running;
wake-only mode may lose the first byte. Timer, event and JTAG wake are supported.
Wake requests must be observable while destination clocks are stopped.

Performance watchdog resets the performance domain, preserving AON state.
Lite watchdog, POR and brownout reset the MCU. Actuators enter configured
failsafe on either watchdog fault independently of performance reset, while
clock/supply are valid. Whole-chip reset disables outputs. See
[06-power-clock-reset.md](06-power-clock-reset.md).

## Pins and optional USB

Limited register-selectable alternate functions, not an arbitrary crossbar.
External clock/reset and JTAG retain dedicated pins; general-purpose outputs
start disabled. Freeze a map allowing all baseline interfaces simultaneously.

USB CDC-ACM uses TX/RX byte FIFOs, status/control, interrupts and wake through
reviewed CDC. The identical-port stub is replaced only after implementer
verification and physical requirements are available. UART/JTAG remain the
fallback before the Phase 3 floorplan-freeze cutoff.
