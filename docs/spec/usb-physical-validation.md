# T19 standalone routed USB validation, 2026-11-20

**Outcome: failed validation; not physical signoff.** The mandatory routed
recheck was performed on the unchanged integrated USB wrapper. Three reported
path classes exceed the approved limits. Local reset-release structure and
interstage timing are qualified under the stated digital model, but asynchronous
boundary timing and analog/integration RDC qualification remain open. No RTL,
acceptance limit, assertion, clock phase or timing exception was changed.
No CI tier, USB aggregate, simulation or proof solver ran in this follow-up.

## Snapshot, tools and assumptions

All measurements below use base `d8d51aca578b8353a582d05129c01624c915dc6a`
plus the physical-tooling sources bound in `build/t19/physical-04/receipt-final.json`.
The preparer checks the unchanged production/tool source inventory against
`build/t19/boundary-frozen-fast-01/fast/usb`; this is a reuse of the mapped
snapshot, not fresh emission or proof qualification. The pre-layout replay
reproduced every historical class delay exactly. Original mapped cell identities
and all original input/output connections are preserved through physical buffers
and ties; new state cells and clock inversions are rejected.

The companion runtime is pinned in `tools/physical/lock.json`: OpenROAD
`26Q4-2433-gf11b4276ba` in immutable OCI image
`sha256:2d98f423095ad3f96bb0150e649f3461a336c4c8101d5d554298622a99163ea9`.
The original pinned environment supplies Yosys and OpenSTA 3.2.0. Physical
LEF, Liberty and OpenRCX views come from the same hash-verified GF180 release
already selected by the project; no main environment lock change was made.

**Assumed standalone geometry:** square core, 55% initial utilization,
placement density 0.60, 10 µm margin, routing Metal2–Metal5, automatically
placed boundary pins. The upstream chip floorplan, PDN and pad ring are absent.
These are diagnostic floorplan choices, not a production floorplan approval.
Clocks retain the historical **estimated** USB period `1000/48 = 20.833333 ns`
and **assumed** application/AON periods of 41.6 ns, asynchronous groups and
unchanged uncertainty/exception policy.

**Estimated boundary contract retained:** pad plus package/board delay
`0..1 + 0..1 = 0..2 ns`; RX/VBUS minimum zero preserves arbitrary asynchronous
phase diagnostics. Reset release is modeled as upstream `dffrnq_1` CLK-to-Q,
recharacterized at each PVT over the unchanged **assumed** 0.02..0.5 ns clock
slew and 0.001..0.05 pF load envelope. Assertion remains asynchronous. Exact
per-corner values and library hashes are in the receipt. They do not establish
an upstream implementation or peer-domain phase guarantee.

## Routed timing

**Measured** by the commands below: detailed route, three OpenRCX extractions
(min/nom/max), and five PVT libraries (SS at 125/−40 °C, 3 V; FF at 125/−40 °C,
3.6 V; TT at 25 °C, 3.3 V), forming fifteen STA cases. Clock trees are propagated.
The following are worst **observed** class delays across those cases, all at
SS/125 °C/3 V with max RC. Delay retains CLK-to-Q and data-wire/logic delay,
subtracting actual launch CLK arrival rather than external source latency.
Endpoint enumeration chooses worst absolute arrival before that subtraction;
these are not exhaustive maxima of data-delay ordering. Passing rows therefore
do not assert signoff. Raw period-based setup slack is checked separately.

| Class | Measured delay (ns) | Target / failure limit (ns) | Start → end | Result |
| --- | ---: | ---: | --- | --- |
| appClock.FF | 12.637247 | 24.96 / 24.96 | `_7470_/Q` → `_6982_/D` | within limit |
| appClock.IR | 9.727015 | 24.96 / 24.96 | `bus_bits_addr[13]` → `_6965_/D` | within limit |
| appClock.RO | 4.833343 | 24.96 / 24.96 | `_6965_/Q` → `bus_rdata[1]` | within limit |
| appClock.IO | 7.750520 | 24.96 / 24.96 | `vbus` → `pullupEnable` | within limit |
| usbClock.CP | 15.892605 | 37.5 / 37.5 | `_7057_/Q` → `_7709_/D` | within limit |
| usbClock.FP | **13.691668** | **12.5 / 12.5** | `_7583_/Q` → `_7709_/D` | **fails** |
| usbClock.CF | 14.200759 | 12.5 / 15 | `_7513_/Q` → `_7273_/D` | warning |
| usbClock.FC | **16.003422** | **12.5 / 15** | `_6520_/Q` → `_7435_/D` | **fails** |
| usbClock.FF | **15.516943** | **12.5 / 15** | `_6398_/Q` → `_7362_/D` | **fails** |
| usbClock.IR | 11.230111 | 12.5 / 15 | `vbus` → `_7273_/D` | within limit |
| usbClock.RO | 11.972084 | 12.5 / 15 | `_7700_/Q` → `pullupEnable` | within limit |
| usbClock.IO | 7.750520 | 12.5 / 15 | `vbus` → `pullupEnable` | within limit |
| aonClock.FF | 2.615033 | 24.96 / 24.96 | `_7236_/Q` → `_7237_/D` | within limit |
| aonClock.RO | 4.028082 | 24.96 / 24.96 | `_7237_/Q` → `usbClockRequest` | within limit |
| aonClock.IO | 7.750520 | 24.96 / 24.96 | `vbus` → `pullupEnable` | within limit |
| usbClock.CC | 24.910442 | 50 / 50 | `_7045_/Q` → `_6878_/D` | within limit |
| usbClock.CC_reset | 14.548691 | 12.5 / 15 | `_7583_/Q` → `_7181_/D` | warning |

