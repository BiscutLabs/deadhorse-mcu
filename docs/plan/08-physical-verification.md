# 08 Physical implementation and verification

## T42 fresh production budget

This supersedes the historical T41-plus-T40 estimate below. Measured on main
`f534b34` plus source-hashed D108 changes by the EmitSoc, plan04_map,
plan04_screen, plan04_area and t35_budget commands in the
[T42 report](tasks/reports/T42.md), under `build/t42/timing01`.

| Item | Area mm2 | Provenance |
| --- | ---: | --- |
| Whole mapped digital including ROM and current DMA | 3.5594355776 | Measured SS125 mapping |
| Scan substitution | 0.4026611456 | Estimated from measured flop mix |
| Placed digital | 7.3259886895 | Estimated T35 allowances and assumed0.55 utilization |
| SRAM footprint | 2.8745586760 | Estimated from measured pinned LEF,16 main1024x8 and4 retained512x8 macros |
| Analog/pads/SRAM halo | 1.1500000000 | Unchanged assumptions |
| Total | **11.3505473655** | Estimated sum |
| Headroom against12.92 | **1.5694526345** | Estimated subtraction |

Matched isolated grant mapping measures794.6624um2/9flops before and74.6368um2/
1flop after, a720.0256um2 reduction. That is not an additive whole-map delta;
the fresh production map includes parent optimization. Main worst is measured
67.515236ns against75ns in both AON strap modes. USB retains its approved
13.485458ns warning, and pre-layout hold/reset/RDC checks remain unqualified.
All macro capacities and analog/clock/reset/pad/utilization allowances remain.
Macro-only24KiB option estimates12.5938557895mm2, leaving0.3261442105mm2 before
extra decoder/control;32KiB estimates13.8371642135mm2 and does not fit. No SRAM
growth or physical fit is approved by these estimates.

## Historical T40 DMA delta on the T41 budget

The current estimate uses the T41 ROM-inclusive budget, then adds the
isolated four-channel DMA change; it does not claim a new whole-SoC mapping.
Measured by `python hw/ip/dma/check_timing.py --output build/t40/timing-before`
and `--output build/t40/timing-final01` on `10a142c` plus receipt-hashed T40
sources, using identical GF180 SS125 / main-9MHz conditions. Arithmetic is
reproducible with `python hw/ip/dma/area_delta.py --before
build/t40/timing-before --after build/t40/timing-final01 --budget
build/t41/consolidated-timing04/area-budget.json --output
build/t40/area-final01.json` in the pinned environment.

| Item | Area mm2 | Provenance |
| --- | ---: | --- |
| T41 total, including its controller/reset changes | 11.3344345975 | Estimated T35 budget; historical measured maps authenticated |
| DMA baseline / circular implementation | 0.1604361920 / 0.1638980224 | Measured isolated maps |
| Added DMA standard cells | 0.0034618304 | Measured difference, below D102's 0.010 cap |
| Additional scan substitution | 0.0006322176 | Estimated same-drive replacements for measured flop mix |
| Added placed digital | 0.0074437236 | Estimated `(0.0034618304 + 0.0006322176) / 0.55` |
| Updated total | **11.3418783211** | Estimated T41 total plus delta |
| Headroom against 12.92 | **1.5781216789** | Estimated subtraction |

All SRAM, analog, pad, clock/reset and utilization allowances remain unchanged.
This replaces the T40 cap reservation below rather than adding a second charge.
Placement, routing and actual scan insertion remain unmeasured here.

## PLAN05 production ROM-inclusive estimate

This supersedes the Phase2 estimate below. Measured on main5ba87bf plus
receipt-hashed final PLAN05 sources by `python scratch/plan05_t36_timing03.py`
in the pinned environment. The receipt records fresh EmitSoc, plan04_map with
`--sram --rom-image build/t36/rom/rom.hex`, plan04_screen, plan04_area,
t35_budget and plan05_area_leakage commands under
`hw/top/reference/measurements/`, base `build/plan05/t36-timing03`.

