# Production SoC

PLAN03 consolidates the existing blocks into one `DeadhorseSoc` under D72.
The current contract and profile history are in
[soc.md](../../../docs/spec/soc.md). Production includes the actual lite hart,
boot release, watchdogs, PWM/DMA, pinmux and native QSPI/XIP. USB is real by
default; `usb-stub-test` is a named simulation substitution. `SocMinimalI0`
is a named minimal boot/performance fixture. ADC is unassigned under D74.
No new peripheral is implemented by consolidation.

```sh
python tools/env/run.py run -- python dv/soc/prepare_production.py
python tools/env/run.py run -- python tools/sbt.py "hw/runMain deadhorse.top.EmitSoc build/plan03/soc-production-8 production 8"
```

These are preparation/emission commands, not acceptance claims. PLAN03 results
are tracked in STATUS. D76 requires fast CI on main and full CI at integration
stage ends; old no-CI notes below are historical. Clock/power/analog/JTAG,
production boot firmware, memory macros and physical qualification remain open.

## Historical integration notes

The following predates PLAN03. Its optional profiles are superseded by D72;
historical measurements retain their original fixture and source scope.

The optional I1 assembly now connects all three UARTs, SPI/I2C hosts, main/AON
fabrics and bridges, local mailbox views, retained SRAM and recovery loader.
USB defaults to an error target; the real USB variant has an independently
reset application slot. `DeadhorseSoc` retains I0 as its default configuration;
`EmitSocI1` selects the complete I1 binding explicitly. No peripheral RTL changed.

Focused I1 checks exercise native bus/pin interfaces, including CPU boot,
serial chip-ID fixtures, recovery I2C loading, CRC rejection, retained byte lanes,
mailbox routing, owner denial, interrupt wiring and USB-reset timeout recovery.
The [formal scope](formal/README.md) distinguishes control proofs from RAM data
integrity and whole-chip CDC/reset acceptance. Commands and qualifications are
in the [T20 report](../../../docs/plan/tasks/reports/T20.md).

```sh
python tools/env/run.py run -- python3 dv/soc/prepare_i1.py
python tools/env/run.py run -- python3 tools/sbt.py "hw/runMain deadhorse.top.EmitSocI1 build/t20/i1/fresh soc stub"
# Substitute usb for stub for the real T19 variant.
```

The I1 assembly now also has a USB wire/MMIO echo test using the unchanged T19
host, including enumeration, lost-ACK replay, IRQ routing and new wake from a
stopped main clock. Directed bridge resets cover both crossing directions,
after source acceptance and after destination dispatch. A full-core test resets
the core with an offered UART write and verifies its retained side effect plus
successful reboot. Actual corrupt wiring is rejected by the same oracles.

These are native-interface composition checks, not gateway/four-target system
acceptance. Full composition/CDC inventory, physical pin fit and fresh I1
multi-domain timing/area remain open. D67 numbers below
belong to I0 and must not be reused as I1 measurements. Fast and full CI remain
unrun by user instruction; changes remain local on main. Run the added suites
with `hw/testOnly deadhorse.top.SocI1UsbSpec deadhorse.top.SocI1ResetSpec deadhorse.top.SocI1CoreResetSpec`
through the pinned `tools/sbt.py` command.

The inactive QSPI, actuator, JTAG, IMU DRDY, GPIO, ADC and timer logical ports
are bound in both complete I1 variants. The [stub contract](../stubs/README.md)
lists safe values, output enables and the static-output exception. Inputs
have no functional consumers; JTAG is not a debug master. Port widths are
checked against generated YAML metadata during elaboration. The completed
provisional contract reserves three GPIO and four shared capture/compare timer
pins, plus ADC MISO/SCLK/CS. Estimated simultaneous allocation is 40 output-capable
and 10 input-only functions against the historical 40/12 slot; no sharing is
assumed. The checker rejects missing/renamed/mis-sized functions and overflow.
This is not physical pin-fit acceptance. No new functional peripheral RTL is
introduced; all new outputs/enables remain inactive and their MMIO windows error.

