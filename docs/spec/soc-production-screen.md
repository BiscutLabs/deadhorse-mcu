# PLAN03 B4 production mapping screen

## Outcome and scope

Stopped, 2026-11-22: the production SoC's mapped USB paths fail existing class
limits in both main-clock configurations, triggering PLAN03's stop condition.
No production RTL, assertion, assumption, timing limit or register map changed.
Main register paths meet the 8 MHz budget but miss the 9 MHz budget.

Base: `e18e2e8` on main; production RTL is identical to the fresh emissions
made immediately before that documentation/tooling commit. Pinned tools:
Yosys 0.71+34 (`e419c4eef`), OpenSTA 3.2.0. Library:
`gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib`, SHA-256
`5d2f37ba6f43e33aeba26dc1da55c96394a862eeec4148043f1d48bdf65ccea6`.
This is mapped, pre-layout, ideal-clock screening without wire delays.

All production features and RVFI observations remain. Six synchronous memory
interfaces are exposed: four performance-SRAM banks, retained SRAM and ROM.
Exact graph restoration checks that only those interfaces were removed; their
read/write synchronization was checked before projection. USB packet memories
remain standard cells. Macro timing/area, complete boundary/clock-gate/reset
checks and whole-chip physical qualification are not closed by this screen.

## Commands and preserved evidence

Each command below uses `python tools/env/run.py run --`. Scripts and generated
receipts remain under scratch/build; this is a stopped experiment, not a new
CI acceptance path.

```text
python tools/sbt.py 'hw/runMain deadhorse.top.EmitSoc build/plan03/production-measure01/emit-8 production 8' 'hw/runMain deadhorse.top.EmitSoc build/plan03/production-measure01/emit-9 production 9'
python scratch/plan03_production_hierarchy.py
python scratch/plan03_production_map.py
python scratch/plan03_production_map02.py
python scratch/plan03_production_sta.py build/plan03/production-measure03 8
python scratch/plan03_production_sta.py build/plan03/production-measure03 9
yosys -Q -T -s build/plan03/production-measure03/map-8/canonical.ys
yosys -Q -T -s build/plan03/production-measure03/map-9/canonical.ys
python scratch/plan03_usb_context.py
python scratch/plan03_production_certificate.py
python scratch/plan03_production_classes.py 8
python scratch/plan03_production_classes.py 9
python scratch/plan03_class_audit.py 8
python scratch/plan03_class_audit.py 9
python scratch/plan03_screen_seal02.py
```

Final directories under `build/plan03/production-measure03/`: `map-8/9`,
`sta-8/9`, `context02-8/9`, `certificate05-8/9`, `classes-8/9`.
Independent review verified all 2238 source/artifact hashes in
`build/plan03/production-screen-seal02.json` before the documentation update.
This authenticates the failed experiment, not a timing pass. Seal01 included
its own live stdout; seal02 preserves it and binds the completed log without
including its own live outputs.

Earlier diagnostics are preserved. Hierarchical, unconstrained mapping in
`production-measure01` measured an electrically overloaded main path of
507.550964 ns; it is not the accepted method. Map02 stopped at a clock-alias
check. Corrected map03 uses flattened, load-aware mapping and the project's
explicit buffer/upsize/dnsize recipe. Its assumed 62.5 ns optimization target
does not replace any STA limit. Existing screening assumptions remain:
0.5 ns input slew and 0.05 pF output load. The mapper's estimated alias load
is 5 x 50 fF = 250 fF. State recoding and retiming are disabled.
Measured inserted reset-buffer count is 4933 in each mapping, with every
original cell connection and clock preserved and a real buffer-cycle fault
rejected. Both final register screens report zero electrical violations.

## Measured paths and area

All delays and areas below are measured by the commands above. Main budgets
are estimated as `0.60 x 1000 / MHz`. AON uses the explicitly assumed 1 MHz
active-service clock, budget `0.60 x 1000 = 600 ns`; this does not implement
or qualify the nominal 32 kHz oscillator.

| Main configuration | Main RR worst / budget, ns | Start to end | AON RR worst / budget, ns | Mapped logic area, mm2 |
| --- | --- | --- | --- | --- |
| 8 MHz | 70.504395 / 75, pass | `_205281_/Q` to `_212145_/D` | 70.677109 / 600 | 3.2919833856 |
| 9 MHz | 70.190018 / 66.666667, fail | `_197201_/Q` to `_196184_/D` | 68.661133 / 600 | 3.2880144640 |

Area excludes the six memory sockets. No SRAM-inclusive chip-fit budget or
per-block/domain area allocation is accepted. Hierarchical diagnostic area
is not substituted for the flattened area.

