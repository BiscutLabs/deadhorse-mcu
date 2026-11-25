# T41 production reset inventory before RTL changes

## Boundary and reproducibility

Measured on production source `d11fe8ccbd377bc5a32b3ed5a51dec91651bc054`
(PLAN05 implementation, T41/T43 planning only). No RTL changed for this inventory.
The emitted production build uses real USB, both cores, hard SRAM sockets and
RVFI excluded. Commands run in the pinned environment:

```text
python tools/env/run.py run -- python tools/sbt.py "hw/runMain deadhorse.top.EmitSoc build/t41/inventory01/emit production 8"
python tools/env/run.py run -- python hw/top/reference/measurements/reset_inventory.py --emit build/t41/inventory01/emit --output build/t41/inventory04
```

Emission passed in measured 11.056481 s. The second command imports through
Yosys/slang, `proc`, `chformal -remove`, `memory_collect`, preserving hierarchy;
import passed in measured 2.329853 s, inventory traversal in measured 2.923563 s.
The emission log/receipt is in `build/t41/inventory02/`. Import/count receipts,
input SHA-256, full pin/alias/consumer records and generated tables are
in `build/t41/inventory04/`. All 269 emitted files are byte-identical to the
completed PLAN05 `build/plan05/t36-timing03/emit` snapshot (measured SHA-256
comparison); this is not a rerun of PLAN05 timing or functional acceptance.

Counting boundary: explicit sequential Q bits in the elaborated digital
hierarchy, before optimization/technology mapping. Port and wire-buffer aliases
are unified; single-bit inversion is normalized with pin polarity retained.
Distinct Boolean expressions are **not** assumed equivalent. Each Q bit is
counted once, not repeatedly through overlapping cold/warm source cones.
Reset controls mean asynchronous load/reset or explicit synchronous-reset pins;
ordinary D-input mux clear conditions are not extra reset nets. SRAM macros,
analog macros, inferred memories and temporary pre-optimization latch cells are
outside the explicit-flop count. This is not a mapped area, physical reset-tree
or CDC/RDC signoff count. The same tool/boundary must be used after consolidation.

| Inventory item | Measured count |
| --- | ---: |
| Shared ResetRelease instances | 89 |
| State bits inside those releases | 178 |
| Distinct reset-control nets after alias/inversion normalization | 150 |
| Unique explicit flop bits controlled by those nets | 15,071 |
| All explicit flop bits | 23,113 |
| Explicit flop bits without a reset pin | 8,042 |
| ResetRelease instances inside the USB wrapper | 14 |

The ten specification rows are architectural descriptions, not ten release
instances. Neither the 150 reset nets nor the 15,071 affected bits are an area
estimate. Asynchronous GPIO event-capture controls are included in the raw
control-pin inventory and identified as events below, not hidden as a fifth
system-reset cohort. The pre-optimization model also contains 176 temporary
latch bits in retained vendor SIE lowering, seven inferred memories and 24
blackbox instances; those are reported separately and are not claimed mapped
storage cells or new RTL.

## Sources, predicates and dependencies

Names below are active-low unless stated otherwise. `cold` is selected directly
by the static POR_BYPASS strap: external pin in bypass mode, on-die supply reset
otherwise. `pin` is always the external active-low pad. `wholeHold` and
`performanceHold` are current watchdog outputs. No software-reset command
exists in the current power_reset register map; T41 must not invent one.

| Source / current cohort | Current predicate and firing condition | Domain / consumers | Reason, dependent evidence and proposed disposition |
| --- | --- | --- | --- |
| Supply cold | `Mux(POR_BYPASS, pin, supplyReset_n)` | AON, main, TCK; indirectly OSC_IN and USB | Initialize causes, debug and watchdog history. ResetBootstrap/ResetCauses proofs and SocClockResetSpec/SocResetPhaseSpec. Retain cold source; share release per reached domain |
| Pin warm | `pin` in normal mode; also cold in bypass | Bootstrap and all service domains; BIST abort | Capture even a pulse between clock edges. ResetCauses pin proof, reset-phase tests, T35 pin-abort tests. Warm source plus cold-owned cause/event capture; do not replace with a sampled level |
| Main service | `cold && pin && !wholeHold && !ndmreset && !bist.resetHold && mainServiceReset_n` | Main core service, fabrics, DMA, UART/SPI/I2C/QSPI, merged timers, bridges | Keep reset asserted until first clock qualification; SocI1ResetSpec/phase tests. Merge application reset into warm; qualification stays controller state |
| AON service | Same source conjunction with `aonServiceReset_n` | AON fabric, lite service, mailbox, timers, AON SPI/GPIO and MMIO | Quarantine AON until selected source runs; cancel stale service transactions. Same integration tests plus dormant tests. Merge into warm after bootstrap readiness |
| Performance client | Main-service conjunction plus performance hold and client input | Performance core/client adapter, separate PWM safe-disable | D70 containment being replaced by D103. Watchdog/client phase and PWM-reset tests migrate to warm expectations; preserve immediate output disable |
| Debug module | Cold only | Main debug module/SBA and TCK TAP | Must survive ndmreset and run to clear it. Debug module/epoch/command proofs and debug-wire tests. Shared cold/debug release |
| Debug DMI transport epoch | Cold and TCK-registered TAP clear epoch | TCK/main FIFO endpoints, pending response, custom-DMI command state | Flush transport without aborting accepted BIST. DebugTransport/epoch tests. Functional flush under cold/debug reset, not an extra distributed reset tree |
| SRAM BIST epoch | `cold && pin`, excluding ndmreset and BIST's own hold | Main and AON March agents, manager, result FIFO, custom-DMI command lifetime | T35 explicitly survives ndmreset but pin aborts. SRAM ownership proof debt and JTAG BIST tests. Cold/debug-owned state with reliably captured pin abort, immediate port quarantine and acknowledged functional clearing; do not feed self-generated warm reset into BIST |
| BIST reset hold | `bist.resetHold` high from accepted destructive test through both agents' relinquish | Main/AON functional consumers, including memory controllers | Test ownership excludes functional accesses. SRAM ownership/March tests. A warm assert source; manager remains a documented warm survivor |
| Lite functional reset/boot hold | `aonRaw && !debugResetting && !liteBootHeld` | Lite core/adapter and reset acknowledgement back to main DM | C3 application halt/load/release and debug teardown. BootControl/LiteBootState/LiteBootRelease and debug tests. Shared warm async reset plus acknowledged synchronous initialization/hold; no clock-stop substitute |
| Oscillator policy epoch | Cold, pin and AON bootstrap readiness; excludes internal watchdog/ndmreset | AON sequencer/configuration snapshots | Internal reset must cancel sleep without deadlocking the clock needed by debug. OscResetConfig/ClockComposition/dormant tests. Cold-owned controller with functional warm-entry invalidation and restart while warm remains asserted |
| Source qualification epoch | AON bootstrap readiness AND OSC_EN | OSC_IN counter, ungated divide-by-six gate executor, configuration/command/result FIFOs | Clear stale permission before oscillator stops. ClockContracts/Divider/OscStability proofs and clock tests. Functional epoch invalidation/acknowledged FIFO flush; preserve fresh qualification before reopening |
| USB transport | Existing app/USB/AON combinations, VBUS, enable/configuration, bus reset, session flush and endpoint toggle-reset | USB, main and AON wrapper; SIE/EP0/buffers and payload FIFOs | T19 independent-reset/certificate obligations and wire tests. Preserve all USB-local release trees and source behavior under the explicit USB exception; do not add performance-watchdog reset to USB implicitly |
| GPIO edge capture | Enabled edge level OR common reset at capture cell | AON GPIO event flip-flops and shared synchronizers | Sub-AON-cycle pulse capture, not a system-reset bank. AON GPIO capture tests/proof debt. Preserve event capture and label separately |
| Watchdog and cause retention | Cold-qualified state; service reset only controls admission/configuration | AON watchdog history, pin/brownout record | WatchdogPause/PowerReset/ResetCauses evidence. Preserve causes on all warm sources, add debug cause ABI as required by T41 |

### Service qualification precisely

`ResetBootstrap` first selects the strapped AON source. Its `raw` reset is
`pin && cold`. A shared release takes two selected-clock edges; `locked` is then
set and a counter reaches the configured `stableEdges` (production value 8).
`aonServiceReset_n` is `released && locked && edges == stableEdges`. It asserts
on raw reset without waiting for clock edges and remains asserted during initial
source counting. It does not independently detect later oscillator failure.
`AON_CLK_SEL` remains frozen after this bootstrap until raw reset.

`OscClockReset.bootDone` starts false under that AON bootstrap reset and sets
when the AON policy's `authorized` is seen. `mainServiceReset_n` is
`bootstrap.aonReset_n && bootDone`. Once initially qualified it remains high
through normal light/deep sleep; it is not the instantaneous stability indication
and is not reset on every internal watchdog/debug service reset. `OSC_EN` low
separately invalidates source-domain authorization, FIFO payload and stability.

A straight replacement of every controller reset with level-held warm reset is
incorrect: warm includes `ndmreset`, the DM needs main clock to clear ndmreset,
and a reset-held sequencer cannot authorize that clock. Likewise a bootstrap
counter cannot be reset by the qualified release it must create. T41 must keep
cold/debug-owned control running, invalidate epoch state on warm entry, then
qualify clocks while application warm remains held. OSC_IN, ungated divide-by-six,
gated main, selected AON and TCK are distinct clock nets in the tables; equal
frequency does not justify treating different edge streams as interchangeable.
No fifth distributed cohort is established as necessary by this inventory.

