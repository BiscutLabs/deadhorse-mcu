# PLAN03 SoC test inventory

Measured runtime names, before B2 and after consolidation, then after the
separate D74 ADC retirement. All 82 named cases in 24 suites were retained and passed after
consolidation; D74 then explicitly removed five ADC-only cases, leaving 77 in
the same 24 suites. No other runtime case disappeared or became skipped.
Commands and source snapshots are in [the PLAN03 report](../plan/tasks/reports/PLAN03.md).
This table transcribes baseline/test-inventory.json and actual passing XML from
consolidation02 and adc-retirement, checked against inventory-comparison.json.
Focused fixtures were rebound to production. The GPIO oracle checks actual
masked pin output and independently reads retained raw data through MMIO; it
no longer mistakes raw GPIO data for the pinmux output. Existing behavioral
obligations were preserved. This is a durable inventory, not a claim that the
historical runs were rerun now.

| Suite | Exact test name | Before B2 | After B2 | After D74 |
| --- | --- | --- | --- | --- |
| SocBootReleaseSpec | bypassing the release binding is rejected by the same whole-top oracle | PASS | PASS | PASS |
| SocBootReleaseSpec | real recovery loader and lite firmware release performance with independent resets | PASS | PASS | PASS |
| SocBootSpec | I0 boots faithful RV32IMFC, checks SRAM byte writes and FMUL, and prints on real UART | PASS | PASS | PASS |
| SocBootSpec | I1 boots faithful RV32IMFC, checks SRAM byte writes and FMUL, and prints on real UART | PASS | PASS | PASS |
| SocDmaMemorySpec | DMA memory arbitration, lane ownership and core-reset retention at latency 1 | PASS | PASS | PASS |
| SocDmaMemorySpec | DMA memory arbitration, lane ownership and core-reset retention at latency 3 | PASS | PASS | PASS |
| SocDmaMemorySpec | idle DMA preserves CPU grant/response trace at latency 1 | PASS | PASS | PASS |
| SocDmaMemorySpec | idle DMA preserves CPU grant/response trace at latency 3 | PASS | PASS | PASS |
| SocDmaSpec | PWM DMA updates survive held core/AON resets; service reset cancels | PASS | PASS | PASS |
| SocDmaSpec | real UART and SPI DMA loopbacks, packed SRAM, ownership and IRQ8 | PASS | PASS | PASS |
| SocI1CoreResetSpec | core-only reset retains the offered I1 MMIO side effect, corrupt=false | PASS | PASS | PASS |
| SocI1CoreResetSpec | core-only reset retains the offered I1 MMIO side effect, corrupt=true | PASS | PASS | PASS |
| SocI1ResetSpec | accepted crossings cancel once on stopped-clock peer reset and source reset drains dispatched work | PASS | PASS | PASS |
| SocI1Spec | integrated I2C reads a BMP390 chip-ID wire fixture and detects a corrupted reply | PASS | PASS | PASS |
| SocI1Spec | integrated SPI reads a BMI270 chip-ID wire fixture and detects corrupted MISO | PASS | PASS | PASS |
| SocI1Spec | mailbox round trip, retained byte lanes, denied program writes and independent service reset | PASS | PASS | PASS |
| SocI1Spec | opposite-direction traffic completes without circular bridge admission | PASS | PASS | PASS |
| SocI1Spec | real USB recovers after an outer timeout while its service reset blocks admission | PASS | PASS | PASS |
| SocI1Spec | recovery I2C wire loads actual retained SRAM, rejects bad CRC and preserves lock across warm reset | PASS | PASS | PASS |
| SocI1Spec | serial endpoints, ownership, exact decode, all stub windows and IRQ wiring | PASS | PASS | PASS |
| SocI1Spec | wrong generated interrupt connection is detected | PASS | PASS | PASS |
| SocI1SupportSpec | reset slot cancels once across stopped-clock reset, drains normally and rejects withdrawn offers | PASS | PASS | PASS |
| SocI1SupportSpec | retained memory uses independent byte model, denies program stores and quarantines revoked loader grant | PASS | PASS | PASS |
| SocI1UsbSpec | USB wire/MMIO loopback crosses I1 fabrics, wakes stopped main and recovers independent resets | PASS | PASS | PASS |
| SocInactiveSpec | I1 elaboration rejects YAML width drift at the physical stub boundary | PASS | PASS | PASS |
| SocInactiveSpec | inactive pads remain safe through exhaustive original and new input-bank sweeps without service clocks | PASS | PASS | PASS |
| SocInactiveSpec | the safety oracle rejects an actual enabled ADC output | PASS | PASS | retired by D74 |
| SocInactiveSpec | the safety oracle rejects an actual enabled GPIO output | PASS | PASS | PASS |
| SocInactiveSpec | the safety oracle rejects an actual enabled TIMER output | PASS | PASS | PASS |
| SocInactiveSpec | the safety oracle rejects an actual enabled actuator output | PASS | PASS | PASS |
| SocIoSpec | ADC pin producer reaches AON MMIO and both interrupt destinations | PASS | PASS | retired by D74 |
| SocIoSpec | AON deadline and GPIO level wake with main stopped; independent reset scopes | PASS | PASS | PASS |
| SocIoSpec | functional I/O decode, ownership, pad outputs and timer IRQ | PASS | PASS | PASS |
| SocLiteSpec | recovery START runs retained RV32E code, timer/mailbox IRQs and independent resets | PASS | PASS | PASS |
| SocLiteSpec | wrong START handoff status is rejected on the public loader wire | PASS | PASS | PASS |
| SocMemorySpec | byte masks, banks, errors and retained RAM; banks=1 latency=1 | PASS | PASS | PASS |
| SocMemorySpec | byte masks, banks, errors and retained RAM; banks=4 latency=1 | PASS | PASS | PASS |
| SocMemorySpec | byte masks, banks, errors and retained RAM; banks=4 latency=3 | PASS | PASS | PASS |
| SocMemorySpec | client reset cancels a pipelined local reply and drains before the new epoch | PASS | PASS | PASS |
| SocMemorySpec | concurrent instruction/data arbitration preserves ordered replies; latency=1 | PASS | PASS | PASS |
| SocMemorySpec | concurrent instruction/data arbitration preserves ordered replies; latency=3 | PASS | PASS | PASS |
| SocMemorySpec | corrupted memory response is rejected by the same independent ROM oracle | PASS | PASS | PASS |
| SocMemorySpec | current-request arbitration serves contention and excludes the MMIO response edge | PASS | PASS | PASS |
| SocMemorySpec | issued MMIO response across client reset boundary -1 | PASS | PASS | PASS |
| SocMemorySpec | issued MMIO response across client reset boundary 0 | PASS | PASS | PASS |
| SocMemorySpec | issued MMIO response across client reset boundary 1 | PASS | PASS | PASS |
| SocMemorySpec | one-edge ROM replies sustain consecutive native fetches | PASS | PASS | PASS |
| SocMemorySpec | stalled MMIO retains payload, allows fetch, and drains across a short core reset | PASS | PASS | PASS |
| SocNestedSpec | late endpoint completion cannot acknowledge quiet or contaminate fresh traffic after nested watchdogs | PASS | PASS | PASS |
| SocPinmuxCoreResetSpec | real core reset preserves pin selection and registered outputs | PASS | PASS | PASS |
| SocPinmuxSpec | ADC pin producer reaches AON MMIO and both interrupt destinations | PASS | PASS | retired by D74 |
| SocPinmuxSpec | AON deadline and GPIO level wake with main stopped; independent reset scopes | PASS | PASS | PASS |
| SocPinmuxSpec | functional I/O decode, ownership, pad outputs and timer IRQ | PASS | PASS | PASS |
| SocPinmuxSpec | pin mux routes all three sources, retains raw inputs/wake and survives AON reset | PASS | PASS | PASS |
| SocPwmCoreResetSpec | real core reset preserves the active waveform and queued configuration | PASS | PASS | PASS |
| SocPwmSpec | ADC pin producer reaches AON MMIO and both interrupt destinations | PASS | PASS | retired by D74 |
| SocPwmSpec | AON deadline and GPIO level wake with main stopped; independent reset scopes | PASS | PASS | PASS |
| SocPwmSpec | PWM profile pins, IRQ10, clock demand, holes, denial and independent resets | PASS | PASS | PASS |
| SocPwmSpec | functional I/O decode, ownership, pad outputs and timer IRQ | PASS | PASS | PASS |
| SocQspiSpec | lite bridge ownership handoff, shared service containment and physical pin binding | PASS | PASS | PASS |
| SocQspiSpec | wrongly widening QSPI reset to the AON service cohort is rejected | PASS | PASS | PASS |
| SocWatchdogCoreSpec | real watchdog resets core/client epoch, firmware observes preserved DMA/GPIO and inhibited PWM | PASS | PASS | PASS |
| SocWatchdogEpochSpec | PWM DMA updates survive held core/AON resets; service reset cancels | PASS | PASS | PASS |
| SocWatchdogEpochSpec | bypassing actual epoch readiness is caught by the retained STOP scenario | PASS | PASS | PASS |
| SocWatchdogEpochSpec | real UART and SPI DMA loopbacks, packed SRAM, ownership and IRQ8 | PASS | PASS | PASS |
| SocWatchdogEpochSpec | retained pre-watchdog STOP drains before break acknowledgment is enabled | PASS | PASS | PASS |
| SocWatchdogSpec | ADC pin producer reaches AON MMIO and both interrupt destinations | PASS | PASS | retired by D74 |
| SocWatchdogSpec | AON deadline and GPIO level wake with main stopped; independent reset scopes | PASS | PASS | PASS |
| SocWatchdogSpec | functional I/O decode, ownership, pad outputs and timer IRQ | PASS | PASS | PASS |
| SocWatchdogSpec | lite watchdog resets all ordinary services but retains causes and SRAM | PASS | PASS | PASS |
| SocWatchdogSpec | performance watchdog preserves shared state and disables all PWM routes while main is stopped | PASS | PASS | PASS |
| SocWatchdogSpec | wrongly widening performance watchdog reset is rejected | PASS | PASS | PASS |
| SocXipMemorySpec | bypassing the reset fence is rejected | PASS | PASS | PASS |
| SocXipMemorySpec | client reset drains orphan XIP: latency=1 data=false | PASS | PASS | PASS |
| SocXipMemorySpec | client reset drains orphan XIP: latency=1 data=true | PASS | PASS | PASS |
| SocXipMemorySpec | client reset drains orphan XIP: latency=3 data=false | PASS | PASS | PASS |
| SocXipMemorySpec | client reset drains orphan XIP: latency=3 data=true | PASS | PASS | PASS |
| SocXipMemorySpec | data native reads coexist with ordered pipelined local fetch and propagate errors | PASS | PASS | PASS |
| SocXipMemorySpec | local data and DMA continue during instruction XIP, ordered fetch and denied DMA | PASS | PASS | PASS |
| SocXipMemorySpec | native instruction grant waits for every earlier three-stage local reply | PASS | PASS | PASS |
| SocXipMemorySpec | restart waits for both native fetch and MMIO; neither orphan is returned | PASS | PASS | PASS |
| SocXipSpec | recovery-loaded lite enables flash; real performance core executes and loads native flash | PASS | PASS | PASS |

The five D74 removals are the ADC producer case inherited by SocIoSpec,
SocPinmuxSpec, SocPwmSpec and SocWatchdogSpec, and SocInactiveSpec's enabled-ADC
pad fault. ADC-only AdcSpec, AdcRawSpec and AdcSampleStateSpec were removed with
hw/ip/adc after B2 passed; the pre-deletion file/test inventory and separate
commit 2504a31 retain that record. Software conversion tests remain.

Focused map tests explicitly replaced obsolete ADC owner/size cases with
rejection of ADC reintroduction, added mandatory DMA/real-lite checks, and
retired ADC-only pin-width validation. Existing top emissions became the four
8/9 MHz production/USB-stub test targets; old emitters were deleted only after
exact emitted-HDL comparison. Minimal-I0 and focused memory fixtures remain.
