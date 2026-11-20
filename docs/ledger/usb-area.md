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


## Historical D51 measured block areas

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

Historical D48 block-area command: `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d48-frozen-check-01`, base `15161bf897d1b4b4cba69030154daf89ee19ca12` plus its frozen hashes. SRAM replacement estimates above are unchanged; no macro swap or buffer RTL change occurred.

The historical D51 table above uses `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d51-frozen-check-01`, baseline `269fa0f7fe1b0560d58dd62c44ef01340e84b06b` plus frozen hashes. Only mapped enable-buffer sizing changes these areas; SRAM estimates remain unchanged.


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


## D53 measured candidate, 2026-11-19

Measured by the D53 frozen USB aggregate command and base/hashes/corner in the
timing ledger. Mapped pre-layout cell areas; no placement or whole-chip fit claim.
D52 comparison uses its preserved frozen receipt. Percent reduction is estimated
as 100×(D52−D53)/D52 from the measured areas; a negative value is an increase.

| Block | D52 measured um² | D53 measured um² | Estimated reduction % |
| --- | ---: | ---: | ---: |
| control | 45539.4240 | 46165.0560 | -1.374 |
| in | 108636.0576 | 39542.1376 | 63.601 |
| out | 105938.1568 | 38339.1680 | 63.810 |
| resume | 4783.3408 | 4783.3408 | 0.000 |
| engine | 294903.1680 | 156976.5568 | 46.770 |
| registers | 8365.9072 | 8365.9072 | 0.000 |
| usb | 332364.2560 | 197043.3472 | 40.715 |
| sie | 58611.8400 | 58260.6080 | 0.599 |

Estimated wrapper-minus-engine difference is 197043.3472−156976.5568=
40066.7904 um². Integration changes optimization, so this is not an isolated
measurement of CDC/event/clock-request glue.

The 16-byte candidate materially reduces storage area but does not close timing,
packet proofs or protocol qualification. No SRAM macro swap is performed.

Fresh local catalog command: `python tools/env/run.py run -- python3
scratch/t19_d53_sram_area.py`, receipt `build/t19/d53-sram-area-01/result.json`.
Both preserved SRAM archives were checked against the pinned SHA-256 values
above and the bootstrap's release commit; all 28 LEF views were rescanned.
The smallest footprint is still `gf180mcu_ocd_ip_sram__sram256x8m8wm1`:
measured LEF dimensions 301.30×224.93 um, estimated footprint
301.30×224.93=67771.409 um². It accommodates the 17-address candidate ring.
This supersedes D52's limited 1024×8 comparison; the complete pinned catalog
was already documented at the top of this ledger.

Even this smallest macro alone exceeds the whole measured candidate buffer:
estimated excess is 67771.409−39542.1376=28229.2714 um² for IN and
67771.409−38339.1680=29432.2410 um² for OUT. Separate per-buffer macros cannot
reduce area at this size before adaptation/scheduling overhead. Sharing a macro
is a different architecture and is not assessed or implemented here. Macro
footprints and mapped standard-cell sums are pre-layout comparisons, not a
physical integration or timing qualification.


## D54 retry lifecycle, 2026-11-19

Measured by `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d54-frozen-check-03`, base commit `c20e625ea44baaf65c9a523f7a9e12fb070dee22` plus the receipt's exact frozen source hashes. Fast CI independently repeats the same measurements. GF180 7-track SS/125 C/3.0 V, Yosys 0.71+34/OpenSTA 3.2.0, mapped pre-layout cell area/delay and ideal clocks; no routed or board signoff. Budgets remain estimated 0.60×1000/48=12.5 ns full-rate and 0.60×4×1000/48=50 ns for certified compatible pairs; other domains retain existing limits.

| Block | D53 measured um² | D54 measured um² | Estimated change % |
| --- | ---: | ---: | ---: |
| control | 46165.0560 | 46165.0560 | 0.000 |
| in | 39542.1376 | 39875.8080 | 0.844 |
| out | 38339.1680 | 38339.1680 | 0.000 |
| resume | 4783.3408 | 4783.3408 | 0.000 |
| engine | 156976.5568 | 160743.5200 | 2.400 |
| registers | 8365.9072 | 8365.9072 | 0.000 |
| usb | 197043.3472 | 198496.5696 | 0.738 |
| sie | 58260.6080 | 66591.3920 | 14.299 |

Estimated percentage is 100×(D54−D53)/D53 using measured areas. The repair adds ownership state without new packet RAM. SRAM macros are unchanged; the D53 pinned-catalog footprint comparison remains historical evidence, not a new measurement.


## T19 D58/D59 pre-enable flags — 2026-11-19

Measured with `python tools/env/run.py run -- python3 scratch/t19_d58_measure.py engine`
and `usb`, base099c27f plus exact hashes in `build/t19/d59-timing-01`, GF1807-track
SS/125C/3.0V, mapped pre-layout. Engine160743.5200→160227.6480µm²; wrapper
198496.5696→197379.2128µm² versus historical D54. Calculated differences:
−515.8720µm² (−0.3209%) and −1117.3568µm² (−0.5629%). Ten physical P capture FFs
per block represent thirteen source flag identities after legal merging; the
added cadence strobe is separate. packetData remains full-rate. No SRAM change,
gated bank, physical area estimate or power measurement is claimed.

The frozen fast02 USB aggregate (`python3 hw/ip/usb/check.py --output build/t19/d59-frozen-fast-02/fast/usb`, invoked by the pinned fast tier) reproduces these measured engine/wrapper areas exactly. Full fresh per-block areas and path classes are listed in the T19 report. No physical layout or SRAM substitution was performed.