Limits are the unchanged approved values from the bound baseline. Unpopulated
classes remain unpopulated; there are no clock-gate cells in this snapshot.
IO rows repeated across clock query groups do not assert domain ownership.
The failing identities map to:

- FP: `_engine_configured` → `engine.control.inReady`.
- FC: `engine._control_inValid` → `engine.sie.u_phy_tx.data_q[3]`.
- FF: `engine.sie.u_phy_rx.nrzi_q[3]` → `engine.sie.u_phy_rx.shift_register_q[1]`.

The **measured** worst full-period setup slack is **+3.296796 ns**,
`_7700_/Q` → `pullupEnable`, at SS/max RC. This does not override the stricter
project class budgets. Contracted output checks and electrical slew/capacitance
checks report no violations in the measured cases. Clock minimum-pulse checks
report no violations; arbitrary reset pulse waveforms are not qualified.

## Hold and reset-domain crossing

All **measured** negative hold/removal rows across the fifteen cases start at
top-level inputs; none starts at an internal register Q. This is a result for
the reported checks and asynchronous clock-group model, not blanket CDC/RDC
closure. Worst input hold is **−3.828268 ns**, `dnRx` → `_7547_/D`; worst reset
removal is **−2.508364 ns**, `vbus` → `_6357_/RN`, both SS/max RC. At FF/−40 °C
with min RC the corresponding worst values are **−1.105727 ns** and
**−0.774790 ns**. Application bus input holds also remain negative under the
inherited zero-arrival application contract. No positive minimum delay or false
path was invented to suppress these diagnostics; no hold-fix RTL was added.

The raw application/USB reset combination asynchronously drives RN on two
local release flops per destination. AON has its own pair. The first D is tied
high; first Q drives only second D, never another consumer or external output.
Boolean cone evaluation verifies asynchronous assertion from the intended
raw inputs, including after physical clock/tie insertion. This structurally
qualifies the four historical peer-reset sinks as destination release-chain
stages, not unsynchronized functional-state resets.

**Measured** directed reset-chain slacks, worst across all cases:

| Domain / first → second | Interstage setup (ns) | Interstage hold (ns) | Downstream recovery (ns) | Downstream removal (ns) |
| --- | ---: | ---: | ---: | ---: |
| AON / `_7632_` → `_7699_` | +37.954819 | +0.478416 | +38.770657 | +0.627729 |
| USB / `_7638_` → `_7700_` | +17.216627 | +0.474508 | +11.728995 | +1.361288 |
| app / `_7640_` → `_7654_` | +38.035152 | +0.461312 | +31.674341 | +1.471521 |

Full clock-expanded reports retain the interstage skew and available digital
setup margin; this is not an MTBF calculation or a metastability-resolution
guarantee. Actual reset minimum pulse width, glitch freedom, monotonic release,
clock availability and analog metastability parameters require upstream
qualification. The **measured library scalar** RN minimum low width ranges
from 0.294 ns (FF/−40 °C) to 1.017 ns (SS/125 °C); transition-dependent tables
and actual pulse propagation remain required, so that scalar is not a proposed
system reset specification. The core's historical −0.975158 ns zero-delay
artifact is not reused as a routed result or a waiver.

## Physical scope and area

**Measured** connectivity inventory: 5,515 original cells retained, 326 added
physical buffers/inverters/ties, 5,841 total. CTS reports three roots, 165 clock
buffers and 1,311 sinks. **Measured** routed Liberty cell-area sum is
217149.1840 µm², versus historical mapped 197379.2128 µm²; the **derived**
increase is `217149.1840 − 197379.2128 = 19769.9712 µm²`. This excludes PDN,
pad ring, fillers and die/core whitespace and is not a silicon-area signoff.

No connected signal is missing parasitic annotation: the measured unannotated
drivers are sinkless ports/cells or omitted dummy CTS outputs; partial annotation
count is zero. The router's DRC report is empty. Neither fact establishes
foundry DRC/LVS: unsupported `LEF58_ENCLOSURE` without `CUTCLASS` warnings for
Via1–Via4 remain, and there is no PDN, pad ring or foundry signoff run.

## Commands and evidence

Commands actually run in this session, with artifacts under `build/`:

