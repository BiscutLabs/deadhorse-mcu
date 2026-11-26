# T43 analog physical implementation extension

User direction 2026-11-25, D111: implement the missing LF/POR layouts, seek
small area, finish T43 and merge the reviewed result to main. This extends
T43's earlier physical-input dependency; it does not waive checks or declare
the current schematic candidates production-ready.

Unchanged acceptance authorities: [LF interface](../../analog/lf_rc/README.md),
[POR interface](../../analog/por_brownout/README.md), and the
[characterization matrix](../../analog/characterization.md). In particular,
threshold changes discard incomplete POR qualification; reserved codes remain
safe and test inputs inert; brownout stays sticky until power loss and the
power-epoch output retains its contract even though production does not use it.

## Contract and implementation order

1. Adopt the pinned RISCay oscillator and supply-monitor topologies with their
   attribution. Use the authenticated current-PDK device models and actual
   supported 1 kOhm/square resistor option. Preserve original sources; record
   adaptations in reproducible generators under analog/.
2. Establish circuits compatible with the existing LF and POR pin contracts
   before declaring physical views usable. LF must start without an external
   POR stimulus. POR must implement threshold selection, hysteresis, autonomous
   qualification and cause outputs; a raw monitor-good signal is insufficient.
   No internal HF service clock, package pin, trim-storage or reset-interface
   change is included. Any digital macro logic remains clocked Chisel.
3. Use pinned PDK device generators and design rules for compact placement,
   matched-device arrangements, guard rings, well/substrate ties and routing.
   Assess resistor folding and reduced resistor ratios/current tradeoffs by
   simulation. Minimize measured area among passing candidates; do not claim
   a global minimum or reduce electrical margins to satisfy an area objective.
4. Generate actual layout, extraction, GDS, LEF and circuit views under build/.
   Source generators, manifests, provenance and results documentation are
   versioned. LEF dimensions and obstructions must come from that layout.
5. Check DRC and LVS, then extracted behavior against the unchanged contracts.
   Record nominal and corner/ramp evidence, negative controls and unqualified
   conditions explicitly. Digital tests cannot qualify analog startup or
   thresholds; a schematic simulation cannot qualify extracted behavior.
6. Bind only checked physical views into T43's real Deadhorse synthesis,
   floorplan, padring and PDN smoke. Stop before global placement. Replace the
   assumed macro-area entries with measured footprints and update headroom.
   Run affected pad/reset/boot checks and independent final review, then merge
   to main if T43 acceptance passes. No aggregate fast/full CI.

## Review and limits

T43 acceptance is pre-global-placement smoke, as its assigned brief states.
Independent review distinguished that requirement from the characterization
matrix's later electrical/signoff work: checked real geometry, extracted
connectivity, actual fit and PDN binding close the physical-input dependency.
They do not establish full RC accuracy, complete POR electrical composition,
PVT/trim qualification or silicon readiness. Preserve those gaps and failed
diagnostics in the handoff. No unchecked electrical premise becomes a pass.

Independent review covers circuit/interface compatibility, device/layout
generation, extraction/DRC/LVS, measurement validity and physical integration.
Retain the existing assumed LF/POR area allowances and electrical targets;
report measured figures separately. No fabricated footprints, disconnected
analog instances, ideal behavioral production circuits or acceptance relaxation.
T38 full-chip routing and analog silicon/statistical qualification remain
distinct obligations. Report missing model support or an unmet contract rather
than treating it as a pass. Existing scoped proof/timeout policy remains.
