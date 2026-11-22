# PLAN03 production measurements

B4 mapped/digital measurements, 2026-11-22, on main `736ed5c` with unchanged
production RTL. The approved mapping follow-up closes the prior register-path
regression without changing RTL, assertions or limits. The failed experiment
remains in [soc-production-screen.md](soc-production-screen.md).

All timing and cell-area figures below are **measured** by the commands below:
pinned Yosys 0.71+34 and OpenSTA 3.2.0, GF180 7t5v0 SS/125 C/3.0 V. This is
mapped, pre-layout, ideal-clock screening with 0.5 ns input slew and 0.05 pF
output load. Assumed clocks: main 8/9 MHz, AON active service 1 MHz, USB 48 MHz.
This does not select the future oscillator. Six synchronous SRAM/ROM interfaces
are exposed; USB packet RAM remains standard cells. No chip physical signoff.

## Mapping and certificate

Fresh USB mapping reproduces the qualified mapped Verilog byte for byte,
including preserved resume decodes, its mapper target, enable replication,
fanout and sizing. It is bound at the production USB instance with owner=1.
Exact restoration recovers every other module/connection. Every USB cell,
pin and boundary port survives full-SoC mapping under a bijective net map.
The whole reset-buffer transformation is reconstructed independently; an
actual wrong-pin control rejects. The required enable replica remains present.

A proof-only metadata view reconstructs removed live aliases from checked
final pins. Missing live bits and conflicting aliases fail closed. Partially
dead vectors are listed, not restored. Reversing the added aliases/renames
recovers the actual graph exactly before unrelated ICG outputs are cut to
arbitrary values for local invariants. No assumptions are added. STA uses
the unchanged integrated netlist. Fresh source/mapped/reset/cadence/pre-enable
certificates and faults pass. The final attestation binds exact audited buffers,
aliases, certificates and producer hashes and rejects a wrong-alias control.

The existing all-state source/context proof binds the production and qualified
USB sources with no state/output exclusions or assumptions. Applied SDC audits
pass for measured 82,194 setup-4/hold-3 pairs and 2,500 setup-3/hold-2 pairs per
build; a wrong multiplier rejects. No new timing exception is introduced.

## Timing

Budgets are estimated as 0.60 x period. Existing USB ceilings remain unchanged.

| Domain/class | 8 MHz build, ns | 9 MHz build, ns | Budget / ceiling, ns | Result |
| --- | ---: | ---: | --- | --- |
| main RR | 64.830223 | 65.965767 | 75 / 66.666667 (8/9 MHz) | pass |
| aon RR | 63.095551 | 64.042114 | 600 | pass |
| USB CC | 20.921200 | 20.921200 | 50 / 50 | pass |
| USB CC_reset | 12.001124 | 12.001124 | 12.5 / 15 | pass |
| USB CF | 10.944381 | 10.944381 | 12.5 / 15 | pass |
| USB CP | 12.811203 | 12.811203 | 37.5 / 37.5 | pass |
| USB FC | 11.993650 | 11.993650 | 12.5 / 15 | pass |
| USB FF | 13.485458 | 13.485458 | 12.5 / 15 | warning |
| USB FP | 9.182744 | 9.182744 | 12.5 / 12.5 | pass |

| Class | Launch to capture, 8 MHz build | Launch to capture, 9 MHz build |
| --- | --- | --- |
| main RR | `_189568_/Q` to `_203660_/D` | `_191373_/Q` to `_197303_/D` |
| aon RR | `_193845_/Q` to `_194752_/D` | `_195676_/Q` to `_205471_/D` |
| USB CC | `subsystem.usb._7042_/Q` to `subsystem.usb._7596_/D` | `subsystem.usb._7042_/Q` to `subsystem.usb._7596_/D` |
| USB CC_reset | `subsystem.usb._7280_/Q` to `subsystem.usb._6543_/D` | `subsystem.usb._7280_/Q` to `subsystem.usb._6543_/D` |
| USB CF | `subsystem.usb._7254_/Q` to `subsystem.usb._6522_/D` | `subsystem.usb._7254_/Q` to `subsystem.usb._6522_/D` |
| USB CP | `subsystem.usb._7057_/Q` to `subsystem.usb._7683_/D` | `subsystem.usb._7057_/Q` to `subsystem.usb._7683_/D` |
| USB FC | `subsystem.usb._7609_/Q` to `subsystem.usb._7435_/D` | `subsystem.usb._7609_/Q` to `subsystem.usb._7435_/D` |
| USB FF | `subsystem.usb._6398_/Q` to `subsystem.usb._7356_/D` | `subsystem.usb._6398_/Q` to `subsystem.usb._7356_/D` |
| USB FP | `subsystem.usb._7583_/Q` to `subsystem.usb._7683_/D` | `subsystem.usb._7583_/Q` to `subsystem.usb._7683_/D` |

