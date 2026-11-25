# Production clock, reset and sleep boundaries

PLAN05 target amendment: performance owns oscillator/power/reset MMIO through
toAon and is the single boot master. Whole-chip reset holds lite until explicit
release; performance-only reset preserves watcher state. Committed dormant
freezes only the performance watchdog through oscillator qualification, while
lite watchdog continues. Radio GPIO/SPI IRQs wake lite; validated mailbox
wakes main. AON pad ownership survives performance reset. Implementation and
composition evidence remain pending; [PLAN05 contract](plan05-integration.md).

T33 supplements [the production SoC contract](soc.md). This is the digital
boundary inventory and qualification checklist, not physical signoff. Clock
rates are the D78 design contract: OSC_IN 48 MHz, divided main 8 MHz, AON
nominal 32 kHz. TCK is independent. Related main/USB clocks retain their CDC.

## Reset cohorts

| Cohort | Assert sources | Release / consumers | Retention |
| --- | --- | --- | --- |
| Supply cold | On-die POR/brownout; external pin instead when static POR_BYPASS is high | Shared ResetRelease, then clock bootstrap sequencing | No promise across power loss; initializes debug and watchdog history |
| Pin warm | External active-low pin in normal mode | Asynchronous assertion, per-domain synchronized release | Cold-only watchdog state survives; no loader under D93 |
| Main service | Cold, pin, lite watchdog, ndmreset, main-service qualification | Main ResetRelease; shared fabrics, peripherals, DMA and client adapters | Normal sleep does not reset this cohort |
| AON service | Cold, pin, lite watchdog, ndmreset, AON-service qualification | AON ResetRelease; AON fabric, lite service, power/reset MMIO, UART-mode transfer | Reset flushes transfer endpoints; does not reset the source qualification epoch |
| Performance client/PWM | Main-service sources plus performance watchdog | Core/client ResetRelease and separate PWM ResetRelease | Shared DMA, buses, peripherals, lite and retained memory survive performance-only reset |
| USB application/transport | Existing main/USB service combination, cold/pin/whole reset | Existing USB reset-release and CDC endpoint reset logic | Independent transport reset obligations remain in T19 |
| Debug module/transport | Cold only | Existing shared main/TCK reset-release primitives | ndmreset does not reset its own debug controller or remove the clock needed to clear it |
| Oscillator policy epoch | Cold, pin, bootstrap release | AON ResetRelease | Internal service resets cancel sleep through forceRun; they do not discard qualification or a latched source fault |
| Source qualification / gate command epoch | Bootstrap reset or OSC_EN low | Source and ungated-main ResetRelease; shared FIFO endpoint release | A new oscillator epoch requires fresh qualification; light sleep retains the epoch |
| Watchdog causes | Cold initialization; existing watchdog capture | Existing AON watchdog registers | Performance resets preserve recorded reasons; loader removed by D93 |

Reset assertion paths are intentionally asynchronous. Reset **release** is
synchronized at each destination; asynchronous assertion is not a data CDC
exception. The reset input of a ResetRelease is not evidence that all downstream
recovery/removal paths pass physical timing.

## Clock-control and wake crossings