| Item | Area mm2 | Provenance |
| --- | ---: | --- |
| Production mapped standard cells, ROM included | 3.542381069 | Measured SS125 mapping, no wire delays |
| Scan substitution | 0.401930144 | Estimated from measured flops/library replacements |
| Remaining clock/reset/power | 0.020333997 | Estimated unused allowance |
| Scan glue | 0.050000000 | Assumed; ROM placeholder removed because actual ROM is mapped |
| Placed digital at assumed0.55 utilization | 7.299354927 | Estimated sum/utilization |
| Main16KiB and retained2KiB SRAM | 2.874558676 | Estimated from20 measured pinned LEF footprints |
| LF RC/POR/pads/SRAM halo | 1.150000000 | Assumed0.10+0.15+0.50+0.40 |
| Total | **11.323913603** | Estimated planning use, not placement |
| Headroom against12.92 | **1.596086397** | Estimated subtraction |

The exact6776-byte firmware maps separately to measured0.098597408mm2,
6007 cells and32 flops, below its assumed0.50mm2 allowance. This isolated
number is **not additive** to the parent-optimized whole map. All16384 ROM
words are authenticated against the built image. Mapped main worst67.850388ns
passes75ns in both AON source modes; physical hold/removal/pulse diagnostics
remain unqualified before CTS, with no physical signoff claimed.

| Main capacity | Extra macro footprint mm2 | Estimated total mm2 | Estimated headroom mm2 |
| --- | ---: | ---: | ---: |
| 16KiB | 0.000000000 | 11.323913603 | 1.596086397 |
| 24KiB | 1.243308424 | 12.567222027 | 0.352777973 |
| 32KiB | 2.486616848 | 13.810530451 | -0.890530451 |

24KiB fits this macro-only estimate, before additional decoder/control costs;
32KiB does not. D99 approves measurement only: production remains16KiB.
Historical queued T40 reservation: its0.010mm2 mapped cap /0.55 =0.018181818mm2 placed:
estimated current total11.342095421mm2 and headroom1.577904579mm2. Additional
T40 scan was unmeasured/excluded in that reservation; the current delta above includes it.
The older T40/Phase2 reservation below is historical, not a second charge.

## Historical PLAN05 Phase2 mapped estimate


Measured on main `29cab7e5` plus emitted source hashes in
`build/plan05/timing03/map/result.json`; latest Phase2 RTL; phase-end CI remains separate.
Commands in the pinned environment: `python tools/sbt.py 'hw/runMain
deadhorse.top.EmitSoc build/plan05/timing03/emit production 8'`, then
`plan04_map.py --base build/plan05/timing03 --usb-reference
build/t33/pre-fast03/fast/usb/timing/usb --stability-reference
build/plan04/digital-timing06/stability --threshold-control --sram`,
`plan04_area.py --base build/plan05/timing03`,
`t35_budget.py --base build/plan05/timing03` and
`plan05_area_leakage.py --base build/plan05/timing03`, scripts under
`hw/top/reference/measurements/`.

| Item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built standard-cell logic | 3.427122093 | Measured mapped cells, hard SRAM excluded |
| Scan substitution | 0.400487898 | Estimated from measured cells and library substitutes |
| Remaining clock/reset/power | 0.020333997 | Estimated .10 minus built isolated logic and scan |
| ROM / scan glue | 0.550000000 | Assumed .50 + .05, unchanged |
| Digital subtotal at .55 utilization | 7.996261795 | Estimated sum above / assumed .55 |
| Main16KiB + retained2KiB SRAM | 2.874558676 | Estimated16 x measured1024x8 LEF footprint plus4 x measured512x8 footprint |
| LF RC / POR / pads / SRAM halo | 1.150000000 | Assumed .10 + .15 + .50 + .40, unchanged |
| Total | **12.020820471** | Estimated planning use, not placement |
| Headroom against12.92 | **0.899179529** | Estimated subtraction |