D65 extends the experiment to current-request arbitration under contention.
The candidate grants one current request per cycle, with a client-reset
round-robin preference initially favoring instruction. Each accepted request
favors the other client next. Data must be neither busy nor returning a reply.
Responses, MMIO drainage and reset scopes stay registered and unchanged.
Grant outputs alone have the approved combinational exception. Fourteen
focused simulations and the unchanged eleven-property control proof pass.
Fresh performance measures worst 4,350 fixed / 9,007 hard-float cycles, within
the unchanged limits; commands and source-bound evidence are in the T20 report.
The initial measured request/grant paths reach 51.692348 ns, within both trial
budgets. The subsequent reset buffer trees remove electrical violations and
pass all measured hold/recovery/removal checks. XOR-balanced mapping improves
worst RR to 70.011482 ns (an RVFI capture); the functional integer RF subset is
69.443718 ns. Both still miss the 9 MHz budget. This observation-enabled I0
diagnostic excludes SRAM/ROM macro timing and area; it is not the standalone
trace-off ASIC core boundary. Commands and evidence are in the T20 report.
The D65 candidate remains local and uncommitted. D66's approved MAC carry
experiment proved exactly equivalent and passed 26 focused simulations and
both unchanged performance limits. It worsened measured RR to 79.044106 ns
by preventing fused MAC compression, so the original core RTL was restored
byte-for-byte. Commands, source-bound receipts and independent review are in
the T20 report. No CI, timing waiver or clock choice was made.

D67's matched unchanged-MAC synthesis control subsequently passes the integrated
8/9 MHz logic screens: measured RR 66.563103 ns, zero electrical/hold/reset
violations, area 1,112,314.4256 um2. These come from `timing/logic_timing.py`
and reset-buffer export on `72bcfac` plus the source-hashed D65/D67 tree;
receipts are `build/t20/fused-mac/control`. The flow checkpoints coarse synthesis,
isolates/reinserts the original MAC and reversibly namespaces private names
before the same fine synthesis and ABC recipe. Exact graph restoration is
checked. The two alternative compressor mappings are not retained: FA gains
only 0.137070 ns over the control and needs its arithmetic proof; 4:2 fails
9 MHz. This resolves the measured logic-screening failure without RTL changes.
Memory macros, wire parasitics, physical qualification and remaining T20
integration/acceptance are still open; no CI or clock decision.

D64 authorized an experiment allowing the currently instruction-owned slot to
serve a data request immediately when there is no current instruction request.
Only the grant outputs receive a combinational exception: input request signals
may affect instruction.gnt/data.gnt; service state, arbitration under contention,
responses and MMIO drainage remain registered. The epoch-ready, registered
instruction ownership and dataBusy guards must all permit donation. A current
instruction request prevents donation. Independent reset, fairness, data and
performance checks and integrated GF180 request-to-grant/memory timing plus a
combinational-loop check are required before retaining the experiment. The
baseline trace has no observed data-wait edge with instruction.req low, so no
performance benefit was predicted for that preserved execution. The experiment
is now rejected and archived: the workload remains at measured worst 4,821
cycles, and formal found donation overlapping a registered MMIO response.
Baseline arbitration was restored at that checkpoint. The subsequent D65
candidate above remains unqualified; the report preserves both experiments.

The [contract](../../../docs/spec/soc.md) defines the first integration stages.
`soc.yaml` is the provisional machine-readable map, clock/reset inventory,
trusted-origin and fast-interrupt assignments, and initial logical pin groups.
Q15/Q16 remain open. AON's 1 MHz option is an assumed already-running test
service profile, not an implemented clock-source change or startup guarantee.

The preserved I0 deliverable is description validation plus the Chisel assembly:
faithful RV32IMFC core, boot ROM, banked SRAM, local arbitration,
retained MMIO slot, main fabric and UART0. Firmware checks SRAM byte writes
and a floating-point multiply, then prints through the UART pin in simulation.
The existing `EmitHello` remains only a build fixture. Physical pin-ring
assignment (including clock/reset and test access) and target-interface
transport remain implementation work. The RTL and
firmware consume generated JSON/C configuration. This focused boot test is
not the brief's gateway-based system acceptance or core lockstep suite.

I0 requires an externally running main clock. `clockHold` is UART-only demand,
not whole-top permission to stop that clock. Client-only reset retains and
drains old MMIO before admitting a new core epoch. Service reset resets both
the hub and fabric/UART; neither reset clears SRAM. ROM and RAM are synchronous
models, not physical macros. Read latency and bank count are elaboration parameters.

Run through the pinned environment, without invoking CI:

```sh
python tools/env/run.py run -- python3 hw/top/reference/check_soc_map.py
python tools/env/run.py run -- python3 -m unittest discover -s hw/top/reference -p test_soc_map.py -v
python tools/env/run.py run -- python3 dv/soc/prepare_i0.py
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.top.SocMemorySpec deadhorse.top.SocBootSpec"
python tools/env/run.py run -- python3 hw/top/reference/formal/check_memory.py --output build/t20/formal-control-fresh
```

