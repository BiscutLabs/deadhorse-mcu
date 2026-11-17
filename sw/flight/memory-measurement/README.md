# S3 representative memory measurement

This is a separate allocation fixture, not deployable flight firmware. It links
the unchanged historical `control_step.c` and `control_init.c` with RV32IMFC,
`ilp32f`, and both `-Os` and `-O2`. The historical `airspeed` input receives a
constant groundspeed proxy; no airspeed sensor is introduced. A representative
sum/difference converts the historical elevator/rudder outputs to two V-tail
commands. Neither the proxy nor this mix qualifies the airframe.

Run in the pinned container:

```sh
python3 tools/spikes/s3_memory/firmware.py --output build/s3-firmware
python3 -m unittest discover -s tools/spikes/s3_memory -p test_firmware.py
```

The output directory must be fresh. All downloaded vendor files, objects, ELF
files, compiler stack-usage records, QEMU traces, command logs and JSON receipts
stay under that directory. A verified prep cache under `build/s3-prep/upstream`
may supply the exact locked bytes; otherwise fetching needs network access.
`bmi270.lock.json` pins Bosch SensorAPI v2.113.0 and all six files by SHA256.
The driver and 8192-byte configuration are unchanged BSD-3-Clause material.
The driver includes `stdio.h` without using stdio declarations; the empty
compatibility header supplies that include only. The freestanding runtime
provides byte-copy/clear functions required by compiler-generated code.

The SPI/register model checks chip ID, dummy reads, reset, power-save delay,
configuration write addresses, 64-byte transfers, all 8192 delivered bytes,
configuration hash and resulting status. No 8 KiB configuration buffer is
allocated in SRAM. Timestamped sample bursts pass through the real Bosch
read/parser path. Python independently checks sample values, timestamps,
binary32 navigation accumulation, trap counts, all pre-commit observations,
atomic nine-channel publication and the buffer/DMA summary. The historical
control algorithm is exercised but is not independently requalified here.
Four separately compiled actual faults corrupt configuration bytes, delivered
sample bytes, publication order and the lite checksum; each must fail the
intended oracle check.

The firmware uses four bounded DMA configuration structures, not linked DMA
descriptors or production hardware DMA. Assumed capacities are 64-byte SPI,
128-byte GPS, 64-byte RC, eight 256-byte logging pages plus one 256-byte staging
page. Logging capacity matches the separate arbitration model; this fixture
does not implement its complete enqueue/drop controller. Sensor-model RAM is
reported separately and excluded from the candidate allocation, while its
reachable code and UART observation code are conservatively included. The real
SPI MMIO driver, complete navigation/scheduler and other sensor drivers remain
qualification gaps, so passing this fixture is not a complete firmware fit.

The hot loop is a separate function, including loop control and all reachable
callees. Object relocations and final linked branches form a conservative call
graph; the indirect Bosch read/delay callbacks are explicitly included.
All linked non-configuration constants count as hot, including cold-init
templates, to avoid optimistic constant placement. The ELF runs entirely in
QEMU DRAM; its execution addresses are not an MCU placement result.

An actual synchronous `ecall` enters a 256-byte full GPR/F-register/fcsr save
frame and returns through `mret`. This models conservative context storage,
not asynchronous pin arrival or latency. QEMU single-step SP traces measure
observed peaks. Allocation additionally reserves the deepest GCC static hot
call chain plus one full trap/handler at its deepest point, with `main` live.
That estimate assumes no nested traps and the listed callbacks. Cold-init stack
is observed only; error paths and future code can increase it. No QEMU clock or
instruction count is a Deadhorse cycle measurement.

The RV32E/ilp32e lite fixture measures only a concrete chunk/CRC/wake/calibration
subset with 128/32/64-byte buffers. It is not a complete bootloader, scheduler,
retained-core implementation or proof that all retained functionality fits.

Both the hot-code size and the candidate SRAM working set (hot text, constants,
state/buffers and reserved stack) are checked against the unchanged 12 KiB review
threshold. The retained subset is compared with 3 KiB. The runner returns
`review_required` with a nonzero exit when exceeded, preserving all measurements;
it never changes flags, buffers, code or limits to force a fit.
