# Production SoC contract

PLAN03 / D72: `DeadhorseSoc` is the single production assembly. This contract
describes digital integration, not a pad-level or physically qualified chip.
Q15 is resolved by D78; Q16 (application loop rate) remains open.
The profile history below is historical evidence, not selectable chip features.

## Assembly

The top contains the faithful RV32IMFC Chisel performance core with its shared
integer/FPU MAC, local ROM and banked performance SRAM path, main and AON
fabrics, shared-CDC bidirectional bridge/permit and mailbox, three UARTs, SPI
host, I2C host, USB CDC-ACM, GPIO, main capture/compare/timebase, AON deadlines,
generic PWM, DMA, pinmux, both watchdog channels, real lite hart, boot-release
control, shared QSPI command/native-XIP engine and frozen I2C recovery loader.
T32 adds the two-hart JTAG debug binding (acceptance in progress). Clock/power
control and analog interfaces await their own briefs.
Reserved address holes are error targets, not implemented gateway/debug hardware.

`SocProduction` supplies one set of generated register descriptions. Main
frequency is selected at 8 MHz by D78; historical 9 MHz fixtures retain their
measurement scope. Production
uses real USB; the named USB-stub simulation configuration retains every other
production feature. `SocMinimalI0` is a named minimal boot/performance fixture.
Bus-driven tests substitute stimulus at the CPU boundary; real-core tests use
the actual recovery loader and lite-first release. Neither fixture is a second
production configuration. `EmitSoc` is the production emission entry point;
the old profile emitters have been removed after the B2 test comparison passed.

The dedicated SPI ADC is retired by D74. Firmware uses the general SPI host
and DMA for external converters. Its former window and three logical pins are
unassigned; IRQ12 is unassigned. After the B2 comparison passed, the ADC source
and ADC-only tests were removed in the separately authorized retirement change.

## PLAN04 clock/reset implementation contract (acceptance pending)

OSC_IN is the dedicated 48 MHz clock pad and clocks USB directly. A registered
/6 divider with equal high/low phases supplies main at 8 MHz through the shared
ICG. The timing flow must declare a generated clock, retaining all existing
main/USB CDC. OSC_EN is an AON-controlled output with reset value one and a
board pull-up. No internal HF oscillator remains. AON uses nominal 32 kHz LF RC
or reset-sampled AON_CLK_IN selected by AON_CLK_SEL; no runtime switching.
POR_BYPASS ignores on-die POR/brownout, leaving the external active-low pin as
the supply-reset authority. D84 makes it a static board strap with default low,
fixed from power application until removal. It directly selects reset without
depending on initialized state. Watchdog/debug containment is preserved.

The production `DeadhorseSoc` boundary supplies OSC_IN, OSC_EN, AON_CLK_IN,
AON_CLK_SEL, static POR_BYPASS and external reset, the existing peripheral/JTAG
pad functions, and analog power pins. `SocExternalClockTest` preserves the
complete digital assembly with independently driven clocks/resets solely for
focused tests (including historical 9 MHz trials); it is not a chip profile.
The named analog-model test configuration substitutes only the LF/POR macros
with their digital models. Main/USB service reset waits for first qualification;
later oscillator-off sleep retains service state and requires fresh gate
authorization on wake. `bootDone` is never permission to open the clock gate.
Internal status/cause outputs are T33 integration/verification signals, not
additional assigned pads. Existing loader START/core boot permission remains.

Fallback bootstrap requires the board to hold external reset, establish valid
AON_CLK_IN and stable straps, and supply selected-clock sampling edges before
releasing reset. AON_CLK_SEL sampling cannot itself be held reset by the failed POR
or clock it bypasses. Normal POR-only startup samples with the RC running while
raw POR holds reset. Functional domain release waits for frozen strap selection
and counted AON stability. Undefined power-up with bypass asserted but no valid
external reset is outside that board contract. An AON_CLK_SEL change after release
must have no effect until the next reset-held sampling sequence.

POR/brownout asserts ordinary resets asynchronously; release uses the shared
per-domain primitives, AON first, then qualified external-clock domains. Keep
separate cold and warm causes: POR/brownout clears the frozen loader lock.
Normal-mode external pin and lite-watchdog reset preserve it. Under D83,
bypass-mode external reset is cold for loader lock, retained watchdog history
and debug POR state; its recorded cause is external pin, not POR.
Performance watchdog retains
D70 core/client reset plus PWM disable, preserving shared services. Latched POR,
brownout and pin causes feed the T33 reset-reason register described below. AON release
permits existing loader START; autonomous lite ROM boot remains T36 work.

The controller owns a new child at AON parent offset 0x400 (0x100 bytes),
leaving existing child registers unchanged. It accepts sleep request, wake
enables, startup delay, stable count and UART wake configuration; reports state,
sticky fault and last wake cause. Before stop it requires qualified performance
WFI and all main holds released, then a source-clock gate-closed acknowledgement.
USB's separate enabled-level request is unmaskable and retains OSC_EN (D81).
Enabled USB uses light sleep. USB must be disabled before oscillator-off sleep; physical detachment alone does not release its clock request.

Existing UART wake monitors are reused. Controller-owned wake polarity must
match the UART's existing ACTIVE.invert. Firmware configures while disarmed,
allows at least four AON edges to settle, arms, then requests wake-only sleep.
No UART register or behavior change is implied. Holds are independent of wake
masks. The frozen AON recovery loader uses f_SCL <= f_AON,min / 8 (D82);
nominal 4 kHz is estimated, not tolerance-qualified.

Analog pin-level model boundary (T34 digital contract; physical qualification pending):

| Macro | Inputs | Outputs / safe default |
| --- | --- | --- |
| LF RC | VDD/VSS, enable, trim, test controls | AON clock and ready; enabled at reset, nominal 32 kHz assumed, safe trim before firmware |
| POR/brownout | VDD/VSS, threshold selection, test controls | active-low supply reset, initial-power epoch (`powerOn_n`) and sticky brownout indication; safe default threshold, hysteresis and qualified release before firmware |

These are BlackBox boundaries; digital behavioral substitutes model supplied
clock/startup and supply-ramp/threshold/hysteresis/release events. They do not
implement analog circuits or establish accuracy. Numerical thresholds, encoding,
release time and LF trim remain assumptions until T34/process/SRAM qualification.
The [LF pin contract](../../analog/lf_rc/README.md),
[POR pin contract](../../analog/por_brownout/README.md) and
[characterization handoff](../../analog/characterization.md) define the detailed
T34 boundary. Production ties LF enable high, trim to startup code0 and both
test controls low. LF ready and POR powerOn_n are intentionally unused
diagnostics; counted AON edges and the existing supply-reset combination remain
the release authority. No production trim-loading/storage or analog test mux
is implemented. Reserved LF trim codes use startup behavior in the model;
frequency tuning and four-state/power-aware behavior remain unqualified.
The current digital POR model assumes default 3.10 V falling / 3.20 V rising,
1000 reference edges at assumed 1 MHz (estimated 1 ms qualified release), and
an initial-power epoch below assumed 0.10 V. Encoding 01 selects assumed
3.20/3.30 V; other encodings use the default. These are simulation parameters,
not qualified operating-voltage guarantees; the T33 selection contract follows.

