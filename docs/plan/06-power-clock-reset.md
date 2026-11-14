# 06 Power, clocks and reset

Approved scope: retained clock-gated sleep, programmable sleep peripherals,
internal LF/HF clocks, external-clock fallback, and on-chip supply monitoring.
Targets below are assumptions pending characterization, not silicon results.

## Power modes and wake

| Mode | Behavior |
| --- | --- |
| Run | Cores and required peripherals clocked; idle blocks gated |
| Idle | Performance core at `wfi`; other consumers clocked as needed |
| Retained deep sleep | Performance core gated, SRAM/registers retained; lite core on LF and itself gated at `wfi`; selected serial blocks may request HF |
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
not new latch-based storage. Deep sleep is refused while actuators are armed.

## Clock sources

| Source | Purpose | Qualification still required |
| --- | --- | --- |
| Internal nominal 32 kHz LF | AON, watchdogs, sleep timers | Redesign RISCay LF schematic; trim, layout, startup, corners, power |
| Restartable internal HF | Main/peripheral timing; divided AON bursts | Trim, jitter, duty cycle, glitch-free stop/restart, corners |
| Dedicated external clock input | Main-clock fallback through divider and glitch-free selection; USB reference | Pad limits, valid source/divider settings, switching/reset behavior |
| Optional USB clock domain | USB timing while included | Implementer requirements; external 48 MHz is the current assumption |

Existing targets remain: LF within 5 percent after trim and under 1 microamp;
HF 12 or 24 MHz, within 2 percent after trim and startup within 100 microseconds;
wake within 200 microseconds; whole-chip quiescent sleep below 50 microamps
at 25 C. These are **assumed targets**, not guaranteed specifications.
Sleep power with receive-mode UART or active sensors is a separate mode.
S1 determines feasible main frequency; analog work establishes actual tolerances.

No PLL or LF crystal driver is required in the baseline. Calibration words may
be loaded from external flash after safe startup. The external clock fallback
is approved; autonomous seamless failover is not specified. Test switching
with stopped sources and qualify the mux at the cell level.

## Reset containment

| Cause | Required effect |
| --- | --- |
| Performance watchdog | Reset performance domain; preserve lite core, retained AON SRAM and reset reason; force actuator failsafe independently |
| Lite watchdog | Reset whole MCU; fault path requests actuator failsafe while clock/supply are valid, then whole-chip reset disables outputs |
| Power-on/brownout | Whole-chip reset and disabled general-purpose outputs |
| External reset | Whole-chip reset with qualified release |

Assert reset asynchronously and release synchronously per domain only after
supply/clock qualification. Flush or cancel crossing transactions under a
defined protocol; stale responses must not reach the restarted core.
Performance reset must not clear the actuator's retained failsafe configuration
or stop its valid clock. Reset reason is retained in AON across performance reset;
no retention guarantee is made across power loss or brownout.

## Actuator fault handling

Hardware command timeout, watchdog faults and firmware fault request the
configured per-channel actions. Timeout is configurable; deadline and recovery
policy remain open for testing (D31), not fixed keyed re-arm or automatic recovery.
The actuator has independent reset and an ungated required clock while active.
No valid-pulse guarantee applies when its clock or supply fails. Board-defined
inactive output levels and ESC loss-of-signal behavior must be verified.

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
