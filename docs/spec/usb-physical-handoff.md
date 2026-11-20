# T19 USB physical timing handoff

This historical handoff is superseded by the
[2026-11-20 routed validation](usb-physical-validation.md): placement, CTS,
routing and extracted-wire measurements now exist, with three over-limit
classes and unresolved boundary/signoff qualification. The data below records
the earlier pre-layout handoff; it is not physical signoff. Standalone digital
acceptance also remains blocked by packet composition and prior proof qualification.

## Bound snapshot and reproduction

Historical measurement: `build/t19/boundary-frozen-fast-01/fast/usb`, based on
`33cf2510e99a6a16348bd664ffb79867ae6f7507` plus the recorded dirty snapshot.
Its `result.json` records the exact `tools/timing/check.py` command for each
block; `timing/{engine,usb}/commands.jsonl` records the synthesis/STA commands.
Numbers below are **historically measured** by those commands, not remeasured
by this handoff.

On `8084eb2` plus the evidence-tooling changes, the read-only command
`python tools/env/run.py run -- python3 scratch/t19_physical_handoff.py`
verified **50 source hashes** (measured inventory) for USB production RTL,
shared library, stubs, vendor inputs and timing/build tooling against that
snapshot. It also verified both emitted-source and timing-flow inventories.
`build/t19/nonproof-physical-handoff-01/result.json` records these bindings,
current tool availability, and hashes of the following existing artifacts:

| Artifact under each `timing/{engine,usb}` directory | Use |
| --- | --- |
| `mapped.v`, `mapped.json` | Mapped design and endpoint/net identity lookup |
| `boundary.sdc` | Applied estimated pad/reset boundary contract |
| `protocol.tcl` | Certificate-generated timing classes and exceptions |
| `timing.tcl`, `commands.jsonl`, `sta.log` | Exact pre-layout STA setup and execution |
| `paths.tsv`, `short_reset_checks.tsv`, `output_checks.tsv` | Class paths, hold/removal, and both output polarities |
| `result.json` | Full classes, budgets, warnings, reset sinks and open qualifications |

Generated artifacts remain under `build/`; none is committed. Preserve the
parent snapshot and handoff manifest together. A consumer must verify their
hashes against the files before using them. Re-emission/remapping invalidates
the numeric endpoint names below and requires fresh certificate binding.
`boundary.sdc` was captured before the protocol multicycle exceptions: never
use it alone. Replay the complete `timing.tcl` setup, including `protocol.tcl`.
Historical wrapper screening used an **estimated** USB period of
`1000/48 = 20.833333 ns` and conservative **assumed** app/AON periods of 41.6 ns,
with asynchronous clock groups. Those groups do not qualify CDC or peer reset
release; the production clock relationships still need integration validation.

## Remaining physical work

| Item | Historical measured result | Required closure evidence |
| --- | --- | --- |
| Engine FF setup | 14.726458 ns, `_6206_/Q` → `_6197_/D` | D59 warning; recheck with placed/routed wires and clock tree |
| Wrapper USB FF setup | 13.485458 ns, `_6398_/Q` → `_7356_/D` | D59 warning; same mandatory physical recheck |
| Engine RX hold | −0.102503 ns: `dnRx` → `_6154_/D`, `dpRx` → `_6166_/D` | Fast-corner/min-delay pad, data and clock-tree analysis |
| Wrapper RX hold | −0.102503 ns: `dpRx` → `_6439_/D`, `_6503_/D`; `dnRx` → `_7547_/D`, `_7608_/D` | Same; retain first-sampler/metastability interpretation |
| Engine worst reset removal | +0.559058 ns, `vbus` → `_6355_/RN` | Conditional SS contract result; verify actual upstream reset/pad implementation |
| Wrapper worst reset removal | +0.961138 ns, `vbus` → `_6357_/RN` | Same, including all reset domains |

The setup target remains **estimated** `0.60 × 1000/48 = 12.5 ns` for the
sample-clock single-cycle class, with the user-approved **15 ns** D59 warning
ceiling for eligible paths. Strict FP, reset, multicycle and other limits are
unchanged. There is no setup path above the applicable failure limit in this
historical snapshot, but proof qualification is still unresolved. Area is
**historically measured** at 160227.6480 µm² for the engine and 197379.2128 µm²
for the wrapper; neither figure includes a physical pad ring or routed area.

The wrapper has these **four measured** cross-domain reset sinks without a
qualified reset-domain-crossing argument:

| Source reset/domain | Sink/domain |
| --- | --- |
| `appReset_n` / `appClock` | `_7638_/RN`, `_7700_/RN` / `usbClock` |
| `usbReset_n` / `usbClock` | `_7640_/RN`, `_7654_/RN` / `appClock` |

A release synchronized to the source clock gives no peer-domain phase
guarantee. These sinks need an integration-level RDC/reset-sequencing argument
and physical checks; positive owner-domain removal slack does not close them.
Reset assertion remains asynchronous. No RTL delay is added for pre-CTS hold.

## Boundary assumptions to replace at integration

The existing contract estimates pad plus package/board delay as
`0..1 + 0..1 = 0..2 ns` for `dpRx`, `dnRx`, `vbus`, `dpTx`, `dnTx`, transmit
enable and pull-up enable. RX/VBUS minimum zero preserves asynchronous first
sampler diagnostics; it does not establish a source-synchronous phase.

Reset deassertion arrives from an upstream `dffrnq_1`, with an **estimated**
2.420..3.882108633 ns CLK-to-Q envelope and 2.4 ns transition. Its basis is the
pinned SS/125°C/3 V Liberty table, **assumed** clock slew 0.02..0.5 ns and Q load
0.001..0.05 pF. This is not a fast-corner minimum-delay guarantee.
The repeated historical −0.975158 ns AON removal value is the same zero-delay
boundary artifact seen in the core study; the source-flop contract makes that
row +1.143400 ns conditionally. It does not waive reset checks or peer RDC.

## Physical flow prerequisites and exit evidence

At the time of this historical handoff, the pinned environment exposed OpenSTA; OpenROAD, OpenLane,
Magic and KLayout are not found on PATH (measured with `shutil.which` by the
handoff command).
`phys/gf180-ws-1x1` contains the block timing policy, not a placement/CTS/routing
flow. The following work therefore needs the project physical-flow integration:

1. Pin the implementation toolchain, floorplan, pad cells, RC extraction and
   min/max corner libraries; identify actual clocks and upstream reset flops.
2. Replace the estimated boundary values with characterized pad/package/board
   and source-flop delays. Keep asynchronous assertion and all domain identities.
3. Carry certificate-generated exceptions onto the mapped/placed register
   identities, re-audit coverage and generated/gated clocks, and retain every
   full-rate limit and negative control.
4. Report per-class setup, min-delay hold, recovery/removal, clock-gate and
   electrical checks after placement and after routing with extracted wires.
   Preserve the failing paths and repair physical hold in the physical flow.
5. Attach RDC, pad/ESD/VBUS and clock-tolerance qualification before physical
   signoff. None is supplied by a passing digital simulation.

No physical tool was installed, no RTL was changed, and no CI was run for that
handoff. The later validation adds a separately pinned physical companion.
Whole-chip gateway/clock-controller and pad-ring implementation remain
outside the standalone USB brief.
