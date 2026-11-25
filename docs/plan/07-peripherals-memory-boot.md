# 07 Peripherals, memory, boot and debug

PLAN05 D92-D101 is the current target contract; production migration remains
pending in STATUS. The I2C recovery loader is removed, superseding its freeze.
Keep all nine PWM and four timer physical pins for twelve muxed channels.

Approved architecture is in [03-architecture.md](03-architecture.md).
Capacities/counts are requirements; unmeasured rates, latencies, area and
buffer depths remain targets/assumptions until the relevant task reports.

## Peripherals

| Peripheral | Baseline | Requirements |
| --- | --- | --- |
| UART | Three | 8N1, inversion, target up to 921,600 baud, FIFOs; receive/wake-only/disabled sleep modes |
| SPI controller | One, two chip selects | Modes 0/3, target at least 4 MHz; timestamped IMU acquisition, DMA |
| I2C controller | One | 100/400 kHz targets, clock stretching and stuck-bus recovery |
| AON SPI | One chip select, lite-owned | Mode0/3, programmable LF divider, eight-byte TX/RX FIFOs and completion interrupt; no external oscillator required |
| AON GPIO | Six GPIO-capable pads with limited alternates | Four SPI signals plus two GPIO simultaneously; short-pulse edge capture, lite IRQ, radio power output |
| External ADC access | Firmware through general SPI, DMA where needed | D74 retires the dedicated ADC block; its former window and pins are unassigned |
| QSPI flash | Boot/XIP and separate logging chip selects | Bounded arbitration; no flash program/erase blocking the control loop |
| USB | Full-speed CDC-ACM in the production top | Separate domain and FIFO boundary; existing physical cutoff remains a future explicit decision, not an opt-in profile |
| General timers | Microsecond timebase plus three timers with four channels each | Shared prescaler/period per timer; each channel PWM/output compare/input capture; period-boundary shadow compares; all running channels hold main clock |
| Basic DMA | SPI and UART | Ownership/memory checks, bounded bursts, completion/error IRQ; no linked descriptors initially |
| GPIO/pin mux | Remaining pins | Limited alternate functions, wake, reset-disabled outputs |
| Interrupt/debug | Both cores | Bounded interrupt service; JTAG halt/step/register/memory access |

Main UART/SPI/I2C/QSPI ownership is exclusively performance; AON SPI/GPIO belong to lite. Ownership checks
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
| Lite SRAM | 2 KiB retained, D96 | Proposed 1 KiB program + 1 KiB data from measured watcher; implementation pending |
| Boot ROM | Capacity/area not yet measured | One performance ROM at0x0, reset entry0x80; no lite ROM |
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

T36 implements the reviewed [single-master boot contract](../spec/boot-rom-proposal.md).
Performance ROM validates the paired A/B/golden bundle, loads both images,
and releases lite if requested. Only performance may write lite program RAM,
and only while boot control holds lite reset. The application can later hold,
reload and release a watcher. Other program writes error without effect.

Recovery uses performance-ROM UART0 plus JTAG, with no I2C loader or handoff.
Performance-only reset validates/reloads the same generation without touching
lite state; fail closed if ownership/drain or image validity cannot be established.
Sleep wake resumes after WFI and does not execute ROM.

**No signed firmware.** CRC detects corruption, not authenticity. Unlocked
JTAG and UART gateway permit physical debug/programming access. The programming
lock prevents accidental transaction misuse; it is not a security boundary.
No authenticated debug or permanent debug-disable fuses. Explicit test mode
provides scan access; include SRAM self-test and analog calibration/test access.

## Pin allocation

Use limited register-selectable alternate functions; general-purpose outputs
disabled at reset. Dedicated external clock/reset and JTAG pins remain.
The initial chip has no chip-to-chip QSPI pads or required LF crystal driver.

PLAN05's estimated physical demand is 40 output-capable and 12 input-only
pads against unchanged assumed capacities 40 and 12. Remove two loader pads,
add three AON-extra pads and reuse three existing GPIO pads as alternates.
BOOT_MODE reuses GPIO1/MOSI; all nine PWM and four timer pads remain. OSC_IN reuses the
dedicated clock pad; external reset and analog pads remain separately counted.
This is an inventory estimate, not pad placement or electrical qualification.

| Dedicated clock/control function | Direction | Reset/startup contract |
| --- | --- | --- |
| OSC_IN | Clock input | External 48 MHz CMOS, USB directly and main /6 |
| OSC_EN | Output | High during reset, board pull-up; controls true oscillator standby |
| AON_CLK_IN | Clock input | First-silicon external AON fallback |
| AON_CLK_SEL | Strap input | Sample while reset held, freeze before domain release |
| POR_BYPASS | Static strap input | D84: default low, fixed while powered; directly bypass on-die POR/brownout for pin-only recovery |

The board oscillator must support 48 MHz, 3.3 V CMOS output, true standby with
microamp current (output-enable alone is insufficient), and total frequency
tolerance well within USB full-speed +/-0.25%. An **assumed** 5 ms maximum
startup/resume is based on the [SiT8008B datasheet](https://www.sitime.com/datasheet/SiT8008).
Its 3.3 V standby specification is 2.1 microamps typical, 4.3 microamps maximum;
these are vendor specifications, not project measurements. A
[48 MHz, 3.3 V, +/-20 ppm standby option](https://www.sitime.com/parts/sit8008bi-71-33s-48000000)
illustrates feasibility; no board part is selected or qualified by this plan.
Recheck the actual ordered part's startup, output loading and temperature range.
Plan06 includes startup margin and separate oscillator-on/off sleep contracts.

D81 retains the oscillator whenever USB is enabled. D82 keeps recovery I2C on
AON and requires host SCL <= minimum qualified AON frequency / 8 (estimated
nominal 4 kHz). This restriction is on the dedicated recovery target, not the
general main-clock I2C controller.

Freeze the exact map at G1 against the selected slot and simultaneous interfaces.
Three UARTs are a baseline capability; GPS/RC/telemetry pin assignments and the
proposed shared telemetry/configuration UART policy were not approved.