### Retention guardrails for implementation

- BIST pin abort is distinct from aggregate warm edges: a pin pulse may arrive
  while ndmreset or the test's own hold already keeps warm asserted. Capture it
  independently, quarantine SRAM pins immediately and acknowledge both agents'
  state/result flush before readmission. No new minimum reset-pulse assumption;
  the GPIO capture model's 1 us assumption must not silently apply to reset.
- Application HOLD is already drain-qualified. Lite synchronous initialization
  must clear **all** formerly reset state, including GPRs, CSR/debug, pipeline and
  adapter handshake state, before program-RAM writes are allowed. `held` alone,
  debug halt or a stopped clock does not meet C3. Preserve ownership and accepted
  start/entry acknowledgements through shared CDC.
- DMI clear must reject stale requests/responses without aborting an already
  accepted destructive test. Source-off must clear stale gate permission before
  restart. Both are functional protocol epochs requiring tests, not reset-tree
  names to retain by default.
- USB remains the explicit unchanged exception. Its incoming application/service
  sources need isolation from the new performance-watchdog warm source; no new
  USB reset behavior is authorized by deleting performance-client reset.
- SRAM contents have no reset-clearing path. BIST is deliberately destructive;
  interrupted-test memory contents remain unspecified under the existing contract.

## Scoped verification manifest (planned, not run)

The inventory changes no RTL; the following is the pre-change obligation list,
not a passing-test receipt. Existing assertions and negatives remain. No test is
removed by this inventory. At implementation, record each old cohort expectation
and its D103 replacement explicitly; new cases augment the list.

| Family | Existing entrypoints | T41 checks / disposition |
| --- | --- | --- |
| Shared release/CDC | `python hw/lib/formal/cdc_proof.py --width 8 --depth 2 --output build/t41/cdc-final`; `deadhorse.lib.CdcSpec` | Re-prove release async-assert/two-edge behavior; shared qualified endpoints and functional flush ordering; no unchanged timeout reruns |
| Bootstrap, divider, cause capture | `osc_ctrl/formal/reset_check.py`, `reset_causes_check.py`, `divider_check.py`; ResetBootstrapSpec, DividerResetSpec, OscClockSpec, OscBoundarySpec | Both bypass/source straps; cold initializes, pin captured, no early domain release, glitch-free divider |
| Oscillator policy/start-stop | `osc_ctrl/formal/clock_contracts_check.py`, `composition_check.py`; OscSequencerSpec, OscCtrlSpec, OscResetConfigSpec, OscSleepTransferSpec | Re-scope existing deferred shutdown/startup claims; warm during OFF/STARTING; debug can clear ndmreset; stale source permission rejected |
| Causes/threshold/watchdogs | `power_reset/formal/check.py`, `watchdog/formal/check.py`; PowerResetSpec, WatchdogSpec, WatchdogMmioSpec, WatchdogPauseSpec | Both watchdogs warm, correct retained cause, safe PWM immediately, performance watchdog frozen in dormant; cause-clear negative |
| Boot authority/state | `boot_control/formal/check.py`; BootControlSpec, LiteBootStateSpec, BootResetContextSpec, BootModeStrapSpec | Acknowledged full lite initialization before writes; hold/load/release/start and surviving debug ownership |
| Core/service integration | SocI1ResetSpec, SocI1CoreResetSpec, SocClientPhaseSpec, SocResetPhaseSpec, SocWatchdogSpec, SocWatchdogCoreSpec, SocWatchdogEpochSpec, SocWatchdogPhaseSpec, SocWatchdogOfferedSpec, SocPwmCoreResetSpec, SocPinmuxCoreResetSpec | Migrate only obsolete performance-containment expectations; each warm source, active DMA reset, SRAM retention, safe-output negative |
| Production sleep/boot | SocClockResetSpec, SocDormantSpec, SocDormantHoldSpec, SocBootSpec, SocBootReleaseSpec, SocBootStrapSpec, SocPowerThresholdSpec | Reset during sleep/start; qualification order; wake without reset still resumes; both images' valid-CRC and reload paths |
| ROM wire/policy | `python dv/soc/boot/check.py --output build/t41/boot-final` | Both-image warm fast path, corrupt either image forces reload, cause ABI; preserve original malformed/update/power-cut/UART controls |
| Debug/BIST | DebugSpec, DebugModuleSpec, DebugSbaRouteSpec, SramStatusSpec, SramSpec; `debug/formal/{check,transport,epoch,command,ownership}.py`; `sram/formal/ownership.py` | Live session survives ndmreset, accepted BIST cannot self-abort, pin during stopped clocks/held warm aborts and flushes; triage existing unresolved jobs only after changed model |
| USB | Existing T19 check and reset/certificate receipts | USB source/boundary equivalence required if upstream wiring changes; leave local reset/CDC behavior unchanged and retain outstanding debt |
| Structural/measurement | check_soc_map.py; tools/check_structure.py --include-untracked; git diff --check; this inventory; affected domain STA and mapped power/reset area | Run relevant checks, no aggregate fast/full CI. Before/after use identical count and mapping boundaries |

Fully qualified Scala packages follow their existing directory: `deadhorse.top`,
`deadhorse.osc_ctrl`, `deadhorse.power_reset`, `deadhorse.watchdog`,
`deadhorse.boot_control`, `deadhorse.debug`, `deadhorse.sram`, `deadhorse.lib`.
Use focused `hw/testOnly` selections. Existing 120 s solver caps and deferred
proof status stand. No source-text behavioral tests or broad proof sweep.
Missing warm-reset negative controls must be implemented, not treated as covered
by the inventory. Analog tests need rerun only if their digital hookup changes;
the macro interface itself must remain unchanged.

## Exhaustive release instances

Each row contributes two release-state bits. Direct reset-controlled bits below
exclude descendants behind additional gates/releases; they are **not** summed
as transitive source fanout. The reset-control table following this one partitions
all 15,071 affected bits exactly once. Sources and consumers in both tables map
to the contract/evidence families above. All names are relative to DeadhorseSoc.

