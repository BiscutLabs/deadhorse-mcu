# AON watchdogs

T26 digital RTL and focused functional/output-disable checks are implemented;
full-width channel formal acceptance remains unresolved. D70 (user,
2026-11-21): performance-watchdog expiry resets the performance core and
client epoch, disables PWM outputs, and preserves shared buses, DMA and
other peripherals. Lite expiry retains the whole-MCU reset scope.

## Contract

Two identical channels run on AON edges, with fixed performance/lite bus
owners. No wall-time accuracy is claimed until the AON source is qualified.
Each channel starts disabled. START atomically captures PERIOD, WINDOW and
WARNING; require PERIOD > 0, WINDOW < PERIOD, WARNING < PERIOD. WINDOW is
the minimum elapsed edges before a feed, zero permits immediate feed.
WARNING is the remaining-edge threshold, zero disables warning. Active
settings cannot be changed or lengthened; there is no software stop command.

At the edge accepting START, remaining becomes PERIOD. The next PERIOD
unserviced edges cause expiry. A feed at remaining=1 is too late: expiry
wins. An early feed causes expiry. A legal feed reloads the captured period.
START while active is rejected, never reloads or inhibits counting. Invalid
keys/configuration report a sticky error and do not service the watchdog.
Warning is a registered level while active, 0 < remaining <= WARNING;
legal feed clears it. Expiry disarms the channel and holds reset for four
AON intervals (assumed digital fixture hold; not analog qualification).
Commands during hold are rejected. Software must START again after expiry.

Active state and MMIO reset with the AON service epoch. Hold, sticky cause
and a saturating 32-bit per-channel expiry count reset only with POR/brownout.
Self-generated warm reset must not truncate the hold or erase its cause.
Simultaneous expiry records both causes and increments both counts once.
Enabled channels and reset holds retain AON clock demand; performance warning
also demands the main clock. All domain releases use shared ResetRelease;
warning crosses through shared CdcSync. This is an advisory level, not an
acknowledged event: firmware must allow synchronizer and service latency;
short warnings or a stopped main clock do not guarantee NMI delivery before
expiry. Reset does not depend on NMI delivery. Raw reset assertion is asynchronous.

Performance expiry resets PWM channel execution/pending state, while the
PWM register shadows and DMA/fabric remain alive. Outputs stay disabled
after reset release. In this opt-in profile, a per-channel break latch starts
inhibited at reset. Firmware issues STOP to acknowledge the break, then a
later APPLY to start. DMA never emits STOP, so an in-flight DMA APPLY cannot
undo watchdog shutdown. Shadows, DMA and fabrics survive. APPLY while
inhibited is discarded and sets the existing config-error event. STOP during
hold or before the local command pipeline has drained does not acknowledge
the break; an observed idle bus and low command pulses qualify subsequent
STOP. The actual SocLocalMemory.epochReady also qualifies acknowledgment:
a retained pre-reset STOP must drain before the new CPU epoch is ready.
The standalone peripheral fixture explicitly supplies this upstream-drained
input; the whole SoC binds the real memory output. Coincident STOP/APPLY stops without starting. Dedicated pads and
PWM-selected GPIO pads disable even with main stopped; GPIO/timer alternate
functions retain state. Ordinary main-core reset still preserves PWM.


## Register map

Generated from watchdog.regmap.yaml; each channel occupies 256 bytes in the
power/reset window: performance offset 0x100, lite offset 0x200. Owner-only
access, aligned words, no aliases. Command keys require all byte lanes.

| Offset | Register | Access | Meaning |
| --- | --- | --- | --- |
| 0x00 | period | RW | Shadow period, AON edges |
| 0x04 | window | RW | Shadow minimum elapsed edges |
| 0x08 | warning | RW | Shadow remaining-edge warning threshold |
| 0x0c | start | WO | Key 0x57445354 captures settings |
| 0x10 | feed | WO | Key 0x57444644 services active channel |
| 0x14 | status | RO | active bit0, warning bit1, reset hold bit2, cause bit3 |
| 0x18 | remaining | RO | Active countdown |
| 0x1c | crashes | RO | POR-retained saturating expiry count |
| 0x20 | events | W1C | command/config/key error bit0 |

## Adoption and limits

Count/hold sequencing derives from Apache-2.0 RISCay ClockedWatchdog,
commit 4671317186003740ceb61360ba08c59bbdf10136,
designs/clocked/src/main/scala/riscay/clocked/ClockedPowerReset.scala.
Changes: explicit enable/start/feed, runtime captured configuration, window
checks, warning, separate epoch/POR state and retained count. No upstream
equivalence or verification is inherited. No private synchronizers, event
clocks or upstream wake/gate implementation are imported.

Estimated storage per channel: active countdown/configuration 4×32 bits,
three shadow settings 3×32, count 32, plus control/hold/bus state; area must
be measured. The conservative existing 9MHz screen is a digital bound, not
a selection of AON frequency. Physical RDC/recovery/removal and pad behavior
remain signoff work. A whole-MCU watchdog reset currently clears loader
validImage/START while preserving its POR-only lock: autonomous restart of
a locked retained image is not implemented by this stage.

Output exception: pinmux pads OR two mutually exclusive registered banks.
The PWM bank has the watchdog reset, while the GPIO/timer bank does not.
Both retain the existing disabled selection-change interval. Hold and status
outputs decode registered state; no input-to-output combinational data path.

## Verification checkpoint

See [T26 report](../../../docs/plan/tasks/reports/T26.md). Frozen functional
checks, four top emissions and break/pad proofs pass. The follow-up receipt
verifies the unchanged production bytes, adds the missing-epoch fault and
corrects only mapped reset fanout with real buffers, preserving limits.
Mapped setup/electrical screens pass; hold/RDC and full SoC physical signoff
remain separate. The watchdog channel proof timed out under its existing cap;
no unchanged rerun or helper attempt followed. No CI, commit or push.

Formal assumptions are listed in [formal/README.md](formal/README.md): the
channel starts with POR and service reset asserted; output-disable jobs start
with normal reset asserted. Thereafter reset, commands, settings, epochReady,
idle and pad inputs are unconstrained as applicable. No fairness, timely-feed
or truthful-epoch assumption is added. The real memory-to-PWM epoch binding
has separate functional composition tests and an actual bypass fault.
