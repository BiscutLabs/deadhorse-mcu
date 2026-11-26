# Analog characterization and physical handoff

T34 defines interfaces, digital models and this plan. T43/D111 adds compact
experimental LF/POR layouts, selected DRC/LVS, limited extracted diagnostics and
connected chip floorplan/PDN smoke. The full characterization matrix below
remains open. These views establish physical fit, not production electrical
qualification or a tape-out gate. See the [T43 report](../docs/plan/tasks/reports/T43.md).

## Provenance and process boundary

The repository's T06 bootstrap pins RISCay at
`4671317186003740ceb61360ba08c59bbdf10136`; its available checkout is under
`build/riscay-mcu`. Relevant sources there are:

- `analog/gf180-lf-osc/{sources.json,NOTICE.md,README.md,characterization.md}`:
  LF candidate topology/attribution. Its upstream reference is Tim Edwards'
  `sky130_ef_ip__rc_osc_500k`, revision
  `343f4481b2199efe4ddba48428c89fcf1029ae9a`. The historical candidate is not
  a qualified 32 kHz macro; its frequency/area results are not inherited.
- `analog/gf180-clock-reset/{README.md,circuits.py,riscay_supply_monitor_gf180.spice}`:
  original RISCay bandgap/comparator starting point. Raw supply-good chatter,
  nonzero dip-detection latency and dependence on a longer digital hold prevent
  inheriting its results as evidence for the present ideal assertion/1 ms model.
- Historical T06 `physical/gf180/pdk-lock.json`: open_pdks revision
  `40cee970d8a9b7eaea35a34fe7d6068f05721f0a`, cell libraries and model hashes.
- `soc/sram-lock.json`: SRAM repository revision
  `efdbf734d806c2ac3b858d281a5b832625a8e928`, views and hashes.
- LF `sources.json` separately pins GF180 primitive model revision
  `9f992d5a9186d1f7820c58f039c484ad35b2edea`; reconcile model revisions and
  selected process options before analog implementation, not by silently mixing.

T43 selects template PDK `792ef67037d74c8c51811eab3ce23cf793491296` through
`phys/gf180-ws-1x1/pdk-lock.json` and the versioned physical fetch. The old
40cee970 reference above describes retained RISCay provenance only, not the
active process pin. No analog SPICE/layout result is migrated by changing the
digital library. Reconcile analog primitive model provenance before simulation.

Pinned cell/SRAM views include SS 3.0 V, TT 3.3 V and FF 3.6 V corners with
temperature labels -40/25/125 C. These are available characterization points,
not an absolute-maximum rating or a qualified continuous operating envelope.
Shuttle acceptance, high-resistance poly, PNPs, device limits and SRAM minimum
operating/retention voltages remain Q5/Q6/T35 qualification inputs. The scoped
checker records hashes of available provenance; it does not simulate SPICE.

## Measurement matrix for a later physical brief

Use the frozen macro netlist, selected foundry models and extracted parasitics;
record tool/model hashes, seeds, circuits, loads, waveforms and extraction
commands. Start with the available MOS TT/SS/FF/SF/FS corners, resistor and
BJT corners as supported, and -40/25/125 C, 3.0/3.3/3.6 V as **assumed sweep
points**, plus qualified min/max limits once established. Unsupported device
corners or mismatch models are missing evidence, never silently nominal.