## T33 power/reset completion contract (acceptance pending)

The [clock/reset boundary inventory](soc-power-reset.md) lists reset cohorts,
crossing protocols and the physical qualification still required.

The lite-owned power/reset child at 0x40000500 adds read-only reason bits
0 POR, 1 brownout, 2 external pin, 3 performance watchdog, 4 lite watchdog.
It samples the existing AON cause sources, retaining their cold-epoch semantics:
normal cold reset provisionally reports POR until held brownout is classified;
POR_BYPASS initialization reports pin. Performance reset preserves the sources.
The frozen loader's watchdog-only reason and crash-count ABI is unchanged.

Threshold shadow0x04, keyed apply0x08 (full-word0x42524f57), active0x0c and
W1C invalid-command event0x10 follow the power_reset register YAML. Only00/01
apply; reserved selections and invalid keys leave the active value unchanged.
One active selector flop with a tied-low high bit avoids digital decode hazards.
Service reset restores the existing safe00 setting. D85 requires the macro to
prevent unsafe release pulses across changes, assert immediately below the new
falling limit and fully qualify any subsequent release at the new rising limit.
Still-valid supply may stay released. During incomplete release qualification,
the model restarts counting on a selection change; no old-setting samples are
reused. Voltage/time numbers remain assumptions and analog validation is T34.

Internal lite-watchdog, JTAG system and AON-service resets flush functional
transports immediately. Their stretched indication is synchronized in the
retained AON policy epoch before configuration defaults and unmaskable sleep
cancellation are applied. MMIO reopens only after configuration reset completes.
A wake preceding that synchronized indication captures old coherent settings;
a reset-forced start uses defaults; existing STARTING settings remain captured.
They preserve the oscillator policy/source qualification epoch so the
main-clock debug module can service the DMI write that clears ndmreset. Cold
and external-pin resets still clear the clock epoch; actual oscillator-off
requires fresh qualification. A failed-start fault remains sticky within that
epoch and is not bypassed by an internal reset. D70 performance reset scope,
loader cold/warm cohorts and shared transaction drainage remain unchanged.
No new clock domain, runtime source selection or power-gated mode is introduced.

## Authoritative map

`hw/top/reference/soc.yaml` defines production regions, child windows, trusted
origins, interrupts and logical pins. Peripheral register YAMLs define register
semantics; generated descriptions/headers go under build/. Unmapped, reserved,
misaligned and denied accesses error without side effects. ROM writes and device
instruction accesses error. Legal subword memory instructions retain byte masks.

| Endpoint | Base | Size | Home | Implementation |
| --- | --- | --- | --- | --- |
| debug_mem | 0x00010000 | 0x1000 | debug leaf | pinned PULP execution debug ROM/data/flags |
| boot_rom | 0x00000000 | 0x10000 | main local | synchronous ROM model; production firmware pending |
| xip | 0x10000000 | 0x10000000 | main local | native QSPI reads |
| performance_sram | 0x20000000 | 0x4000 | main local | synchronous banked model |
| retained_sram | 0x30000000 | 0x0c00 | aon | synchronous SRAM macro wrappers; nominal-supply retention |
| power_reset_timer | 0x40000000 | 0x1000 | aon | AON timer, watchdogs and boot-release children |
| mailbox | 0x40001000 | 0x0100 | each domain local | real paired endpoints |
| uart0 | 0x40010000 | 0x0100 | main | real |
| uart1 | 0x40010100 | 0x0100 | main | real |
| uart2 | 0x40010200 | 0x0100 | main | real |
| spi_host | 0x40010300 | 0x0100 | main | real |
| i2c_host | 0x40010400 | 0x0100 | main | real |
| dma | 0x40011000 | 0x1000 | main | real, low 256 bytes |
| gpio_pinmux | 0x40012000 | 0x1000 | main | GPIO, timer and pinmux children |
| qspi_control | 0x40013000 | 0x1000 | main | command and native-XIP configuration |
| unassigned_aon | 0x40020000 | 0x10000 | aon | unassigned; always error |
| actuator | 0x40030000 | 0x1000 | main | generic PWM, low 256 bytes |
| gateway_reserved | 0x40040000 | 0x0800 | main | reserved; always error |
| usb | 0x40040800 | 0x0100 | main/usb/aon | real |
| future_bridge | 0x60000000 | 0x10000000 | each domain | reserved; always error |

Child offsets: AON timer 0, performance watchdog 0x100, lite watchdog 0x200,
boot release 0x300, oscillator control 0x400 and power/reset control 0x500 in the AON parent; GPIO 0, main timers 0x100, pinmux 0x200 in
the GPIO parent. QSPI native configuration extends the command map at 0x100.
Child holes remain errors. No parent or endpoint timeout changes.

| Source | Fast index | Production binding |
| --- | --- | --- |
| uart0 | 0 | UART0 |
| uart1 | 1 | UART1 |
| uart2 | 2 | UART2 |
| spi_host | 3 | SPI |
| i2c_host | 4 | I2C |
| mailbox | 5 | main endpoint |
| usb | 6 | USB application IRQ |
| future_bridge | 7 | inactive reservation |
| dma | 8 | DMA |
| gpio_pinmux | 9 | GPIO |
| actuator | 10 | PWM |
| power_reset_timer | 11 | main timer or synchronized AON timer |

## T32 debug binding (acceptance in progress)

The reviewed contract is in hw/ip/debug/README.md. TAP uses external TCK;
shared CDC FIFOs carry DMI to the POR-owned main-clock DM. Lite is hart0,
performance hart1. Both have execution-debug ROM access at0x10800 (exceptions
at0x10810). A dedicated shared-primitive leaf bridge carries lite debug memory
traffic; the ordinary two-way permit/fabrics and reserved windows stay intact.
SBA is a distinct origin and accesses memory only. It never impersonates a CPU.
No 12-bit hartinfo scratch address is advertised for the nonzero debug base.

Debug-only reset entry is separate from firmware boot release. Loader commands
that mutate images/lock/START are cancelled through its existing busy-error path
while debug requests ownership; already accepted writes finish. Ordinary boot,
loader lock and watchdog containment are unchanged. Independent target resets
clear that hart's DM status; reset cancellation retains transaction fences.

## Memory, ownership and transactions

Instruction/data access to ROM and SRAM bypasses peripheral arbitration.
D65 current-request arbitration retains exclusive acceptance, round-robin
preference, synchronous responses and exclusion of a returning data response.
The core's outstanding fetch behavior, byte enables and epoch drain remain.
DMA is confined to performance SRAM and fixed UART/SPI/PWM register endpoints;
its origin is assigned by hardware. Offered operations drain before abort.
ROM aperture is a model capacity, not a measured mask-ROM allocation.

