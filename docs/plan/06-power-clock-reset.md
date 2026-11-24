# 06 Power, clocks and reset

Approved scope: retained clock-gated sleep, programmable sleep peripherals,
on-die LF RC, external 48 MHz clock with divided main, reset-held LF fallback,
and on-chip POR/brownout (D78/D79).
Targets below are assumptions pending characterization, not silicon results.

## Power modes and wake

| Mode | Behavior |
| --- | --- |
| Run | Cores and required peripherals clocked; idle blocks gated |
| Idle | Performance core at `wfi`; other consumers clocked as needed |
| Retained deep sleep | Performance core gated, SRAM/registers retained; lite core on LF and itself gated at `wfi`; selected serial blocks may request HF |
| Oscillator-on light sleep | OSC_EN remains high; main can gate after consumers drain. Required while USB is enabled (D81); attached resume uses the existing USB/AON wake path |
| Oscillator-off retained sleep | All main/USB demands released, performance core in qualified WFI; close main ICG before dropping OSC_EN. USB is disabled (and therefore detached); wake incurs external startup and stability counts |
| Power-gated standby | Out of initial scope |

Sleep drains/cancels outstanding transactions and checks pending wakes before
gating. HF is stopped only when no enabled consumer needs it. Keep request/wake
capture and ownership control available in AON so starting HF never requires
a transaction through a stopped domain. SRAM retention is not a power-off claim.

SPI, I2C and UART are selectively available during sleep. Each UART selects:

- **Receive:** retain the clock necessary for full reception and FIFO operation.
- **Wake-only:** detect activity, request HF; first byte may be lost, requiring
  a sender preamble or retry contract.
- **Disabled:** no receive or UART wake.

Timer deadlines, events (including GPIO, loader and internal notifications),
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
Recovery I2C runs directly on AON without stretching: D82 requires
f_SCL <= f_AON,min / 8. Estimated nominal ceiling 4 kHz becomes 3.8 kHz only
if the assumed -5% LF tolerance is actually qualified; it is not yet guaranteed.

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
The frozen loader has separate cohorts: POR/brownout clears its programming
lock; normal-mode external pin and lite-watchdog reset preserve that lock.
D83 makes external pin reset cold in bypass mode only, initializing/clearing
loader lock, retained watchdog history and debug POR state. Watchdog containment
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