| Measurement | Method and perturbations | Acceptance / owner |
| --- | --- | --- |
| LF autonomous startup | Cold DC and transient starts, all initial conditions, slow/fast/noisy ramps, enable and restart phases, supply interruption | Starts without firmware or trusting a POR held by its own output; maximum time to valid edges and ready measured; later LF layout brief |
| LF trim range/monotonicity | Sweep every implemented code at PVT, coarse/fine transitions and mismatch; count settled edges against calibrated reference | Assumed nominal 32 kHz, within 5% after trim; safe code0 bounds and reserved/unknown-code behavior documented; no unimplemented tuning curve inferred |
| LF waveform | Edge intervals and threshold crossings after settling at min/max load; transient-noise runs, timestep-convergence control | Measure jitter, duty, slew and minimum pulse widths; limits derived from actual clock-tree/library receivers before acceptance |
| LF power | Integrate total supply current including reference/startup/output buffer; steady, startup, restart and disabled if supported | Assumed LF <1 microamp; aggregate extracted chip retained sleep <50 microamps at25 C, separately budgeted |
| POR startup/invalid rail | Ramps from zero to invalid/valid plateaus; pauses, reversal and noise around each threshold; no reference/AON source dependency | Never release below qualified safe voltage; no startup-good glitch can escape full qualification |
| Threshold/hysteresis | Slow up/down sweeps, all encodings, MOS/resistor/BJT corners and mismatch; regulator tolerance | Measured min/max rising/falling limits with positive hysteresis and digital/SRAM safety margin; assumed values in POR contract are not acceptance evidence |
| D85 selection change | Switch both directions at below/between/above threshold voltages, at each qualification phase; include selector slew/skew | No unsafe release pulse, assertion below new falling threshold, full fresh qualification after assertion; still-valid supply may remain released |
| Brownout response | Dips of swept depth/duration/phase, fast collapse and recovery; slow noisy crossings; load transient and hold-up model | Measure detection plus distribution delay and minimum guaranteed pulse; rail remains valid until reset reaches every sink; reset-cause sampling/retention separately qualified |
| Reset release | Measure minimum/maximum qualified delay and any glitches across PVT/noise/mismatch, timebase stopped/failed | No early release; minimum reset pulse and downstream recovery/removal met; assumed model 1 ms replaced by characterized limits |
| Loading/coupling | Extract output/load interconnect; sweep fanout, substrate/supply noise and neighbouring digital switching | Clock/reset receiver levels, slew/pulse widths and reset integrity; T38 integration |
| Statistical robustness | Foundry-supported mismatch/Monte Carlo and noise, recorded seeds/sample count, failure-rate confidence | Yield/confidence target requires a documented physical acceptance decision; no invented statistical guarantee |
| Test/calibration | Standalone probe then approved T37/T38 test path, safe entry/exit and stuck controls | Observe frequency/thresholds; load approved trim without unsafe reset/clock release; no new storage implied |

## Later implementation briefs to prepare

**LF physical macro:** choose a topology compatible with the confirmed process
options and assumed 0.10 mm2 allowance; define real trim encodings and safe
startup independently of firmware. Deliver schematic/SPICE, license/provenance,
layout, extracted netlist, GDS/OASIS, LEF blockage/pins, CDL, DRC/LVS/antenna
reports, clock timing/noise/power models and the LF rows above. Measure actual
width/height and replace the allowance; do not reuse the historical resistor
footprint as a claimed fit.

**POR/brownout physical macro:** realize D79/D85 with safe default selection,
hysteresis, autonomous release timebase and defined supply-invalid outputs.
Deliver the same physical views plus threshold/delay/mismatch characterization,
reset pulse/glitch and cause behavior. Assumed area is 0.15 mm2. Demonstrate
board/supply margins and startup independence; no raw bandgap-good output may
substitute for the qualified reset contract.

**Shared T35/T37/T38 handoff:** confirmed device/SRAM operating limits; macro
pin locations/supplies, guard rings, isolation and substrate rules; test access
and calibration loading proposal (currently absent); reset/clock SDC arcs and
loads, voltage domains/ESD/latch-up and antenna constraints. Implement neither
trim storage nor new package pins without approval. Integration must close
CTS/hold/recovery/removal/MTBF with real views; a digital model cannot do so.

T43/D111 now provides experimental real layouts, extracted-capacitance
diagnostics and measured dimensions; see its report. Still missing: accepted
resistance extraction, complete POR electrical composition, qualified
timing/power/accuracy, four-state power-aware models, trim-loading/test route
and process/shuttle qualification. T34 completion
does not mark these delivered. No analog measurement or area claim follows
from a passing digital model test.