Trusted origins: lite 0, performance 1, JTAG SBA 2. Existing fixed-owner
peripherals check every local/remote/DMA access. QSPI alone has its existing
idle-only keyed ownership handoff. USB ownership is constant during application
reset release. There is no added dynamic ownership controller.

Retained SRAM contains 2048 program bytes and 1024 working bytes. CPU program
writes are denied. Loader programming requires halted, unlocked, in-range
aligned writes and acknowledgment after the synchronous write. Lite reads its
program while halted or after admitted START. Remote performance accesses
require the lite hart halted and loader idle. Separate JTAG SBA writes require
lite debug mode or not-started with no START pending, and loader idle. Ordinary
CPU program-write checks remain unchanged.
Service resets flush handshakes, not RAM contents. The real hart supplies halt
status; legacy external stand-in controls are inert in production.

T35 binds these memories to the pinned GF180 1024x8 macro: sixteen byte macros
for performance SRAM and four for retained SRAM. Four byte lanes form each
word; performance word bits [1:0] select one of four banks. Retained physical
rows 768–1023 remain inaccessible. A read still returns on the existing edge;
writes still return zero. Power-on contents are arbitrary and resets never
initialize the RAM. The [SRAM contract](../../hw/ip/sram/README.md) records
view discrepancies, operating-rail retention limits and physical obligations.

Destructive March self-test is a custom JTAG DMI device at words 0x70–0x7f,
outside the CPU address map. Its keyed start requires active DM and acknowledged
whole-system `ndmreset`. A separate cold-owned test hold prevents reset release
until both test agents relinquish their ports. Both cores, DMA, loader and
functional memory controllers remain reset throughout; normal permissions and
latencies apply again after release. TAP/DM reset cannot cancel ownership.
Cold/pin reset aborts the test. SRAM must be reloaded before code relies on it;
the loader lock retains its existing cold-reset-only semantics. Status lives
outside tested memory and crosses main/AON only through shared CDC primitives.

Native XIP serves aligned performance reads, little endian, with no cache or
prefetch. Three-byte addresses reject unrepresentable offsets; four-byte mode
uses the window. Disabled reads, writes and wrong origins error. Complete frames
arbitrate round robin with captured CS1 commands. Raw CS0 commands are denied
while XIP is enabled. Configuration/handoff is idle-only. Firmware handles
flash readiness and must execute reconfiguration from ROM/SRAM. Native reads
use the existing estimated bound `2 * 53299 + 32 = 106630` running main edges;
peripheral bound 128 and bridge 131072/fabric 131080 are unchanged.

## Clock, reset and boot

Clocks are explicit external model inputs: main 8/9 MHz trials, USB 48 MHz, AON
nominal 32 kHz or a declared active-service test clock. These are assumed model
rates, not selected/qualified oscillators. SPI's existing divider allows at most
estimated main/6, or 1.333/1.5 MHz; its separate 4 MHz target remains unmet. Loader
needs eight service edges per SCL period; normal I2C speeds cannot run at 32 kHz.

Shared ResetRelease supplies asynchronous assertion and synchronous release.
Cold and warm reset affect all ordinary state; loader lock survives warm reset.
Performance core reset preserves shared fabrics/peripherals/DMA and drains old
accepted client work before epochReady. D70 performance-watchdog expiry also
disables PWM; a post-drain STOP acknowledgment and APPLY are required to restart
outputs. GPIO/timer alternatives survive. Lite watchdog resets the whole MCU.
Main-service reset cancels its peripherals/memory control, AON-service reset
cancels the lite/loader/AON transport, and USB-service reset flushes USB. Crossing
reset isolation and nested-fabric drain acknowledgments remain connected; no
quiescent input is tied true to manufacture recovery.

Validated recovery START launches the real lite hart. A lite-owned keyed write
to boot release then releases performance through its client reset. Release
survives AON-service reset but not whole reset. D73 freezes the loader's existing
image-invalidation policy: warm/AON reset invalidates START/image metadata while
lock remains; no retained-image restart extension or autonomous boot is implied.
Production QSPI image selection/CRC/recovery firmware is still pending.

Clock demands/wakes pass through shared CDC to the always-running controller
boundary and survive stopped destination clocks as specified by each block.
Those outputs are not permission to stop a running core. The clock/power/reset
controller, analog qualification, full crossing inventory/MTBF and physical
reset/hold/clock-tree checks remain separate obligations.

## Pins and verification boundary

Three GPIO pads select disconnected, same-index GPIO, timer compare or PWM.
Selections reset disconnected; switching includes the existing disabled interval.
Dedicated timer/PWM pins remain, and input/wake routes are independent. Firmware
must quiesce sources when a truncated pulse is unacceptable. Serial, recovery,
QSPI, USB and dedicated JTAG/external-clock/reset logical groups retain their
contracts. The implemented T32 TAP drives JTAG TDO and its output enable.

Estimated simultaneous digital demand after PLAN04 is 39 output-capable and 12
input-only pads: D74's 38/9 plus OSC_EN (1 output) and the three fallback/strap
inputs. OSC_IN reuses the dedicated clock pad. Nominal slot capacities remain
40/12; dedicated clock/reset/analog are separate. This is allocation arithmetic,
not measured pad-ring fit or USB electrical qualification. Scan sharing and
final physical assignment remain open.

Focused tests use independent bus/pin/architectural oracles and real faults.
The minimal I0 QEMU fixture preserves its declared relocated address map,
preloads and marker targets; it is not production-top performance evidence.
Production performance must be measured separately. No inherited T13/T14/T17/
T19/T23/T25/T26 proof or physical obligation is waived. D76 now requires fast CI
on main and full CI at integration-stage ends; historical no-CI notes below do
not govern current acceptance.

## Appendix: historical profile contracts

The following is the pre-PLAN03 contract, retained as history with retired-source
links redirected to the historical report. Its
profiles, stub tables, pending-work descriptions and no-CI instructions are
superseded by the current contract and D72–D76.

# Reference SoC contract — T20 I0/I1

Initial contract reviewed, 2026-11-20, based on `f1c17ba`. This specifies
the reference simulation top, not a pad-level chip or accepted physical design.
Authority: [plan 16](../plan/16-soc-integration.md), the
[T20 brief](../plan/tasks/T20-soc-integration.md), [bus contract](bus.md) and
[reset plan](../plan/06-power-clock-reset.md). Q15/Q16 remain open. Numerical
configuration choices below are provisional assumptions unless identified as
existing requirements; no measurement is claimed in this contract.

## Assembly and public boundary

`DeadhorseSoc` will instantiate the production faithful RV32IMFC Chisel
`IbexTop` (`RegisteredExecution=false`, `WithF=true`), preserving its current
shared-multiplier configuration and RVFI observation option. No reference
SystemVerilog core is allowed. ASIC/model clock-gate selection uses the shared
wrapper. Main clock frequency is an elaboration/test parameter, evaluated at
both 8 and 9 MHz without choosing a production clock source.