Physical retained SRAM is now four512x8 macros, not merely a smaller accessible
window in four1024x8 macros. Both model and vendor512-word tests passed; paired
slow-corner pre-layout timing was measured. Physical SRAM signoff remains open.
The SRAM hard-macro footprint reduction is estimated0.233712384mm2. Mapped
standard-cell reduction from historical T35 is measured0.212477798mm2 by subtracting
its recorded3.639599891 from the current3.427122093; different snapshots/mapper
optimization prevent attributing that entire reduction to any single block.

| Main capacity option | Extra macros | Estimated total mm2 | Estimated headroom mm2 |
| --- | ---: | ---: | ---: |
| 16KiB (unchanged) | 0 | 12.020820471 | 0.899179529 |
| 24KiB | 8 | 13.264128895 | -0.344128895 |
| 32KiB | 16 | 14.507437319 | -1.587437319 |

Alternatives add measured LEF footprint only, before extra decoder/control cost;
neither larger option fits this estimate. D99 makes no memory-growth decision.
All original physical/analog/ROM allowances remain. T40's separate plan branch
reserves up to estimated0.018181818mm2 placed area and must rebase this budget
after PLAN05; it is not implemented or included above. Estimated physical-pad
inventory remains40 output-capable/12 input-only; T38 qualifies placement/electrics.

Deadhorse is entirely clocked (decision D17), so it uses a standard
synchronous flow: synthesis, clock-tree synthesis, static timing analysis,
scan insertion. Nothing in this document needs custom asynchronous tooling.

## Process and slot

| Item | Value | Source |
| --- | --- | --- |
| Process | GF180MCU, 3.3 V devices and I/O | Official wafer.space template; T43 pins and qualifies the selected views |
| Cells | D15 selects `gf180mcu_fd_sc_mcu7t5v0` at nominal 3.3 V; shuttle qualification remains open | Pinned project library; T43 compares the template PDK |
| SRAM | `gf180mcu_ocd_ip_sram` 1024x8 and 512x8; current measured LEF footprints and counts above | `hw/vendor/gf180_sram/gf180_sram.lock.json`; T43 compares new-PDK hashes before switching |
| Slot | wafer.space 1x1 target: die 3.932 by 5.122 mm, core 12.92 mm2 | D105; verify exact pinned upstream slot in T43 |
| Pad ring | 40 bidirectional, 12 input-only, 2 analog, dedicated clock/reset pads | D105 target; T43 verifies slot/map, T38 qualifies placement/electrics |

D105 replaces D9: use only the official wafer.space project template with
its pinned PDK and LibreLane dependencies. T43 imports the selected licensed
collateral and records reviewed patches; no Coldfoot physical material is
authorized. Existing measurements keep their original PDK provenance until
matched old/new measurements qualify migration. Full P&R remains T38.

### Cell library (decision D15)

Checked in the pinned PDK release: `gf180mcu_fd_sc_mcu7t5v0` has integrated
clock-gating cells (`icgtp`, `icgtn`) and scan flip-flops (`sdffq`,
`sdffrnq`). `gf180mcu_as_sc_mcu7t3v3` has about 40 cell types and neither. A
clocked design that relies on clock gating for its power modes and on scan
for production test needs both, so the approved choice is
`gf180mcu_fd_sc_mcu7t5v0`, subject to the shuttle accepting it at 3.3 V.

## T35 mapped SRAM/BIST estimate and remaining allowances

This supersedes the historical estimates below for T35's frozen working sources
on `ad3bb201` (exact hashes in `build/t35/timing03/`). Commands in the pinned
environment: `plan04_map.py --base build/t35/timing03 --usb-reference
build/t33/pre-fast03/fast/usb/timing/usb --stability-reference
build/plan04/digital-timing06/stability --threshold-control --sram`, then
`plan04_area.py --base build/t35/timing03` and
`t35_budget.py --base build/t35/timing03`, all under
`hw/top/reference/measurements/`.

