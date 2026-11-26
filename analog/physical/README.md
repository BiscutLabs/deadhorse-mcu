# Physical analog implementation (D111)

Generated layouts and diagnostic netlists are under
`build/t43/`; they are experimental macros, not electrically qualified for
tape-out. T43 checks their geometry/connectivity and actual chip fit. A real layout is
needed to establish footprint, pin access, obstructions and power connectivity.
An area allowance cannot supply those facts to the chip floorplan.

## Reproduce the selected physical candidate

Use the immutable template environment from
`phys/gf180-ws-1x1/physical-env.lock.json` and its pinned Nix flake. All commands
below run with repository `/work` in that environment. Tools outside Magic
also have executable/module hashes recorded in `provenance.json`; the immutable
environment supplies their version pin. `library-inputs.lock.json` authenticates
248 installed Magic/primitive/standard-cell files against the pinned release
archives. A failed command retains an incomplete/failed receipt.

```text
python analog/physical/generate_lf.py --output build/t43/lf-generator05
python analog/physical/generate_lf.py --role por-timebase --output build/t43/por-timebase-generator03
python analog/physical/generate_monitor.py --output build/t43/monitor-generator04 --tech build/t43/pnp-repair01/gf180mcuD.tech
python analog/physical/assemble_lf.py --analog build/t43/lf-generator05 --mapping build/t43/lf-ready02/mapped.json --output build/t43/lf-assembled03
python analog/physical/assemble_por.py --monitor build/t43/monitor-generator04 --timebase build/t43/por-timebase-generator03 --digital build/t43/por-digital01/runs/prototype06/final --tech build/t43/pnp-repair01/gf180mcuD.tech --output build/t43/por-assembled03
python analog/physical/add_power_access.py --lf build/t43/lf-assembled03 --por build/t43/por-assembled03 --tech build/t43/pnp-repair01/gf180mcuD.tech --output build/t43/analog-access05
python analog/physical/write_abstracts.py --access build/t43/analog-access05 --interfaces build/t43/analog-interfaces.json --output build/t43/analog-abstract10
```

The mapped readiness and routed qualifier are the production-parameter Chisel
components described in [physical-digital.md](../physical-digital.md). Earlier
reference layouts, digital routing outputs and diagnostic waveforms remain
receipt-bound under build. No GDS, emitted RTL or netlist is committed.
The generator derives mapped port bindings by name, rejects ambiguous aliases,
checks the actual qualifier SPICE pin order and retains all endcap supply pins.
The abstract writer verifies actual supply landings and the entire cleared
Metal4 access band. It refuses foreign metal rather than hiding it behind an
optimistic LEF obstruction.

`check_views.py` performs selected macro DRC and flat LVS; `check_generation.py`
checks geometry reproduction and rejection controls. `export_pdn.py` checks
the complete memory/analog inventory, bounds, halos and supply bindings.
`check_pdn.py` checks actual macro/PDN net overlap, PG rail coverage, injected
faults, conductor/cut geometry and supply shorts. None claims complete analog
electrical qualification or whole-chip DRC. Exact final invocations and measured
times are in the [T43 report](../../docs/plan/tasks/reports/T43.md).

## PNP extraction correction

`inputs.lock.json` pins the official primitive archive, unchanged Magic device
views, original/corrected extraction deck and the complete immutable Magic
8.3.677 output tree. The latter includes its launcher, actual `magicdnull`
extractor and startup Tcl. The PDK initialization files are pinned separately.
`pnp-extraction.patch` is a local extraction-tool correction, not a change to
foundry geometry, device models, model names, area bounds or LVS tolerances.

In the pinned deck, trailing `*pdiff error` is parsed as the optional substrate
layer/name. Only the collector remains a numbered terminal, so the `a2`
emitter-area condition reads an unused zero-initialized slot. Magic reports
that no device model matches and falls back to the first model name. This
happens on the untouched official primitive, before Deadhorse adds routing.

The four-line correction declares emitter and collector as explicit terminals
and tests the emitter's `a1` area. Magic's MOS-like subcircuit writer orders
drain/gate/source as collector/base/emitter. No post-extraction renaming is
used. Source evidence is the pinned Magic revision
`3f1747b1fb915358414da70659b82cecb0314be2`, `extract/ExtTech.c` terminal parsing
and `ext2spice/ext2spice.c` subcircuit pin ordering.

Run in the pinned native environment:

```text
python analog/physical/check_pnp_extraction.py --pdk build/t43/pdk-candidate/gf180mcuD --output build/t43/pnp-check-production02
```

Measured at base `b99f754` plus receipt-hashed working sources: PASS for all
four original PNP identities, C/B/E pin order and emitter areas (2.1, 4.2, 25,
100 square micrometres). A distinct-terminal 2.5-square-micrometre emitter
negative is rejected. The receipt authenticates every input, artifact and tool
file. Independent review verified the receipt and checker. This is a tool
component result, not complete-macro acceptance.

Preserved diagnostics: `pnp-audit01` reproduces the original failure;
`pnp-repair-check02` contains an invalid first negative which accidentally
shorted base to emitter; `pnp-repair-check03` corrects that control and checks
streamed-GDS connectivity. `por-layout04` retains the original vendor leaf
unchanged and places access routing in a wrapper. Its GDS roundtrip gives
unique LVS (43 devices and 27 nets after permitted device merging).

## Outstanding electrical verification

The LF nominal flat-capacitance diagnostic and digital qualification proofs
are documented in the T43 report and `../physical-digital.md`. They do not
establish autonomous complete-POR startup. The full-transistor 40 ms POR case
hit the existing 120-second command cap; it is retained as unresolved, not
rerun unchanged. Smaller interface checks may support a reviewed composition
with the unchanged 1000-edge proof, but every initialization, loading and
feedback premise must be discharged first.

Flat capacitance extraction explicitly disables hierarchy; an earlier
hierarchical run omitted capacitance. Resistance extraction still needs a
validated topology/capacitance-conservation argument or a justified bound on
omitted resistance. Neither schematic LVS nor geometry DRC closes that item.
Density, antenna, full-chip routing and silicon/statistical qualification are
separate from the selected macro-geometry checks.
