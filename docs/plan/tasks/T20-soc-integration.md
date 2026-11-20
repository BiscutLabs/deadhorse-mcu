# T20 Reference SoC integration, stages I0 and I1

## Goal

Build the reference SoC top in Chisel with the blocks that exist, as stages
I0 and I1 of [16-soc-integration.md](../16-soc-integration.md). Every block
that does not exist yet is a stub with its final ports. Establish the single
machine-readable SoC description, the generated address decode and
interrupt map, the SoC system tests, and the first whole-chip measurements.
Later block briefs replace their own stubs; this task does not wait for them.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../16-soc-integration.md](../16-soc-integration.md)
- [../03-architecture.md](../03-architecture.md),
  [../06-power-clock-reset.md](../06-power-clock-reset.md),
  [../07-peripherals-memory-boot.md](../07-peripherals-memory-boot.md)
- [../../spec/bus.md](../../spec/bus.md),
  [../../spec/gateway-protocol.md](../../spec/gateway-protocol.md),
  [../../spec/regmap-format.md](../../spec/regmap-format.md)
- [../13-test-environment.md](../13-test-environment.md),
  [../14-timing-design-rules.md](../14-timing-design-rules.md)
- Block READMEs and reports for T13–T19 and S3, including their open issues
  and deferred proofs

**Skills** — deadhorse-task-execution, clocked-chisel-block-design,
regmap-authoring, reference-model-testing, chisel-formal-properties,
gf180-synth-timing-check, formal-timeout-triage.

## Inputs and readiness

Requires T05, T07, T09, T13 (faithful RV32IMFC production profile as it
stands; its open integration proof stays open), T14–T19 and S3. Commands
below are interfaces to create, not yet run.

Not decided, and not to be decided here: the main clock source and frequency
(Q15) and the loop-rate target (Q16). Parameterize the main frequency and
report results at both 8 MHz and 9 MHz.

## May change

`docs/spec/soc.md` (new), `hw/top/reference/` (SoC top, `soc.yaml`,
generators, emitters, tests), `hw/top/stubs/` (new stubs),
`dv/soc/` (system tests, models, check script), `sw/boot/` and `sw/hal/`
(minimal boot and test firmware only), `sw/include/` generated-header
tooling, `tools/ci.py` registration, the timing and area ledgers, this
task's report and its own STATUS row and log. Block RTL under `hw/ip/` may
change only for a connection defect found by integration, each recorded
with a test; any behaviour change stops the task (see below).

## Deliverables

1. **`docs/spec/soc.md` first, then review.** The contract for: address
   regions (start from the bus contract's table), bus masters and targets per
   domain, the local memory path, interrupt assignment, clock and reset
   domains, reset release order, stub behaviour, and the provisional pin list.
   Obtain independent review before writing RTL.
2. **`hw/top/reference/soc.yaml`.** The machine-readable form of that
   contract. A generator produces fabric region parameters, the interrupt
   map, a C header for firmware and a Markdown table for the spec. A check
   fails if the spec table and generated table differ, if regions overlap,
   or if any block's register map does not fit its window.
3. **Local memory path.** Core instruction and data ports reach the boot ROM
   model and performance SRAM model with Ibex's native grant and response
   timing, outside the fabric. Peripheral and remote windows go through the
   fabric. The SRAM model has the word-wide, byte-enable, banked interface
   chosen for the macros in S3, with configurable read latency.
4. **Stage I0.** Core, boot ROM model loaded from a firmware image, SRAM
   model, main fabric, one UART. Firmware prints over UART in simulation.
   Run the existing core lockstep suites with the core inside the SoC, not
   standalone, and show they still pass.
5. **Stage I1.** Add SPI, I2C, all three UARTs, mailbox and domain bridge,
   the AON bus with a retained-SRAM model and the I2C recovery loader, and
   USB. USB is the stub by default; the real T19 block is a build variant
   with one loopback test. A lite-core stand-in (a bus-master model in the
   test bench) drives the AON side until the lite core exists.
6. **Stubs** for timers, actuator, GPIO/pin mux, interrupt routing beyond
   the fixed map, DMA, QSPI/XIP, JTAG, power/clock/reset and the lite core.
   Each has its final port list as far as the approved contracts define it,
   errors every access in its window, holds outputs reset-safe and drives
   interrupts and wake inactive. Record each stub in `soc.yaml`.
7. **SoC system tests** in `dv/soc/` through the four-target interface, run
   on the simulation target: boot and UART print; SPI read of an independent
   BMI270 model; I2C read of an independent barometer model; mailbox round
   trip; recovery load over I2C; bus errors for every stubbed and unmapped
   window; reset of each domain in turn with the bus contract's
   peer-reset behaviour; interrupt delivery for every connected interrupt.
   Each test has a negative control.
8. **SoC-level formal** on the generated top: address decode is disjoint and
   complete against `soc.yaml`; every interrupt source reaches its assigned
   input; reset release order matches the spec. Block internals are not
   re-proved. A structural check enumerates every clock-domain crossing and
   rejects any not built from the shared CDC primitives.
9. **Measurements**, each labelled measured or estimated:
   - mapped area per block and whole SoC (main and AON separately);
   - worst path per clock domain at 8 and 9 MHz under the 60% rule;
   - flight-loop cycles per iteration (mean and worst, fixed point and hard
     float) running from the SoC's SRAM model through the local memory path,
     compared with the T13 round-2 figures. Use the same workloads as the
     T13 round-2 measurement; the S1 performance script it used is not on
     `main` as of 2026-11-20, so either commit it under S1 first or write
     `dv/soc/performance.py` with the same workloads and a negative control;
   - the rebuilt chip area budget for
     [../08-physical-verification.md](../08-physical-verification.md),
     with unbuilt blocks as named, labelled allowances.

## Acceptance checks

Proposed interfaces, **not yet run**:

```sh
python3 hw/top/reference/check_soc_map.py
python3 tools/sbt.py "hw/testOnly deadhorse.top.*"
python3 dv/soc/check.py --stage i1 --output build/t20/soc
python3 dv/core/lockstep.py --soc --isa rv32imfc --suite arch,flight-float --output build/t20/lockstep
python3 dv/soc/performance.py --main-mhz 8,9 --output build/t20/performance
python3 tools/timing/check.py --top DeadhorseSoc --domains main,aon --output build/t20/timing
python3 tools/ci.py --tier fast
```

Report the fast tier result and state the full tier status. Inherited
deferred proofs from T14, T17 and the open T13/T19 items are listed, not
waived.

## Stop and ask

- Integrating a block needs a change to its behaviour, its register map or
  its verified interface.
- Flight-loop cycles on the integrated memory path are more than 10% above
  the T13 round-2 worst figures, or the local memory path cannot keep Ibex's
  native timing.
- Any clock domain misses the 60% rule at both 8 and 9 MHz.
- The address map, interrupt map or pin list cannot satisfy every approved
  interface at once.
- The SoC area budget exceeds the 12.92 mm2 core area with the named
  allowances included.
- A choice is needed on Q15 or Q16.

## Out of scope

New peripheral blocks, the lite core, power/clock/reset control, boot ROM
content beyond a test program, JTAG, DMA, the pad ring, physical layout,
FPGA build and analog work. These belong to the block briefs listed in
[16-soc-integration.md](../16-soc-integration.md).