USB remains at 48 MHz. Its ordinary target is 12.5 ns with the approved 15 ns
ceiling, except FP retains its strict 12.5 ns limit. CC/CP retain 50/37.5 ns.
Bold measured delays below fail the unchanged ceiling.

| Class | Target / ceiling, ns | 8 MHz configuration, ns | Start to end | 9 MHz configuration, ns | Start to end |
| --- | --- | ---: | --- | ---: | --- |
| CC | 50 / 50 | 28.636534 | `_211432_/Q` to `_214032_/D` | 23.481016 | `_210896_/Q` to `_213496_/D` |
| CC_reset | 12.5 / 15 | 14.108039 | `_211309_/Q` to `_211325_/D` | **15.204027** | `_210774_/Q` to `_210791_/D` |
| CF | 12.5 / 15 | **15.623331** | `_212557_/Q` to `_214014_/D` | **17.394888** | `_212022_/Q` to `_213479_/D` |
| CP | 37.5 / 37.5 | 18.551130 | `_211439_/Q` to `_213934_/D` | 14.484763 | `_210904_/Q` to `_213399_/D` |
| FC | 12.5 / 15 | **18.821064** | `_210758_/Q` to `_212507_/D` | **15.094015** | `_213561_/Q` to `_210694_/D` |
| FF | 12.5 / 15 | **16.256580** | `_214175_/Q` to `_214014_/D` | **15.763020** | `_213640_/Q` to `_213479_/D` |
| FP | 12.5 / 12.5 | **14.991170** | `_213953_/Q` to `_213934_/D` | **13.273643** | `_213418_/Q` to `_213399_/D` |

Failing logical identities:

- CF, both: PHY TX `tx_state_q[0]` to resume `carries_3`.
- FC, 8 MHz: cadence enable to PHY RX `cnt_q[16]`.
- FC, 9 MHz: SIE bus-reset output to EP0 `header_1[6]`.
- FF, both: synchronized `usbUp_r_released` to resume `carries_3`.
- FP, both: engine configured output to IN `consume`; this launch does not
  receive CP's exception.
- CC_reset, 9 MHz: EP0 `state[5]` to `writeCount[1]`; reset compatibility keeps
  this pair single-cycle.

Minimum measured hold slack among queried same-domain register paths is
+1.711015 ns in main/AON and +1.696710 ns in USB. These limited queries do not
establish boundary hold, reset-removal or clock-gate closure.

## Certificate composition and independent review

The production emitter folds the existing owner=performance(1) connection.
A complete all-state next-function miter compares that instance with the
reviewed standalone wrapper connected to the same constant: measured 364 state
bindings per configuration, no state/output exclusions or environment
assumptions. Every next value, clock/reset function and public output agrees;
an actual next-cursor mutation fails.

The existing D58 emission-inventory guard is unchanged. Its exact reviewed
source inventory connects to the production emission through that context
proof. Existing source/mapped value, reset, cadence and pre-enable proofs then
bind actual SoC identities: measured 294 certified registers per configuration.
The proof view changes only module/alias names, with exact restoration checked.
Unrelated clock-gate outputs are freed conservatively in the local proof only;
STA uses the unchanged mapped graph. Every certified/pre-enable/cadence
register is checked against actual `i1_usbClock`. Canonical JSON re-export
produces byte-identical Verilog.

All existing certificate faults remain. The written SDC exactly matches the
certificate: measured 82781 setup-4/hold-3 pairs and 2510 setup-3/hold-2 pairs
per configuration; a wrong multiplier is rejected. No extra false path is
introduced. This failed screen does not claim a new complete delay-fault
campaign or physical signoff. Seal02 binds proof scripts, models, logs,
certificates, mappings, timing queries and audits.

Independent review accepted the context composition, mapped identities,
applied pair inventory, failures and corrected seal. Initial adapter failures
(unrecognized unrelated ICG, private-buffer JSON bit/name allocation and
full-SoC versus standalone D58 inventory mismatch) remain preserved; no guard
was bypassed and none was called a solver timeout.

## Proposed follow-up and open work

Carry the existing USB mapping measures into production synthesis: preserved
resume decode boundaries, cadence-enable replication, fanout buffering and
USB-specific sizing. The current generic full-SoC recipe lacks those measures.
This is a plausible mapping remedy, not proof of closure or evidence that RTL
must change. Keep production binding, certification, limits and checks intact.
PLAN03 requires approval to continue after the both-frequency failure.

B4 stops here: integrated fixed/hard-float cycles, per-block/domain area,
SRAM-inclusive allowance budget and remaining boundary timing are open. T20
remains open. B5 debt triage and B6 briefs/re-planning have not started.
B3 fast CI passed with twelve explicit deferrals; full CI was not run.