| Producer → consumer | Primitive / protocol | Reset and ownership obligation |
| --- | --- | --- |
| AON bootstrap reset level → OSC_IN divider data control | CdcSync with reset tied inactive | Both transitions are sampled in OSC_IN. Initial synchronizer/divider state is arbitrary; downstream asynchronous reset and startup qualification quarantine convergence, even when the source misses the reset pulse |
| Asserting AON service reset → retained AON policy | ResetRelease pulse stretching followed by CdcSync in the policy epoch | Raw service reset asserts immediately; sleep cancellation observes the synchronized level later. The sampler must not be reset by the service reset it reports |
| AON configuration → retained policy | Configuration reset defaults applied by the synchronized service-reset indication | MMIO adapter asserts reset immediately and waits for configuration readiness before reopening. An OFF wake preceding synchronized reset captures old coherent settings; a reset-forced start selects defaults; an existing STARTING snapshot is retained |
| AON policy → ungated main gate executor | One-bit command CdcFifo | One command outstanding; both endpoints reset on source-epoch end |
| Ungated main executor → AON policy | One-bit completion CdcFifo | Completion belongs to the outstanding command; source closure stays latched until an explicit reopen |
| AON qualification count → OSC_IN counter | 16-bit CdcFifo, retained head | Atomic payload retained throughout the source epoch; no bitwise configuration crossing |
| AON qualification permission → ungated main executor | CdcSync | New source epoch clears authorization before the source can stop |
| OSC_IN stable report → AON policy | CdcSync | Must be fresh for this oscillator epoch; minimum full-width count proof remains separate |
| Main WFI/holds → AON policy | Registered main aggregate and CdcSync | Surviving work keeps its demand; AON-service reset cannot erase orphan demand |
| AON UART sleep/mode configuration → main | Seven-bit CdcFifo | Pending transfer is a hold until read acknowledgement; common service reset flushes stale mode data |
| UART pins → AON wake monitors | Existing UartWake synchronization/capture | Receive, wake-only and disabled modes retain their existing contracts |
| GPIO pins → AON wake state | Existing GPIO synchronization and retained wake state | Masked wake capture; main sleep does not discard enabled AON capture |
| AON timer/mailbox → AON policy | Local registered events | Pending wake is checked while stopping and retained through startup |
| USB resume / clock request → AON policy | Existing USB AON wake/request CDC | D81 keeps OSC_IN running while USB is enabled; no claim that the full USB resume detector works without its source clock |
| TCK pending request → AON policy | Existing debug pending handshake and CdcSync | Pending request persists until main services it; POR-only reset cohort |
| Main debug active/halt → AON lite/debug ownership | CdcSync with cold-only reset | ndmreset must not erase the request required to resume debug service |
| AON lite debug entry/reset state → main DM | Shared synchronization / ResetRelease | Reset acknowledgement waits for real domain reset; debug module survives |
| AON watchdog warning → main NMI | CdcSync | Warning is data; watchdog reset containment is a separate asynchronous path |
| Raw external pin → AON reason recorder | ResetRelease pulse capture | Pin pulses between AON edges survive as a recorded reason |
| Analog held brownout indication → AON reason recorder | CdcSync | Macro holds the power-epoch cause; digital proof does not establish analog detection |
| AON threshold selection → analog macro | One registered active bit, reserved high bit zero | D85 switching guarantee; T34 owns analog transient and capacitance characterization |

General bus bridges, mailbox payloads, debug DMI, USB byte/event channels and
their endpoint-reset protocols retain their block-local crossing inventories
and evidence. The table above identifies the clock/reset controller's composed
interfaces; it is **not** a claim that a whole-netlist CDC/RDC audit has passed.
That audit must reconcile every mapped register clock and reset endpoint with
these cohorts and the existing block inventories, rejecting unknown paths.

## Physical qualification still required

- Use both frozen AON source modes. AON_CLK_SEL may change only while reset
  holds all consumers; its settled value is frozen before AON release. Startup
  transitions and the reset-held mux need cell-model checks, not a runtime
  clock-switching waiver. POR_BYPASS is static for a powered session (D84).
- Shared ICG functional and test-enable checks must use the actual input clock
  period and stated slew/load. The production test-enable remains inactive;
  T37 owns physical test entry/scan. No new firmware or package bypass is added.
- Report recovery, removal and minimum pulse checks for each reset cohort and
  gate. Ideal-clock and unbuffered pre-CTS violations remain visible; neither
  a generic zero-delay reset port nor a blanket false path qualifies them.
- Preserve the live threshold endpoint in area/timing. Its measured digital
  clock-to-output delay uses the existing assumed output load until T34 supplies
  macro pin capacitance; there is no invented analog setup/hold requirement.
- Whole-chip CTS, routed reset distribution, metastability analysis and analog
  macro characterization remain physical-flow obligations. Local cell tests
  and RTL proofs cannot close those items by themselves.

T33's report records which checks have actually run and which remain open.