Measured minimum same-domain register hold slack: +1.711015 ns main/AON,
+1.696710 ns USB. Data-net electrical reports have no violations. Measured
worst ICG enable setup/hold across builds: +99.175240/+4.729134 ns.

The supplemental zero-delay IO screen measures main IR 31.572651/29.496504 ns,
RO 60.152504/62.065704 ns; AON IR 1.108881 ns, RO 14.576858/14.639792 ns;
USB IR 7.699076 ns, RO 9.581448 ns and pad IO 4.400927 ns. These isolate data
delay. All-clock IO phase assignments are raw diagnostics, not actual interface
contracts. Raw IO hold -0.102503 ns, reset removal -0.975158 ns, artificial
cross-clock setup slacks and unbuffered gated-clock pulse violations remain
visible in boundary-8/9/sta.log. They are not qualified physical passes or
failures. Macro/pad contracts, reset sequencing, CTS/propagated clocks and
physical hold/RDC remain T33/T35/T38 obligations. No false paths or RTL hold
buffers were added to this screen.

## Area

Each actual mapped cell is counted once: exclusive backward endpoint cones,
plus explicit shared/unattributed rows. This is an allocation, not a sum of
standalone block areas. Values are measured mm2. USB block area includes its
app/AON glue; USB domain area counts the 48 MHz allocation only.

| Domain allocation | 8 MHz build, mm2 | 9 MHz build, mm2 |
| --- | ---: | ---: |
| main | 2.408042 | 2.403013 |
| output-only/unattributed glue | 0.013867 | 0.013744 |
| shared clock/reset/domain glue | 0.000786 | 0.000781 |
| aon | 0.726124 | 0.724989 |
| usb | 0.173989 | 0.173989 |
| Total logic | 3.322808384 | 3.316516941 |

| Block/cone allocation | 8 MHz build, mm2 | 9 MHz build, mm2 |
| --- | ---: | ---: |
| core (ibex_top) | 0.941262 | 0.940843 |
| subsystem.p (Pwm) | 0.317994 | 0.317955 |
| subsystem.liteHart (LiteHart) | 0.224527 | 0.225175 |
| subsystem.usb (Usb) | 0.205431 | 0.205431 |
| shared inter-block glue | 0.185692 | 0.181482 |
| subsystem.dma (Dma) | 0.178975 | 0.177583 |
| subsystem.flash (Qspi) | 0.131170 | 0.131209 |
| subsystem.timers (MainTimers) | 0.110331 | 0.110550 |
| subsystem.loader (RecoveryLoader) | 0.098468 | 0.097353 |
| subsystem.spi (SpiHost) | 0.078103 | 0.078869 |
| subsystem.mailbox (Mailbox) | 0.074865 | 0.074986 |
| subsystem.toMain (BusBridge) | 0.062765 | 0.062752 |
| subsystem.toAon (BusBridge) | 0.062506 | 0.062486 |
| subsystem.aonTimer (AonTimers) | 0.061573 | 0.061358 |
| subsystem.uarts_0 (Uart) | 0.059257 | 0.059382 |
| subsystem.uarts_1 (Uart_1) | 0.059231 | 0.059154 |
| subsystem.channels_1 (Watchdog_1) | 0.059119 | 0.058825 |
| subsystem.channels_0 (Watchdog) | 0.058998 | 0.058768 |
| subsystem.uarts_2 (Uart_2) | 0.058823 | 0.058588 |
| subsystem.i2c (I2cHost) | 0.057984 | 0.058280 |
| subsystem.mf (BusFabric) | 0.034471 | 0.033986 |
| subsystem.af (BusFabric_1) | 0.026571 | 0.026509 |
| memory (SocLocalMemory) | 0.025991 | 0.026345 |
| subsystem.serial (BusFabric_2) | 0.024446 | 0.024492 |
| subsystem.gpio (Gpio) | 0.019711 | 0.019759 |
| subsystem.powerFabric (BusFabric_5) | 0.018007 | 0.017957 |
| subsystem.ioFabric (BusFabric_4) | 0.016789 | 0.016760 |
| subsystem.gateway (BusFabric_3) | 0.015742 | 0.015863 |
| output-only/unattributed glue | 0.013867 | 0.013744 |
| subsystem.boot (BootControl) | 0.011626 | 0.011613 |
| unattributed state | 0.008109 | 0.008026 |
| subsystem.p_1 (Pinmux) | 0.007826 | 0.007813 |
| subsystem.retained (SocRetainedMemory) | 0.005253 | 0.005225 |
| subsystem.slot (SocResetSlot) | 0.005227 | 0.005227 |
| Remaining small CDC/reset cones | 0.002099 | 0.002171 |

