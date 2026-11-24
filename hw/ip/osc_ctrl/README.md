# External oscillator control

PLAN04 implementation in progress; no RTL acceptance claimed. D78 supplies
USB directly from OSC_IN at assumed 48 MHz and main from registered /6. AON
uses nominal 32 kHz LF RC or a reset-held external fallback. D81 keeps OSC_EN
high while USB is enabled. D82 leaves the recovery loader clocked by AON, with
host SCL bounded by minimum qualified AON frequency / 8.

D83 makes external pin reset cold only when POR_BYPASS is selected, initializing
and clearing the loader lock, retained watchdog history and debug POR state.
Normal-mode external reset remains warm; watchdog containment is unchanged.
D84 makes POR_BYPASS a static board strap, default low and fixed throughout
each powered session. Reset selection is independent of flop initialization.
AON_CLK_SEL alone is sampled during reset and frozen afterward.

Gate commands and completions use two shared single-bit CDC FIFOs between AON
and ungated /6, with at most one command outstanding. A close is rejected if
local work is active; late activity during draining also rejects it and restores
the clock. Successful closure is latched only after the ICG has been low across
two source edges and stays closed until an explicit open command. AON reports
closed only for a completed close with no intervening command or changed demand.
Cancellation still returns the policy to RUN and restores UART service
immediately; it never waits for the core to return to WFI. Both FIFO endpoints
reset together on chip reset or oscillator-off, preventing old completions
from crossing epochs. FIFO handshake wires are combinational protocol controls;
gate enable, completion payload and public closure status are registered.

The controller lives in AON at 0x40000400, owned by lite. All main holds and
qualified WFI cross through shared primitives. Wake bits are timer, GPIO,
UART0, UART1, UART2, USB, lite mailbox and JTAG in increasing bit order.
Safety holds are never masked by wake enables. UART wake polarity is configured
here to match each UART's existing ACTIVE.invert while disarmed; wait at least
four AON edges before arming. UART modes retain the existing UART encoding.
Multi-bit sleep settings and the request travel atomically through the shared
CDC FIFO. Its read-pointer acknowledgement keeps a main-clock hold active until
main consumes the payload. STOPPING allows that hold to register before requesting
closure; sleep configuration is captured only from RUN. Focused tests cover
cancellation, consecutive settings, paused main and either-side reset; full
composition proof and production qualification remain open.

RUN accepts firmware sleep requests. STOPPING requests main gate closure and
waits for source-clock confirmation, with all consumers drained and performance
WFI qualified by boot/epoch readiness. OFF retains state; OSC_EN stays high in
light sleep, and falls only for deep sleep with USB disabled and all holds low.
STARTING raises OSC_EN, waits the AON startup delay, then observes a fresh
OSC_IN stability count through shared CDC before opening the gate. A timeout
sets sticky fault and requires reset to retry; OSC_EN remains high and the gate
closed. Pending wake is retained in every state; simultaneous wake wins sleep.

The programmable stability count crosses through a shared 16-bit CDC FIFO,
once per oscillator epoch after qualification is requested. Its source-domain
head remains valid through light sleep; deep OFF or chip reset clears both
endpoints. This adds FIFO delivery latency before counting source edges, within
the unchanged startup timeout. The intentionally retained payload's pending
flag is not a clock hold. Raw AON count bits never drive the source counter.

Planning defaults are **assumed**: 512 startup AON ticks, 256 OSC_IN stable
edges, 4096 AON timeout ticks. Estimated nominal startup delay is 16 ms; board
part startup is assumed <=5 ms (plan07). Zero programmed counts are clamped to
one; settings are captured when starting and cannot shorten an active sequence.
Gate closure must be acknowledged by ungated source-clock sequencing before
oscillator shutdown; an elapsed AON delay is insufficient.
The divider finishes an active high phase during reset before parking low;
its unreset state is initialized within four supplied OSC_IN edges while all
consumers remain reset/gated. Source-clock gate authorization comes from AON's
accepted startup epoch, never directly from the raw stable report. A startup
timeout therefore cannot be undone by a late source report or local hold.

