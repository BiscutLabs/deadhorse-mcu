# ADC raw acquisition evidence

T27 on main `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus receipt-bound
local sources. D71 now selects raw acquisition in production. Historical T21
denied/scaler evidence remains in its report and is not replaced here.

## Initial staged engine checkpoint (historical)

Measured command:

```
python tools/env/run.py run -- python hw/ip/adc/formal/check_raw.py --output build/t27/formal01
```

| Claim/job | Result | Engine | Measured wall seconds |
| --- | --- | --- | --- |
| First-discard publication, uncalibrated result, one-cycle completion, completed-frame pins/busy, sampled-edge count, serial data integrity, held result: seven assertions | proved, unbounded | ABC PDR | 4.670 |
| Actual raw capture bit-flip, data assertion `assert__chisel3_builtin_4` | intended fault rejected | BTOR btormc | 0.716 |
| First discard, valid all-ones and valid zero: three covers | covered | BTOR btormc | 0.916 |

Only assumption: reset_n starts low, then reset and all inputs are arbitrary.
The engine is manual-start at halfPeriodCycles4; full data/control widths,
no cutpoints. The cover/fault depth270 is estimated from two complete serial
frames (2×16×2×4=256edges) plus reset/launch/completion allowance; it does
not bound the unbounded proof. Existing120-second job caps are unchanged.
Exact source/artifact hashes and solver evidence are in the receipt. This
does not qualify the eventual raw MMIO wrapper, CDC, pads or integrated SoC.


## D71 production migration, 2026-11-21

All times below measured by these pinned-environment commands on the same
HEAD plus local receipt-bound sources; no CI or physical qualification.

```
python tools/env/run.py run -- python hw/ip/adc/formal/check_raw.py --output build/t27/engine02
python tools/env/run.py run -- python hw/ip/adc/formal/check_raw.py --case publication --output build/t27/publication01
python tools/env/run.py run -- python dv/soc/check_io_formal.py --output build/t27/owner-scale02 --cases adc_denied adc_scale
```

| Job | Assertions | Result | Engine | Measured positive wall seconds |
| --- | ---: | --- | --- | ---: |
| Raw serial engine | 7 | proved, unbounded | ABC PDR | 5.472 |
| Production publication registers | 4 | proved, unbounded | ABC PDR | 0.568 |
| Production owner-denial safety | 7 | proved, unbounded | ABC PDR | 0.465 |
| Retained historical scaler | 2 | bounded16 sampled edges | BTOR btormc | 1.817 |

Every job's covers and intended faults pass. Publication faults corrupt the
actual captured data or let ACK discard a simultaneous sample; they fail
assert__chisel3_builtin and assert__chisel3_builtin_1 respectively. Publication
covers reach an old unread sample with simultaneous ACK/new data, overrun,
and acknowledged nonzero sequence. Full45-bit production state, arbitrary
sample/data/ACK/reset after initial reset; no producer-spacing assumption or
cutpoint. Cover/fault depth8, positive unbounded, cap120seconds.

Engine assumptions/scope remain as above. Denied safety assumes only initial
reset and maps origin0 to1 against owner0 to cover every non-owner tag. The
legacy scaler still checks one arbitrary captured sample over16edges; it is
not production hardware and contributes no raw-path proof claim. Its original
assertions/fault remain unchanged. Owner-scale01 had the same passing model;
owner-scale02 refreshes the receipt after additional test-only cadence logging.

The actual Adc wrapper directly connects registered raw engine result/valid
and READ_ACK to AdcSampleState in the same AON/reset domain. Independent wire,
MMIO and SoC simulations check this composition, including exact ACK/W1C
publication collisions; no unbounded whole-SoC composition claim follows.
