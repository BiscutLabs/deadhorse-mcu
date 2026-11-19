# USB packet-memory area estimate (2026-11-18)

Independent review at baseline `38e0bddb691288eeba92cb257d30935a40c15fb6`
inspected both SRAM archives in the bootstrap's pinned public PDK release
`gf180mcu-f6bfbd4d3d23c4236ff1f36126489ee59aa35cbd`.
Command: `python tools/env/run.py --network bridge run -- python3 scratch/t19_sram_catalog_review.py`.
Receipts and complete LEF catalog: `build/t19/sram-catalog-review-01/`.

The smallest available footprint in those archives is
`gf180mcu_ocd_ip_sram__sram256x8m8wm1`. **Measured** LEF dimensions are
301.30 × 224.93 um; **estimated** footprint is their product,
67771.409 um2. It accommodates the existing 65-address ring. FD's smallest
64×8 macro has **estimated** footprint 100571.5568 um2 and is too shallow.
The locally installed 1024×8 macro is not the smallest available macro.

Archive SHA-256, verified against the pinned release asset metadata:

- FD: `338c9a09e74e18f2a9b0e82abff9b0a3379cfc3002131e8392b213739c01f67e`
- OCD: `62c12904ac105fe68fc7ebd91214d6f59b3126edc5c87c4f3238c29bf2fdf6d0`
- Selected LEF: `232555e5205f01bfb758a23e31e37c52bbe91decdbe0867333b2a266b6f92168`

Fresh independent **measured** standalone `UsbPacketMemory` mapped area is
96009.2672 um2; worst delay 11.140153 ns, zero reported electrical violations,
under the same pinned GF180 7-track SS/125 C/3.0 V pre-layout assumptions:

```sh
python tools/env/run.py run -- python3 tools/timing/check.py --top UsbPacketMemory --source build/t19/emit-13/in/UsbPacketMemory.sv --source build/t19/emit-13/in/banks_8x8.sv --clock clk --operating-point usb-48mhz --output build/t19/sram-catalog-review-01/packet-memory-timing
```

First-order **estimates** use previous measured buffer area minus standalone
memory area plus macro footprint:

| Buffer | Previous measured mapped area um2 | Estimated replacement um2 | Estimated reduction |
| --- | ---: | ---: | ---: |
| IN | 105051.2960 | 105051.2960 − 96009.2672 + 67771.409 = 76813.4378 | 26.88% |
| OUT | 102331.4432 | 102331.4432 − 96009.2672 + 67771.409 = 74093.5850 | 27.59% |

Estimated available overhead before break-even: 96009.2672 − 67771.409 =
28237.8582 um2 per buffer. Standalone subtraction does not account for
integration optimizations. The macro has a shared read/write address port;
scheduling, adaptation logic, timing, reset and equivalence are unqualified.
This is an area comparison, not an SRAM implementation or fit claim.
No SRAM macro was introduced; the production packet-memory emission is unchanged.


## Latest measured block areas

Commands, source hashes, corner and baseline commit are recorded in the final frozen
section of [the timing ledger](timing.md). These are **measured** mapped cell
areas, not routed footprints. Independent mapping/constant propagation means
the rows are not additive.

| Block | Measured um2 |
| --- | ---: |
| Retained SIE plus production cadence/replicas, external endpoint inputs | 55171.9616 |
| Chisel EP0, final frozen certificate-preserving mapping | 42922.7456 |
| IN packet buffer | 105051.2960 |
| OUT packet buffer | 102331.4432 |
| Combined engine | 282454.1888 |
| Complete wrapper, including CDC/events/clock requests | 319390.6240 |

The wrapper-minus-engine difference is **estimated** by subtraction:
319390.6240 − 282454.1888 = 36936.4352 um2. It is not an isolated glue-area
measurement because integration changes optimization and buffering.

Latest block-area command: `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d48-frozen-check-01`, base `15161bf897d1b4b4cba69030154daf89ee19ca12` plus its frozen hashes. SRAM replacement estimates above are unchanged; no macro swap or buffer RTL change occurred.

D51 latest measured areas use `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d51-frozen-check-01`, baseline `269fa0f7fe1b0560d58dd62c44ef01340e84b06b` plus frozen hashes. Only mapped enable-buffer sizing changes these areas; SRAM estimates remain unchanged.


## D52 fresh mapped block areas, 2026-11-19

**Measured** with `python tools/env/run.py run -- python3 hw/ip/usb/check.py
--output build/t19/d52-frozen-check-01`, baseline
acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf plus frozen source/flow hashes.
Pinned GF180 7-track SS/125 C/3.0 V, Yosys0.71+34/OpenSTA3.2.0;
mapped pre-layout cell area, no placement/parasitic or whole-chip fit claim.

| Block | Measured um² |
| --- | ---: |
| Standalone SIE/PHY fixture | 58611.8400 |
| EP0 | 45539.4240 |
| IN buffer | 108636.0576 |
| OUT buffer | 105938.1568 |
| Resume | 4783.3408 |
| Registers | 8365.9072 |
| Combined engine | 294903.1680 |
| Complete wrapper | 332364.2560 |

Estimated wrapper-minus-engine difference: 332364.2560 − 294903.1680 = 37461.0880 um². Integration changes optimization; this is not an isolated glue measurement.

Estimated comparison to the previously locked 1024×8 macro footprint: IN macro/buffer = 155413.553/108636.0576 = 1.4306; excess 155413.553 − 108636.0576 = 46777.4954 um².

Estimated comparison to the previously locked 1024×8 macro footprint: OUT macro/buffer = 155413.553/105938.1568 = 1.4670; excess 155413.553 − 105938.1568 = 49475.3962 um².

This only compares the macro in the pinned local inventory, not a proved global minimum across all GF180 macros. Macro peripheral logic, placement and routing would add costs. No SRAM swap is performed.