I0 connects the core, test boot ROM, performance SRAM, local memory adapter,
main fabric and UART0. I1 adds UART1/2, SPI, I2C, bridge/permit, mailbox,
retained SRAM, recovery loader and a selectable real USB block. All other
functional windows error. The lite stand-in is a test-bench master, not a
substitute production processor. Test access and RVFI are verification ports,
not claimed production JTAG or gateway implementations.

Public groups: explicit main/AON/USB clocks; cold, warm, main and USB reset
inputs; UART pins; SPI pins; separate I2C host and recovery-loader pins; USB
digital pad signals; provisional inactive QSPI/actuator/GPIO/JTAG signals;
retained clock/wake demands and reset-readiness observations. Memory models
are synchronous and loaded from build artifacts. There is no clock mux,
oscillator, DMA, pin-mux controller or power-controller implementation in T20.

## Single machine-readable description

`hw/top/reference/soc.yaml` will own region bases/sizes, endpoint instances,
implementation/stub variants, trusted master identities, interrupt indices,
clock/reset assignments and logical pin allocations. Existing peripheral
register YAMLs remain the sole source for register offsets and semantics.
Generated Scala configuration, firmware headers and Markdown tables go under
`build/t20/`; none is committed. The map checker must compare generated rows
with this contract, reject unknown keys/duplicate names/overlaps and register
maps that exceed their window, and distinguish legal domain-local mailbox
addresses from accidental aliases. No production address decoder or interrupt
index may restate these tables by hand.

## Address contract

The following assumed subdivisions retain the parent windows in the bus
contract. Sizes are byte counts; endpoints reject addresses outside their
actual capacity even where an aligned fabric aperture is larger.

| Endpoint | Base | Size | Home | I1 implementation |
| --- | --- | --- | --- | --- |
| boot_rom | 0x00000000 | 0x10000 | main local | read-only test ROM model |
| xip | 0x10000000 | 0x10000000 | main local | error stub |
| performance_sram | 0x20000000 | 0x4000 | main local | synchronous SRAM model |
| retained_sram | 0x30000000 | 0x0c00 | aon | synchronous SRAM model |
| power_reset_timer | 0x40000000 | 0x1000 | aon | error stub |
| mailbox | 0x40001000 | 0x0100 | each domain local | real local endpoint, no remote alias |
| uart0 | 0x40010000 | 0x0100 | main | real |
| uart1 | 0x40010100 | 0x0100 | main | real |
| uart2 | 0x40010200 | 0x0100 | main | real |
| spi_host | 0x40010300 | 0x0100 | main | real |
| i2c_host | 0x40010400 | 0x0100 | main | real |
| dma | 0x40011000 | 0x1000 | main | error stub |
| gpio_pinmux | 0x40012000 | 0x1000 | main | error stub |
| qspi_control | 0x40013000 | 0x1000 | main | error stub |
| adc_loader_reserved | 0x40020000 | 0x10000 | aon | error stub; loader is wire-only |
| actuator | 0x40030000 | 0x1000 | main | error stub, independent reset |
| gateway_reserved | 0x40040000 | 0x0800 | main | error stub |
| usb | 0x40040800 | 0x0100 | main/usb/aon | error stub by default; real variant |
| future_bridge | 0x60000000 | 0x10000000 | each domain | always error |

All remaining addresses, mailbox-window padding, reserved gaps, misaligned
bus accesses, instruction accesses to device windows and writes to ROM error
without a downstream side effect. RV32 byte/halfword stores preserve the
core's aligned address/byte-enable protocol; this does not prohibit legal
subword instructions. Both local mailbox views use owner-specific instances
at the same address; a bridge must not make the peer staging interface alias
the local one. Local ROM capacity is a simulation aperture, not a measured
boot-ROM macro allocation. Unsupported or unpopulated ROM bytes must be
defined explicitly by the image format, not read from host memory.

`BusFabric` currently permits at most eight disjoint power-of-two regions.
Use a main peripheral fabric with a subordinate serial fabric: the serial
group has exactly the three UARTs, SPI, I2C, DMA, GPIO and QSPI-control windows.
Local memory is selected before peripheral arbitration. Bridge routing groups
remote windows without forwarding unmapped holes or bouncing a request back
to its source. The 3 KiB retained region may use a 4 KiB fabric aperture only
with the final 1 KiB rejected at the memory endpoint. No region-count limit
or endpoint register decoder is widened to accommodate integration.

The default local completion bound remains 128 running edges. Nested fabric
overhead must fit that original end-to-end bound; assigning each nested
stage its own fresh 128-edge allowance does not establish it. Preserve bridge
watchdog 131072 and source-fabric bridge allowance 131080, including actual
registered forwarding/return edges. If grouping cannot satisfy those limits,
report the path before changing bounds or an existing interface.

## Local memory path and arbitration

Instruction fetch and local data SRAM/ROM requests bypass `BusFabric`.
Requests use the existing core grant/response interface; every accepted beat
gets one in-order response, no earlier than the following edge. Preserve the
core's multiple outstanding fetch capability; size and verify response tags
from the production interface rather than silently forcing one transaction.
Simultaneous instruction/data access, branch redirects, split loads/stores,
byte masks and reset with outstanding replies require directed tests and RVFI
comparison. No combinational memory read or unqualified ready chain is allowed.

The performance model holds the required 16 KiB; the retained model holds
3 KiB. Use configurable banks with 32-bit words and four byte enables, matching
S3's byte-lane macro interface. Bank conflicts arbitrate rather than duplicating
RAM contents. A configured synchronous latency is an assumption, not a macro
measurement. Start with one-edge model reads and report longer supported
latencies separately; T20's unchanged round-2 performance stop still applies.
The optimized round-2 baseline is distinct from the older S1 checkpoint.

Trusted origins are provisional: lite/stand-in=0, performance=1,
gateway/debug=2; unused values deny. Bridges preserve origin; a DMA stub
issues no requests. Software cannot choose its origin. Main local memories
admit performance access; gateway/debug access requires an explicitly held
halt/programming condition. Lite access to performance-private windows errors.
Retained-memory remote access must be checked against loader ownership and
lite halt state. Memory load through a simulator is a declared preload before
execution, not a passing test of a missing production programming gateway.

The provisional I1 retained-memory policy is explicit. Program bytes occupy
offsets `0x000..0x7ff`, working bytes `0x800..0xbff`. `halted` is the held
stand-in halt level; `busy` and `locked` are actual loader outputs. Admission
retains permission until completion; changing an input cannot retag a request.

| Requester | Program reads | Program writes | Working reads/writes |
| --- | --- | --- | --- |
| Loader memory handshake | none | its offered in-range word, while halted and not locked | none |
| Lite stand-in, origin 0 | halted, or admitted running image after loader start | denied | allowed while loader not busy |
| Main remote, origin 1 | only halted and loader not busy | denied | only halted and loader not busy |
| Gateway/debug, origin 2; unused tags | denied in I1 | denied | denied in I1 |

