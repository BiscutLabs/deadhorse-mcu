# Reference SoC (T20)

The [contract](../../../docs/spec/soc.md) defines the first integration stages.
`soc.yaml` is the provisional machine-readable map, clock/reset inventory,
trusted-origin and fast-interrupt assignments, and initial logical pin groups.
Q15/Q16 remain open. AON's 1 MHz option is an assumed already-running test
service profile, not an implemented clock-source change or startup guarantee.

Current deliverable: description validation plus the I0 Chisel assembly:
faithful RV32IMFC core, boot ROM, banked SRAM, registered local arbitration,
retained MMIO slot, main fabric and UART0. Firmware checks SRAM byte writes
and a floating-point multiply, then prints through the UART pin in simulation.
The existing `EmitHello` remains only a build fixture. I1 fabric hierarchy/admission parameters,
full pin-budget allocation (including JTAG, dedicated clock/reset and remaining
GPIO) and target-interface transport remain implementation work. The RTL and
firmware consume generated JSON/C configuration. This focused boot test is
not the brief's gateway-based system acceptance or core lockstep suite.

I0 requires an externally running main clock. `clockHold` is UART-only demand,
not whole-top permission to stop that clock. Client-only reset retains and
drains old MMIO before admitting a new core epoch. Service reset resets both
the hub and fabric/UART; neither reset clears SRAM. ROM and RAM are synchronous
models, not physical macros. Read latency and bank count are elaboration parameters.

Run through the pinned environment, without invoking CI:

```sh
python tools/env/run.py run -- python3 hw/top/reference/check_soc_map.py
python tools/env/run.py run -- python3 -m unittest discover -s hw/top/reference -p test_soc_map.py -v
python tools/env/run.py run -- python3 dv/soc/prepare_i0.py
python tools/env/run.py run -- python3 tools/sbt.py "hw/testOnly deadhorse.top.SocMemorySpec deadhorse.top.SocBootSpec"
python tools/env/run.py run -- python3 hw/top/reference/formal/check_memory.py --output build/t20/formal-control-fresh
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
No RTL is source-matched by these tests. Memory tests use independent byte and
response scoreboards, concurrent fetch/data requests, reset races and an actual
corrupted-output negative. Boot uses an independent UART decoder with an
observer-corruption negative. ChiselSim memory randomization is disabled because
it overwrites loaded ROM after initialization; register randomization remains
enabled and RAM comparisons follow explicit writes. The pinned vendor generic
clock-gate model is linked without modifying it.

The firmware preparer invalidates stale receipts before rebuilding, hashes its
inputs and outputs, and records preparation separately from execution. Its minimal
linker supports this stack/local-data test, not a general initialized-data runtime.
The [focused control proof](formal/README.md) records its reset assumptions and
scope. Integrated lockstep, performance, timing/area, I1 and the remaining T20
acceptance remain open. Neither CI tier has run under the user's no-CI direction.
