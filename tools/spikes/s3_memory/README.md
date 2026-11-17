# S3 memory measurement

Run in the pinned Linux environment:

```sh
python3 tools/spikes/s3_memory/check.py --output build/s3
```

Use a fresh output directory. The driver records input hashes, exact child
commands, results and elapsed time. A failed check, missing receipt or unknown
result fails acceptance. `review_required` is non-passing: the brief requires
review before optimizing an initial hot set above 12 KiB. The 16 KiB performance
and 3 KiB lite baselines remain unchanged.

## Scope

- Separate RV32IMFC hard-float measurement firmware, at `-Os` and `-O2`, includes
  the unchanged Bosch BMI270 driver and real initialization data, representative
  acquisition, control/navigation, DMA configuration storage, actuator publication
  and trap/context work. Historical flight measurement sources remain unchanged.
- The Bosch input is fetched by pinned commit and file hashes into `build/`.
  No vendor file is patched. The configuration stays cold and is uploaded in
  bounded chunks. A freestanding compatibility header/runtime supplies only the
  C support needed by the unchanged driver; this is not a new libc dependency.
- QEMU supplies instruction execution and observable outputs. Its memory layout
  and modeled sensor registers are test infrastructure, not the Deadhorse SoC.
  An ecall exercises trap entry; it does not measure external interrupt latency.
- The lite fixture is a representative retained-workload allocation, not the
  complete boot/recovery firmware. Final image fit needs the later implementation.
- Banked access and flash scheduling are executable organization models checked
  against independent byte/arithmetic oracles and injected faults. They do not
  qualify an SRAM macro, RTL controller, hardware latency or power consumption.

Report hot text and constants, cold text and constants, mutable state/buffers,
and stack separately. Include hot-call closure and explicit callback targets.
GCC `-fstack-usage` reports individual frames; it does not by itself establish
whole-program stack usage. Observed stack coverage, any conservative estimate,
and interrupt/nesting assumptions must remain distinct. Hot code is the sum of
reachable ELF function sizes; final SRAM placement and alignment padding are
not measured. The remaining ELF text includes startup and linker padding.

## Flash assumptions

No flash part or board UART allocation is selected. Profiles explicitly state
command/address/data widths, dummy clocks, serial clock frequency, transaction
and page bounds, program/erase busy time, capacity and queue allocation. Logging
uses a separate chip select. Busy time of that device must not hold the shared
bus; XIP may wait for an already-started bounded transfer. The hot loop does not
fetch from XIP or block on logging. Overflow drops and counts records.

Sustained-rate scenarios require the stated pre-erased logging region and page
batching. Erase-during-flight stress is separate and must report lost records.
Assumed QSPI clock rates are not a claim that the selected CPU divider provides
them. Model observations are not device measurements or guaranteed worst-case
flight performance.

## Physical evidence

No SRAM macro is qualified by this spike. The plan's inherited footprint gives
an **estimate** of `16 * 155414 um2 = 2.486624 mm2` for performance memory and
`3 * 155414 um2 = 0.466242 mm2` for the retained capacity, before wrappers/routing.
The footprint is an inherited planning input, not a fresh S3 measurement.
Power, access timing, banking overhead and retention remain unmeasured; neither
one-cycle access nor a power saving follows from word-wide organization.

## Sources and limits

- [Bosch BMI270 API, pinned release](https://github.com/boschsensortec/BMI270_SensorAPI/tree/41129fcfe39c583ee5462d79195741945d51c1fe)
- [Bosch BMI270 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi270-ds000.pdf)
- [GCC stack-usage semantics](https://gcc.gnu.org/onlinedocs/gnat_ugn/Static-Stack-Usage-Analysis.html)
- [GCC function/data sections](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html)
- [S3 brief](../../../docs/plan/tasks/S-spikes.md#s3-memory)

This is a measurement fixture, not production firmware, an airframe-control
validation, SRAM hardware acceptance or a completed full-chip formal proof.
No new RTL is introduced; formal properties for a future production SRAM/QSPI
controller belong to its integration brief.