| Item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built production digital logic including SRAM control/BIST/custom DMI | 3.639599891 | Measured mapped standard cells; actual 20 SRAM instances excluded from this cell sum |
| Scan-cell substitution | 0.432592698 | Estimated from measured cell inventory and same-drive scan replacement areas; T37 still qualifies insertion |
| Remaining clock/reset/power allowance | 0.020647910 | Estimated: .10 minus measured isolated controller logic .068426579 and its estimated scan .010925510 |
| ROM and scan glue | 0.550000000 | Assumed .50 + .05; former .05 BIST placeholder replaced by built logic, not counted again |
| Digital subtotal at .55 utilization | 8.441528180 | Estimated sum of digital rows / assumed .55 |
| Performance and retained SRAM | 3.108271060 | Estimated: 20 x measured pinned LEF 301.3 x 515.81 um2 / 1e6 |
| LF RC, POR/brownout, pad keepout, SRAM halo/glue | 1.150000000 | Assumed .10 + .15 + .50 + .40, unchanged |
| Total | **12.699799240** | Estimated planning use, not placed fit |
| Headroom against 12.92 | **0.220200760** | Estimated subtraction |

### T40 circular UART RX reservation (D102)

The historical T35 table above retains its original scope. The current
reservation uses the measured/estimated PLAN05 Phase2 budget below
(`build/plan05/timing03/area-budget.json`); it credits no unaccepted Phase3 ROM
savings. Reserve T40's user-approved maximum increment:

| Additional item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Circular RX across all four DMA channels | 0.010000000 | Assumed reservation at the approved mapped standard-cell cap; not measured |
| Placement allowance for that increment | 0.018181818 | Estimated 0.010 / existing assumed 0.55 utilization; replaces, not adds to, the cell row in the placed total |
| PLAN05 Phase2 plus T40 placement reservation | 12.039002289 | Estimated 12.020820471 + 0.018181818 |
| Provisional headroom against 12.92 | 0.880997711 | Estimated 12.92 - 12.039002289 |

This subtotal excludes any additional scan substitution arising from T40;
that delta is unmeasured and must be charged before claiming final fit. Keep
the existing scan/glue, clock/reset, ROM, SRAM, analog, pad and halo rows.
T40 must replace the reservation with matching before/after measurements
against the post-PLAN05 design, account for scan and routing overhead, and
recompute headroom. No new placed-fit claim or main SRAM growth is approved.
See [T40](tasks/T40-dma-circular-uart-rx.md).

The actual mapping includes 140 measured non-inverting SRAM-load buffers;
pin-by-pin connection equivalence and a cycle fault control protect that
transformation. Macro pin setup/hold, clock-to-Q, pulse and period checks use
paired SRAM/standard-cell Liberty corners, not vendor behavioral delays.
Retained SRAM stays powered at its normal rail in sleep. The pinned vendor
specifies CEN-high standby state retention; no reduced-voltage or power-off
retention is introduced. Physical rail margins, clock trees and placement are
still signoff obligations. See [T35](tasks/reports/T35.md) and the
[physical handoff](../../phys/gf180-ws-1x1/sram.md).

## PLAN04 historical mapped estimate and remaining allowances

D78/D79 remove the internal HF macro. Replace the former assumed 0.50 mm2
analog allowance with assumed 0.10 mm2 LF RC plus 0.15 mm2 POR/brownout.
Fresh production mapping on `2c33976` plus receipt-hashed PLAN04 sources gives
the following estimate. Commands (pinned environment):
`python hw/top/reference/measurements/plan04_map.py --base build/plan04/production-timing12 --usb-reference build/t32/timing-fast01/fast/usb/timing/usb --stability-reference build/plan04/digital-timing06/stability`,
then `plan04_area.py --base build/plan04/production-timing12` and
`plan04_budget.py --base build/plan04/production-timing12` in the same directory.
The method and double-counting boundary were independently reviewed; final
review of this refreshed snapshot remains part of PLAN04 acceptance.