| Instance (relative to DeadhorseSoc) | Clock net | Reset source | Released net | Release bits | Direct reset-controlled bits |
| --- | --- | --- | --- | ---: | ---: |
| causes.cold | causes.clk | causes.coldReset_n | causes.cold.second | 2 | 4 |
| causes.pin | causes.clk | externalReset_n | causes.pin.second | 2 | 0 |
| clocks.bootstrap.released | causes.clk | clocks.bootstrap.raw | clocks.bootstrap.released.second | 2 | 0 |
| clocks.commands.rd | clocks.gate.clk | clocks.commands.commonReset_n | clocks.commands.readUp | 2 | 10 |
| clocks.commands.wr | causes.clk | clocks.commands.commonReset_n | clocks.commands.writeUp | 2 | 10 |
| clocks.completions.rd | causes.clk | clocks.completions.commonReset_n | clocks.completions.readUp | 2 | 10 |
| clocks.completions.wr | clocks.gate.clk | clocks.completions.commonReset_n | clocks.completions.writeUp | 2 | 10 |
| clocks.configuration.rd | oscIn | clocks.configuration.commonReset_n | clocks.configuration.rd.second | 2 | 21 |
| clocks.configuration.wr | causes.clk | clocks.configuration.commonReset_n | clocks.configuration.writeUp | 2 | 11 |
| clocks.counter.release_0 | oscIn | clocks.counter.release_0.reset_n | clocks.counter.request.reset_n | 2 | 20 |
| clocks.gateReset | clocks.gate.clk | clocks.gateReset.reset_n | clocks.gateReset.second | 2 | 0 |
| digital.coreRelease | status_mainLevel | digital.coreRelease.reset_n | digital.core.rst_ni | 2 | 1811 |
| digital.serviceRelease | status_mainLevel | digital.serviceRelease.reset_n | digital.memory.serviceReset_n | 2 | 12 |
| digital.subsystem.aonUp_r | causes.clk | digital.subsystem.aonRaw | digital.subsystem.af.reset_n | 2 | 1700 |
| digital.subsystem.bist.aonUp_r | causes.clk | digital.subsystem.debugger_bist_epoch_n | digital.subsystem.bist.a.reset_n | 2 | 101 |
| digital.subsystem.bist.fifo.rd | status_mainLevel | digital.subsystem.bist.fifo.commonReset_n | digital.subsystem.bist.fifo.readUp | 2 | 89 |
| digital.subsystem.bist.fifo.wr | causes.clk | digital.subsystem.bist.fifo.commonReset_n | digital.subsystem.bist.fifo.wr.second | 2 | 10 |
| digital.subsystem.bist.mainUp_r | status_mainLevel | digital.subsystem.debugger_bist_epoch_n | digital.subsystem.bist.m.reset_n | 2 | 300 |
| digital.subsystem.coldUp_r | causes.clk | causes.coldReset_n | digital.subsystem.coldUp_r.second | 2 | 110 |
| digital.subsystem.controllerUp_r | causes.clk | digital.subsystem.bootStrap.wholeReset_n | digital.subsystem.fromMain_s.reset_n | 2 | 10 |
| digital.subsystem.debugActiveAon_q_reset_n_r | causes.clk | causes.coldReset_n | digital.subsystem.debugActiveAon_q.reset_n | 2 | 2 |
| digital.subsystem.debugMainUp_r | status_mainLevel | causes.coldReset_n | digital.subsystem.debugMainUp_r.second | 2 | 4 |
| digital.subsystem.debugWake_q_reset_n_r | causes.clk | causes.coldReset_n | digital.subsystem.debugWake_q.reset_n | 2 | 2 |
| digital.subsystem.debugger.release_0 | status_mainLevel | causes.coldReset_n | digital.subsystem.debugger.dm.rst_ni | 2 | 848 |
| digital.subsystem.debugger.tapRelease | pins_inactive_jtagTck | causes.coldReset_n | digital.subsystem.debugger.tap.rst_ni | 2 | 166 |
| digital.subsystem.debugger.transport.req.rd | status_mainLevel | digital.subsystem.debugger.transport.req.commonReset_n | digital.subsystem.debugger.transport.req.readUp | 2 | 50 |
| digital.subsystem.debugger.transport.req.wr | pins_inactive_jtagTck | digital.subsystem.debugger.transport.req.commonReset_n | digital.subsystem.debugger.transport.req.wr.second | 2 | 10 |
| digital.subsystem.debugger.transport.resp.rd | pins_inactive_jtagTck | digital.subsystem.debugger.transport.resp.commonReset_n | digital.subsystem.debugger.transport.resp.rd.second | 2 | 43 |
| digital.subsystem.debugger.transport.resp.wr | status_mainLevel | digital.subsystem.debugger.transport.resp.commonReset_n | digital.subsystem.debugger.transport.resp.writeUp | 2 | 10 |
| digital.subsystem.debugger.transport.tckRelease | pins_inactive_jtagTck | causes.coldReset_n | digital.subsystem.debugger.transport.tckRelease.second | 2 | 1 |
| digital.subsystem.debugger_ndmAck_q_reset_n_r | status_mainLevel | causes.coldReset_n | digital.subsystem.debugger_ndmAck_q.reset_n | 2 | 2 |
| digital.subsystem.gpio.w.ar | causes.clk | digital.subsystem.gpio.w.common | digital.subsystem.gpio.w.ar.second | 2 | 15 |
| digital.subsystem.gpio.w.f.rd | causes.clk | digital.subsystem.gpio.w.f.commonReset_n | digital.subsystem.gpio.w.f.readUp | 2 | 18 |
| digital.subsystem.gpio.w.f.wr | status_mainLevel | digital.subsystem.gpio.w.f.commonReset_n | digital.subsystem.gpio.w.f.writeUp | 2 | 10 |
| digital.subsystem.gpio.w.mr | status_mainLevel | digital.subsystem.gpio.w.common | digital.subsystem.gpio.w.mr.second | 2 | 21 |
| digital.subsystem.haltLite_q_reset_n_r | causes.clk | causes.coldReset_n | digital.subsystem.haltLite_q.reset_n | 2 | 2 |
| digital.subsystem.leaf.localSourceReset | causes.clk | digital.subsystem.aonRaw | digital.subsystem.leaf.ackSync.reset_n | 2 | 65 |
| digital.subsystem.leaf.localTargetReset | status_mainLevel | digital.subsystem.mainRaw | digital.subsystem.leaf.consumer.reset_n | 2 | 42 |
| digital.subsystem.leaf.requests.rd | status_mainLevel | digital.subsystem.leaf.requests.commonReset_n | digital.subsystem.leaf.requests.rd.second | 2 | 81 |
| digital.subsystem.leaf.requests.wr | causes.clk | digital.subsystem.leaf.requests.commonReset_n | digital.subsystem.leaf.requests.wr.second | 2 | 10 |
| digital.subsystem.leaf.responses.rd | causes.clk | digital.subsystem.leaf.responses.commonReset_n | digital.subsystem.leaf.responses.rd.second | 2 | 42 |
| digital.subsystem.leaf.responses.wr | status_mainLevel | digital.subsystem.leaf.responses.commonReset_n | digital.subsystem.leaf.responses.wr.second | 2 | 10 |
| digital.subsystem.leaf.sourceTransport | causes.clk | digital.subsystem.leaf.transportReset_n | digital.subsystem.leaf.producer.linkUp | 2 | 0 |
| digital.subsystem.leaf.targetTransport | status_mainLevel | digital.subsystem.leaf.transportReset_n | digital.subsystem.leaf.consumer.linkUp | 2 | 0 |
| digital.subsystem.leafPermit.ar | causes.clk | digital.subsystem.leafPermit.ar.reset_n | digital.subsystem.leafPermit.ar.second | 2 | 9 |
| digital.subsystem.leafPermit.mr | status_mainLevel | digital.subsystem.leafPermit.ar.reset_n | digital.subsystem.leafPermit.mr.second | 2 | 2 |
| digital.subsystem.liteClientUp_r | causes.clk | digital.subsystem.liteClientRaw | digital.subsystem.liteHart.reset_n | 2 | 1796 |
| digital.subsystem.liteEntryAck_q_reset_n_r | status_mainLevel | causes.coldReset_n | digital.subsystem.liteEntryAck_q.reset_n | 2 | 2 |
| digital.subsystem.liteResetSeen_r | status_mainLevel | digital.subsystem.liteClientRaw | digital.subsystem.liteEpoch | 2 | 0 |
| digital.subsystem.mailbox.am.rd | status_mainLevel | digital.subsystem.mailbox.am.commonReset_n | digital.subsystem.mailbox.m.rxUp | 2 | 41 |
| digital.subsystem.mailbox.am.wr | causes.clk | digital.subsystem.mailbox.am.commonReset_n | digital.subsystem.mailbox.a.txUp | 2 | 10 |
| digital.subsystem.mailbox.ar | causes.clk | digital.subsystem.aonRaw | digital.subsystem.mailbox.a.reset_n | 2 | 144 |
| digital.subsystem.mailbox.ma.rd | causes.clk | digital.subsystem.mailbox.ma.commonReset_n | digital.subsystem.mailbox.a.rxUp | 2 | 41 |
| digital.subsystem.mailbox.ma.wr | status_mainLevel | digital.subsystem.mailbox.ma.commonReset_n | digital.subsystem.mailbox.m.txUp | 2 | 10 |
| digital.subsystem.mailbox.mr | status_mainLevel | digital.subsystem.mainRaw | digital.subsystem.mailbox.m.reset_n | 2 | 144 |
| digital.subsystem.mainUp_r | status_mainLevel | digital.subsystem.mainRaw | digital.subsystem.p.reset_n | 2 | 4896 |
| digital.subsystem.oscillatorPolicyUp_r | causes.clk | digital.subsystem.oscillatorPolicyUp_r.reset_n | digital.subsystem.oscillator.epochReset_n | 2 | 94 |
| digital.subsystem.perfEpoch_r | status_mainLevel | digital.coreRelease.reset_n | digital.subsystem.perfEpoch_r.second | 2 | 1 |
| digital.subsystem.permits.ar | causes.clk | digital.subsystem.permits.ar.reset_n | digital.subsystem.permits.ar.second | 2 | 9 |
| digital.subsystem.permits.mr | status_mainLevel | digital.subsystem.permits.ar.reset_n | digital.subsystem.permits.mr.second | 2 | 2 |
| digital.subsystem.pwmUp_r | status_mainLevel | digital.subsystem.pwmUp_r.reset_n | digital.subsystem.pwmUp_r.second | 2 | 0 |
| digital.subsystem.toAon.localSourceReset | status_mainLevel | digital.subsystem.mainRaw | digital.subsystem.toAon.ackSync.reset_n | 2 | 65 |
| digital.subsystem.toAon.localTargetReset | causes.clk | digital.subsystem.aonRaw | digital.subsystem.toAon.consumer.reset_n | 2 | 42 |
| digital.subsystem.toAon.requests.rd | causes.clk | digital.subsystem.toAon.requests.commonReset_n | digital.subsystem.toAon.requests.rd.second | 2 | 81 |
| digital.subsystem.toAon.requests.wr | status_mainLevel | digital.subsystem.toAon.requests.commonReset_n | digital.subsystem.toAon.requests.wr.second | 2 | 10 |
| digital.subsystem.toAon.responses.rd | status_mainLevel | digital.subsystem.toAon.responses.commonReset_n | digital.subsystem.toAon.responses.rd.second | 2 | 42 |
| digital.subsystem.toAon.responses.wr | causes.clk | digital.subsystem.toAon.responses.commonReset_n | digital.subsystem.toAon.responses.wr.second | 2 | 10 |
| digital.subsystem.toAon.sourceTransport | status_mainLevel | digital.subsystem.toAon.transportReset_n | digital.subsystem.toAon.producer.linkUp | 2 | 0 |
| digital.subsystem.toAon.targetTransport | causes.clk | digital.subsystem.toAon.transportReset_n | digital.subsystem.toAon.consumer.linkUp | 2 | 0 |
| digital.subsystem.uartSleep.fifo.rd | status_mainLevel | digital.subsystem.uartSleep.fifo.commonReset_n | digital.subsystem.uartSleep.fifo.readUp | 2 | 23 |
| digital.subsystem.uartSleep.fifo.wr | causes.clk | digital.subsystem.uartSleep.fifo.commonReset_n | digital.subsystem.uartSleep.fifo.writeUp | 2 | 18 |
| digital.subsystem.uartWake_monitor.release_0 | causes.clk | digital.subsystem.fromMain_s.reset_n | digital.subsystem.uartWake_monitor.release_0.second | 2 | 3 |
| digital.subsystem.uartWake_monitor_1.release_0 | causes.clk | digital.subsystem.fromMain_s.reset_n | digital.subsystem.uartWake_monitor_1.release_0.second | 2 | 3 |
| digital.subsystem.uartWake_monitor_2.release_0 | causes.clk | digital.subsystem.fromMain_s.reset_n | digital.subsystem.uartWake_monitor_2.release_0.second | 2 | 3 |
| digital.subsystem.usb.aonUp_r | causes.clk | digital.subsystem.aonRaw | digital.subsystem.usb.aonUp_r.second | 2 | 4 |
| digital.subsystem.usb.appUp_r | status_mainLevel | digital.subsystem.usb.commonReset | digital.subsystem.usb.appUp_r.second | 2 | 108 |
| digital.subsystem.usb.engine.inRelease | oscIn | digital.subsystem.usb.engine.inRelease.reset_n | digital.subsystem.usb.engine.in.reset_n | 2 | 48 |
| digital.subsystem.usb.engine.outRelease | oscIn | digital.subsystem.usb.engine.outRelease.reset_n | digital.subsystem.usb.engine.out.reset_n | 2 | 41 |
| digital.subsystem.usb.engine.release_0 | oscIn | digital.subsystem.usb.engine.release_0.reset_n | digital.subsystem.usb.engine.sie.rstn_i | 2 | 372 |
| digital.subsystem.usb.events.rd | status_mainLevel | digital.subsystem.usb.events.commonReset_n | digital.subsystem.usb.events.rd.second | 2 | 17 |
| digital.subsystem.usb.events.wr | oscIn | digital.subsystem.usb.events.commonReset_n | digital.subsystem.usb.events.wr.second | 2 | 10 |
| digital.subsystem.usb.rx.rd | status_mainLevel | digital.subsystem.usb.rx.commonReset_n | digital.subsystem.usb.rx.rd.second | 2 | 17 |
| digital.subsystem.usb.rx.wr | oscIn | digital.subsystem.usb.rx.commonReset_n | digital.subsystem.usb.rx.wr.second | 2 | 10 |
| digital.subsystem.usb.snapshot.rd | status_mainLevel | digital.subsystem.usb.snapshot.commonReset_n | digital.subsystem.usb.snapshot.readUp | 2 | 41 |
| digital.subsystem.usb.snapshot.wr | oscIn | digital.subsystem.usb.snapshot.commonReset_n | digital.subsystem.usb.snapshot.writeUp | 2 | 10 |
| digital.subsystem.usb.tx.rd | oscIn | digital.subsystem.usb.tx.commonReset_n | digital.subsystem.usb.tx.rd.second | 2 | 17 |
| digital.subsystem.usb.tx.wr | status_mainLevel | digital.subsystem.usb.tx.commonReset_n | digital.subsystem.usb.tx.wr.second | 2 | 10 |
| digital.subsystem.usb.usbUp_r | oscIn | digital.subsystem.usb.commonReset | digital.subsystem.usb.resume.reset_n | 2 | 43 |
| digital.subsystem.usbAppUp_r | status_mainLevel | digital.subsystem.usbAppUp_r.reset_n | digital.subsystem.gateway.admit_1 | 2 | 0 |

