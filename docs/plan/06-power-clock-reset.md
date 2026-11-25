# 06 Power, clocks and reset

## PLAN05 dormant contract

| Mode | Required behavior |
| --- | --- |
| Sleep | Performance in WFI; external oscillator running; main peripherals may run; wake in cycles |
| Deep sleep/dormant | Main clock stopped, external oscillator in standby; DMA idle, UART TX drained, all general-timer channels stopped and USB disabled under D81; lite and its AON SPI/GPIO operate at nominal 32 kHz |
| Wake from dormant | Raise OSC_EN, wait/qualify startup, resume retained performance state after WFI; never re-enter ROM |

RAM remains powered in every mode (D100). Freeze performance-watchdog count,
window and warning state for committed dormant and through oscillator restart;
resume only with qualified main operation. WFI alone never freezes it. Expiry
at admission wins over sleep, cancelled entry unfreezes, and reset-hold logic
is never paused. Lite watchdog stays active with its existing reset scope.
Raw radio IRQ and AON SPI completion wake lite only. A validated mailbox
message wakes performance; AON-owned radio pad edges must not also trigger
main GPIO wake. Pad selection and watcher state survive performance-only reset.

The general toMain bridge and recovery loader are removed. Main serial blocks
remain usable in oscillator-on sleep but are inaccessible to lite. Boot order
is AON release with lite held, qualified oscillator/main release, performance
ROM, explicit lite release. No lite ROM or fast AON service clock is added.

Measured Phase1 watcher source-hashed on main29cab7e with
`python sw/lite/watcher/measure.py --routed --output build/plan05/watcher-opt05`:
worst modeled routed publication2764cycles and return-to-WFI2996cycles.
Estimated at assumed32000Hz:86.375ms and93.625ms. This is not integrated
peripheral, LF-frequency or power qualification. The production dormant tests measure2633AON ticks from radio IRQ to OSC_EN
(estimated82.28125ms at nominal32kHz), and2644ticks to copy the lite image
(estimated82.625ms, diagnostic copy without production ROM verification).
Final ROM copy/readback measures16,405,620 quanta for the588-byte watcher
(estimated170.891875ms at assumed96MHz quantum), and28,504,620 for1024bytes
(estimated296.923125ms). D104 accepts only the maximum-image250ms excess
for now; T42 retains the original target. B12 library leakage estimates below exclude dynamic and
board power; no complete microamp system-current signoff exists.


Approved scope: retained clock-gated sleep, programmable sleep peripherals,
on-die LF RC, external 48 MHz clock with divided main, reset-held LF fallback,
and on-chip POR/brownout (D78/D79).
Targets below are assumptions pending characterization, not silicon results.

## Power modes and wake

| Mode | Behavior |
| --- | --- |
| Run | Both cores and required peripherals clocked; idle blocks gated |
| Sleep | Performance WFI with oscillator running; main peripherals may continue; wake in cycles |
| Deep sleep/dormant | Main stopped and oscillator in standby after all holds release; lite/AON SPI/GPIO continue at LF; RAM retained |
| Wake from dormant | Qualify oscillator/main restart and resume after WFI; not a boot |
| Power-gated standby | Out of scope; retained RAM is never powered down |

Sleep drains/cancels outstanding transactions and checks pending wakes before
gating. HF is stopped only when no enabled consumer needs it. Keep request/wake
capture and ownership control available in AON so starting HF never requires
a transaction through a stopped domain. SRAM retention is not a power-off claim.

SPI, I2C and UART are selectively available during sleep. Each UART selects:

- **Receive:** retain the clock necessary for full reception and FIFO operation.
- **Wake-only:** detect activity, request HF; first byte may be lost, requiring
  a sender preamble or retry contract.
- **Disabled:** no receive or UART wake.

Timer deadlines, events (including GPIO and internal notifications),
and JTAG wake are supported. Optional USB resume also requests wake. Pending
wake survives clock gating. All asynchronous input capture is reviewed CDC,
not new latch-based storage. Enabled peripherals retain their required clocks. Application arming and
sleep eligibility beyond those clock demands are firmware policy (D69).

## Clock sources

| Source | Purpose | Qualification still required |
| --- | --- | --- |
| Internal nominal 32 kHz LF RC | AON, watchdogs, sleep timers | Trim, layout, startup, corners and power under T34 |
| OSC_IN, external 48 MHz CMOS | Direct USB; registered /6 main at 8 MHz | Board oscillator standby/startup, frequency tolerance, jitter, duty cycle and pad limits |
| AON_CLK_IN fallback | Replaces RC when reset-sampled AON_CLK_SEL selects it | Valid fallback clock while reset held; no runtime source switching |

Retained **assumed targets**: LF within 5 percent after trim and under 1 microamp;
whole-chip quiescent sleep below 50 microamps at 25 C. No internal HF oscillator
is included. Oscillator-off wake no longer has the former 200 microsecond
target: it includes the board part's startup, AON delay and OSC_IN stability
count. Plan07 assumes a 5 ms maximum board-part startup pending selection.
Initial controller planning assumptions are 512 AON startup ticks (estimated
16 ms at nominal 32 kHz, 15.238 ms at assumed +5%) and 256 OSC_IN stable edges
(estimated 5.333 microseconds at 48 MHz), plus shared CDC/release latency.
These defaults are not measured silicon guarantees. Oscillator-on sleep avoids
the startup delay; its wake latency must be measured separately.
Sleep power with receive-mode UART or active sensors is a separate mode.
S1 determines feasible main frequency; analog work establishes actual tolerances.