The checker validates existing peripheral register maps, checks domain-visible
address ranges and interrupts against the spec tables, and emits `soc.h`, `SocMap.scala`,
`soc-map.md` and `soc.json` under `build/t20/map/`. Logical memory capacity is
not necessarily a power-of-two fabric aperture: retained SRAM remains exactly
3 KiB; its I1 4 KiB fabric aperture rejects the extra 1 KiB at the memory
endpoint. The description preserves the true capacity separately from that
aperture and does not claim a physical SRAM implementation.

Tests mutate the configuration to check overlap, wrap, bad origins/domains,
missing register descriptions, register overflow, interrupt collision/drift,
duplicate YAML keys, spec drift, unsafe pin defaults and output symlink escape.
No RTL is source-matched by these tests. Memory tests use independent byte and
response scoreboards, concurrent fetch/data requests, reset races and an actual
corrupted-output negative. Boot uses an independent UART decoder with an
observer-corruption negative. ChiselSim memory randomization is disabled because
it overwrites loaded ROM after initialization; register randomization remains
enabled and RAM comparisons follow explicit writes. The pinned vendor generic
clock-gate model is linked without modifying it.

The firmware preparer invalidates stale receipts before rebuilding, hashes its
inputs and outputs, and records preparation separately from execution. Its minimal
linker supports this stack/local-data test, not a general initialized-data runtime.
The [focused control proof](formal/README.md) records its reset assumptions and
scope. Integrated lockstep, performance, timing/area, I1 and the remaining T20
acceptance remain open. Neither CI tier has run under the user's no-CI direction.

The integrated performance fixture is invoked separately:

```sh
python tools/env/run.py run -- python3 dv/soc/performance.py --main-mhz 8,9 --output build/t20/performance-fresh
python tools/env/run.py run -- python3 -m unittest discover -s dv/soc -p test_fixture.py -v
```

It relocates the same SRAM/ROM model to QEMU's test map, explicitly preloads
the four SRAM banks and separate ROM bootstrap, and adds registered test-only
finisher/marker/MSIP targets behind the actual fabric. The verification option
uses hart zero to match QEMU; production retains hart one and no test targets
or SRAM preload. Every fetch/load/store still uses the real RTL memory/fabric
path. The minimal C++ driver observes public RVFI and advances clocks/reset.
Pinned firtool's memory-file and reset initialization guards are enabled;
random initialization remains disabled for this deterministic fixture.

The original flight sources/scenarios/options are retained, with only linker
stack placement changed to fit the real SRAM capacity. Allocated ELF sections,
BSS, a reserved stack and observed SP are checked before acceptance. The same
QEMU comparator, loop boundaries and result/drop negative controls are reused.
Outputs retain source/model/binary/trace hashes and command receipts. Frequency
conversions are estimates from measured cycles, not a timing-qualified clock.

The first qualified fixed-point measurement exceeded the unchanged round-2
overhead limit; see the T20 report. The runner stops before hard-float on that
failure. This remains fixture-map evidence, not production-map system acceptance
or the full architectural suite. At that checkpoint no production memory-path
optimization had been made in response to the failure.

The subsequent approved idle-data-grant parking experiment was rejected:
correctness, original regressions, its added directed test and control proof
passed, but the worst fixed loop increased from 4,821 to 4,835 cycles (measured
by `dv/soc/performance.py`, receipts `build/t20/performance-3` and
`build/t20/performance-parking`). The prior arbitration was restored exactly.
The +10% limit remains unchanged. D65 later resolves the measured performance
limit, as recorded above; integrated timing qualification remains open.

The approved two-consecutive-idle qualifier also failed the performance gate:
measured mean 4,296.750 / worst 4,819 cycles using the same command, receipt
`build/t20/performance-qualified-parking`. Original simulations plus the added
qualifier/reset test and control proof/covers/fault passed, but the worst remains
34 cycles above the unchanged limit. This candidate is archived and the baseline
arbitration restored; no parking optimization is retained. Independent review
checked logic, receipts and raw cycle counts. No CI was run.

`dv/soc/trace_memory.py` can replay a preserved measured image with fixture-only
public bus observations. It requires exactly identical RVFI and retirement
cycles, so it is passive diagnosis rather than another acceptance workload.
The baseline trace and independent analysis identify one/two-cycle gaps before
speculative fall-through fetches, rather than immediately before checksum SRLs.