Memory admission never fabricates `memValid` or bypasses loader BEGIN/CRC/order
checks. Finish an accepted word before emitting one `memDone`; no other master
may overlap it. Reject requests until reset release and permission inputs are
valid. Program writes cannot bypass the loader regardless of lock, programmed
or started state. The stand-in observes START before enabling running fetch;
ordinary reset clears that admission. This test-stage policy does not implement
production debug permissions or a dynamic ownership-control register.

Serial/USB owners are fixed configuration parameters in I0/I1 (default main=1).
USB owner must remain constant while its application reset is released; any
later transfer uses the existing explicit application-reset/transport flush.
Dynamic owner transfer remains unimplemented: no owner may change while a peripheral or bus
transaction is live. Endpoint owner checks remain active for every origin.
Do not add a software-visible ownership controller under this integration brief.

## Clock, reset and retained-work contract

Simulation clocks are explicit externally driven inputs. Main runs at the
selected 8/9 MHz trial, USB at the existing 48 MHz requirement. AON's nominal
32 kHz remains a product target; an explicitly identified active-service AON
test profile is required for loader traffic. T18 requires at least eight
service edges per SCL period and never stretches SCL. No 100/400 kHz loader
claim is valid on 32 kHz alone. I1 may model an already-running faster AON
service clock, but cannot claim implementation of source switching, startup
or stopped-clock address-probe wake.

The existing SPI divider minimum is three half-period edges: estimated maximum
SCLK at main 8/9 MHz is `8/6 = 1.333...` / `9/6 = 1.5 MHz`. I1 sensor traffic
must use a legal rate and report this limitation; it does not meet or waive the
separate 4 MHz SPI target. No new peripheral clock is silently introduced.

Cold reset (POR/brownout) asserts every reset, including the loader lock reset.
Warm whole-chip reset (external/lite watchdog) resets ordinary main/AON/USB
state and memory handshakes but preserves the loader lock. Performance-only
reset leaves AON loader, lock and SRAM contents intact. The legacy actuator
endpoint is still an inactive stub in I1 and has no functional failsafe state.
D69 places application failsafe policy in firmware; a scoped generic PWM
brief must define its reset/output-disable contract. Existing stub reset wiring
is unchanged by this planning decision.
Distinguish core-only reset from the reset of the main fabric/shared-HF
endpoints. Core-only reset must not reset a peripheral serving a surviving
owner. Retain accepted-transaction bookkeeping until old work drains and
discard its reply to the reset core before admitting a new epoch. The
serial `quiescent` outputs describe engine/queue state, not BusRegAdapter
idle, so they cannot alone authorize bus-slot reuse. Whole-domain reset may
flush jointly reset endpoints; independently retained endpoints require the
explicit isolation/drain acknowledgement below.
Use shared `ResetRelease` for asynchronous assertion and local synchronous
release. Existing blocks with internal release chains retain them; record the
resulting readiness latency instead of replacing their reset logic.

Active-low test inputs are distinct. `coldReset_n` and `warmReset_n` feed every
ordinary reset. Additional domain inputs narrow the scope below; they do not
implement fault-detection policy. Use shared release in each affected clock.

| Asserted input | Core/local response epoch | Main fabric and serial endpoints | Main mailbox / USB application | AON fabric, SRAM handshake, loader ordinary state | Loader lock | USB engine / AON USB wake |
| --- | --- | --- | --- | --- | --- | --- |
| coldReset_n | reset | reset | reset | reset | reset | reset / reset |
| warmReset_n | reset | reset | reset | reset | retain | reset / reset |
| mainCoreReset_n | reset epoch, drain accepted work | retain | retain | retain | retain | retain / retain |
| mainServiceReset_n | reset | reset | reset | retain | retain | existing USB app-reset flush / retain |
| aonServiceReset_n | retain | retain | peer mailbox transport flush only | reset | retain | retain / reset |
| usbServiceReset_n | retain | retain | mailbox retains; USB application registers/configuration/events and transport reset | retain | retain | reset / retain |

The surviving mailbox endpoint retains T14's peer-reset event semantics.
Both bridge transports/permit reset on either service-domain reset, while
surviving-source accepted-request records stay under their own domain reset.
SRAM contents do not clear implicitly. The actuator stub's functional reset
combines cold/warm only, not performance resets.

The opt-in T22 PWM profile replaces that inactive endpoint with generic outputs
at the same reserved address and pins. Its validated `pwm` metadata defines a
256-byte register window, performance ownership and main-service reset. Cold,
warm or main-service reset asynchronously disables outputs and clears all PWM
state; core-only and AON-service reset preserve active and queued configurations.
The existing I1 and T21 profiles remain unchanged. See the
[PWM contract](../../hw/ip/pwm/README.md). IRQ10 and main-clock demand are bound;
DMA requests remain local in that profile. The opt-in T23 `SocDmaFiles` profile
additionally binds UART/SPI and PWM requests to four finite-count DMA channels.
The low 256 bytes of the reserved DMA window become performance-owned MMIO;
IRQ8 and main-clock demand are connected. The controller accesses performance
SRAM through the optional third native memory master, and fixed peripheral
registers through the main fabric with hardware-assigned performance origin.
Addresses and command masks derive from validated register maps. Cold/warm and
main-service reset jointly cancel DMA and its endpoints; core/AON reset preserves
transfers. SRAM contents survive. See the [DMA contract](../../hw/ip/dma/README.md)
for abort/partial-error behavior and the software FIFO ownership requirement.

Core fetch-ready requires released reset, initialized local memory and drain
of any old local response epoch. Fabric target admission requires owning reset
release plus endpoint drainage and transport readiness where applicable.
Bridge readiness includes the direction permit and real endpoint-quiescent
acknowledgement. Loader writes require warm release, cold lock-reset release
and an empty/flushed memory handshake. Elapsed time alone establishes none
of these readiness predicates.

Keep fetch disabled until main reset release and local memory initialization
are complete. The test harness supplies the lite-first release sequence until
I3 provides the real controller. Warm resets flush pending memory replies;
RAM contents are not implicitly reset. Independent USB resets retain the
existing T19 transport-flush behavior and may invalidate USB application state.

Use `DirectionPermit` and both `BusBridge` instances as specified by T14.
Admission waits for permission and actual endpoint readiness. Never tie
`quiescent` high merely because a fabric or bridge reset; retain/drain/cancel
old downstream work and prove the acknowledgement. Reset-isolation glue is
limited to this handshake, not a new power/reset policy controller. If an
existing endpoint cannot express cancellation, keep it isolated and report it.
Collect source `clockRequest`, destination `targetClockHold`, mailbox pending
wake and peripheral `clockHold` through shared CDC into the always-running
test controller. No demand may depend on edges from a stopped destination.

Every crossing, including verification stand-ins and interrupt/wake levels,
must be enumerated from the elaborated top. Use `CdcSync`, `CdcFifo` and shared
reset release; no independent bit synchronization of multi-bit payloads.
Physical Gray skew, reset removal and MTBF remain explicit inherited items.
SPI `timeNow` is a coherent main-domain test input until the timebase exists;
do not synchronize a running counter bit by bit or advertise a zero placeholder
as a timestamp service. External test controls for sleep/ownership/configuration
are declared by owning domain and remain stable under the endpoint contract.

