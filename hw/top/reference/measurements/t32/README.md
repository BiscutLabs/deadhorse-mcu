# T32 area-review measurement producers

## Current area07 replay

The current standalone entry point is:

```sh
python tools/env/run.py run -- python hw/top/reference/measurements/t32/replay.py --output build/t32/replay-fresh
```

Use a new output directory. The runner freshly emits the production 8 MHz top,
checks the memory interfaces, maps the observer projection, applies the reviewed
layer-balanced reset buffers, computes the unchanged budget, and runs register,
electrical, gate, hold, reset, pulse and qualified USB-class screens. It archives
every producer and command. Only output/input artifact path constants change in
the preserved producers; no mapping or budget algorithm is rewritten.

Prerequisites are the pinned GF180 Liberty/LEF already prepared by the physical
tool flow, plus an existing qualified USB mapped island and matching certificate.
Defaults name the PLAN03 inputs used for area07. `--usb-map` and
`--usb-certificate` accept other explicit paths under `build/`; certificates and
pin identities are checked before class constraints are accepted. A raw USB
mapping without its matching certificate is insufficient. These are explicit
measurement inputs, not an ignored area03 setup dependency.

`t32_area07_{hierarchy,sockets,map,partition,budget}.py` are byte-identical to
the executed area07 producers; the source hashes are in `area07/run.json`.
The USB class/policy and pulse producers are also retained. The physical model
still contains negative reset-removal and unbuffered core-clock pulse diagnostics;
successful execution of the measurement runner does not label those checks passed.
T33/T38 own actual reset/clock-tree/CTS and pad qualification.

The preserved partition producer contains historical prose saying "Includes RVFI
observation logic". For area07 and this replay that description is superseded by
the audited physical-boundary projection: RVFI observation-only outputs/cones are
excluded. Numeric cell accounting is unaffected. The original area07 erratum is
retained beside its partition receipt; this explicit correction also applies to
replay partition descriptions. The producers remain exact executed source copies.

## Historical comparison producers

Exact executed Python sources, preserved for review/reproduction, not generated
RTL or result artifacts. The approved whole-SoC review retains functional RTL,
instrumented tests, all non-RVFI ports, memory capacities, timing limits, the
0.55 utilization assumption and every unbuilt allowance.

Run from the repository root through `python tools/env/run.py run --`.
Historical working paths are `scratch/`; copying these sources there reproduces
the imports and receipt paths. Do not overwrite differing local scripts.
Use fresh output directories or an explicitly recorded path-only adaptation;
the producers refuse to overwrite their principal output directories.

Inputs: the source-bound area03 instrumented production emission/hierarchy and
mapped snapshots, pinned PDK/USB island, and current budget inputs documented in
the T32 report. `t32_observer_audit.py` gives a conservative graph-only projection;
`t32_area04_run.py` performs the fresh observer-boundary remap. It reads the
existing area03 hierarchy, reversibly removes only `rvfi_*` output ports and
retains the same six memory interface cuts. No test loses RVFI observation.

`t32_layered_map.py` consumes the area04 unbuffered graph, applies full-layer
reset buffering with the same buf_4 cell and fanout limit eight, then exports
area06 and computes its budget. `t32_packed_reset.py` is a validation/exploratory
dependency; its mixed-depth minimal tree is not the selected physical mapping.
The selected layered tree has equal inserted depth per original root and does
not increase maximum depth. Exact original-pin and observer-cone audits are
required in addition to area arithmetic.

Run `t32_timing_screen.py <area04-or-area06>/mapped 8`, then
`t32_reset_timing.py <...>/mapped`, then `t32_reset_endpoints.py <...>/mapped`
for both snapshots, followed by `t32_reset_compare.py`. The endpoint producer
also emits corrected `result02.json` summaries: the earlier raw summary parser
did not recognize the asynchronous-group removal line. Original evidence is
retained. These matched ideal-clock screens do not constitute CDC/CTS/pad/macro
or physical signoff. Raw USB exceptions are unapplied; negative asynchronous
removal and the unbuffered core-clock pulse diagnostic remain explicit.

The SRAM producer reads the pinned archived LEFs without network access. It
does not select or implement a new memory organization. Production boot-ROM
firmware is not implemented, so its allowance remains unchanged.

Evidence/qualifications: `docs/plan/tasks/reports/T32.md` and
`docs/spec/soc-physical-boundary.md`. No clean replay of these copied paths is
claimed; hashes below prove identity with the executed producers.

| Source | Executed SHA-256 |
| --- | --- |
| `t32_observer_audit.py` | `cf238f038e95064e109e97841c89066a00810a0fa769d1e7a1cebbcd4b428dba` |
| `t32_observer_map_setup.py` | `b9bc86f7267e6779b18149aaa3572a44a2605582ee7565df56824569e2065bfe` |
| `t32_area04_run.py` | `4caa78e69d88b7a3eced20fd8eb68ef99fd826b521f071d0261aeeab3aa502c6` |
| `t32_area04_map.py` | `71cbfa8738676f4f2d01f63fda430ab9f24cbf61159a45fbc1de4c62806eabd1` |
| `t32_area04_partition.py` | `8b54da49a704aacce59cba53a4603730bc5d6aa3a82bd092d34eb3b9685727aa` |
| `t32_area04_budget.py` | `be66b6c13e2179f877cc5189ec4a0129c593789a338a686a028f6b10cbf28d0a` |
| `t32_packed_reset.py` | `8a912a685382b67966315b8757ba3e5ffb315bc2f0afd88661a0d23983ae83a8` |
| `t32_layered_reset.py` | `36fad27bd33d0fe128fcd752bb7eaf792a67603acdc51ad106232c4f71f4418c` |
| `t32_layered_map.py` | `e9859c14b1cfc152de71d2ce0752d2511f618138d6d2e47e2307c276f56fbbe0` |
| `t32_area06_partition.py` | `5facb12fea36508d02282e76915f5c464d91f85ab63dc0fcd96d4685a416685e` |
| `t32_area06_budget.py` | `5ff2eac5baa46e946d12557a8b87ec09f1e09f9290c3984099d0e9bbb99884ec` |
| `t32_timing_screen.py` | `d112f888657f9569493fc55832eb89ac30a08bc604b824f452900bfd4438b14f` |
| `t32_reset_timing.py` | `9b68ecd520b29f235c8ff404688279f1deb2ca4600c8bb9cb9a34b8c9acfc727` |
| `t32_reset_endpoints.py` | `a0d30e86bd14d9fca47bebf6035199c8876204b28fedc613248f8f52ff074683` |
| `t32_reset_compare.py` | `e34f3bcf40ad53349626adc2d5a32b6bb0df93f49b5eb5f9a805c7c31dd014e3` |
| `t32_sram_review.py` | `3a209377b149e181b38f9bc3d45bdded34d5e87835b8150d3c3daf7235c08d90` |