D67 authorizes an isolated synthesis experiment on the existing shared MAC:
pinned Yosys `arith_tree -strategy fa -final prefix` versus
`arith_tree -strategy 42 -final prefix`, with FMA fusion enabled. Production
RTL and latency remain unchanged. Exact arithmetic equivalence, verified
reinsertion and integrated GF180 timing under the existing limits are required
before retention; no CI is run for this experiment.

## Functional flight I/O profile (T21, D68)

`EmitSocIo` adds actual GPIO, main microsecond capture/compare, AON sleep
deadlines and retained receive-only ADC to the same assembly. `EmitSocI1`
continues to select its original stub/error profile. The logical pin bundle's
legacy name `inactive` is unchanged; GPIO/timer/ADC/IMU fields are functional
in the I/O profile, while QSPI, actuator and JTAG stay inactive. No pad-ring
or oscillator qualification is implied.

From the pinned environment, explicit focused commands (never CI):

```sh
python3 dv/soc/prepare_io.py
python3 tools/sbt.py 'hw/runMain deadhorse.top.EmitSocIo build/t21/example soc usb 8'
python3 dv/soc/check_io.py --output build/t21/fresh-check
python3 dv/soc/check_io_formal.py --output build/t21/fresh-proof
```

The emitter accepts `8` or `9` main MHz and `stub` or `usb`; this is a
parameter binding, not a Q15/Q16 clock-source decision. `flight_io` in soc.yaml
defines each child window and generated firmware bases. Read the
[T21 report](../../../docs/plan/tasks/reports/T21.md) for measured results,
formal scope, physical limitations and the no-CI status.

## Generic PWM profile (T22)

`EmitSocPwm` extends the I/O profile with the nine generic PWM outputs at the
existing reserved window/pins. `soc.yaml` records the profile's main-service
reset, owner and low 256-byte decode. The original I1 and I/O profiles are
unchanged. IRQ10 and clock demand are connected; external DMA acknowledgement
is tied low until the separate controller exists. See the
[PWM contract](../../ip/pwm/README.md).

```sh
python3 dv/soc/prepare_pwm.py
python3 tools/sbt.py 'hw/runMain deadhorse.top.EmitSocPwm build/t22/example soc usb 8'
python3 dv/soc/check_pwm.py --output build/t22/fresh-check
```

These are explicit focused commands, not CI. Core-only and AON reset preserve
PWM; service or whole-chip reset asynchronously disables it. No physical
pad/routed-timing or complete DMA qualification is implied.

## T23 DMA profile

`SocDmaFiles` / `EmitSocDma` extends PWM with four finite-count DMA channels
for UART/SPI bytes and PWM words. Endpoint addresses come from the validated
map; a third native memory master accesses performance SRAM only. The main
fabric admits the DMA's fixed peripheral endpoints with hardware origin1.
Main-service reset cancels DMA together with its buses; core/AON reset preserves
it. IRQ8 and clock demand are connected. Prior profiles retain their stubs.

Use `dv/soc/prepare_dma.py`, then `EmitSocDma <build-output> soc <stub|usb> <8|9>`.
`dv/soc/check_dma.py --output <fresh-build-output>` runs focused regression
and whole-top emission without CI. See the [DMA contract](../../ip/dma/README.md)
and [T23 report](../../../docs/plan/tasks/reports/T23.md) for proof/timing scope.

## T24 limited output pin mux profile

`SocPinmuxFiles` / `EmitSocPinmux` extends the DMA profile with a main-service
output selector at 0x40012200. Each of the three GPIO output pads selects
disconnected, same-index GPIO, timer compare or PWM. Selection changes insert
one disabled main-clock interval; stable outputs have one main-edge latency.
Reset disconnects the pads. Raw GPIO inputs/wake and dedicated timer/PWM
outputs stay connected. This logical selection table does not freeze the
physical pad map. Existing profiles retain their prior behavior.

Use `dv/soc/prepare_pinmux.py`, then
`EmitSocPinmux <build-output> soc <stub|usb> <8|9>`.
`dv/soc/check_pinmux.py --output <fresh-build-output>` runs focused regressions
and whole-top emissions without CI. See the [pin mux contract](../../ip/pinmux/README.md).
The inherited T23 range-proof and complete-SoC qualification remain open.

## T25 recovery-loaded lite-core profile