## Exhaustive reset-control nets and consumers

Each ID is unique within this frozen hierarchy. Anonymous tuple names identify
the exact module-local Yosys wire bit; all named aliases, reset pin polarity,
source-cone leaves and individual Q-bit endpoints are in reset-inventory.json.
The source appendix gives those leaves explicitly. Generated internal names are
not stable acceptance identities across a changed emission. This table includes
event-capture async controls; it does not classify each as a system cohort.

| ID | Reset control net (inversion normalized) | Clock net(s) | Unique flop bits | Consumer modules |
| --- | --- | --- | ---: | --- |
| R001 | ('clocks', 60) | causes.clk | 6 | clocks |
| R002 | ('digital.memory', 2870) | status_mainLevel | 7 | digital.memory |
| R003 | ('digital.subsystem.boot.state', 24) | causes.clk | 1 | digital.subsystem.boot.state |
| R004 | ('digital.subsystem.debugger.custom', 326) | status_mainLevel | 1 | digital.subsystem.debugger.custom |
| R005 | ('digital.subsystem.oscillator', 196) | causes.clk | 1 | digital.subsystem.oscillator |
| R006 | ('digital.subsystem.p', 1444) | status_mainLevel | 26 | digital.subsystem.p |
| R007 | ('digital.subsystem.p.pads_0', 31) | status_mainLevel | 2 | digital.subsystem.p.pads_0 |
| R008 | ('digital.subsystem.p.pads_1', 31) | status_mainLevel | 2 | digital.subsystem.p.pads_1 |
| R009 | ('digital.subsystem.p.pads_2', 31) | status_mainLevel | 2 | digital.subsystem.p.pads_2 |
| R010 | ('digital.subsystem.slot', 513) | status_mainLevel | 1 | digital.subsystem.slot |
| R011 | causes.cold.second | causes.clk | 4 | causes, causes.brown |
| R012 | causes.coldReset_n | causes.clk, pins_inactive_jtagTck, status_mainLevel | 22 | causes.cold, digital.subsystem.coldUp_r, digital.subsystem.debugActiveAon_q_reset_n_r, digital.subsystem.debugMainUp_r, digital.subsystem.debugWake_q_reset_n_r, digital.subsystem.debugger.release_0, digital.subsystem.debugger.tapRelease, digital.subsystem.debugger.transport.tckRelease, digital.subsystem.debugger_ndmAck_q_reset_n_r, digital.subsystem.haltLite_q_reset_n_r, digital.subsystem.liteEntryAck_q_reset_n_r |
| R013 | clocks.bootstrap.raw | causes.clk | 7 | clocks.bootstrap, clocks.bootstrap.released |
| R014 | clocks.commands.commonReset_n | causes.clk, clocks.gate.clk | 4 | clocks.commands.rd, clocks.commands.wr |
| R015 | clocks.commands.readUp | clocks.gate.clk | 10 | clocks.commands.reader, clocks.commands.reader.sync |
| R016 | clocks.commands.writeUp | causes.clk | 10 | clocks.commands.writer, clocks.commands.writer.sync |
| R017 | clocks.completions.commonReset_n | causes.clk, clocks.gate.clk | 4 | clocks.completions.rd, clocks.completions.wr |
| R018 | clocks.completions.readUp | causes.clk | 10 | clocks.completions.reader, clocks.completions.reader.sync |
| R019 | clocks.completions.writeUp | clocks.gate.clk | 10 | clocks.completions.writer, clocks.completions.writer.sync |
| R020 | clocks.configuration.commonReset_n | causes.clk, oscIn | 4 | clocks.configuration.rd, clocks.configuration.wr |
| R021 | clocks.configuration.rd.second | oscIn | 21 | clocks.configuration.reader, clocks.configuration.reader.sync |
| R022 | clocks.configuration.writeUp | causes.clk | 11 | clocks, clocks.configuration.writer, clocks.configuration.writer.sync |
| R023 | clocks.counter.release_0.reset_n | oscIn | 2 | clocks.counter.release_0 |
| R024 | clocks.counter.request.reset_n | oscIn | 20 | clocks.counter, clocks.counter.request |
| R025 | clocks.gate.reset_n | clocks.gate.clk | 9 | clocks.gate, clocks.gate.valid |
| R026 | clocks.gateReset.reset_n | clocks.gate.clk | 2 | clocks.gateReset |
| R027 | digital.bootReleased | oscIn | 2 | clocks.dividerRelease |
| R028 | digital.core.rst_ni | digital.core.u_ibex_core.clk_i, status_mainLevel | 1811 | digital.core, digital.core.gen_regfile_ff_register_file_i, digital.core.u_ibex_core, digital.core.u_ibex_core.cs_registers_i, digital.core.u_ibex_core.ex_block_i.gen_multdiv_fast_multdiv_i, digital.core.u_ibex_core.floatExecution.fpu, digital.core.u_ibex_core.floatExecution.fpu.div, digital.core.u_ibex_core.id_stage_i, digital.core.u_ibex_core.id_stage_i.controller_i, digital.core.u_ibex_core.if_stage_i, digital.core.u_ibex_core.if_stage_i.gen_prefetch_buffer_prefetch_buffer_i, digital.core.u_ibex_core.if_stage_i.gen_prefetch_buffer_prefetch_buffer_i.fifo_i, digital.core.u_ibex_core.load_store_unit_i |
| R029 | digital.coreRelease.reset_n | status_mainLevel | 4 | digital.coreRelease, digital.subsystem.perfEpoch_r |
| R030 | digital.memory.serviceReset_n | status_mainLevel | 12 | digital.memory |
| R031 | digital.serviceRelease.reset_n | status_mainLevel | 2 | digital.serviceRelease |
| R032 | digital.subsystem.af.reset_n | causes.clk | 1700 | digital.subsystem, digital.subsystem.af, digital.subsystem.af_quiescent_1_d, digital.subsystem.af_quiescent_3_d, digital.subsystem.aonGpio, digital.subsystem.aonGpio.ack, digital.subsystem.aonGpio.adapter, digital.subsystem.aonGpio.c, digital.subsystem.aonGpio.c.level, digital.subsystem.aonGpio.c.sync, digital.subsystem.aonGpio.c_1, digital.subsystem.aonGpio.c_1.level, digital.subsystem.aonGpio.c_1.sync, digital.subsystem.aonGpio.c_2, digital.subsystem.aonGpio.c_2.level, digital.subsystem.aonGpio.c_2.sync, digital.subsystem.aonGpio.c_3, digital.subsystem.aonGpio.c_3.level, digital.subsystem.aonGpio.c_3.sync, digital.subsystem.aonGpio.c_4, digital.subsystem.aonGpio.c_4.level, digital.subsystem.aonGpio.c_4.sync, digital.subsystem.aonGpio.c_5, digital.subsystem.aonGpio.c_5.level, digital.subsystem.aonGpio.c_5.sync, digital.subsystem.aonGpio.inputs, digital.subsystem.aonGpio.mainDrive, digital.subsystem.aonGpio.regs, digital.subsystem.aonIo, digital.subsystem.aonSpi, digital.subsystem.aonSpi.adapter, digital.subsystem.aonSpi.input_0, digital.subsystem.aonSpi.regs, digital.subsystem.aonTimer, digital.subsystem.aonTimer.adapter, digital.subsystem.aonTimer.regs, digital.subsystem.boot.context_0, digital.subsystem.boot.state, digital.subsystem.channels_0.adapter, digital.subsystem.channels_0.regs, digital.subsystem.channels_1.adapter, digital.subsystem.channels_1.regs, digital.subsystem.credit_1, digital.subsystem.powerFabric, digital.subsystem.powerReset, digital.subsystem.powerReset.adapter, digital.subsystem.powerReset.control, digital.subsystem.powerReset.regs, digital.subsystem.retained, digital.subsystem.route, digital.subsystem.s_2 |
| R033 | digital.subsystem.aonGpio.c._captured_T_1 | causes.clk | 1 | digital.subsystem.aonGpio.c |
| R034 | digital.subsystem.aonGpio.c_1._captured_T_1 | causes.clk | 1 | digital.subsystem.aonGpio.c_1 |
| R035 | digital.subsystem.aonGpio.c_2._captured_T_1 | causes.clk | 1 | digital.subsystem.aonGpio.c_2 |
| R036 | digital.subsystem.aonGpio.c_3._captured_T_1 | causes.clk | 1 | digital.subsystem.aonGpio.c_3 |
| R037 | digital.subsystem.aonGpio.c_4._captured_T_1 | causes.clk | 1 | digital.subsystem.aonGpio.c_4 |
| R038 | digital.subsystem.aonGpio.c_5._captured_T_1 | causes.clk | 1 | digital.subsystem.aonGpio.c_5 |
| R039 | digital.subsystem.aonRaw | causes.clk | 10 | digital.subsystem.aonUp_r, digital.subsystem.leaf.localSourceReset, digital.subsystem.mailbox.ar, digital.subsystem.toAon.localTargetReset, digital.subsystem.usb.aonUp_r |
| R040 | digital.subsystem.bist.a.reset_n | causes.clk | 101 | digital.subsystem.bist, digital.subsystem.bist.a, digital.subsystem.bist.remoteRun_s |
| R041 | digital.subsystem.bist.fifo.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.bist.fifo.rd, digital.subsystem.bist.fifo.wr |
| R042 | digital.subsystem.bist.fifo.readUp | status_mainLevel | 89 | digital.subsystem.bist.fifo.reader, digital.subsystem.bist.fifo.reader.sync |
| R043 | digital.subsystem.bist.fifo.wr.second | causes.clk | 10 | digital.subsystem.bist.fifo.writer, digital.subsystem.bist.fifo.writer.sync |
| R044 | digital.subsystem.bist.m.reset_n | status_mainLevel | 300 | digital.subsystem.bist, digital.subsystem.bist.m, digital.subsystem.bist.remoteBusy_s, digital.subsystem.bist.remoteReset_s |
| R045 | digital.subsystem.boot.up | causes.clk | 173 | digital.subsystem.boot.adapter, digital.subsystem.boot.regs |
| R046 | digital.subsystem.bootStrap.wholeReset_n | causes.clk | 3 | digital.subsystem.bootStrap, digital.subsystem.controllerUp_r |
| R047 | digital.subsystem.channels_0.channel._trip_T | causes.clk | 132 | digital.subsystem.channels_0.channel |
| R048 | digital.subsystem.channels_1.channel._trip_T | causes.clk | 131 | digital.subsystem.channels_1.channel |
| R049 | digital.subsystem.coldUp_r.second | causes.clk | 110 | digital.subsystem, digital.subsystem.channels_0.channel, digital.subsystem.channels_1.channel |
| R050 | digital.subsystem.debugActiveAon_q.reset_n | causes.clk | 2 | digital.subsystem.debugActiveAon_q |
| R051 | digital.subsystem.debugMainUp_r.second | status_mainLevel | 4 | digital.subsystem |
| R052 | digital.subsystem.debugWake_q.reset_n | causes.clk | 2 | digital.subsystem.debugWake_q |
| R053 | digital.subsystem.debugger.custom.reset_n | status_mainLevel | 106 | digital.subsystem.debugger, digital.subsystem.debugger.custom, digital.subsystem.debugger.custom.regs |
| R054 | digital.subsystem.debugger.dm.rst_ni | status_mainLevel | 848 | digital.subsystem.debugger.dm.i_dm_csrs, digital.subsystem.debugger.dm.i_dm_csrs.$driver$abstractauto_q, digital.subsystem.debugger.dm.i_dm_csrs.$driver$command_q, digital.subsystem.debugger.dm.i_dm_csrs.$driver$dmcontrol_q, digital.subsystem.debugger.dm.i_dm_csrs.$driver$sbcs_q, digital.subsystem.debugger.dm.i_dm_csrs.i_fifo, digital.subsystem.debugger.dm.i_dm_mem, digital.subsystem.debugger.dm.i_dm_mem.gen_rom_snd_scratch.i_debug_rom, digital.subsystem.debugger.dm.i_dm_sba, digital.subsystem.debugger.sba |
| R055 | digital.subsystem.debugger.tap.rst_ni | digital.subsystem.debugger.tap.i_dmi_jtag_tap.tck_n, pins_inactive_jtagTck | 166 | digital.subsystem.debugger.tap, digital.subsystem.debugger.tap.$driver$dtmcs_q, digital.subsystem.debugger.tap.i_dmi_jtag_tap |
| R056 | digital.subsystem.debugger.transport.req.commonReset_n | pins_inactive_jtagTck, status_mainLevel | 4 | digital.subsystem.debugger.transport.req.rd, digital.subsystem.debugger.transport.req.wr |
| R057 | digital.subsystem.debugger.transport.req.readReset_n | pins_inactive_jtagTck | 1 | digital.subsystem.debugger.transport |
| R058 | digital.subsystem.debugger.transport.req.readUp | status_mainLevel | 50 | digital.subsystem.debugger.transport.req.reader, digital.subsystem.debugger.transport.req.reader.sync |
| R059 | digital.subsystem.debugger.transport.req.wr.second | pins_inactive_jtagTck | 10 | digital.subsystem.debugger.transport.req.writer, digital.subsystem.debugger.transport.req.writer.sync |
| R060 | digital.subsystem.debugger.transport.resp.commonReset_n | pins_inactive_jtagTck, status_mainLevel | 4 | digital.subsystem.debugger.transport.resp.rd, digital.subsystem.debugger.transport.resp.wr |
| R061 | digital.subsystem.debugger.transport.resp.rd.second | pins_inactive_jtagTck | 43 | digital.subsystem.debugger.transport.resp.reader, digital.subsystem.debugger.transport.resp.reader.sync |
| R062 | digital.subsystem.debugger.transport.resp.writeUp | status_mainLevel | 10 | digital.subsystem.debugger.transport.resp.writer, digital.subsystem.debugger.transport.resp.writer.sync |
| R063 | digital.subsystem.debugger.transport.tckRelease.second | pins_inactive_jtagTck | 1 | digital.subsystem.debugger.transport |
| R064 | digital.subsystem.debugger_bist_epoch_n | causes.clk, status_mainLevel | 4 | digital.subsystem.bist.aonUp_r, digital.subsystem.bist.mainUp_r |
| R065 | digital.subsystem.debugger_ndmAck_q.reset_n | status_mainLevel | 2 | digital.subsystem.debugger_ndmAck_q |
| R066 | digital.subsystem.fromMain_s.reset_n | causes.clk | 10 | digital.subsystem.fromMain_s, digital.subsystem.oscillator_coreIdle_s, digital.subsystem.uartWake_monitor.release_0, digital.subsystem.uartWake_monitor_1.release_0, digital.subsystem.uartWake_monitor_2.release_0 |
| R067 | digital.subsystem.gpio.w.ar.second | causes.clk | 15 | digital.subsystem.gpio.w.inputSync, digital.subsystem.gpio.w.state |
| R068 | digital.subsystem.gpio.w.common | causes.clk, status_mainLevel | 4 | digital.subsystem.gpio.w.ar, digital.subsystem.gpio.w.mr |
| R069 | digital.subsystem.gpio.w.f.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.gpio.w.f.rd, digital.subsystem.gpio.w.f.wr |
| R070 | digital.subsystem.gpio.w.f.readUp | causes.clk | 18 | digital.subsystem.gpio.w.f.reader, digital.subsystem.gpio.w.f.reader.sync |
| R071 | digital.subsystem.gpio.w.f.writeUp | status_mainLevel | 10 | digital.subsystem.gpio.w.f.writer, digital.subsystem.gpio.w.f.writer.sync |
| R072 | digital.subsystem.gpio.w.mr.second | status_mainLevel | 21 | digital.subsystem.gpio.w, digital.subsystem.gpio.w.ackValid_s, digital.subsystem.gpio.w.ack_s, digital.subsystem.gpio.w.peerUp_s, digital.subsystem.gpio.w.pending_s |
| R073 | digital.subsystem.haltLite_q.reset_n | causes.clk | 2 | digital.subsystem.haltLite_q |
| R074 | digital.subsystem.leaf.ackSync.reset_n | causes.clk | 65 | digital.subsystem.leaf.ackSync, digital.subsystem.leaf.drainSync, digital.subsystem.leaf.producer |
| R075 | digital.subsystem.leaf.consumer.reset_n | status_mainLevel | 42 | digital.subsystem.leaf.consumer |
| R076 | digital.subsystem.leaf.requests.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.leaf.requests.rd, digital.subsystem.leaf.requests.wr |
| R077 | digital.subsystem.leaf.requests.rd.second | status_mainLevel | 81 | digital.subsystem.leaf.requests.reader, digital.subsystem.leaf.requests.reader.sync |
| R078 | digital.subsystem.leaf.requests.wr.second | causes.clk | 10 | digital.subsystem.leaf.requests.writer, digital.subsystem.leaf.requests.writer.sync |
| R079 | digital.subsystem.leaf.responses.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.leaf.responses.rd, digital.subsystem.leaf.responses.wr |
| R080 | digital.subsystem.leaf.responses.rd.second | causes.clk | 42 | digital.subsystem.leaf.responses.reader, digital.subsystem.leaf.responses.reader.sync |
| R081 | digital.subsystem.leaf.responses.wr.second | status_mainLevel | 10 | digital.subsystem.leaf.responses.writer, digital.subsystem.leaf.responses.writer.sync |
| R082 | digital.subsystem.leaf.transportReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.leaf.sourceTransport, digital.subsystem.leaf.targetTransport |
| R083 | digital.subsystem.leafPermit.ar.reset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.leafPermit.ar, digital.subsystem.leafPermit.mr |
| R084 | digital.subsystem.leafPermit.ar.second | causes.clk | 9 | digital.subsystem.leafPermit.control, digital.subsystem.leafPermit.mainReq, digital.subsystem.leafPermit.returnedGrant |
| R085 | digital.subsystem.leafPermit.mr.second | status_mainLevel | 2 | digital.subsystem.leafPermit.mainGrant |
| R086 | digital.subsystem.liteClientRaw | causes.clk, status_mainLevel | 4 | digital.subsystem.liteClientUp_r, digital.subsystem.liteResetSeen_r |
| R087 | digital.subsystem.liteEntryAck_q.reset_n | status_mainLevel | 2 | digital.subsystem.liteEntryAck_q |
| R088 | digital.subsystem.liteHart.reset_n | causes.clk | 1796 | digital.subsystem.liteHart.adapter, digital.subsystem.liteHart.core |
| R089 | digital.subsystem.mailbox.a.reset_n | causes.clk | 144 | digital.subsystem.mailbox.a, digital.subsystem.mailbox.a.adapter, digital.subsystem.mailbox.a.regs |
| R090 | digital.subsystem.mailbox.a.rxUp | causes.clk | 41 | digital.subsystem.mailbox.ma.reader, digital.subsystem.mailbox.ma.reader.sync |
| R091 | digital.subsystem.mailbox.a.txUp | causes.clk | 10 | digital.subsystem.mailbox.am.writer, digital.subsystem.mailbox.am.writer.sync |
| R092 | digital.subsystem.mailbox.am.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.mailbox.am.rd, digital.subsystem.mailbox.am.wr |
| R093 | digital.subsystem.mailbox.m.reset_n | status_mainLevel | 144 | digital.subsystem.mailbox.m, digital.subsystem.mailbox.m.adapter, digital.subsystem.mailbox.m.regs |
| R094 | digital.subsystem.mailbox.m.rxUp | status_mainLevel | 41 | digital.subsystem.mailbox.am.reader, digital.subsystem.mailbox.am.reader.sync |
| R095 | digital.subsystem.mailbox.m.txUp | status_mainLevel | 10 | digital.subsystem.mailbox.ma.writer, digital.subsystem.mailbox.ma.writer.sync |
| R096 | digital.subsystem.mailbox.ma.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.mailbox.ma.rd, digital.subsystem.mailbox.ma.wr |
| R097 | digital.subsystem.mainRaw | status_mainLevel | 8 | digital.subsystem.leaf.localTargetReset, digital.subsystem.mailbox.mr, digital.subsystem.mainUp_r, digital.subsystem.toAon.localSourceReset |
| R098 | digital.subsystem.oscillator.adapter.reset_n | causes.clk | 38 | digital.subsystem.oscillator.adapter |
| R099 | digital.subsystem.oscillator.configUp | causes.clk | 104 | digital.subsystem.oscillator, digital.subsystem.oscillator.regs |
| R100 | digital.subsystem.oscillator.epochReset_n | causes.clk | 94 | digital.subsystem.oscillator.control, digital.subsystem.oscillator.serviceReset |
| R101 | digital.subsystem.oscillator.reset_n | causes.clk | 13 | digital.subsystem.oscillator |
| R102 | digital.subsystem.oscillatorPolicyUp_r.reset_n | causes.clk | 2 | digital.subsystem.oscillatorPolicyUp_r |
| R103 | digital.subsystem.p.reset_n | status_mainLevel | 4896 | digital.subsystem, digital.subsystem.credit, digital.subsystem.debugger.mem, digital.subsystem.dmArb, digital.subsystem.dma, digital.subsystem.dma.adapter, digital.subsystem.dma.engine, digital.subsystem.dma.regs, digital.subsystem.flash, digital.subsystem.flash.adapter, digital.subsystem.flash.e, digital.subsystem.flash.regs, digital.subsystem.flash.scheduler, digital.subsystem.flash.sync, digital.subsystem.gateway, digital.subsystem.gpio, digital.subsystem.gpio.adapter, digital.subsystem.gpio.regs, digital.subsystem.gpio.sync, digital.subsystem.gpio.w, digital.subsystem.i2c, digital.subsystem.i2c.adapter, digital.subsystem.i2c.regs, digital.subsystem.i2c.sclSync, digital.subsystem.i2c.sdaSync, digital.subsystem.ioFabric, digital.subsystem.mf, digital.subsystem.mf_quiescent_0_d, digital.subsystem.mf_quiescent_3_d, digital.subsystem.nativeArb, digital.subsystem.nativeRoute, digital.subsystem.nmi, digital.subsystem.ownerSync, digital.subsystem.p, digital.subsystem.p.adapter, digital.subsystem.p.inputSync, digital.subsystem.p.pads_0, digital.subsystem.p.pads_1, digital.subsystem.p.pads_2, digital.subsystem.p.regs, digital.subsystem.s, digital.subsystem.s_1, digital.subsystem.serial, digital.subsystem.serial_quiescent_6_d, digital.subsystem.slot, digital.subsystem.spi, digital.subsystem.spi.adapter, digital.subsystem.spi.regs, digital.subsystem.spi.sync, digital.subsystem.timerIrq_s, digital.subsystem.timers, digital.subsystem.timers.adapter, digital.subsystem.timers.dma, digital.subsystem.timers.regs, digital.subsystem.uarts_0, digital.subsystem.uarts_0.adapter, digital.subsystem.uarts_0.regs, digital.subsystem.uarts_0.synchronizer, digital.subsystem.uarts_1, digital.subsystem.uarts_1.adapter, digital.subsystem.uarts_1.regs, digital.subsystem.uarts_1.synchronizer, digital.subsystem.uarts_2, digital.subsystem.uarts_2.adapter, digital.subsystem.uarts_2.regs, digital.subsystem.uarts_2.synchronizer |
| R104 | digital.subsystem.perfEpoch_r.second | status_mainLevel | 1 | digital.subsystem |
| R105 | digital.subsystem.permits.ar.reset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.permits.ar, digital.subsystem.permits.mr |
| R106 | digital.subsystem.permits.ar.second | causes.clk | 9 | digital.subsystem.permits.control, digital.subsystem.permits.mainReq, digital.subsystem.permits.returnedGrant |
| R107 | digital.subsystem.permits.mr.second | status_mainLevel | 2 | digital.subsystem.permits.mainGrant |
| R108 | digital.subsystem.pwmUp_r.reset_n | status_mainLevel | 2 | digital.subsystem.pwmUp_r |
| R109 | digital.subsystem.timers.executionReset | status_mainLevel | 28 | digital.subsystem.timers, digital.subsystem.timers.permit_guard |
| R110 | digital.subsystem.toAon.ackSync.reset_n | status_mainLevel | 65 | digital.subsystem.toAon.ackSync, digital.subsystem.toAon.drainSync, digital.subsystem.toAon.producer |
| R111 | digital.subsystem.toAon.consumer.reset_n | causes.clk | 42 | digital.subsystem.toAon.consumer |
| R112 | digital.subsystem.toAon.requests.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.toAon.requests.rd, digital.subsystem.toAon.requests.wr |
| R113 | digital.subsystem.toAon.requests.rd.second | causes.clk | 81 | digital.subsystem.toAon.requests.reader, digital.subsystem.toAon.requests.reader.sync |
| R114 | digital.subsystem.toAon.requests.wr.second | status_mainLevel | 10 | digital.subsystem.toAon.requests.writer, digital.subsystem.toAon.requests.writer.sync |
| R115 | digital.subsystem.toAon.responses.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.toAon.responses.rd, digital.subsystem.toAon.responses.wr |
| R116 | digital.subsystem.toAon.responses.rd.second | status_mainLevel | 42 | digital.subsystem.toAon.responses.reader, digital.subsystem.toAon.responses.reader.sync |
| R117 | digital.subsystem.toAon.responses.wr.second | causes.clk | 10 | digital.subsystem.toAon.responses.writer, digital.subsystem.toAon.responses.writer.sync |
| R118 | digital.subsystem.toAon.transportReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.toAon.sourceTransport, digital.subsystem.toAon.targetTransport |
| R119 | digital.subsystem.uartSleep.fifo.commonReset_n | causes.clk, status_mainLevel | 4 | digital.subsystem.uartSleep.fifo.rd, digital.subsystem.uartSleep.fifo.wr |
| R120 | digital.subsystem.uartSleep.fifo.readUp | status_mainLevel | 23 | digital.subsystem.uartSleep, digital.subsystem.uartSleep.fifo.reader, digital.subsystem.uartSleep.fifo.reader.sync |
| R121 | digital.subsystem.uartSleep.fifo.writeUp | causes.clk | 18 | digital.subsystem.uartSleep, digital.subsystem.uartSleep.fifo.writer, digital.subsystem.uartSleep.fifo.writer.sync |
| R122 | digital.subsystem.uartWake_monitor.release_0.second | causes.clk | 3 | digital.subsystem.uartWake_monitor, digital.subsystem.uartWake_monitor.synchronizer |
| R123 | digital.subsystem.uartWake_monitor_1.release_0.second | causes.clk | 3 | digital.subsystem.uartWake_monitor_1, digital.subsystem.uartWake_monitor_1.synchronizer |
| R124 | digital.subsystem.uartWake_monitor_2.release_0.second | causes.clk | 3 | digital.subsystem.uartWake_monitor_2, digital.subsystem.uartWake_monitor_2.synchronizer |
| R125 | digital.subsystem.usb.aonUp_r.second | causes.clk | 4 | digital.subsystem.usb.usbClockRequest_s, digital.subsystem.usb.wake_s |
| R126 | digital.subsystem.usb.appUp_r.second | status_mainLevel | 108 | digital.subsystem.usb, digital.subsystem.usb.registers, digital.subsystem.usb.registers.adapter, digital.subsystem.usb.registers.regs, digital.subsystem.usb.registers_configured_s, digital.subsystem.usb.registers_connected_s |
| R127 | digital.subsystem.usb.commonReset | oscIn, status_mainLevel | 4 | digital.subsystem.usb.appUp_r, digital.subsystem.usb.usbUp_r |
| R128 | digital.subsystem.usb.engine.in.reset_n | oscIn | 48 | digital.subsystem.usb.engine.in, digital.subsystem.usb.engine.in.memory |
| R129 | digital.subsystem.usb.engine.inRelease.reset_n | oscIn | 2 | digital.subsystem.usb.engine.inRelease |
| R130 | digital.subsystem.usb.engine.out.reset_n | oscIn | 41 | digital.subsystem.usb.engine.out, digital.subsystem.usb.engine.out.memory |
| R131 | digital.subsystem.usb.engine.outRelease.reset_n | oscIn | 2 | digital.subsystem.usb.engine.outRelease |
| R132 | digital.subsystem.usb.engine.release_0.reset_n | oscIn | 2 | digital.subsystem.usb.engine.release_0 |
| R133 | digital.subsystem.usb.engine.sie.rstn | oscIn | 156 | digital.subsystem.usb.engine.sie, digital.subsystem.usb.engine.sie.u_phy_tx |
| R134 | digital.subsystem.usb.engine.sie.rstn_i | oscIn | 372 | digital.subsystem.usb.engine, digital.subsystem.usb.engine.cadence, digital.subsystem.usb.engine.control, digital.subsystem.usb.engine.sie.u_phy_rx |
| R135 | digital.subsystem.usb.events.commonReset_n | oscIn, status_mainLevel | 4 | digital.subsystem.usb.events.rd, digital.subsystem.usb.events.wr |
| R136 | digital.subsystem.usb.events.rd.second | status_mainLevel | 17 | digital.subsystem.usb.events.reader, digital.subsystem.usb.events.reader.sync |
| R137 | digital.subsystem.usb.events.wr.second | oscIn | 10 | digital.subsystem.usb.events.writer, digital.subsystem.usb.events.writer.sync |
| R138 | digital.subsystem.usb.resume.reset_n | oscIn | 43 | digital.subsystem.usb, digital.subsystem.usb.ackUsb_s, digital.subsystem.usb.enabledUsb_s, digital.subsystem.usb.resume, digital.subsystem.usb.resume.pins |
| R139 | digital.subsystem.usb.rx.commonReset_n | oscIn, status_mainLevel | 4 | digital.subsystem.usb.rx.rd, digital.subsystem.usb.rx.wr |
| R140 | digital.subsystem.usb.rx.rd.second | status_mainLevel | 17 | digital.subsystem.usb.rx.reader, digital.subsystem.usb.rx.reader.sync |
| R141 | digital.subsystem.usb.rx.wr.second | oscIn | 10 | digital.subsystem.usb.rx.writer, digital.subsystem.usb.rx.writer.sync |
| R142 | digital.subsystem.usb.snapshot.commonReset_n | oscIn, status_mainLevel | 4 | digital.subsystem.usb.snapshot.rd, digital.subsystem.usb.snapshot.wr |
| R143 | digital.subsystem.usb.snapshot.readUp | status_mainLevel | 41 | digital.subsystem.usb.snapshot.reader, digital.subsystem.usb.snapshot.reader.sync |
| R144 | digital.subsystem.usb.snapshot.writeUp | oscIn | 10 | digital.subsystem.usb.snapshot.writer, digital.subsystem.usb.snapshot.writer.sync |
| R145 | digital.subsystem.usb.tx.commonReset_n | oscIn, status_mainLevel | 4 | digital.subsystem.usb.tx.rd, digital.subsystem.usb.tx.wr |
| R146 | digital.subsystem.usb.tx.rd.second | oscIn | 17 | digital.subsystem.usb.tx.reader, digital.subsystem.usb.tx.reader.sync |
| R147 | digital.subsystem.usb.tx.wr.second | status_mainLevel | 10 | digital.subsystem.usb.tx.writer, digital.subsystem.usb.tx.writer.sync |
| R148 | digital.subsystem.usbAppUp_r.reset_n | status_mainLevel | 2 | digital.subsystem.usbAppUp_r |
| R149 | externalReset_n | causes.clk | 2 | causes.pin |
| R150 | status_aonReleased | causes.clk | 3 | clocks, clocks.stable_s |

