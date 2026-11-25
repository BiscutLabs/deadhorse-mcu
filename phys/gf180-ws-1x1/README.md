# gf180-ws-1x1

GF180MCU wafer.space physical base. T43 is blocked pending the pad-readback
decision; no chip-top or physical-flow qualification is claimed.

`template.lock.json` pins the official Apache-2.0 template, selected files and
complete Nix dependency locks. `prepare_template.py` authenticates canonical Git
blobs and materializes them under `build/`, following the SRAM vendor workflow.
The retained `LICENSE` is upstream's license. Attribution is retained in the
materialized `AUTHORS.md` and source headers. The patch list is currently empty.

`pdk-candidate.lock.json` authenticates the comparison inputs. The active
`pdk-lock.json` and `block-timing.json` select revision 792ef67037d74c8c51811eab3ce23cf793491296.
The selected libraries are staged under a revision-named directory, preserving
the old PDK and its receipts. Matched SoC, USB, DMA, timer and SRAM STA results
show no numerical regression; this does not qualify a physical implementation.
`tools/pdk.py` authenticates active Liberty and functional-model bytes;
`physical-views.lock.json` and `tools/physical/pdk_views.py` authenticate physical
views and reject stale prepared inputs before extraction or sealing.

The format-only USB library witness requires identical complete Liberty tokens
and cell bodies, retains the original certificate and map identities, and is
paired with the current production source-binding check. It does not relabel
an old proof. Historical PLAN03/T32 replay scripts and `tools/t13_gate.py` retain
old evidence provenance. The latter's strict configuration check needs a separate
requalification before aggregate acceptance; it has not been waived or run here.

`pad-map.yaml` assigns every production signal with no digital spare pads and
two unassigned analog pads. This is a checked logical map, not placed fit.
The approved library and SRAM inventory are D109; pad readback while driving
still needs the separate behavioral decision below.

`physical-env.lock.json` pins the Nix bootstrap and template flake. The measured
toolchain reports LibreLane v3.1.0.dev3. `Physical.Dockerfile` records the build
recipe but has not itself been built; the measured flow uses the cached image
from the authenticated bootstrap. No upstream source patches have been applied.

Run in the pinned environment (prefix Python commands with
`python tools/env/run.py run --`):

```text
python phys/gf180-ws-1x1/prepare_template.py --source build/t43/upstream --output build/t43/template02
python phys/gf180-ws-1x1/compare_pdk.py --old build/physical/pdk --new build/t43/pdk-candidate --mapped build/t42/timing01/map/canonical.json --output build/t43/comparison03
python phys/gf180-ws-1x1/test_compare_pdk.py
```

The source checkout must match the full lock revision; output directories must
be new. Comparison reports file hashes, cell/LEF inventories and pinned SRAM
view identity. Missing baseline corners or used definitions fail closed.
Text identity does not replace timing, electrical or physical qualification.

See the [pad-readback proposal](../../docs/spec/t43-pad-readback-decision.md)
and [T43 report](../../docs/plan/tasks/reports/T43.md) for remaining work.
