# Task briefs

Read [../../../AGENTS.md](../../../AGENTS.md) and the assigned brief's Read first
list before work. Progress lives only in [../STATUS.md](../STATUS.md).
PLAN03 prepares T32-T38; writing a brief does not start implementation. D76
requires fast CI on main before new block work and after every task, and full
CI at each I2/I3/I4/I5 exit. Historical no-CI instructions below describe earlier
checkpoints; current progress and evidence live only in STATUS.

| ID | Brief | Dependencies | Readiness |
| --- | --- | --- | --- |
| PLAN01 | [Decision reconciliation](PLAN01-reconcile.md) | User approval conversation | Assigned documentation work |
| PLAN02 | [General-purpose MCU scope](PLAN02-general-mcu.md) | User decision D69 | Documentation only; no CI or RTL changes |
| PLAN03 | [SoC consolidation and tape-out planning](PLAN03-soc-consolidation.md) | User decisions D72–D76 | Assigned on main; ordered B1–B6; no new peripheral RTL |
| PLAN04 | [Tapeout clock/reset architecture](PLAN04-clock-reset.md) | D78/D79; production clock/wake/reset contracts | Assigned on main; acceptance unverified; implementation subset of T33 |
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
| T21 | [GPIO, timers and retained ADC](T21-flight-io.md) | T05, T07, T09, T14, T20 interfaces | User assigned functional implementations; no CI; D68 split timer services approved |
| T22 | [General-purpose PWM](T22-pwm.md) | D69, T21, T20 interfaces | User assigned continued RTL; generic PWM and request interface, DMA controller separate; no CI |
| T23 | [Basic DMA controller](T23-dma.md) | D25, D69, T22, T20 interfaces | User assigned continued RTL; contract review before implementation; no CI |
| T24 | [Limited GPIO output pin mux](T24-pinmux.md) | D39, D69, T21–T23 interfaces | Continued RTL; existing pads and sources, contract review before implementation; no CI |
| T25 | [Clocked lite core adoption](T25-lite-core.md) | D1, T06, T14, T18, T20/T24 interfaces | Continued RTL; pinned baseline first, reviewed machine/boot/bus contract; no CI |
| T26 | [Digital watchdog/reset supervision](T26-watchdog.md) | D70, T20/T22/T24/T25 interfaces | Continued RTL; external clocks retained, no CI |
| T27 | [Raw ADC acquisition](T27-adc-raw.md) | D69, T21 | Continued RTL; D71 approved raw production migration and register retirement; no CI |
| T28 | [Lite-first performance release](T28-boot-release.md) | T25/T26/T27 interfaces | Continued RTL; reviewed digital handoff from validated loader START; no CI |
| T29 | [Bounded QSPI command interface](T29-qspi-command.md) | Plans04/07, T28 interfaces | Continued RTL; reviewed command subset, no CI |
| T30 | [Native QSPI read path](T30-qspi-xip.md) | Plans03/07, T29 interfaces | Continued RTL; reviewed native read/arbitration contract; no CI |
| T31 | [Retained locked-image restart](T31-retained-loader-restart.md) | D73 | Withdrawn; recovery loader frozen, no extension without a new decision |
| T32 | [Two-hart JTAG debug](T32-jtag-debug.md) | PLAN03; T33 interface coordination | Unimplemented; acceptance unverified |
| T33 | [Clock/reset/power controller](T33-clock-reset-power.md) | PLAN03; T32/T34 interface coordination | Unimplemented; acceptance unverified |
| T34 | [Analog interfaces/models](T34-analog-models.md) | PLAN03 | Unimplemented; acceptance unverified |
| T35 | [SRAM macros and BIST](T35-sram-bist.md) | T32/T33 completed; coordinate T36 | Unimplemented; acceptance unverified |
| T36 | [Production boot ROM](T36-boot-rom.md) | T32/T33 completed; coordinate T35 | Unverified acceptance; boot-path contract prerequisite |
| T37 | [Test mode and scan](T37-test-scan.md) | T35/T36; coordinate T38 | Unimplemented; acceptance unverified |
| T38 | [Chip top and pad ring](T38-chip-top-pads.md) | T35/T36; T34 interfaces; coordinate T37 | Unimplemented; acceptance unverified |
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

## Remaining implementation order

T32 and T33 first in parallel; then T35/T36, then T37/T38. T34 may start any
time after PLAN03. Each ends with the single production top and existing system
tests. T36 explicitly resolves autonomous lite boot without extending D73's
frozen loader. Analog layout/extraction, board/silicon work and complete stage
application/FPGA acceptance need later briefs; no implicit new work is assigned.
T31 is withdrawn. D18 and chip-to-chip work remain deferred.

## Writing a new brief

State goal, Read first, inputs, May change, deliverables, executable acceptance
checks and stop conditions. Mark commands not yet run as unverified. Keep new
RTL clocked Chisel with independent tests, formal negative controls and T09
timing. Upstream verification counts only for modules formally proved
equivalent to the pinned upstream source; never for changed or new logic.