| Item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built production digital logic | 3.539272666 | Measured, mapped pre-layout, no wires; includes PLAN04 and debug |
| Scan-cell substitution | 0.419276614 | Estimated from measured 21,221 flops and library areas; two negative-edge cells require T37 qualification |
| Remaining clock/reset/power allowance | 0.034947443 | Estimated: original .10 minus isolated built logic .056339808 and its scan estimate .008712749 |
| ROM, BIST and scan glue | 0.600000000 | Assumed: .50 + .05 + .05, unchanged |
| Digital subtotal at .55 utilization | 8.351812224 | Estimated sum of digital rows / assumed .55 |
| Performance and retained SRAM | 3.108271060 | Estimated pinned macro footprints, unchanged 16 + 4 macros |
| LF RC, POR/brownout, pad keepout, SRAM halo/glue | 1.150000000 | Assumed: .10 + .15 + .50 + .40 |
| Total | **12.610083284** | Estimated, not physical fit |
| Headroom against 12.92 | **0.309916716** | Estimated: ceiling minus total |

The isolated controller cost reduces the original allowance; it is not added
again to whole-top mapped area. Isolated-to-integrated optimization differences
mean the remaining T33 allowance is an estimate, not an exact area partition.
Clock-tree synthesis, routing and actual macro placement remain unqualified.
Raw pulse-width diagnostics include negative slack from unbuffered clock gates
driving thousands of loads outside characterized slew/load ranges; these are
retained physical-flow issues, not passing clock checks.

Estimated pad demand becomes 39 output-capable and 12 input-only functions
against assumed 40/12 capacities: add OSC_EN and AON_CLK_IN/AON_CLK_SEL/
POR_BYPASS. OSC_IN reuses the dedicated clock pad. Pad placement, ESD, supply
pads and electrical qualification remain T38 work.

## T32 provisional physical-boundary budget: before PLAN04 allowance update

T32's uncommitted production integration on main `9b80375` replaces the assumed
JTAG allowance with measured whole-top logic. The same PLAN03 mapping method
and all other allowances remain unchanged. Following the approved SBA-routing
experiment, the user approved a broader area review. The independently checked
[physical boundary](../spec/soc-physical-boundary.md) excludes verification-only
RVFI observations from measurement while retaining them in every test. Complete
bottom-up reset-buffer layers retain the same cell and fanout bound. These
measurement refinements restore the estimate below the ceiling without a budget
exception. This is not physical fit or final T32 acceptance.
Commands, evidence hashes, qualifications and open checks are in the
[T32 report](tasks/reports/T32.md).

| Item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built functional production logic including debug, 8 MHz mapping trial | 3.480476429 | Measured, `python scratch/t32_area07_run.py` and area07 partition in the pinned environment; observers excluded only from physical measurement |
| Separate JTAG allowance | 0 | Removed to avoid double counting; actual integration is in mapped logic |
| Remaining digital allowances | 0.700000000 | Assumed: controller .10, ROM .50, BIST .05, scan glue .05 |
| Scan-flop uplift on built logic | 0.410504595 | Estimated from mapped flops and library scan areas; two negative-edge flops use an explicitly estimated scan-flop plus clock-inverter implementation, to qualify in T37 |
| Digital subtotal at unchanged 0.55 utilization | 8.347238225 | Estimated sum of digital rows / .55 |
| Performance and retained SRAM | 3.108271060 | Estimated from unchanged pinned macro footprints below |
| Analog, pad/keepout and halo/glue allowances | 1.400000000 | Assumed, unchanged .50 + .50 + .40 |
| Total core use | **12.855509285** | Estimated, `python scratch/t32_area07_budget.py`; area-only ceiling check passes |
| Headroom under unchanged 12.92 ceiling | **0.064490715** | Estimated subtraction; narrow, not placement margin qualification |

This supersedes the fit estimate below for the current T32 working tree, not
the published pre-T32 main baseline. No allowance, utilization or ceiling has
been revised. Independent graph, arithmetic and matched endpoint reviews resolve
the area-only stop. Original T32 validation resumes; final CI, complete timing
and implementation acceptance remain open. Raw reset-removal, USB exception
qualification and unbuffered core-clock pulse diagnostics remain visible.