## Source-cone leaves by reset-control ID

Traversal stops at sequential state, macro outputs or primary inputs. It does
not assume Boolean equivalence or infer an allowed reset source from a name.

| ID | Source-cone leaves (relative to DeadhorseSoc) |
| --- | --- |
| R001 | clocks.commands.writeUp, clocks.completions.readUp |
| R002 | digital.core.rst_ni, digital.memory.serviceReset_n |
| R003 | digital.subsystem.af.reset_n |
| R004 | digital.subsystem.debugger.dm.rst_ni, digital.subsystem.debugger.transport.req.readUp, digital.subsystem.debugger.transport.resp.writeUp, externalReset_n, porBypass, supplyReset |
| R005 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.af.reset_n, digital.subsystem.oscillator.epochReset_n, threshold[1] |
| R006 | digital.subsystem.p.reset_n, digital.subsystem.pwmUp_r.second |
| R007 | digital.subsystem.p.reset_n, digital.subsystem.pwmUp_r.second |
| R008 | digital.subsystem.p.reset_n, digital.subsystem.pwmUp_r.second |
| R009 | digital.subsystem.p.reset_n, digital.subsystem.pwmUp_r.second |
| R010 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.p.reset_n, externalReset_n, porBypass, supplyReset, threshold[1] |
| R011 | causes.cold.second |
| R012 | externalReset_n, porBypass, supplyReset |
| R013 | externalReset_n, porBypass, supplyReset |
| R014 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, oscEn, threshold[1] |
| R015 | clocks.commands.readUp |
| R016 | clocks.commands.writeUp |
| R017 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, oscEn, threshold[1] |
| R018 | clocks.completions.readUp |
| R019 | clocks.completions.writeUp |
| R020 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, oscEn, threshold[1] |
| R021 | clocks.configuration.rd.second |
| R022 | clocks.configuration.writeUp |
| R023 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, oscEn, threshold[1] |
| R024 | clocks.counter.request.reset_n |
| R025 | clocks.commands.readUp, clocks.completions.writeUp, clocks.gateReset.second |
| R026 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, oscEn, threshold[1] |
| R027 | digital.bootReleased |
| R028 | digital.core.rst_ni |
| R029 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_0.channel.hold[0], digital.subsystem.channels_0.channel.hold[1], digital.subsystem.channels_0.channel.hold[2], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R030 | digital.memory.serviceReset_n |
| R031 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R032 | digital.subsystem.af.reset_n |
| R033 | digital.subsystem.af.reset_n, digital.subsystem.aonGpio.c.enable, digital.subsystem.aonGpio.c.falling, digital.subsystem.aonGpio.c.ready, pins_inactive_gpioIn[0] |
| R034 | digital.subsystem.af.reset_n, digital.subsystem.aonGpio.c_1.enable, digital.subsystem.aonGpio.c_1.falling, digital.subsystem.aonGpio.c_1.ready, pins_inactive_gpioIn[1] |
| R035 | digital.subsystem.af.reset_n, digital.subsystem.aonGpio.c_2.enable, digital.subsystem.aonGpio.c_2.falling, digital.subsystem.aonGpio.c_2.ready, pins_inactive_gpioIn[2] |
| R036 | digital.subsystem.af.reset_n, digital.subsystem.aonGpio.c_3.enable, digital.subsystem.aonGpio.c_3.falling, digital.subsystem.aonGpio.c_3.ready, pins_aonExtraIn[0] |
| R037 | digital.subsystem.af.reset_n, digital.subsystem.aonGpio.c_4.enable, digital.subsystem.aonGpio.c_4.falling, digital.subsystem.aonGpio.c_4.ready, pins_aonExtraIn[1] |
| R038 | digital.subsystem.af.reset_n, digital.subsystem.aonGpio.c_5.enable, digital.subsystem.aonGpio.c_5.falling, digital.subsystem.aonGpio.c_5.ready, pins_aonExtraIn[2] |
| R039 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R040 | digital.subsystem.bist.a.reset_n |
| R041 | externalReset_n, porBypass, supplyReset |
| R042 | digital.subsystem.bist.fifo.readUp |
| R043 | digital.subsystem.bist.fifo.wr.second |
| R044 | digital.subsystem.bist.m.reset_n |
| R045 | digital.subsystem.af.reset_n |
| R046 | digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset |
| R047 | digital.subsystem.af.reset_n, digital.subsystem.coldUp_r.second |
| R048 | digital.subsystem.af.reset_n, digital.subsystem.coldUp_r.second |
| R049 | digital.subsystem.coldUp_r.second |
| R050 | digital.subsystem.debugActiveAon_q.reset_n |
| R051 | digital.subsystem.debugMainUp_r.second |
| R052 | digital.subsystem.debugWake_q.reset_n |
| R053 | digital.subsystem.debugger.dm.rst_ni, digital.subsystem.debugger.transport.req.readUp, digital.subsystem.debugger.transport.resp.writeUp |
| R054 | digital.subsystem.debugger.dm.rst_ni |
| R055 | digital.subsystem.debugger.tap.rst_ni |
| R056 | digital.subsystem.debugger.transport.epoch, externalReset_n, porBypass, supplyReset |
| R057 | digital.subsystem.debugger.transport.epoch, externalReset_n, porBypass, supplyReset |
| R058 | digital.subsystem.debugger.transport.req.readUp |
| R059 | digital.subsystem.debugger.transport.req.wr.second |
| R060 | digital.subsystem.debugger.transport.epoch, externalReset_n, porBypass, supplyReset |
| R061 | digital.subsystem.debugger.transport.resp.rd.second |
| R062 | digital.subsystem.debugger.transport.resp.writeUp |
| R063 | digital.subsystem.debugger.transport.tckRelease.second |
| R064 | externalReset_n, porBypass, supplyReset |
| R065 | digital.subsystem.debugger_ndmAck_q.reset_n |
| R066 | digital.subsystem.fromMain_s.reset_n |
| R067 | digital.subsystem.gpio.w.ar.second |
| R068 | digital.subsystem.af.reset_n, digital.subsystem.p.reset_n |
| R069 | digital.subsystem.af.reset_n, digital.subsystem.p.reset_n |
| R070 | digital.subsystem.gpio.w.f.readUp |
| R071 | digital.subsystem.gpio.w.f.writeUp |
| R072 | digital.subsystem.gpio.w.mr.second |
| R073 | digital.subsystem.haltLite_q.reset_n |
| R074 | digital.subsystem.leaf.ackSync.reset_n |
| R075 | digital.subsystem.leaf.consumer.reset_n |
| R076 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.leaf.producer.abort, externalReset_n, porBypass, supplyReset, threshold[1] |
| R077 | digital.subsystem.leaf.requests.rd.second |
| R078 | digital.subsystem.leaf.requests.wr.second |
| R079 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.leaf.producer.abort, externalReset_n, porBypass, supplyReset, threshold[1] |
| R080 | digital.subsystem.leaf.responses.rd.second |
| R081 | digital.subsystem.leaf.responses.wr.second |
| R082 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.leaf.producer.abort, externalReset_n, porBypass, supplyReset, threshold[1] |
| R083 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R084 | digital.subsystem.leafPermit.ar.second |
| R085 | digital.subsystem.leafPermit.mr.second |
| R086 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.liteBootDraining, digital.subsystem.liteBootReleased, digital.subsystem.resetting, externalReset_n, porBypass, supplyReset, threshold[1] |
| R087 | digital.subsystem.liteEntryAck_q.reset_n |
| R088 | digital.subsystem.liteHart.reset_n |
| R089 | digital.subsystem.mailbox.a.reset_n |
| R090 | digital.subsystem.mailbox.a.rxUp |
| R091 | digital.subsystem.mailbox.a.txUp |
| R092 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R093 | digital.subsystem.mailbox.m.reset_n |
| R094 | digital.subsystem.mailbox.m.rxUp |
| R095 | digital.subsystem.mailbox.m.txUp |
| R096 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R097 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R098 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.af.reset_n, digital.subsystem.oscillator.configReady, digital.subsystem.oscillator.epochReset_n, digital.subsystem.oscillator.forceRun, threshold[1] |
| R099 | digital.subsystem.oscillator.epochReset_n, digital.subsystem.oscillator.forceRun |
| R100 | digital.subsystem.oscillator.epochReset_n |
| R101 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.af.reset_n, threshold[1] |
| R102 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, externalReset_n, porBypass, supplyReset, threshold[1] |
| R103 | digital.subsystem.p.reset_n |
| R104 | digital.subsystem.perfEpoch_r.second |
| R105 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R106 | digital.subsystem.permits.ar.second |
| R107 | digital.subsystem.permits.mr.second |
| R108 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_0.channel.hold[0], digital.subsystem.channels_0.channel.hold[1], digital.subsystem.channels_0.channel.hold[2], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R109 | digital.subsystem.p.reset_n, digital.subsystem.pwmUp_r.second |
| R110 | digital.subsystem.toAon.ackSync.reset_n |
| R111 | digital.subsystem.toAon.consumer.reset_n |
| R112 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.toAon.producer.abort, externalReset_n, porBypass, supplyReset, threshold[1] |
| R113 | digital.subsystem.toAon.requests.rd.second |
| R114 | digital.subsystem.toAon.requests.wr.second |
| R115 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.toAon.producer.abort, externalReset_n, porBypass, supplyReset, threshold[1] |
| R116 | digital.subsystem.toAon.responses.rd.second |
| R117 | digital.subsystem.toAon.responses.wr.second |
| R118 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, digital.subsystem.toAon.producer.abort, externalReset_n, porBypass, supplyReset, threshold[1] |
| R119 | digital.subsystem.af.reset_n, digital.subsystem.p.reset_n |
| R120 | digital.subsystem.uartSleep.fifo.readUp |
| R121 | digital.subsystem.uartSleep.fifo.writeUp |
| R122 | digital.subsystem.uartWake_monitor.release_0.second |
| R123 | digital.subsystem.uartWake_monitor_1.release_0.second |
| R124 | digital.subsystem.uartWake_monitor_2.release_0.second |
| R125 | digital.subsystem.usb.aonUp_r.second |
| R126 | digital.subsystem.usb.appUp_r.second |
| R127 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R128 | digital.subsystem.usb.engine.in.reset_n |
| R129 | digital.subsystem.usb.engine.configured, digital.subsystem.usb.engine.control.flush, digital.subsystem.usb.engine.control.inToggle[1], digital.subsystem.usb.engine.sie.bus_reset, digital.subsystem.usb.engine.sie.rstn_i |
| R130 | digital.subsystem.usb.engine.out.reset_n |
| R131 | digital.subsystem.usb.engine.configured, digital.subsystem.usb.engine.control.flush, digital.subsystem.usb.engine.control.outToggle[1], digital.subsystem.usb.engine.sie.bus_reset, digital.subsystem.usb.engine.sie.rstn_i |
| R132 | digital.subsystem.usb.enabledUsb, digital.subsystem.usb.resume.reset_n, pins_usbVbus |
| R133 | digital.subsystem.usb.engine.sie.bus_reset, digital.subsystem.usb.engine.sie.rstn_i |
| R134 | digital.subsystem.usb.engine.sie.rstn_i |
| R135 | digital.subsystem.usb.appUp_r.second, digital.subsystem.usb.resume.reset_n |
| R136 | digital.subsystem.usb.events.rd.second |
| R137 | digital.subsystem.usb.events.wr.second |
| R138 | digital.subsystem.usb.resume.reset_n |
| R139 | digital.subsystem.usb.appUp_r.second, digital.subsystem.usb.engine.rxReset, digital.subsystem.usb.resume.reset_n |
| R140 | digital.subsystem.usb.rx.rd.second |
| R141 | digital.subsystem.usb.rx.wr.second |
| R142 | digital.subsystem.usb.appUp_r.second, digital.subsystem.usb.engine.sessionReset, digital.subsystem.usb.resume.reset_n |
| R143 | digital.subsystem.usb.snapshot.readUp |
| R144 | digital.subsystem.usb.snapshot.writeUp |
| R145 | digital.subsystem.usb.appUp_r.second, digital.subsystem.usb.engine.txReset, digital.subsystem.usb.resume.reset_n |
| R146 | digital.subsystem.usb.tx.rd.second |
| R147 | digital.subsystem.usb.tx.wr.second |
| R148 | clocks.bootDone, clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, digital.subsystem.bist.state[0], digital.subsystem.bist.state[1], digital.subsystem.channels_1.channel.hold[0], digital.subsystem.channels_1.channel.hold[1], digital.subsystem.channels_1.channel.hold[2], digital.subsystem.debugger.ndmReset, externalReset_n, porBypass, supplyReset, threshold[1] |
| R149 | externalReset_n |
| R150 | clocks.bootstrap.edges[0], clocks.bootstrap.edges[1], clocks.bootstrap.edges[2], clocks.bootstrap.edges[3], clocks.bootstrap.frozen, clocks.bootstrap.released.second, digital.bootReleased, threshold[1] |

Hierarchy SHA-256: `cc5d733b8b93a7552020328ba3410393f12f82ac363fa08d6107a0ae11a61597`.
