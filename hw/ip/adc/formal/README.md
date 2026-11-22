# T21 ADC properties

## T27 raw engine

`python3 hw/ip/adc/formal/check_raw.py --output build/<fresh>` checks the
production-selected raw engine at halfPeriodCycles4, with initial reset low and arbitrary
reset/start/allow/MISO thereafter. No other assumptions or cutpoints.
The pin observer reconstructs the serial input word independently; seven
assertions check publication after first-frame discard, calibration flag,
single-cycle completion, idle clock/CS and busy during completion, sixteen
sample edges, raw data integrity and held data. Three covers reach first
discard and subsequent zero/all-ones results. Flipping a bit in the actual
captured raw register must fail the data-integrity assertion.

The initial run `build/t27/formal01/result.json` proved the assertions with
ABC PDR and reached the covers/fault using BTOR within the existing120-second
caps. The270-edge cover/fault bound is estimated from two frames:
2×16×2×4=256sample edges plus reset/launch/completion allowance. It is not
a bound on the unbounded proof. No shared MISO synchronizer, registered pad
wrapper or physical interface is qualified by this engine-only result.
The current production wrapper uses this mode. Owner safety and legacy
arithmetic checks below remain separate.

## T27 publication state

`python3 hw/ip/adc/formal/check_raw.py --case publication --output build/<fresh>`
instantiates the actual AdcSampleState used by Adc. It proves raw/sequence
hold or update together, new-data priority over READ_ACK, and overrun behavior.
Only initial reset low is assumed; sample, data, ACK and subsequent reset are
arbitrary. No assumption on producer spacing and no cutpoint. The proof uses
full production widths. Covers reach ACK/new-data collision with an old unread
sample, overrun and acknowledgement after publication. Actual capture-bit and
ACK-priority faults must fail their respective data/unread assertions.
The positive is unbounded; cover/fault depth8 supplies room for reset plus
successive sample/ACK operations under the unchanged120-second cap.
This internal-state proof composes with the engine result through direct
same-clock wiring; wire/MMIO/SoC tests check that binding and W1C/set collision.

## Production owner safety and legacy arithmetic

`python3 dv/soc/check_io_formal.py --output build/<fresh> --cases adc_denied adc_scale`
runs focused checks in the pinned environment, without CI.

Denied-owner safety covers every non-owner tag (input0 maps to1 against owner0),
arbitrary MISO and bus signals. It asserts immediate denial, zero read data,
inactive pads and IRQ. Bypassing ownership must fail response/state assertions.

Scaling captures one arbitrary 12-bit input at start, then checks completion
after twelve radix steps and exact `floor(raw * 25300 / 4095)`. This is **bounded
to 16 sampled edges**, enough for this configured single conversion; it is not
an unbounded restart/continuous-operation proof. Corrupting the actual scaler
result bit must fail value equality. The all-ones sample completion is covered.
Wire-level mode0 framing, first discard, continuous/manual scheduling and result
overrun have independent external-device simulation checks.

Reset is initially low and arbitrary thereafter. No further formal assumptions.
PDR for denied safety; BTOR for bounded scaling/covers/faults; cap120 seconds.
Exact property/assumption inventories, source/configuration/artifact hashes and
concrete intended fault witnesses are mandatory. No external ADC compatibility,
board calibration, analog metastability or physical pad timing claim.