## PLAN03 baseline measured logic and estimated chip budget

Measured on main `736ed5c`, unchanged production RTL, with the commands and
per-block/domain allocation in [production measurements](../spec/soc-production-measurements.md).
Whole mapped standard-cell logic is **3.322808384 mm2 at the 8 MHz trial** and
**3.3165169408 mm2 at the 9 MHz trial**. This includes real USB and observation
logic, excludes six SRAM/ROM interfaces, and is not a placed-area result.
The main/AON/USB allocation and explicit shared rows reconcile exactly to it.

| Budget item | Area, mm2 | Provenance |
| --- | ---: | --- |
| Built standard-cell logic, larger trial | 3.322808384 | Measured, `python scratch/plan03_area_partition.py`; pinned GF180 SS/125 C/3.0 V |
| Two-hart JTAG debug | 0.150000 | Assumed digital allowance, inclusive of eventual scan overhead; replace in T32 |
| Clock/reset/power controller | 0.100000 | Assumed digital allowance, inclusive of eventual scan overhead; replace in T33 |
| Boot-ROM realization | 0.500000 | Assumed digital allowance; content/implementation dependent, not a guarantee for arbitrary 64 KiB contents; T36/T38 |
| SRAM wrappers and memory BIST | 0.050000 | Assumed digital allowance, inclusive of eventual scan overhead; T35 |
| Scan/test control and insertion glue | 0.050000 | Assumed digital allowance; T37 |
| Scan-flop uplift on built logic | 0.378579802 | Estimated from measured 19,162 mapped FFs and pinned same-drive dff-to-sdff cell areas; T37 must measure actual insertion |
| Digital subtotal at existing 0.55 utilization | 8.275251247 | Estimated: sum of digital rows / 0.55; includes 3.723863061 mm2 whitespace/routing reserve |
| Performance SRAM, 16 KiB | 2.486616848 | Estimated: 16 x 301.300 x 515.810 um2 / 1e6 from pinned 1024x8 LEF |
| Retained SRAM, 3 KiB logical | 0.621654212 | Estimated: four 1024x8 macros, 4 KiB physical; unused 256 words do not enlarge the address map |
| Analog oscillator/POR/supply-monitor macros | 0.500000 | Assumed physical allowance; T34 characterization/layout must replace it |
| Pad interface and in-core keepout | 0.500000 | Assumed core allowance; full external ring is outside this core budget and must fit the die in T38 |
| SRAM halo/channels and other physical glue | 0.400000 | Assumed physical allowance, separate from standard-cell utilization |
| Total core use | **12.783522307** | Estimated, `python scratch/plan03_area_budget02.py` |
| Headroom to 12.92 mm2 | **0.136477693** | Estimated: 12.92 - 12.783522307, approximately 1.06% |

Pinned SRAM LEF SHA-256 is
`35bcf13111ab5029860ca7a2ef473fbf21b4938d6c6244b53b4480bd35f2776a`;
measured dimensions are 301.300 by 515.810 um. Scan uplift is estimated by
substituting each actual mapped dffq/dffrnq/dffsnq with the characterized
same-drive scan variant; no scan RTL or ATPG result is implied. The unbuilt
digital allowances include their eventual scan overhead.

Independent review recomputed the cell inventories, library areas, arithmetic
and headroom. This narrow planning margin is **not physical fit or tape-out
approval**. Macro timing, ROM contents, real analog layouts, pad ring, CTS,
routing and scan/BIST implementation must replace the allowances in T32-T38.
No SRAM macro swap or new peripheral RTL was implemented by PLAN03.

## Historical area budget (not a revised fit result)

The table below predates the PLAN03 budget above; see
[16-soc-integration.md](16-soc-integration.md) for the current inventory.

The following component estimates do not establish whole-chip fit.

