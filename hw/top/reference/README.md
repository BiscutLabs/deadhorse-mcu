# Reference SoC (T20)

The [contract](../../../docs/spec/soc.md) defines the first integration stages.
`soc.yaml` is the provisional machine-readable map, clock/reset inventory,
trusted-origin and fast-interrupt assignments, and initial logical pin groups.
Q15/Q16 remain open. AON's 1 MHz option is an assumed already-running test
service profile, not an implemented clock-source change or startup guarantee.

Current deliverable: description validation and generated configuration.
There is no `DeadhorseSoc` RTL or firmware boot result yet. The existing
`EmitHello` remains only a build fixture. Fabric hierarchy/admission parameters,
full pin-budget allocation (including JTAG, dedicated clock/reset and remaining
GPIO), target-interface transport and generated-config build consumption remain
implementation work; generated configuration is not proof of connected hardware.

Run through the pinned environment, without invoking CI:

```sh
python tools/env/run.py run -- python3 hw/top/reference/check_soc_map.py
python tools/env/run.py run -- python3 -m unittest discover -s hw/top/reference -p test_soc_map.py -v
```

The checker validates existing peripheral register maps, checks domain-visible
address ranges and interrupts against the spec tables, and emits `soc.h`, `SocMap.scala`,
`soc-map.md` and `soc.json` under `build/t20/map/`. Logical memory capacity is
not necessarily a power-of-two fabric aperture: retained SRAM remains exactly
3 KiB; its eventual 4 KiB aperture must reject the extra 1 KiB. The generator
does not silently round a region up or claim a physical SRAM implementation.

Tests mutate the configuration to check overlap, wrap, bad origins/domains,
missing register descriptions, register overflow, interrupt collision/drift,
duplicate YAML keys, spec drift, unsafe pin defaults and output symlink escape.
No RTL is source-matched by these tests. New top-level
RTL will need composition proofs and simulation as required by T20; none is
claimed from this configuration check.