`SocLiteFiles` / `EmitSocLite` extends the pin-mux profile with the clocked
RV32E machine-mode hart at AON master origin0. The loader STARTs its committed
image at the global retained-SRAM base plus entry offset. It fetches and uses
working SRAM through the existing fabric, receives AON timer/ADC/GPIO/mailbox
interrupts, and contributes clock demand. Main reset preserves it; common
AON reset cancels core, adapter and fabric. The old external lite-master and
halted test inputs are inert in this profile. Earlier profiles remain usable.

Use `dv/soc/prepare_lite.py`, then
`EmitSocLite <build-output> soc <stub|usb> <8|9>`.
`dv/soc/check_lite.py --output <fresh-build-output>` runs focused regression
and whole-top emission, never CI. Loader-wire firmware tests cover nonzero
entry, SRAM, timer/mailbox IRQ, WFI, main/AON resets, ownership and START mode.
See the [core contract](../../ip/lite_core/README.md) for machine/RVFI semantics
and qualification limits. This profile retains external clocks and the current
performance-core boot path; it does not complete the power controller or
production boot/debug sequence.

T26 adds an opt-in watchdog profile (`EmitSocWatchdog`) with external clocks,
AON watchdog MMIO, performance core/client-only reset plus PWM disable, and
lite whole-MCU reset. PWM break acknowledgment is qualified by the actual
memory epoch drain. See [watchdog](../../ip/watchdog/README.md). This does not
complete I3 boot/sleep or physical reset qualification. Focused checks use
`python tools/env/run.py run -- python dv/soc/check_watchdog.py --output build/t26/<fresh-output>`;
neither CI tier is invoked.

## D71 raw ADC migration

All functional ADC profiles now use raw acquisition.0x40020014 is retired
and errors on every read/write; raw_sample remains at0x40020010, with
unchanged sequence/event offsets and lite ownership. The registered result
is published atomically. Software conversion lives in sw/hal/adc_convert.h.
See [the ADC contract](../../ip/adc/README.md) and [T27](../../../docs/plan/tasks/reports/T27.md)
for focused evidence; inherited physical/SoC acceptance remains separate.

## T28 lite-first release profile

`SocBootControlFiles` / `EmitSocBootControl <build-output> <stub|usb> <8|9>`
extends the watchdog profile. Performance core/client reset stays asserted
until the real recovery loader accepts START and lite firmware writes the
release key to0x40000304. Shared services keep their prior reset scopes.
The release survives AON service and performance resets; whole reset clears
it asynchronously. Main release uses the existing shared ResetRelease and
memory epochReady still gates fetch.

Use `dv/soc/prepare_boot_control.py` and focused
`dv/soc/check_boot_control.py --output <fresh-build-output>`; neither runs CI.
See [boot control](../../ip/boot_control/README.md) and the
[T28 report](../../../docs/plan/tasks/reports/T28.md). This is recovery-started
digital sequencing. Production ROM/QSPI boot, locked-image warm restart,
oscillator/sleep policy and physical reset qualification remain open.

## T29 QSPI command profile

`SocQspiFiles` / `EmitSocQspi <build-output> <stub|usb> <8|9>` extends T28 with
the bounded main-domain [QSPI command interface](../../ip/qspi/README.md).
The existing QSPI pads and control aperture are active; XIP still errors.
Lite owns the controller after main-service reset and may hand it to the
performance core while idle. Performance/AON resets preserve active commands.

Use `dv/soc/prepare_qspi.py`, then `dv/soc/check_qspi.py --output
<fresh-build-output>` for focused checks; no CI. This subset does not complete
production boot, XIP, logging arbitration or flash/pad qualification.

## T30 native flash profile

`SocXipFiles` / `EmitSocXip <build-output> <stub|usb> <8|9>` extends T29 with
the [native flash interface](../../ip/qspi_xip/README.md). Performance fetch
and data reads use a dedicated local-memory port; complete frames arbitrate
with queued CS1 commands. Configuration ownership, native access permission,
ordered replies and client-reset draining are separate concerns. Older
profiles retain their behavior and the peripheral deadlines are unchanged.

Use `dv/soc/prepare_xip.py`, then `dv/soc/check_xip.py --output
<fresh-build-output>` for focused checks; no CI. The firmware example loads
lite through the actual recovery interface, enables XIP, then boots the
performance core from ROM into flash code that also reads flash data. It is
an integration test, not production boot firmware. Physical reset/hold/pad
qualification, production images and system performance remain open.