| Block | Mapped (mm2) | Basis |
| --- | --- | --- |
| Always-on domain: lite core, power, clock control, timebase, loader | 0.55 to 0.65 | RISCay's clocked design is 0.532 mm2 for its whole MCU (measured by RISCay) |
| Performance core | 0.6 to 1.0 | Assumed two to three times RISCay's CPU; S1 measures it |
| Local bus, flash controller, register blocks | 0.2 to 0.3 | Assumed |
| Serial peripherals, timers, actuator block | 0.3 to 0.5 | Assumed |
| USB (reserved; implemented separately) | 0.2 to 0.3 | Assumed until the implementer supplies a figure |
| SRAM: 16 KiB + 3 KiB | 2.96 | Macro footprints |
| Analog macros: two oscillators, supply monitor | 0.3 to 0.5 | Assumed; RISCay's LF resistor alone is about 0.13 mm2 today |
| --- | --- | --- |

D36 changes access organization, not stored-bit count: sixteen 1024x8 macros
give an estimated 2.487 mm2 performance SRAM footprint; wrapper/routing and
banking overhead still need measurement.

If the Click lite core option is exercised (decision D18), the always-on
domain needs room for the larger version, matched-delay cells characterised
at every corner, and its own timing and test treatment. None of that is in
the budget above; spike S5 measures it.

USB is integrated last. The floorplan reserves its region, pads and clock
route from G1, and the region stays a placement blockage until delivery or the cutoff before Phase 3 floorplan freeze ([07-peripherals-memory-boot.md](07-peripherals-memory-boot.md)).

## Analog and mixed-signal deliverables

None of these has a qualified Deadhorse layout today. D42 selects wafer.space
GF180MCU 1x1, date open; verify actual slot/pad rules, SRAM and library acceptance
and analog process options against the pinned official template/PDK before signoff.

| Macro | Starting point | Work |
| --- | --- | --- |
| LF oscillator, 32 kHz, trimmable | RISCay schematic (7.7 Hz) | Redesign, trim DAC, layout, extraction, mismatch and noise, corner campaign |
| POR/brownout and reset hold | RISCay schematic | Assumed 0.15 mm2 allowance; selectable thresholds with safe hardware default, hysteresis, qualified release, layout/extraction, slow ramps, mismatch and test access; no separate early-warning detector |
| External OSC_IN and AON fallback | Dedicated OSC_IN plus AON_CLK_IN pad | Registered /6 main, reset-held AON selection and shared ICG qualification; no internal HF macro or LF crystal driver |
| USB pad arrangement | Standard 3.3 V bidirectional pads with external series resistors and pull-up | With the USB implementer: validate drive, slew and input thresholds against the full-speed electrical spec |
| Pad ring, ESD, power pads | Official wafer.space template, D105/T43 | Review pad library and mapping in T43; physical qualification in T38 |

LF RC has an assumed 0.10 mm2 allowance. The external oscillator's duty cycle
and cycle-to-cycle jitter enter timing closure, including the generated main
clock. Characterize the actual board part and pad path; no internal HF analog
deliverable remains in this tapeout.

RISCay's LF design requires the GF180 high-resistance poly option. Confirm the
shuttle includes it before investing in the redesign (open question Q5).

## Verification strategy

### One design

There is one RTL source. The same Chisel is simulated, prototyped on FPGA
and taped out. The clockless plan's second, generated design and the checks
that compared the two are gone.

The test environment (tooling, reference models, the four test targets and
the flight simulation) is specified in
[13-test-environment.md](13-test-environment.md).

### Layers

