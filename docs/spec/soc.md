# Reference SoC contract — T20 I0/I1

Draft for independent review, 2026-11-20, based on `f1c17ba`. This specifies
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
reset leaves AON loader, lock and SRAM contents intact and does not clear
actuator failsafe state. The actuator is still an inactive stub in I1.
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

## Verification and acceptance boundary

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

No acceptance command, integrated area/timing, firmware boot, pin-fit check or
SoC proof is claimed here. The user's no-CI instruction remains active. Fast
and full tiers must be reported unrun until authorized; no task/gate is complete.