## Recovery loader binding

`RecoveryLoader` has no LocalBus register interface. Preserve its I2C command
ABI and its `memValid/memReady/memOffset/memWord/memDone` transaction. Bind
the default 2048-byte program and 1024-byte working allocations within retained
SRAM, with loader byte offset zero mapping to its program base. Check bounds
before arbitration and never acknowledge a write until its four lanes commit.
Memory and loader ordinary state share the warm-reset flush; lock uses only
cold reset. Keep lite execution halted during programming. `start` and `entry`
reach the I1 stand-in as observed admission signals, not claimed CPU execution.
`resetReason` and `crashCount` are explicit test-controller inputs until I3.

## Interrupts, stubs and pins

Provisional main fast-interrupt assignment (checked against `soc.yaml`):

| Source | Fast index | I1 status |
| --- | --- | --- |
| uart0 | 0 | real |
| uart1 | 1 | real |
| uart2 | 2 | real |
| spi_host | 3 | real |
| i2c_host | 4 | real |
| mailbox | 5 | real main endpoint |
| usb | 6 | real variant only |
| future_bridge | 7 | inactive reservation |
| dma | 8 | inactive stub |
| gpio_pinmux | 9 | inactive stub |
| actuator | 10 | inactive stub |
| power_reset_timer | 11 | inactive timer-group stub |
| adc_loader_reserved | 12 | inactive in I1; ADC in flight I/O profile |

### Opt-in functional flight I/O profile (T21, D68)

`EmitSocIo` selects the `flight_io` subwindows in soc.yaml. Generated C and
Scala maps include their bases and sizes; I1 retains its error targets and
inactive outputs. GPIO occupies 0x40012000..0x400120ff, main timers
0x40012100..0x400121ff, AON timers 0x40000000..0x400000ff and ADC
0x40020000..0x400200ff. All padding errors. Main services require performance
origin; AON services require lite origin. The outer local timeout remains
128 receiving edges, including the nested GPIO/timer fabric.

In this profile GPIO outputs/input IRQs, timer capture/compare and IMU DRDY
sampling use main clock. GPIO wake samples independently in AON through the
shared CDC block. ADC pins use AON. The `inactive` bundle name and base pin
metadata describe the original I1 profile, not these functional bindings.
QSPI, actuators and JTAG remain inactive in both profiles. Main timer `timeNow`
supplies SPI timestamps; the external SPI timestamp input is ignored here.

Fast IRQ9 is GPIO, IRQ11 ORs main timer IRQ with synchronized AON timer IRQ,
and IRQ12 is synchronized ADC IRQ. AON IRQ ORs mailbox, AON timer, ADC and
GPIO wake. AON timer wake, GPIO wake and ADC IRQ request main service. Main
timers hold main clock while RUN is set; AON deadlines do not need main
clock. Fabric demand bridges the registered peripheral clock-hold latency.
Main service reset clears main registers and GPIO wake transport; AON reset
clears ADC/AON timers and GPIO wake transport but preserves main GPIO values.

Indices 12–14 are reserved inactive. Timer/software/external standard
inputs and watchdog NMI stay inactive until their sources exist. The AON
mailbox interrupt goes to the stand-in. Cross-domain source levels require
shared synchronization; do not sample one-edge pulses in another domain.
Every real source must be tested through the generated assignment with a
wrong-index negative control. This is fixed wiring, not a completed interrupt
controller or a decision about final priorities.

Absent-block stubs retain declared final ports, error every MMIO access and
drive IRQ/wake inactive. Output enables are false, SPI/QSPI selects inactive,
open-drain pins released, actuator outputs disabled. The existing `UsbStub`
inherits working `UsbRegisters` and therefore is not the T20 all-access-error
stub. T20 must provide a separate same-port error wrapper while leaving real
USB behavior unchanged. Real USB remains an explicit build variant with its
existing owner checks and carried timing/proof limitations; test VID/PID
values do not allocate production identifiers.

The gateway is currently a protocol specification only. UART/USB byte ports
do not imply a bus-master gateway exists. Reserve its MMIO space and disable
its master; a future protocol adapter must be named and reviewed before any
gateway-based system test can claim an end-to-end pass.

Logical simultaneous pin groups for `soc.yaml`: UART0/1/2 TX/RX; SPI SCLK,
MOSI, MISO, CS0/1 and IMU DRDY; sensor I2C SCL/SDA; separate recovery SCL/SDA;
QSPI SCLK/DQ0–3/boot-CS/log-CS; nine actuator outputs; JTAG TCK/TMS/TDI/TDO;
external clock/reset; USB D+/D-, VBUS sense and pull-up control; remaining GPIO.
Pins have unique logical allocations, directions and safe enables. T20 must
check simultaneous fit against the provisional pad budget, including USB
sharing and the remaining GPIO count; final pad numbers are frozen at G1.
Do not claim physical fit from logical names alone. I1 keeps
unimplemented alternate functions inactive rather than inventing a pin mux.

I1 now exposes the defined inactive QSPI, actuator, JTAG and IMU DRDY logical
boundary through `SocI1Pins.inactive`; see the
[stub contract](../../hw/top/stubs/README.md). QSPI has separate DQ input,
output and per-bit enable signals, separate SCLK enable, and two inactive-high
selects with disabled enables. All nine actuator outputs/enables and JTAG
TDO/enable are zero. JTAG inputs and IMU DRDY are ignored: no capture, debug,
interrupt or wake function is implied. Static tie-offs are independent of all
clocks/resets; there is no input-to-output logic or retained actuator state.
The map's `inactive` clock label denotes an unsampled function, not a new
clock domain. Elaboration checks these port widths against the generated map.
The GPIO/ADC/timer logical contract is now defined below. No package pad number
or final physical fit is claimed.

D71 raw ADC ABI: the functional ADC profiles publish raw codes at
0x40020010. The former scaled result at0x40020014 is retired; reads and
writes error. Other offsets, ownership and AON reset scope are unchanged.
Conversion/calibration is firmware policy; see the [historical T27 report](../plan/tasks/reports/T27.md).

### Provisional GPIO, ADC and timer pin contract

The user requested completion of these contracts on 2026-11-21. The I1
allocation uses three GPIO pins, four timer capture/compare pins and the
retained receive-only ADC boundary. These are logical interfaces, not new
functional peripherals or a G1 pad freeze.

| Function | Inputs | Outputs | Enables | I1 safe behavior |
| --- | --- | --- | --- | --- |
| GPIO | gpioIn[2:0] | gpioOut[2:0] | gpioEnable[2:0] | inputs ignored; output/enables zero; no wake |
| Timer channels | timerIn[3:0] | timerOut[3:0] | timerEnable[3:0] | inputs ignored; output/enables zero; no capture/IRQ |
| SPI ADC | adcMiso | adcSclk, adcCs_n | adcSclkEnable, adcCsEnable | MISO ignored; SCLK low, CS high; enables zero |

