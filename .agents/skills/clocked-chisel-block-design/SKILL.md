---
name: "clocked-chisel-block-design"
description: "Use when writing or reviewing clocked Chisel RTL for the Deadhorse MCU: new blocks, handshakes, clock-domain crossings, clock gating, reset, or wrapping vendored SystemVerilog."
---

# Clocked Chisel block design (Deadhorse)

Deadhorse is an entirely clocked, synchronous MCU on GF180MCU, written in
Chisel. The FPGA prototype and the ASIC use the same RTL. The usual failure is
RTL that works on the FPGA and cannot close timing, or cannot be tested, on
GF180. These rules prevent that.

Read the repository's `AGENTS.md` and the task brief first. Where they and
this skill disagree, they win. The source documents are
`docs/plan/03-architecture.md`, `06-power-clock-reset.md` and
`14-timing-design-rules.md`.

## Before writing any RTL

1. **Check for something to adopt.** The brief names blocks to reuse. Do not
   rewrite adopted Verilog or SystemVerilog: pin it under `hw/vendor/<name>/`
   and instantiate it through a Chisel `BlackBox`.
2. **Write the block's README contract first:** ports and protocol, which
   clock domain, reset behaviour, an area estimate, status. One page.
3. **Write the register description** if the block has registers. Decode is
   generated from `hw/ip/<block>/<block>.regmap.yaml`; never hand-write it.
4. **Decide the clock domain.** There are three: always-on (`clk_aon`), main
   (`clk_main`), USB (`clk_usb`). A block lives in exactly one.

## Structure rules

| Rule | Do | Do not |
| --- | --- | --- |
| Registered outputs | Drive every output from a register (`RegNext`, `RegEnable`, or a queue's output register) | Let an input reach an output through logic only |
| Handshakes | Use `Decoupled`. Put a two-entry skid buffer (`Queue(x, 2)`) at each boundary: bus to peripheral, network interface to hub, hub port to hub port | Chain `ready` combinationally through more than one block |
| Heavy arithmetic | Make multiply, divide, CRC, floating point and wide timestamp arithmetic iterative or pipelined | Put a 32-bit multiply or a 64-bit compare-and-add in one cycle |
| Memories | Use `SyncReadMem` or the SRAM wrapper; allow at most a mux between memory data-out and the next register | Use `Mem` (combinational read) for more than 32 words |
| Decode and arbitration | Keep them single-cycle and small; add a register stage when a new peripheral breaks the timing budget | Widen a mux tree to make room |
| Storage | Flip-flops only | Latches as storage, handshake controllers, matched delays, chisel-async |
| Pipelining | Add a stage when the timing check fails or a rule above requires it | Pipeline as a precaution: every stage costs area and latency |

Payload registers that are always written before they are read do not need a
reset. Control and valid bits always do.

## Clock-domain crossings

There are only two crossings in the chip: always-on to main (at the lite
core's network interface) and main to USB (at the USB FIFOs).

- **Use the project's one crossing block.** Never write a synchronizer
  inline. If the crossing block does not exist yet, stop and ask.
- **Never synchronize a multi-bit value bit by bit.** Multi-bit data crosses
  through the asynchronous FIFO, or is held stable under a synchronized
  single-bit request.
- **A signal from another domain must not feed logic before it is
  synchronized,** including reset logic and clock-gate enables.
- **Both sides of a crossing reset together,** or the crossing has an explicit
  flush. A reset on one side alone must not corrupt the other.
- If your block seems to need a third crossing, stop and ask. That is an
  architecture change.

## Clock gating and clock control

- Gate a clock only with the library's integrated clock-gating cell, wrapped
  in the project's clock-gate module so the FPGA build can substitute a
  clock-enable. Never AND a clock with a signal.
- A gate's enable is registered in the gated clock's own domain.
- Do not create new clocks, dividers or muxes inside a block. Clock control
  lives in the always-on domain's controller.
- Count time (baud rates, pulse widths, timeouts) in clock cycles of the
  block's own domain. Do not build delay lines.

## Reset

- Asynchronous assert, synchronous release, through the domain's reset
  synchronizer. In Chisel use an `AsyncReset` domain where the brief says so.
- State the reset value of every control register in the README.
- The actuator block's failsafe logic keeps its own reset and an ungated
  clock so it runs while the rest of the main domain is in reset. Do not
  merge reset domains to simplify.

## FPGA and ASIC stay one design

- All differences live in a thin wrapper: clock generation, memory macros,
  pads, the clock-gate cell.
- No FPGA primitives, vendor attributes or `ifdef`-style forks in block RTL.
- **FPGA timing passing says nothing about GF180.** Only the per-block GF180
  timing check counts (see the `gf180-synth-timing-check` skill).

## Black-boxing vendored SystemVerilog

- The Chisel `BlackBox` declares exactly the vendored module's ports; put
  any adaptation in a Chisel wrapper around it, not in the vendored file.
- Give the black box explicit `clock` and `reset` ports; it does not get
  Chisel's implicit ones.
- Record the upstream commit in the vendor lock file. Changes are patches.

## Before you call it done

1. Outputs registered, or each exception written in the README with a reason.
2. No combinational `ready` path through the block (check the emitted
   Verilog, not just the Chisel).
3. Block tests pass against an independent reference model, with one
   negative control.
4. Formal properties written and run (see the `chisel-formal-properties`
   skill), or the README says why formal does not apply.
5. The GF180 timing check is within budget, or an approved exception exists.
6. Nothing generated is committed; emitted Verilog is under `build/`.

## Stop and ask

- You need a latch, a new clock, a new crossing, or a combinational output.
- The timing budget cannot be met without changing the block's interface.
- A vendored block needs an edit to work.

## Status of this skill

The rules come from the project plan. The Chisel build for this project had
not been run when this was written, so no code pattern here has been compiled
in this repository. Treat API names as a guide and check them against the
pinned Chisel version.