No PLL or LF crystal driver is required. Calibration may be loaded after safe
startup. Strap selection is permitted only while domains remain reset; test
fallback with failed RC/POR and qualify clock selection at the cell level.
D93 removes recovery I2C and its D82 rate contract. AON SPI derives SCK from
the same LF source; nominal rates remain estimates until LF characterization.

## Reset containment

| Cause | Required effect |
| --- | --- |
| Performance watchdog | D70: reset performance core/client epoch and disable PWM outputs; preserve shared buses, DMA, other peripherals, lite core, retained AON SRAM and reset reason |
| Lite watchdog | Reset whole MCU and disable outputs according to generic reset semantics |
| Power-on/brownout | Whole-chip reset and disabled general-purpose outputs |
| External reset | Whole-chip reset with qualified release |

Assert reset asynchronously and release synchronously per domain only after
supply/clock qualification. Flush or cancel crossing transactions under a
defined protocol; stale responses must not reach the restarted core.
Peripheral reset scopes and clock-demand guarantees must be explicit; D69
removes the dedicated retained actuator-failsafe requirement. Reset reason is
retained in AON across performance reset;
no retention guarantee is made across power loss or brownout.

D79 combines external-pin assertion with non-bypassed POR/brownout for ordinary
domains. D84 makes POR_BYPASS a static board strap, default low, held fixed from
power application until power removal. It directly selects the reset source;
no uninitialized latch may mask the POR needed to initialize that latch.
AON_CLK_SEL remains sampled while reset is held and then frozen; its capture
must work with the internal RC failed. Release AON only after counted local
edges, then qualify OSC_IN before releasing main/USB through shared primitives.
D93 removes loader-specific reset cohorts. D83 makes external pin reset cold
in bypass mode only, initializing retained watchdog history and debug POR
state. Whole-chip reset holds lite until explicit performance release. Watchdog containment
is unchanged. Preserve distinct POR,
brownout, external-pin and watchdog causes for T33 reset-reason recording.

## Generic output fault handling (D69)

Retain standard watchdog reset, reset-disabled outputs and any explicitly
briefed ordinary timer output-disable/break input. Do not build per-actuator
fallback values, stale-command tracking or arming/recovery policy into RTL.
Firmware and board-level supervision define application fault responses and
validate external-device loss-of-signal behavior. No output waveform guarantee
applies when clock or supply is invalid.

## Supply monitor

Keep RISCay's bandgap/comparator starting point and implement **selectable
thresholds, hysteresis and qualified reset release**. A safe hardware-default
threshold must protect startup before firmware/flash settings exist. Threshold
selection must not transiently release reset or bypass safe operating limits.
Defer the separate early-warning detector; brownout is a reset condition.

Determine thresholds and release interval from qualified SRAM/logic voltage
limits, board regulator tolerance, noise, slow ramps and mismatch. The previous
RISCay fixed thresholds and hold-cycle count are reference data, not Deadhorse
acceptance limits. Selection controls, safe encodings and calibration storage
need an analog brief; no OTP/eFuse requirement is implied. Keep external reset
available for optional board supervision. Analog layout and qualification have
not been performed by this project.

## PLAN05 Phase2 library leakage estimate

Command: `python hw/top/reference/measurements/plan05_area_leakage.py --base
build/plan05/timing03`, main29cab7e5 plus receipt-hashed mapped working snapshot.
Each mapped cell contributes its pinned library's conditional-state minimum,
arithmetic mean and maximum leakage; the mean assumes equally weighted
characterized states, not observed sleep-state probabilities. Sum independently
across cells; this is a library-based estimate, not power simulation. Clock
stopping leaves supplies and every SRAM macro powered. SRAM standby uses its
pinned `cell_leakage_power`, converted frommW touW, at normal supply/CEN high.

| Corner / assumed rail | Estimated cell leakage uW min/mean/max | Estimated SRAM standby uW | Estimated digital+SRAM static current uA min/mean/max |
| --- | --- | ---: | --- |
| TT25C /3.3V | 8.744 /10.126 /12.586 | 5.433 | 4.296 /4.715 /5.460 |
| FF125C /3.6V | 301.048 /469.979 /731.959 | 242.496 | 150.984 /197.910 /270.682 |

Current arithmetic is `(sum cell leakage uW + SRAM standby uW) / rail V`.
Per-domain allocation and input hashes are in `block-area-leakage.json`; shared
combinational/glue leakage is counted once, separately. These are static
subtotals: add AON/watch firmware switching, SRAM accesses, LF/POR analog current,
pads/pull resistors, external-oscillator standby, regulator and radio current.
Their uncharacterized values prevent a defensible complete system-current
number. The25C whole-chip target remains unqualified; hot-corner leakage is
substantially higher. No power signoff or power-gated memory is implied.

PLAN05 leakage qualification: the SRAM Liberty `cell_leakage_power` is an
unconditional scalar, used as an idle/standby proxy with CEN high assumed; it
is not a characterized CEN-high condition. Both selected macro sizes supply
the same scalar. No capacity-based leakage scaling is inferred.


### Final PLAN05 ROM-inclusive static estimate

`python hw/top/reference/measurements/plan05_area_leakage.py --base
build/plan05/t36-timing03`, base main5ba87bf plus receipt-hashed sources,
updates the Phase2 subtotal with the mapped production ROM. Estimated static
digital+SRAM current at TT25/assumed3.3V is4.383810/4.825459/5.603557uA
(minimum/equal-state mean/maximum); FF125/assumed3.6V is
152.535158/200.999967/276.519768uA. Same method and exclusions as above:
sum library leakage plus scalar SRAM CEN-high standby proxy, divided by rail.
Per-domain/block contributions and input hashes are in the receipt. AON
switching, analog macros, pads, external oscillator/radio/board power and future
scan are excluded. This does not establish whole-system microamp power or
qualify SRAM/analog physical retention.