All enables are active high; bidirectional interfaces separate input, output
and enable. A timer channel uses one pin for capture or compare, not two
independent pins. IMU DRDY remains a separate reserved timestamp input. The
microsecond timebase is internal and adds no pin. GPIO wake/event capture and
timer capture synchronization will use the shared CDC primitives in their
future implementation; no asynchronous input is consumed by the inactive stub.
GPIO/timer eventual reset ownership is the existing main/AON register-window
contract; ADC is AON/lite-owned. Static inactive outputs require no clock/reset
and cannot assert IRQ, wake or clock demand. All corresponding MMIO accesses
continue to error in the existing GPIO, power/reset/timer and ADC windows.

The ADC wire inventory comes from the pinned clocked RISCay
`ClockedSpiAdc.scala` at `4671317186003740ceb61360ba08c59bbdf10136`, inspected
in the T06 checkout under `build/riscay-mcu/`: MISO, SCLK and one CS, without
MOSI or ready. This does not select an external ADC part, establish simultaneous
voltage/current acquisition, or import its functional RTL.

Estimated simultaneous digital pin demand (all existing baseline functions,
real USB, and these inactive reservations):

| Pad class | Estimated allocation arithmetic | Cited slot capacity | Remaining |
| --- | --- | --- | --- |
| Bidirectional-capable | UART TX 3 + SPI outputs 4 + I2C 4 + QSPI 7 + actuator 9 + USB data/pullup 3 + JTAG TDO 1 + ADC outputs 2 + timer 4 + GPIO 3 = 40 | 40 | 0 |
| Input-only | UART RX 3 + SPI MISO 1 + IMU DRDY 1 + JTAG inputs 3 + VBUS 1 + ADC MISO 1 = 10 | 12 | 2 |

Capacities are the historical slot figures in plan 08, not a freshly verified
pad ring. Dedicated external clock/reset and the two analog pads are separate
as in that source; I1's three externally supplied service clocks and multiple
test reset controls are simulation/integration controls, not a package pinout.
This explicit allocation totals 40 bidirectional/10 input-only functions and
exceeds the earlier plan-07 bidirectional estimate by `40 - 32 = 8`.
It does not change the slot limit or waive a fit
check. No sharing or mux savings are assumed. `soc.yaml` and its checker account
for every logical pin against the 40/12 nominal capacities and reject overflow.
USB PHY pad eligibility, scan/test access sharing, analog requirements, clock
source selection and physical assignment remain G1/physical-flow obligations.

## Verification and acceptance boundary

The integrated core fixture may relocate the same modeled SRAM to QEMU RAM
at `0x80000000` and ROM to `0x80010000`, retaining their production capacities,
banking, arbitration and response timing. It explicitly separates the SRAM
image from a ROM bootstrap at `0x80010080`; padded historical images must not
be truncated into SRAM. All allocated ELF sections, BSS and reserved stack
must fit the real SRAM capacity. Flight sources, compiler options, scenarios,
loop windows and round-2 comparison limits remain unchanged; only the linker
stack placement may change. Architectural test bytes remain unchanged.

An elaboration-only verification option adds registered fabric targets for
the existing QEMU finisher (`0x00100000`), MSIP (`0x02000000`) and flight markers
(`0x10000000/4`). MSIP supplies the core's software interrupt. These targets
return real bus responses and cannot supply architectural instruction results.
Test SRAM initialization matches the old responder's image/zero initialization;
it is not a production reset guarantee. Production defaults expose none of
these targets or initialized SRAM. RVFI is the only retirement observation.
This fixture qualifies integration against the existing suites, not the
production address map, gateway, physical memory or final system acceptance.

Before RTL: independent review of this contract and the generated map schema.
Then model/negative-control tests for map generation, address errors, trusted
origins, local memory, bridge/reset isolation and interrupt wiring. SoC formal
proves composition properties; it does not rerun or strengthen block internals
without a separate brief. Track assumed clock progress/quiescence explicitly
and discharge each integration guarantee on the real connected design.

I0/I1 firmware tests use the plan's target interface. That interface and the
simulation adapter do not yet exist in this checkout; neither does the gateway
RTL. An adapter design must distinguish preloads/test masters from actual
gateway transport. This is an open interface-review item, not permission to
bypass the required system-test boundary or report a host-only model as RTL.

Carry T13's open formal acceptance; T14's four approved unproved properties
and production-watchdog scope; T17's eight unproved jobs; T19's routed setup,
boundary/RDC/physical and sampling/exception obligations. T19's twelve packet
claims qualify under their mixed-size policy, not all as full-size proofs.
The block reports retain detailed simulation/bounded-proof/physical limits.

### I1 composition implementation

The I1 peripheral assembly is a core-independent submodule of the same top,
with a main-domain performance MMIO port and an AON lite stand-in port. It
uses the existing eight-target fabrics; serial and gateway subfabric apertures
and membership come from `soc.yaml`. The I0 fixture remains available for
unchanged performance comparisons. Main/AON ingress clamps forbidden routes
to a statically checked unmapped address before fabric arbitration. Legal
payloads remain unchanged; incoming bridges cannot bounce or reach the local
mailbox staging interface. Lite origin is assigned at the trusted boundary.

Disjoint remote fabric ports share one bridge in each direction. Their requests
are one-hot with identical captured payload; the region index is retained on
actual bridge acceptance and demultiplexes the response, including quarantine
drainage. Destination acceptance credits live under destination-service reset,
not peer/transport reset. Their empty indication acknowledges bridge quiescence
only when destination and subordinate fabric isolation has also drained.
Parent serial/gateway quarantine receives a registered acknowledgement built
from child request/grant/response, waiting/isolation and endpoint activity. This
recovers a parent timeout before child acceptance without reopening orphan work.
Independent USB reset may cancel application work; its slot must recover through
the fabric timeout/isolation and the actual application-reset acknowledgement.
No serial engine `quiescent` signal is used as a bus-drain acknowledgement.

All integration control inputs are explicit test-controller ports in their
stated clock domains. Fixed owner settings, inactive sleep requests and external
running clocks preserve I1's existing policy; this is not a power controller.
Demand collection uses the cold/warm controller reset cohort, so an AON service
reset does not erase a surviving main-domain request. USB wake contributes to
both main and AON demand. These outputs exclude the core's independent running
requirement and are not permission to stop either clock.

The retained loader adapter rechecks halt/lock/range at actual acceptance. A
malformed controller that revokes permission during an advertised registered
grant causes no write or completion; the adapter quarantines until service
reset. Normal loader completion follows the actual synchronous RAM write.

