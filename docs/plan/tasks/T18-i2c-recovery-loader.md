# T18 — Adopt the lite-domain I2C recovery loader

## Goal

An external programmer can load a compatible lite image into program memory
over I2C, verify it, request start and lock programming, and read back a
coherent result. Adopt the clocked RISCay implementation under D1. The
endpoint belongs to the lite subsystem and serves the external host even when
there is no valid lite application. T17 is the separate sensor-bus controller.

## Read first

Read AGENTS.md, the task index and tracker, plans 03, 04, 06, 07, 11–15,
the [T06 baseline](../../ledger/riscay-baseline.md), the
[bus contract](../../spec/bus.md) and the upstream sources below.

**Skills** — deadhorse-task-execution, clocked-chisel-block-design,
reference-model-testing, chisel-formal-properties and gf180-synth-timing-check.
Use formal-timeout-triage for proof budgets and regmap-authoring if defining
local registers. The external wire protocol already has an ABI.

## Inputs and adoption boundary

Use the T06 checkout at `build/riscay-mcu`, commit
`4671317186003740ceb61360ba08c59bbdf10136`. All upstream paths below are
relative to that revision. Record the upstream blob, adapted destination,
purpose and changes for every imported file or excerpt. Preserve the upstream
Apache-2.0 licence, SPDX headers and applicable notices. The new build must
work independently of the historical checkout.

| Upstream source | What to carry over or use as evidence |
| --- | --- |
| `designs/clocked/src/main/scala/riscay/clocked/ClockedI2cTarget.scala` | Open-drain target, address recognition, byte ACK, frame completion at STOP or repeated START, idle timeout and read serialization. Its stated sampling requirement is a service clock at least eight times SCL. |
| `ClockedFabric.scala` in the same directory | Trace frame dispatch, coherent read-bank capture at read address, program SRAM requests and response acceptance through the Stored command. Extract the recovery path only. Record how the original related front/work clocks made the frame and snapshot handoffs safe. |
| `ClockedSram.scala` in the same directory and `shared/src/main/scala/riscay/HostSchema.scala` | Reference the program-word completion semantics and host-visible service layout. Check the eight-word read window and its trailing supported-word mask against the fabric. |
| `ClockedControl.scala` in the same directory and `soc/src/main/scala/riscay/soc/ControlSchema.scala` | Loader command lengths, little-endian parameters, full-width bounds/compatibility checks, sequential writes, CRC, validity, start, lock and status. Identify the required shared types and constants transitively. |
| `verification/src/test/scala/riscay/SocSpec.scala` | The `ClockedSocSpec` variant drives the clocked SoC over the wires. Its upload sequence computes an independent CRC32, writes image words, verifies READY, starts/locks and tests rejection and full reset. Port the public observations. |
| `ClockedBoundarySpec.scala`, `FabricSpec.scala`, `DeepSleepSpec.scala`, `GenericBootSpec.scala` in the same test directory | References for reset/committed memory, coherent reads, wake and integration with boot. Use clocked fixtures. Upstream `I2cSpec` exercises BD/Click fixtures and cannot establish clocked-target coverage. |

## Deliverables

1. Write and review `docs/spec/i2c-recovery-loader.md` before adapting RTL.
   Enumerate the address, frame formats, command/status/error values, read
   snapshot length including supported-word metadata, reset matrix and clock
   assumptions from the pinned clocked sources. Trace each opcode to its owner.
   Identify boundaries to the boot ROM, QSPI persistence and application
   services, including the observable response when a backend is unavailable.
2. Put the adapted target, recovery control, provenance and licence under
   `hw/ip/i2c_recovery_loader/`. Expose the program-memory request/completion
   and lite start/status interfaces so a standalone fixture can exercise the
   complete transfer. Retain admission priority and count each committed word
   once. Preserve the programming lock across a bus reset/recovery sequence.
   Use D37 for reset containment and the shared CDC implementation for domain
   crossings. Specify the wake probe/retry sequence and active-clock
   requirement before relying on a host transaction during deep sleep.
3. Implement a public-wire test with an independent programmer, CRC oracle
   and memory backend able to delay completion. Begin with an invalid image,
   upload a known multiword image, verify exact bytes, entry, READY, start
   request and lock. Read status over I2C, attempt a locked mutation, then
   exercise full reset and a fresh upload. Observe each outcome from the pins,
   memory port or documented integration outputs.
4. Exercise wrong address, truncated/oversize frames, repeated START, timeout,
   changing status during a read, invalid length/entry/offset/compatibility,
   incomplete upload and bad CRC. Test reset and delayed/duplicate completion
   while writing, including the effect on stored bytes and requalification of
   the image. A negative control must demonstrate detection of actual data or
   accounting corruption. Check wake and reset at the documented boundary.
5. Add scoped formal properties for mutation admission, validated-image start,
   locked writes, and accounting on memory completion. Record assumptions,
   reachable covers, negative controls and actual proof/bound/timeout status.
   Measure GF180 timing and area under the existing T09 rules. Record which
   memory/backend components the measurement includes.

## May change

The loader IP and tests, its specification and provenance, build and CI
registration, the associated ledger entries, T18 task report and T18 tracker
row/log. Whole-chip pin routing, dual-image QSPI boot, gateway integration,
lite CPU changes and physical qualification have separate integration scope.

## Acceptance

The following are proposed implementation entry points. The implementation
must supply the aggregate driver and register it in CI. Run through the
pinned environment and retain receipts under fresh build directories.

```sh
python3 hw/ip/i2c_recovery_loader/check.py --output build/t18/check
python3 tools/ci.py --tier fast --output build/t18/ci-fast
```

The aggregate must check provenance, run the wire-to-memory recovery test,
negative controls and scoped formal jobs, and measure timing from fresh
production RTL. Record commands, results and integration limits in
`docs/plan/tasks/reports/T18.md`. T06's historical success establishes the
reference baseline. The adapted Deadhorse block needs its own evidence.

## Stop conditions

Escalate an incompatible host ABI, a reset/ownership conflict with D37, or a
required change to the approved boot policy. Record the concrete conflict
before choosing new behavior. Keep the lite-image recovery path distinct from
decisions on performance-image selection and persistent flash layout.
