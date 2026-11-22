# hal

Peripheral drivers and hardware abstraction.

`adc_convert.h` converts a raw 12-bit ADC code using caller-supplied rational
gain and signed offset. It performs no MMIO, embeds no board calibration,
and returns false for invalid input without changing the caller's output.
Results wrap to unsigned 32 bits, matching the legacy arithmetic.
For example, the legacy board conversion passes numerator 25300,
denominator 4095 and offset 0; those values are firmware parameters, not a
generic sensor specification.

Run `python tools/env/run.py run -- python sw/hal/tests/test_adc_convert.py
--output build/<fresh>` for exhaustive raw-code and arithmetic-boundary
checks, including a separately compiled faulty result through the same oracle.
The dedicated SPI-ADC hardware was retired by D74. Firmware reads external
converters through the general SPI host, with DMA where needed. This arithmetic
helper and its tests remain independent of the hardware and address map.
Link the matching compiler runtime (`-lgcc`) for wide integer arithmetic.
The focused check also compiles/links for RV32E/ilp32e and RV32IMFC/ilp32f;
these are link checks, not firmware execution or latency measurements.