| Layer | What | Source |
| --- | --- | --- |
| Adopted IP | Each actually adopted block keeps its upstream suite, run in our CI | RISCay carryover, selected HardFloat components, serial cores, USB |
| Converted core | Formal equivalence to the pinned Ibex reference per module and whole core, riscv-formal, lockstep against reference and simulator | T10/T11 |
| FPU and F integration | TestFloat vectors, lockstep with F against the simulator, formal properties; outside the equivalence proof | T12/T13/S1 |
| ISA | RISC-V architectural tests; lockstep comparison with an instruction-set simulator for both cores | Standard suites |
| Block | ScalaTest suites per block, each with a negative control | New |
| SoC, directed | Boot, both images, sleep and wake from every source, reset during every committed operation, bridged bus transactions and mailbox, shared-peripheral ownership/DMA and reset containment | RISCay's clocked chip-test bodies extended |
| SoC, firmware | The real flight firmware against a simulated airframe and sensor models | New |
| Clock-domain crossing | Structural CDC check that every signal crossing a domain goes through the crossing block; simulation with randomised clock phase and frequency ratio; reset during crossing traffic | New |
| Clocking | Glitch checks on every gate and on the always-on clock mux; HF stop and restart at every phase | RISCay's oscillator stop-phase tests extended |
| Formal | The first choice for control logic: full proofs for the crossing FIFO, domain bridge, mailbox, register blocks, bus, watchdogs, power and clock controller, boot lock and actuator block; riscv-formal on both cores; equivalence checks on the netlists. See [12-formal-verification.md](12-formal-verification.md) | Chisel properties, SymbiYosys, riscv-formal |
| FPGA | The SoC on an FPGA board, flying a hardware-in-the-loop simulation, then driving real ESCs, servos and sensors on the bench; no external-link requirement | Project FPGA target flow; separate qualification |

### Deadlines

These existing budgets are assumed targets checked at the chosen clock
frequency. LF wake/qualification and USB have their own clock-domain bounds.
Keep control-loop publication separate from each channel's frame boundary.

| Deadline | Budget |
| --- | --- |
| Control iteration completes and publishes its command set; each output applies at its own boundary | Existing target under 800 microseconds at 1 kHz; not an actuator timeout setting |
| IMU frame read | Under 150 microseconds |
| UART receive service before FIFO overflow at 921,600 baud | 16 bytes, about 170 microseconds |
| Interrupt latency, pin to first handler instruction | Under 50 microseconds |
| Wake from oscillator-off sleep | External startup plus AON delay/stability count and CDC/release, milliseconds under D78; plan06 assumptions, not the former 200 microsecond target |

## Production test (R-PHY-4)

Standard for a clocked design:

- **Scan.** Flip-flops are replaced with scan flip-flops and stitched into
  chains, one set per clock domain, with test clocks and scan enable on
  shared pads. Clock gates are forced open in test mode.
- **Patterns.** Stuck-at patterns from an automatic pattern generator.
  Which generator the open flow can use, and what coverage it reaches, is
  the open part (decision D8, spike S4).
- **SRAM.** T35's hardware March controller owns both memory ports while
  both cores and functional services are reset. Keyed start and results are
  available through the custom JTAG DMI device. T36 firmware may provide
  additional diagnostics; it does not replace destructive-test ownership.
- **Analog.** Oscillator frequency and supply-monitor threshold measured and
  characterized through calibration/test access on the tester or bring-up board.
  Validate threshold selection and safe default separately from oscillator trim;
  no permanent trim storage technology has been selected.

## Signoff gates

None may be waived without written approval.

1. Static timing clean at every corner with extracted RC: setup and hold in
   each domain, with clock uncertainty that includes the HF oscillator's
   measured jitter and duty cycle.
2. Clock tree built to every sink, checked by an independent sink count per
   domain; every clock gate and the clock mux shown glitch-free.
3. Every clock-domain crossing passes the structural CDC check and has a
   stated MTBF.
4. Reset: asynchronous assert reaches every flop; synchronous release per
   domain; recovery and removal timing clean.
5. Electrical rules (slew, capacitance, fanout) clean at every corner.
6. SRAM pin setup, hold, access time and pulse widths met.
7. DRC, LVS, antenna clean on the full chip including analog macros and ring.
8. Full simulation suite passing on the post-layout netlist with back-
   annotated delays at the slow and fast corners.
9. Scan chains shift and capture in gate-level simulation; coverage reported.
10. Deep-sleep current from extracted leakage within R-PWR-3, or the
    requirement formally revised.
