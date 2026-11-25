# gf180-ws-1x1

GF180MCU wafer.space physical base. T43 is in progress; no chip-top or
physical-flow qualification is claimed.

`template.lock.json` pins the official Apache-2.0 template, selected files and
complete Nix dependency locks. `prepare_template.py` authenticates canonical Git
blobs and materializes them under `build/`, following the SRAM vendor workflow.
The retained `LICENSE` is upstream's license. Attribution is retained in the
materialized `AUTHORS.md` and source headers. The patch list is currently empty.

`pdk-candidate.lock.json` authenticates downloaded comparison inputs only; it is
not an active PDK configuration. `block-timing.json` retains the accepted old
library until migration and matched measurements qualify the replacement.

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

See the [pending pad/SRAM proposal](../../docs/spec/t43-physical-base-proposal.md)
and [T43 report](../../docs/plan/tasks/reports/T43.md) for remaining work.
