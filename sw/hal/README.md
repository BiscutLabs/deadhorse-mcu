# hal

Peripheral drivers and hardware abstraction.

`adc_convert.h` converts a raw12-bit ADC code using caller-supplied rational
gain and signed offset. It performs no MMIO, embeds no board calibration,
and returns false for invalid input without changing the caller's output.
Results wrap to unsigned32bits, matching the legacy hardware arithmetic.
For example, the legacy board conversion passes numerator25300,
denominator4095 and offset0; those values are firmware parameters, not a
generic sensor specification.

Run `python tools/env/run.py run -- python sw/hal/tests/test_adc_convert.py
--output build/<fresh>` for exhaustive raw-code and arithmetic-boundary
checks, including a separately compiled faulty result through the same oracle.
The D71 production ADC now returns raw codes at0x10;0x14 is retired and
returns bus errors. See [the ADC contract](../../hw/ip/adc/README.md).
Link the matching compiler runtime (`-lgcc`) for wide integer arithmetic.
The focused check also compiles/links for RV32E/ilp32e and RV32IMFC/ilp32f;
these are link checks, not firmware execution or latency measurements.