The [plan 08](../plan/08-physical-verification.md) budget is estimated
**12.783522 mm2**, leaving **0.136478 mm2** against 12.92 mm2. It includes
measured logic, pinned SRAM footprints, estimated scan uplift and named
assumed digital/analog/pad/routing allowances. This is not a layout-fit result.

## Production performance

Actual DeadhorseSoc, real USB and hart identity, real recovery-wire loader,
lite release and ROM-to-SRAM copy; no fake responder, SRAM preload or boot
bypass. Peripherals are idle except boot and marker traffic. GPIO value/enable
writes carry markers outside timed windows; the real pin mux stays disconnected,
checked throughout simulation.

Complete main-loop instruction sequences match the reference except RAM LUI
relocation; control/scenario objects are byte-identical. Unchanged
iteration_metrics/loop_samples count input preparation, control, checksums and
backedge, exactly 40 iterations per mode. Only three authenticated mode-store
addresses are relabelled in a copied analysis view for the historical helper;
raw PCs, instructions and cycles are unchanged.

| Workload, both builds | Measured mean cycles | Measured worst cycles | T13 round-2 worst | Estimated overhead |
| --- | ---: | ---: | ---: | ---: |
| Fixed point | 3879.791667 | 4350 | 4350 | 0% |
| Hard float | 7809.833333 | 9007 | 8973 | 34 / 8973 = 0.3789156% |

D75 retains the historical accepted 4821-cycle result, not a substitute for
these observations. Both meet the unchanged 10% overhead criterion. At assumed
9 MHz, worst times are estimated 483.333333 us fixed and 1000.777778 us float.
Q16 remains open; no further micro-optimisation is authorized by these results.

No traps/interrupts; stack stays within 2 KiB and sections fit the 16 KiB model.
Target-ISS checksums, wrong-checksum and omitted-iteration controls pass. A
separate comparison matches every workload PC/next-PC, 58,316 floating writes
and FS state, including 12,560 fused instructions, and rejects a wrong result.
This is not full production integer/memory/FCSR lockstep.

Diagnostics are preserved: a scratch-marker choice changed fixed-loop register
allocation and was discarded; retained-memory markers correctly trapped under
the actual ownership policy. The uncontracted native host gave different float
hashes; exact target QEMU and the native FMA-enabled diagnostic both reproduce
production. No RTL or numeric tolerance changed.

## Commands and evidence

All commands use `python tools/env/run.py run --`. Exact executed producer sources
are retained in [measurements](../../hw/top/reference/measurements/README.md), with
original-path hash identities. These are scoped experiments, not a replacement
CI path; generated evidence is under build/plan03.

```text
python scratch/plan03_usb_mapping.py
python scratch/plan03_production_map06.py
python scratch/plan03_mapping_audit.py
python scratch/plan03_production_sta.py build/plan03/production-measure06 8
python scratch/plan03_production_sta.py build/plan03/production-measure06 9
python scratch/plan03_production_certificate09.py 8
python scratch/plan03_production_certificate09.py 9
python scratch/plan03_mapping_attestation.py 8
python scratch/plan03_mapping_attestation.py 9
python scratch/plan03_production_classes06.py 8
python scratch/plan03_production_classes06.py 9
python scratch/plan03_class_audit07.py 8
python scratch/plan03_class_audit07.py 9
python scratch/plan03_production_boundary.py 8
python scratch/plan03_production_boundary.py 9
python scratch/plan03_area_partition.py
python scratch/plan03_area_budget02.py
python scratch/plan03_production_benchmark04.py
python scratch/plan03_qemu_checksums.py
python scratch/plan03_qemu_checksums02.py
python scratch/plan03_run_production_benchmark06.py 8
python scratch/plan03_run_production_benchmark06.py 9
python scratch/plan03_float_reference02.py sim-8c
python scratch/plan03_float_reference02.py sim-9c
```

Final timing/area: production-measure06, certificate09-8/9, transform audits,
classes-8/9 exception-audit02 and area-budget02. Fresh USB mapping:
production-measure04/usb-mapping. Final performance: production-performance04/
sim-8c and sim-9c. Earlier diagnostics remain. Independent review recomputed
paths, area, scan uplift and all four raw-trace cycle results. The transitive source/evidence inventory is `build/plan03/b4-seal02.json`;
independent review verified all 3,613 files before B5. Subsequent tracker/report
updates do not change the measured RTL or producer snapshots. B3 fast CI passed with its
twelve explicit T14/T17 deferrals; full CI has not run.
