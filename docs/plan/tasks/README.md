# Task briefs

Read [../../../AGENTS.md](../../../AGENTS.md) and the assigned brief's Read first
list before work. Progress lives only in [../STATUS.md](../STATUS.md).
PLAN01 is documentation only; no other task is started by this revision.

| ID | Brief | Dependencies | Readiness |
| --- | --- | --- | --- |
| PLAN01 | [Decision reconciliation](PLAN01-reconcile.md) | User approval conversation | Assigned documentation work |
| T08 | [Pinned Linux environment](T08-environment.md) | None | Brief ready; commands not yet run |
| T01 | [Scaffold and CI](T01-scaffold.md) | T08 | After pinned environment |
| T02 | [Historical flight-loop CI](T02-flight-loop-ci.md) | T01, T08 | Historical workload only |
| T03 | Interconnect study | n/a | Withdrawn by D43 |
| T04 | Interconnect study | n/a | Withdrawn by D43 |
| T06 | [RISCay baseline](T06-riscay-baseline.md) | T01, T08 | Full clean gate still unverified |
| T07 | [Clocked Chisel build](T07-chisel-build.md) | T01, T06, T08 | Rewritten; direct Chisel, no async dependency |
| T05 | [Register generator](T05-regmap-generator.md) | T07 | Format fixture; actuator ABI deferred |
| T09 | [GF180 timing flow](T09-timing-flow.md) | T01, T06, T07, T08 | New brief; commands not yet run |
| T10 | [Ibex reference and harness](T10-ibex-reference.md) | T07, T08 | Pin Ibex revision and parameters first |
| T11 | [Ibex conversion](T11-ibex-conversion.md) | T10, T09 | Equivalence-checked; no changes |
| T12 | [FPU](T12-fpu.md) | T07, T09 | New design; parallel with T10/T11 |
| T13 | [F integration](T13-core-f-integration.md) | T11, T12 | Improvements only after F passes |
| S1 | [Selected core measurement](S-spikes.md#s1-core) | T13, T09, T02 | Not a core selection exercise |
| T14 | [Bus, bridge and mailbox](T14-bus-mailbox.md) | T07, T09 | Write `docs/spec/bus.md` first |
| T15 | [UART peripheral](T15-uart.md) | T05, T07, T09, T14 | User assigned standalone peripheral implementation; core optimization deferred |
| T16 | [SPI host](T16-spi-host.md) | T05, T07, T09, T14, T15 | User assigned standalone SPI controller; core optimization deferred |
| T17 | [I2C controller](T17-i2c-host.md) | T05, T07, T09, T14, T16 | User assigned next serial peripheral; controller only, retained loader separate |
| T18 | [Lite I2C recovery loader](T18-i2c-recovery-loader.md) | T06, T07, T09, T14 | Pinned clocked adoption and end-to-end recovery test brief ready |
| T19 | [USB CDC-ACM](T19-usb.md) | T05, T07, T08, T09, T14 | User assigned adoption; source assessment must resolve vendor timing/CDC exceptions before production integration |
| T20 | [Reference SoC integration, I0–I1](T20-soc-integration.md) | T05, T07, T09, T13, T14–T19, S3 | Write `docs/spec/soc.md` first; Q15/Q16 stay open |
| S2 | Interconnect study | n/a | Withdrawn by D43 |
| S3 | [Memory](S-spikes.md#s3-memory) | T02, T07, T08 | Modeling can precede S1 |
| S4 | [Latency/test](S-spikes.md#s4-latency-and-test-access) | S1, T08, T09 | Architecture approved; coverage unmeasured |

## Evidence inherited from initial planning

The original plan reports a successful RISCay Python baseline and firmware
bootstrap and historical flight-loop reproduction.
Those results were not rerun by PLAN01. Maven Central blocked the original
Scala/build verification. The historical QEMU off-by-one issue remains T02's
work; no test failure was fixed by editing this plan.

All newly specified commands in T07-T14, T20 and S1-S4 are explicitly unverified until
those tasks run. A written acceptance command is not an implemented tool.
Missing tools cannot be skipped to claim success.

## Further briefs still required

SoC integration now has a plan ([../16-soc-integration.md](../16-soc-integration.md))
and a brief for its first two stages (T20). Block briefs still required, in
the order the SoC stages need them: timers and timebase; actuator block
(final ABI after policy tests); interrupt routing and GPIO/pin mux; RISCay
lite-core adoption; power/clock/reset controller and watchdogs; boot ROM,
QSPI flash and XIP; JTAG debug for both cores; DMA; analog macro layout and
threshold controls; physical-flow/pad-ring import; production test and
board/silicon integration. Each new block brief ends by replacing its stub
in the reference SoC and passing the SoC system tests. Prepare these from the
approved contracts before assigning implementation. T19 owns the supplied USB digital implementation and
its adoption assessment; USB electrical and shuttle qualification remain open.
D18 and chip-to-chip work are deferred.

## Writing a new brief

State goal, Read first, inputs, May change, deliverables, executable acceptance
checks and stop conditions. Mark commands not yet run as unverified. Keep new
RTL clocked Chisel with independent tests, formal negative controls and T09
timing. Upstream verification counts only for modules formally proved
equivalent to the pinned upstream source; never for changed or new logic.