```text
python tools/env/run.py --network bridge run -- python3 tools/physical/fetch.py
  VERIFIED common.tar.zst; VERIFIED gf180mcu_fd_sc_mcu7t5v0.tar.zst
python tools/physical/run.py openroad -version
  26Q4-2433-gf11b4276ba
python tools/env/run.py run -- python3 tools/physical/usb_prepare.py --snapshot build/t19/boundary-frozen-fast-01/fast/usb --output build/t19/physical-04
  PREPARED /work/build/t19/physical-04
python tools/physical/run.py openroad -exit build/t19/physical-04/run.tcl
  USB_DETAIL_ROUTE_COMPLETE
python tools/env/run.py run -- python3 tools/physical/usb_extract.py --physical build/t19/physical-04 --snapshot build/t19/boundary-frozen-fast-01/fast/usb
  PREPARED three RC and five PVT corners
python tools/physical/run.py openroad -exit build/t19/physical-04/extract-min/run.tcl
python tools/physical/run.py openroad -exit build/t19/physical-04/extract-nom/run.tcl
python tools/physical/run.py openroad -exit build/t19/physical-04/extract-max/run.tcl
  USB_EXTRACTION_COMPLETE (each)
python tools/env/run.py run -- sta -no_init -exit build/t19/physical-04/timing/ss_125C_3v00-max/run.tcl
python tools/env/run.py run -- sta -no_init -exit build/t19/physical-04/timing/ff_n40C_3v60-min/run.tcl
  USB_PHYSICAL_TIMING_COMPLETE (each)
python tools/env/run.py run -- python3 scratch/t19_physical_corners.py
  MEASURED tt_025C_3v30-nom (last remaining case; all fifteen complete)
python tools/env/run.py run -- python3 tools/physical/usb_validate.py --physical build/t19/physical-04 --snapshot build/t19/boundary-frozen-fast-01/fast/usb --output build/t19/physical-04/validation-05
  RECORDED failed-validation; no signoff or CI claim
python tools/env/run.py run -- python3 tools/physical/usb_sdc_audit.py --physical build/t19/physical-04 --validation build/t19/physical-04/validation-05 --output build/t19/physical-04/sdc-audit-02
  PASS effective clock, boundary and multicycle constraints across 15 corners
The same usb_sdc_audit.py command with --verify rechecks complete multiline commands without rerunning STA: PASS.
python tools/env/run.py run -- python3 tools/physical/usb_netlist.py --physical build/t19/physical-04 --output build/t19/physical-04/netlist-audit
  PASS routed netlist and graph binding
python tools/env/run.py run -- python3 -m unittest discover -s tools/physical -p test_usb_*.py
  Ran 10 tests; OK
python tools/env/run.py run -- python3 tools/physical/usb_seal.py --physical build/t19/physical-04 --validation build/t19/physical-04/validation-05 --sdc-audit build/t19/physical-04/sdc-audit-02 --netlist-audit build/t19/physical-04/netlist-audit --output build/t19/physical-04/receipt-final.json
  SEALED diagnostic failures and source/artifact hashes; CI not run
python tools/env/run.py run -- python3 tools/physical/usb_seal.py --verify build/t19/physical-04/receipt-final.json
  PASS sealed physical evidence unchanged
```

Per-case scripts/logs preserve exact expanded invocations. The sealed receipt
binds sources, libraries, constraints, netlist/graph, routed database/DEF/SPEFs,
reports and tool identities. `usb_seal.py --verify <receipt>` rechecks hashes.
The receipt is generated evidence, not committed source.

Failed setup attempts are preserved: physical-01 lacked mounted-file write
access; physical-02 needed explicit tie cells; physical-03 retained an empty
synthetic supply net. Physical-04 removes only disconnected synthetic supply
nets after tie insertion. Original logic preservation is independently checked.
Initial class reporting incorrectly included CTS insertion; original reports
remain intact and the validator corrects that explicitly. Initial reset
diagnostics loaded two `-add_delay` contracts; validation-05 removes the old
boundary values before loading the per-corner contract, and effective-SDC audits
check the resulting clocks, boundaries and protocol exceptions. No changed
limit or hidden waiver is involved. Intermediate malformed/incomplete audit
attempts remain preserved and are not acceptance evidence.

Independent reviewers checked graph/reset containment, delay accounting,
constraint retention, parasitic coverage and failure reporting. Focused tests
reject wrong reset assertion/release/clock, leakage, changed logic/parameters,
stale evidence, missing classes, altered constraints and connected annotation
omissions. Full tier and fast CI were **not run**, as instructed.

## Remaining work

The three over-limit paths trigger the existing stop rule: no further RTL or
physical optimization was attempted after this measurement. Timing repair needs
a separately scoped follow-up. Actual pad/board and upstream reset/clock inputs,
physical hold fixes where applicable, reset/CDC analog qualification and the
missing physical signoff stages are still required. Existing packet composition
and prior sampling/exception proofs remain separate open T19 items. No merge.
