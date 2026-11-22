# 07 Peripherals, memory, boot and debug

Approved architecture is in [03-architecture.md](03-architecture.md).
Capacities/counts are requirements; unmeasured rates, latencies, area and
buffer depths remain targets/assumptions until the relevant task reports.

## Peripherals

| Peripheral | Baseline | Requirements |
| --- | --- | --- |
| UART | Three | 8N1, inversion, target up to 921,600 baud, FIFOs; receive/wake-only/disabled sleep modes |
| SPI controller | One, two chip selects | Modes 0/3, target at least 4 MHz; timestamped IMU acquisition, DMA |
| I2C controller | One | 100/400 kHz targets, clock stretching and stuck-bus recovery |
| I2C target | One, RISCay carryover | Existing recovery loader frozen by D73; T31 withdrawn |
| External ADC access | Firmware through general SPI, DMA where needed | D74 retires the dedicated ADC block; its former window and pins are unassigned |
| QSPI flash | Boot/XIP and separate logging chip selects | Bounded arbitration; no flash program/erase blocking the control loop |
| USB | Full-speed CDC-ACM in the production top | Separate domain and FIFO boundary; existing physical cutoff remains a future explicit decision, not an opt-in profile |
| Timers | Four capture/compare plus microsecond timebase | Timer-driven control loop; timestamp sensor events |
| Timer/PWM outputs | Capacity for the first board; generic channels | Programmable periods/compare, buffered updates and DMA; no motor/servo roles or command timeout engine (D69) |
| Basic DMA | SPI and UART | Ownership/memory checks, bounded bursts, completion/error IRQ; no linked descriptors initially |
| GPIO/pin mux | Remaining pins | Limited alternate functions, wake, reset-disabled outputs |
| Interrupt/debug | Both cores | Bounded interrupt service; JTAG halt/step/register/memory access |

Serial peripheral ownership is exclusive and programmable. Ownership checks
apply equally to local bus, bridged and DMA requests. Clock bridges and
bounded arbitration must preserve latency bounds and prevent partial ownership
transfer. Shared peripherals may run while the performance core sleeps; HF
requests originate through always-available control paths.

### General-purpose timer/PWM outputs (D69)

Use conventional timer/PWM/capture/compare primitives, buffered register updates,
DMA requests and interrupts. Ordinary output-disable/break facilities may be
specified in the timer brief; this is not an approval for a flight command engine.
Firmware constructs DShot waveforms, publishes application command sets,
tracks command age and chooses arming, recovery, endpoints and failsafe behavior.
Generic watchdog/reset containment and reset-disabled outputs remain required.

The first board uses external ESCs and servos. Their timing, loss-of-signal and
fault behavior remain application/bench validation obligations, not dedicated
hardware registers or motor/servo assignments. Existing logical pin/window
reservations remain provisional until the generic PWM/DMA brief reconciles them;
no address or pin is silently changed here. The [old actuator draft](../spec/actuator-block.md)
is historical and superseded as an RTL contract.

### USB contract and cutoff

Implementation is assigned in [T19](tasks/T19-usb.md), using the supplied
`peripherals-ip/USB_FS_CDC` source snapshot. Its adoption assessment must resolve
vendor timing/CDC rule conflicts; source availability is not qualification.

USB protocol handling stays in its subsystem. Boundary: TX/RX byte FIFOs,
status/control, interrupts and wake, through the reviewed CDC implementation
into its separate clock/reset domain. PLAN03 binds real USB in production;
the identical-port stub is only a named test substitution.

Implementer supplies source/macro licence and provenance, executable verification,
timing constraints, reset/clock requirements, PHY/pad arrangement and area. New
project RTL is Chisel; any externally supplied vendor RTL follows vendor rules.
Reserve space/pads only with explicit assumptions until these figures arrive.
The old roughly 0.5 mm2 placed reservation and external 48 MHz reference are
**assumptions**, not accepted implementer measurements.

**Cutoff: before Phase 3 floorplan freeze.** If USB is not ready, omit it and
proceed with UART gateway and JTAG. Freeze the omitted block's safe pad behavior
and rerun physical/functional checks. The interface is approved; delivery and
physical qualification are not complete.

### Flight logging

Existing plan: separate logging flash chip select on the QSPI bus, with bounded
transactions interleaved with boot-flash XIP. UART streaming is the initial
prototype fallback. No logging-flash part or UART board allocation has been
approved. The 64-byte record at 1 kHz is an **assumed format**: estimated rate
64,000 bytes/s; ten minutes requires 38.4 MB before metadata. Capacity, buffer
size, program stalls and arbitration need S3/system measurement. Drop/count
records on overflow rather than block the control loop. Preserve the existing
storage requirement in R-PER-8; do not treat a throughput estimate as a proof.

## Memory

| Memory | Approved baseline | Organization |
| --- | --- | --- |
| Performance SRAM | 16 KiB | 32-bit word-wide interface, byte-write enables, configurable banks |
| Lite SRAM | 3 KiB retained | RISCay program/data starting organization; configurable banking |
| Boot ROM | Capacity not measured | Two-core boot and recovery code |
| External QSPI NOR | Part/capacity to qualify | Boot images and cold-code XIP |

Four byte-wide qualified macros in parallel per bank provide word-wide access
without increasing stored bits. A qualified wider macro is also acceptable.
Macro latency, power and routing overhead require measurement. Using sixteen
existing 1024x8 footprints gives **estimated** performance macro area
16 x 155,414 um2 = 2.487 mm2, excluding wrapper/routing. No claim of one-cycle
access or reduced power follows. S3 checks capacity and banking; room for growth
is a design intent, not a demonstrated fit for a larger memory.

Hot code, handlers and their reachable callees execute from SRAM. Cold code
uses XIP. Include FPU software, actual sensor drivers, DMA buffers and BMI270
initialization streaming in the memory budget; historical inner-loop state alone
does not establish full-firmware fit.

## Boot and debug

T36 implements production ROM firmware; T32 implements unlocked two-hart debug.
The existing I2C recovery loader is frozen at its current features and reset/lock
policy (D73); no T31 extension is authorized. Before autonomous QSPI boot, T36
must resolve the current loader-only lite start/protected-program path without
silently changing ownership or extending the loader.

Keep the RISCay CRC/compatibility checks, A/B and golden recovery approach and
programming lock, adapting to two images and a QSPI controller. Lite boots
first, loads valid calibration/configuration and its image, then releases the
performance core to validate/load its hot image and start. Recovery loading
remains available through the loader/gateway when images are invalid.

**No signed firmware.** CRC detects corruption, not authenticity. Unlocked
JTAG and UART gateway permit physical debug/programming access. The programming
lock prevents accidental transaction misuse; it is not a security boundary.
No authenticated debug or permanent debug-disable fuses. Explicit test mode
provides scan access; include SRAM self-test and analog calibration/test access.

## Pin allocation

Use limited register-selectable alternate functions; general-purpose outputs
disabled at reset. Dedicated external clock/reset and JTAG pins remain.
The initial chip has no chip-to-chip QSPI pads or required LF crystal driver.

The provisional budget is 32 bidirectional and 10 input-only functions before
final muxing, test access and USB PHY review. Dedicated clock/reset and analog
pads are counted separately. The pinout remains provisional.

Freeze the exact map at G1 against the selected slot and simultaneous interfaces.
Three UARTs are a baseline capability; GPS/RC/telemetry pin assignments and the
proposed shared telemetry/configuration UART policy were not approved.