The I0 implementation now connects the production core, modeled ROM/SRAM,
local-memory adapter, fabric and UART0. Its focused boot test exercises SRAM
byte writes and an FPU multiply, and prints through UART0. `clockHold` currently
exports UART demand only: the main clock must continue running externally.
Local memory has D65 exclusive current-request grants, synchronous word banks and
accepted-beat response metadata. The service-reset MMIO slot survives a
client-only reset and drains before releasing a new epoch. Focused control
properties and tests are reported in the T20 report; this does not establish
the brief's full SoC composition or gateway-based acceptance.

D64 permits testing a current-cycle idle-slot donation exception to registered
grants, as specified in the reference README. Only an idle instruction slot may
serve data early; current fetch requests prevent donation. This experiment
retains exclusive acceptance, the existing busy/reset guards and response
latency. Retention requires correctness, performance and integrated timing
qualification; approval alone does not change the accepted baseline.

D65 extends the approved experiment to arbitrate current requests under
contention. A client-reset preference initially favors instruction and changes
to favor the other client on each accepted transfer. Only one beat is accepted
per cycle. Data acceptance requires epoch readiness, no busy transaction and no
public data response in the current cycle. The instruction grant can assert
as soon as epoch readiness asserts, without the prior extra grant-register
edge. Response latency, MMIO retention and reset scopes stay unchanged.
Qualification of the combinational grant exception remains mandatory.

The T20 report records focused QEMU-compared workload performance and diagnostic
mapped logic timing/area for D65. D67's retained control passes I0 logic screening; physical memory,
full lockstep acceptance and pin-fit qualification remain open.

The opt-in T24 profile adds the D39 limited GPIO output alternate functions
to the functional DMA assembly. At 0x40012200, each of three main-service
selectors chooses disconnected, same-index GPIO, timer compare or PWM. The
pad data/enable are registered, with a disabled interval on selection changes;
firmware must quiesce a source when truncated pulses are unacceptable. Raw
GPIO inputs and AON wake remain connected independently of output selection.
Dedicated timer/PWM pins and all serial/input routes remain unchanged. Core
and AON reset preserve the selection; main-service/cold/warm reset disconnects
it. This is a logical profile and does not resolve physical pad-fit decisions.
The user's no-CI instruction remains active. Fast
and full tiers must be reported unrun until authorized; no task/gate is complete.

## T26 optional digital watchdog profile

D70 binds performance expiry to the existing performance core/client reset
and PWM output disable. Main service fabric, SRAM service side, DMA and
other peripherals survive; old accepted CPU MMIO drains before epochReady
permits new fetch or PWM break acknowledgment. Lite expiry joins warm reset
for ordinary main/AON/USB state, while POR-only causes, counts, reset hold
and loader lock survive. External test clocks remain the clock sources.

The power_reset_timer aperture contains its unchanged AON timer at offset0,
performance watchdog at offset0x100 and lite watchdog at offset0x200, each
256 bytes. Owners are respectively performance and lite. Register definitions
come from watchdog.regmap.yaml. Performance pre-warning crosses shared CDC
to irq_nm_i; enabled watchdogs retain AON demand. Cause bits0/1 report
performance/lite expiry. Loader crashCount is the saturating sum of both
channel counts, registered one AON edge later. The watchdog profile overrides
the fixture's externally supplied resetReason/crashCount; prior profiles do not.

PWM requires STOP acknowledgment followed by APPLY after reset in this
profile. A surviving DMA APPLY cannot clear the output-disable latch. Pinmux
PWM pads disable asynchronously; GPIO/timer alternatives survive performance
expiry. Lite-watchdog reset currently invalidates loader START/validImage
while retaining its programming lock, so this stage does not implement
autonomous restart of a locked image. Physical clock/reset qualification,
oscillator selection, lite-first boot and sleep/wake remain separate work.

## T28 optional lite-first release

The boot-control profile extends T26 with lite-owned MMIO at0x40000300,
size0x100, in the existing AON power_reset_timer parent. Status0x00 exposes
boot_seen/released; full-word key0x50455246 to release_core0x04 releases
performance only after a validated recovery START. Events0x08 records early
or incorrect keys. The owner is the real lite hart; the stand-in bus input
is inert in this production profile.

boot_seen records a START in this whole-reset epoch, not current lite health.
Both flags survive AON service reset; adapter/register pulses do not survive
that reset. Whole reset asynchronously clears the release. The release enters
only the existing performance core/client reset synchronizer, preserving
shared service/DMA/PWM reset scopes and the memory epoch drain. Correct
repeated keys are idempotent. A START and key on the same AON edge cannot
release performance on that edge.

External clocks and earlier profiles are unchanged. No production flash boot,
image authentication, oscillator selection, sleep control or autonomous
locked-image warm restart is implied. Those remain separate qualification
and implementation work. See hw/ip/boot_control/README.md for the full contract.

## T29 optional QSPI command profile

The T29 profile replaces only qspi_control at0x40013000/4096 bytes, using the
existing two chip selects, four bidirectional data pins and SCLK. It extends
T28 with bounded mode0 serial/quad commands and registered demand. XIP remains
an error target. No new interrupt or DMA endpoint is assigned.

This profile explicitly adds idle-only keyed ownership handoff between lite0
and performance1. Reset owner is lite. The historical I1 fixed-owner contract
continues for older profiles and other peripherals. The endpoint rechecks
trusted origin at admission through its single-outstanding adapter; handoff's
response returns to its original requester and subsequent former-owner
requests fail. Main-service reset clears the controller and disables pads;
AON and performance-core resets preserve an already accepted flash command.

The engine never holds CS for software continuation or automatically polls
flash busy. Each frame and CS-high gap is bounded in serviced main-clock edges.
Firmware owns part configuration, write-enable/program/erase sequencing and
completion polling. Resetting the controller cannot undo a flash-internal
operation already accepted. Full production boot, XIP/logging arbitration,
flash compatibility, throughput and physical pad timing remain open. The
authoritative command/pin contract is hw/ip/qspi/README.md.

## T30 optional native flash profile

The T30 profile extends T29 with a registered native local-memory connection
to the existing XIP window. Aligned performance instruction/data reads share
the QSPI engine with captured CS1 software commands. Native permission is
independent of MMIO configuration ownership; DMA remains SRAM-only. The
peripheral fabrics and their response deadlines are unchanged.

Native words are little endian. A three-byte flash address rejects offsets
outside its representable range; four-byte addressing uses the whole window.
Disabled XIP, writes and invalid origins/addresses return zero plus error.
Idle-only keyed configuration lives at QSPI offsets 0x100 through 0x10c.
Raw CS0 commands are denied while XIP is enabled. Firmware configures the
part and polls it ready before enabling reads, executing configuration code
from ROM/SRAM. Complete frames arbitrate round robin without preemption.

The local memory controller retains an accepted read across client reset,
suppresses its orphan response and waits for both native and MMIO drains
before epochReady. Main-service reset aborts the controller and disables pads.
Later fetches cannot overtake an outstanding native instruction read; local
data and DMA traffic may proceed independently. No cache or prefetch is added.
See hw/ip/qspi_xip/README.md for the complete contract and estimated bound.
Production image selection/recovery, flash-part compatibility, system
performance and physical qualification remain separate.
