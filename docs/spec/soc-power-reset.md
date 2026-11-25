# Production clock, reset and sleep boundaries

T41/D103 implementation is in progress on the reset-consolidation branch.
The contract below replaces the former ten-row cohort inventory. Fresh
structural measurement finds 30 ResetRelease instances and 59 normalized reset
controls, versus 89 and 150 before consolidation; commands and counting scope
are in [the inventory](reset-consolidation-inventory.md). Final composed
acceptance remains in the T41 report.
D106/D107 preserve immediate DMI/bridge cancellation and selective BIST pin
abort. They are cancellation controls, not resets of their payload banks.

Performance remains the single boot master. Both watchdogs now request warm
reset, so lite is held until ROM has confirmed its image. Dormant wake remains
retained execution after WFI, not a boot. The performance watchdog freezes
while the main clock is stopped; the lite watchdog continues.

T33 supplements [the production SoC contract](soc.md). This is the digital
boundary inventory and qualification checklist, not physical signoff. Clock
rates are the D78 design contract: OSC_IN 48 MHz, divided main 8 MHz, AON
nominal 32 kHz. TCK is independent. Related main/USB clocks retain their CDC.

## Reset cohorts

| Cohort | Assert sources | Release / consumers | Retention |
| --- | --- | --- | --- |
| Cold | On-die POR/brownout; external pin instead when static POR_BYPASS is high | One shared release per AON, ungated main, OSC_IN and TCK domain | Initializes causes, debug and cold-owned control state; no reset clears RAM contents |
| Warm | Cold, normal-mode pin, either watchdog, debug ndmreset; no software reset command currently exists | Shared AON and main releases; cores, fabrics, peripheral controls, DMA and timer outputs | Causes, debug and RAM survive; lite boot hold reasserts; PWM disables immediately |
| Debug | Cold only | Reuses shared cold main/TCK releases | DM survives ndmreset; D106 transport cancellation quarantines admission immediately and flushes synchronously |
| USB transport | Existing T19 cold/pin/lite-watchdog/ndmreset/BIST and USB qualification predicates | Existing USB releases and transport endpoint reset protocol | Performance watchdog does not become a USB reset source; all T19 obligations remain |

Warm release qualification is data, not another asynchronous source. AON must
have its selected clock counted and a cold-owned warm-entry initialization
acknowledged. Main release then waits for AON release and fresh source
qualification. The first warm-release stage fans out only to same-clock
history/initialization logic, not functional consumers; include it in RDC and
timing review. Short warm pulses are remembered even with AON stopped.

Oscillator policy and source qualification are cold-owned state. Warm entry
initializes policy synchronously and requests source-domain clearing. Both
OSC_IN and ungated /6 executors acknowledge clearing; the ACK is delayed past
the ICG closing low phase. Both ACKs must return low before fresh configuration
and stability qualification. Deep sleep completes this flush before OSC_EN
falls and holds clear throughout OFF. Wake during clearing is retained.
Cold-owned control can restart and open the main clock while warm is held,
so debug can subsequently clear ndmreset.

The D107 pin fence is shared by bootstrap sampling, cause capture and BIST
quarantine. Its raw capture includes cold plus pin; each admission endpoint
also waits for its local cold release and peer acknowledgement. A synchronized
pin-low event initializes policy and source state even if another source
already holds warm reset. This preserves divider/strap qualification and BIST
abort for a pin pulse inside held ndmreset. No additional payload reset tree
is created. D106 DMI and D107 bridge timeout fences are separately inventoried.

Reset assertion paths are intentionally asynchronous. Reset **release** is
synchronized at each destination; asynchronous assertion is not a data CDC
exception. The reset input of a ResetRelease is not evidence that all downstream
recovery/removal paths pass physical timing.

## Clock-control and wake crossings

| Producer → consumer | Primitive / protocol | Reset and ownership obligation |
| --- | --- | --- |
| AON bootstrap reset level → OSC_IN divider data control | CdcSync with reset tied inactive | Both transitions are sampled in OSC_IN. Initial synchronizer/divider state is arbitrary; downstream asynchronous reset and startup qualification quarantine convergence, even when the source misses the reset pulse |
| Shared warm release / pin capture → cold-owned AON policy | CdcSync plus cold-owned warm-entry acknowledgement | Initialization cannot be reset by the warm event it reports; pin events are retained even inside held warm |
| AON configuration → cold-owned policy | Shared warm reset of MMIO/configuration; synchronous policy initialization | Warm assertion forces OSC_EN high, clears policy and restores default startup configuration; ordinary deep-sleep entry retains configuration |
| AON policy → ungated main gate executor | One-bit command CdcFifo | One command outstanding; both endpoints synchronously flush under acknowledged epoch clear |
| Ungated main executor → AON policy | One-bit completion CdcFifo | Completion belongs to the outstanding command; source closure stays latched until an explicit reopen |
| AON qualification count → OSC_IN counter | 16-bit CdcFifo, retained head | Atomic payload retained throughout the source epoch; no bitwise configuration crossing |
| AON qualification permission → ungated main executor | CdcSync | Source-domain synchronous clear removes authorization before the source can stop |
| OSC_IN stable report → AON policy | CdcSync | Must be fresh for this oscillator epoch; minimum full-width count proof remains separate |
| Main WFI/holds → AON policy | Registered main aggregate and CdcSync | Ordinary sleep preserves demand; warm reset flushes all ordinary clients together |
| AON UART sleep/mode configuration → main | Seven-bit CdcFifo | Pending transfer is a hold until read acknowledgement; shared warm reset flushes stale mode data |
| UART pins → AON wake monitors | Existing UartWake synchronization/capture | Receive, wake-only and disabled modes retain their existing contracts |
| GPIO pins → AON wake state | Existing GPIO synchronization and retained wake state | Masked wake capture; main sleep does not discard enabled AON capture |
| AON timer/mailbox → AON policy | Local registered events | Pending wake is checked while stopping and retained through startup |
| USB resume / clock request → AON policy | Existing USB AON wake/request CDC | D81 keeps OSC_IN running while USB is enabled; no claim that the full USB resume detector works without its source clock |
| TCK pending request → AON policy | Existing debug pending handshake and CdcSync | Pending request persists until main services it; POR-only reset cohort |
| Main debug active/halt → AON lite/debug ownership | CdcSync with cold-only reset | ndmreset must not erase the request required to resume debug service |
| AON lite debug entry/reset state → main DM | Cold-owned CdcSync plus immediate shared warm-main qualification | Lite reset acknowledgement cannot wait for a stopped main clock; DM survives |
| AON watchdog warning → main NMI | CdcSync | Warning is data; watchdog reset containment is a separate asynchronous path |
| Raw external pin → AON reason recorder | Shared D107 pin capture | Pin pulses between AON edges survive as a recorded reason, without a duplicate release tree |
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