Digital POR-model parameters and physical macro pins are specified in
[the SoC contract](../../../docs/spec/soc.md). They remain assumptions pending
T34. The fallback sequence holds external reset with stable straps and a valid
selected clock; normal startup uses asserted POR and the running RC. There is
no initialization guarantee for bypassed POR without an external reset sequence.

| Offset | Register | Access / reset |
| --- | --- | --- |
| 0x00 | sleep | w1p request |
| 0x04 | wake_enable | rw eight-bit mask, 0 |
| 0x08 | startup_delay | rw 16-bit AON ticks, 512 |
| 0x0c | stable_count | rw 16-bit OSC_IN edges, 256 |
| 0x10 | status | ro state, OSC_EN and gate request |
| 0x14 | events | w1c startup fault, 0; clearing status does not retry |
| 0x18 | last_wake | ro eight-bit captured causes |
| 0x1c | policy | rw deep request, 0 (light sleep) |
| 0x20 | uart_polarity | rw three inversion bits, 0 |
| 0x24 | uart_mode | rw three two-bit sleep modes, 0 |
| 0x28 | startup_timeout | rw 16-bit AON ticks after delay, 4096 |

T33 separates transport/configuration reset from the clock-policy epoch.
AON-service, lite-watchdog and JTAG system resets immediately flush the MMIO
adapter and shared UART sleep transfer. The stretched service-reset indication
passes through a shared synchronizer in the retained AON policy epoch before
canceling sleep and restoring configuration defaults. MMIO stays closed until
that configuration reset completes; accepted fresh writes cannot disappear into
a delayed reset. This prevents asynchronous multi-bit changes at OFF-to-START.
A wake before reset is observed may capture the old coherent settings; restart
after reset is observed uses the existing conservative defaults. STARTING keeps
its already-captured settings. Policy and source
qualification survive those resets so the debug module retains clock service.
Cold/external pin reset clears the policy; oscillator-off still invalidates
source qualification. Startup fault is retained within that epoch; an internal
reset cannot open an unverified clock or restart a failed source qualification.

The divider consumes its reset control as data, so both transitions cross the
shared OSC_IN level synchronizer. That sampler intentionally has no reset;
startup state may be arbitrary if the source misses the reset pulse. Existing
asynchronous gate/domain reset and source qualification quarantine convergence.
This is not a promise about analog metastability settling time.

Reset is asynchronous assertion, shared synchronized release. OSC_EN resets
high, gate request low; startup must qualify before main release. The estimated
digital area allowance is the existing 0.10 mm2 clock/reset/power allocation,
including later T33 work, not an independent extra allowance. Formal properties,
negative controls, independent reference tests, production integration and
GF180 measurements remain required. Analog models do not prove clock quality,
metastability, supply limits or cell-level glitch freedom.

Production wake tests live in `deadhorse.top.SocClockResetSpec`. Their lite
firmware is loaded through the real recovery interface; the performance core
enters WFI and reports retained state through GPIO. UART, AON timer, lite
mailbox, GPIO and JTAG DMI wake cases use oscillator-off sleep. USB host-resume
uses D81 light sleep and the unchanged USB idle qualifier. See the
[PLAN04 report](../../../docs/plan/tasks/reports/PLAN04.md) for current results;
test presence alone is not a pass.

The paired flight-loop check rebuilds the existing production workload with
`hw/top/reference/measurements/plan03_production_benchmark04.py <fresh-output>`
and runs `plan04_flight.py --prepared <fresh-output> --output <fresh-results>`.
It compares the complete fixed-point and hard-float loop windows and target
checksums with/without deep sleep before execution. ROM firmware copies the
same SRAM payload before sleeping; no SRAM preload or bus injection is used.
Its historical target-reference receipt must match the freshly rebuilt workload
bytes. This is workload/retention evidence, not complete ISS lockstep.

T33 completed with D86 exceptions after focused production tests and independent
review. The full-width minimum-count, shutdown ownership and composed reset/CDC
proofs remain deferred and unproved; original formal entrypoints remain strict.
Neither CI tier was run for this closeout. The T33 report records exact evidence,
an initial inherited-test scope error and the corrected case selection. Physical
clock/reset qualification and I3 remain open.
