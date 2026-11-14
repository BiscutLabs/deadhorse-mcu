# RISCay clocked baseline

T06 replay on 2026-11-14. Upstream source:
`4671317186003740ceb61360ba08c59bbdf10136`. Deadhorse execution started at
`4254f2ce5fb7ea3eec20752dee4cd3595e6c50db`. No upstream tracked source, test,
deadline, synthesis recipe or historical reference value was changed.

The clean-checkout Python and full gates pass. The final export is byte-identical
to the measured export, and all mapping inputs and tools match the successful
archived receipt. Task acceptance and review are recorded in the
[T06 report](../plan/tasks/reports/T06.md).

## Environment and tools

Measured execution platform (`uname -srmo`): Linux
`6.6.114.1-microsoft-standard-WSL2`, x86_64, GNU/Linux, through Docker on Windows.
All gates and EDA commands ran in T08's immutable Linux image:
`sha256:77bcdabbba96f6412120d23bcfcf31345ed46381aec3d8b8c6bd32ead33ccf73`.
Host operations only orchestrated containers and copied/read files.

| Tool | Measured version / recorded build input | Evidence |
| --- | --- | --- |
| Python | 3.12.3 | `python3.12 -V` |
| JDK | Temurin 21.0.12.1+1-LTS | `java -version`, upstream bootstrap |
| sbt | 1.12.4 | full-gate startup log |
| Scala / Chisel | 2.13.18 / 7.16.0, pinned build inputs | upstream `build.sbt` and pinned library source |
| firtool | 1.160.0, LLVM 24.0.0git | `firtool --version` |
| Icarus | 13.0 stable, source `dfeee909ed9f20b4870dd93423156c0170c0e1ff` | bootstrap and `iverilog -V` |
| RISC-V GCC | 13.2.0 | firmware report and toolchain lock |
| sv2v | 0.0.13 | `.tools/formal/sv2v --version` |
| Yosys, final gates | 0.33, `2584903a060` | `/usr/bin/yosys -V`; upstream CI selection |
| Yosys, area | 0.62, `7326bb7d6641500ecb285c291a54a662cb1e76cf` | recovered historical binary, `yosys -V` |

Versions are retained in `build/t06/versions.log`, bootstrap logs and gate
receipts. T08's default Yosys 0.71 was used by the first Python-only diagnostic
run; the final replay explicitly selects the documented gate's Yosys 0.33.
Neither version substitutes for the historical area mapper.

The original supplied RISCay workspace retained
`build/clocked-comparison/map-r2/receipt.json`. Its SHA-256 is
`93b7e79d49063b8d3d236e21b8f17c304c1e55ab938a92a8974e260caca63246`.
It identifies the original Yosys/ABC pair under Nix store item
`f1q0w7rd0a4ny4hqvfxlhs4cmariidcy-yosys-0.62`:

| File | Original receipt and replay SHA-256 |
| --- | --- |
| `bin/yosys` | `3a9560d83e60d9e98f34a03cdbedbb49adefc8a63096bd77c7c4108bc9ccdef2` |
| `bin/yosys-abc` | `c4ff60740cc2d6f0afe72f0dda58f65342cce10d64eddb6bf169577c7fa69f71` |
| `sv2v` | `b80a8ac6212aa72a196d9d6129cda35f16dbfa799ec61848c46321f845b6b635` |

Only Yosys/ABC, Yosys resources, and their matching runtime dependencies were
copied to `build/t06/nix/store`; sv2v remains in the upstream `.tools/formal` cache.
ELF interpreter/RUNPATH/NEEDED records determine
the shared-library closure. The embedded Python standard library is included;
site packages and cached bytecode are excluded. The copied subset is mounted
read-only at `/nix/store` inside T08. No binary was patched and no EDA tool ran
in the original workspace/WSL installation. WSL `readlink` was used only to
resolve source symlinks during copying.

Measured inventory: 1,229 runtime files, including 106 ELF files. The independent
review rehashed the exact inventory against `build/t06/nix-files.json` and
checked every recorded ELF dependency. The 23 PDK/SRAM assets in
`build/t06/reference-assets.json` match the upstream `physical/gf180/pdk-lock.json`
and `soc/sram-lock.json`. Tool and library files stay ignored under `build/`.

## Commands and measurements

Preflight: `curl -sI https://repo.maven.apache.org/maven2/ | head -1` returned
`HTTP/2 200`. Source preparation used the brief's public clone and exact checkout.
The Windows CRLF bootstrap was copied byte-for-byte except CRLF-to-LF conversion
to `build/t06/riscay_bootstrap.sh`; the tracked script was not edited.

The executed bootstrap commands, inside T08, are:

```sh
bash build/t06/riscay_bootstrap.sh build/riscay-mcu python-only
bash build/t06/riscay_bootstrap.sh build/riscay-mcu full
```

Final runs prepend `/usr/bin` to PATH, mount a Linux tmpfs at
`/work/build/env/tmp`, and use these JVM options:

```text
-Duser.home=/work/build/env/home
-Dsbt.global.base=/work/build/env/cache/sbt
-Dsbt.boot.directory=/work/build/env/cache/sbt-boot
-Dsbt.ivy.home=/work/build/env/cache/ivy
```

The container invocation uses `docker run --rm --platform linux/amd64 --network
bridge`, the repository bind at `/work`, `--tmpfs /work/build/env/tmp`, and the
immutable image above. `build/t06/run_full.py` supplies the environment, invokes
the full bootstrap, and records elapsed time with `time.monotonic()` in
`build/t06/full-wall.json`. The upstream wall-clock-based durations are retained
unchanged; the host/VM timestamp disagreement makes monotonic elapsed time the
reported duration.

Clocked export, with `build/riscay_env.sh` loaded in the upstream checkout:

```sh
python3.12 tools/sbt.py --bootstrap "clocked/runMain riscay.clocked.EmitClockedSoc build/export/clocked"
ls -l build/export/clocked
```

Area command from upstream `docs/build-and-test.md`, using a fresh output
directory and the absolute historical executable configuration:

```sh
RISCAY_PHYSICAL_TOOLS=/work/build/riscay-mcu/build/t06-physical-tools.json \
  python3.12 tools/map_clocked.py build/export/clocked build/map-clocked-runtime
```

The configuration selects `/nix/store/f1q0w7rd0a4ny4hqvfxlhs4cmariidcy-yosys-0.62/bin/yosys`,
its adjacent ABC, `/work/build/riscay-mcu/.tools/formal/sv2v`, and
`/usr/bin/timeout`. The mapper's original conversion and synthesis deadlines
are unchanged. It uses `gf180mcu_fd_sc_mcu7t5v0`, TT/25 C/3.30 V, with no
frequency target. All area figures below are **mapped, pre-layout, without
wire delay**, and exclude the same SRAM macros.

| Metric | Upstream documented value | Measured replay | Command / evidence |
| --- | ---: | ---: | --- |
| Python tests discovered/executed | 513 | 513 | bootstrap `python-only`; receipt and `python.log` |
| Permitted Linux skips | 1 | 1 | only `test_mounted_drive_hashes_original_windows_file` |
| Reference Scala tests | 268 | 268 in 29 suites, clean replay | bootstrap `full`; receipt coverage |
| Full-gate elapsed time | No reference duration; CI allows a cold job 60 minutes | 1222.066 seconds, warm pinned tool/dependency caches | monotonic wrapper, `full-wall.json` |
| Mapped logic, mm² | 0.5318332992 | 0.5315501184 | `map_clocked.py`; `area.json` |
| Architectural storage bits | 2,977 | 2,977 | `area_ratio.py`; raw storage inventory |
| Storage area, mm² | 0.2041777472 | 0.20417774719999998 | `area_ratio.py`; floating-point representation |
| Periodic clock sinks | 2,979 | 2,979 | mapper `clocks.json`; includes SRAM clocks |
| SRAM macros | 3 | 3 | mapper inventory |
| SPI boot ROM, bytes | 4,224 | 4,224 | mapper/export metadata |
| Event-loop firmware image, bytes | 728 | 728 | bootstrap `build/ci-bootstrap/event_loop/report.json` |

Historical values come from upstream `docs/area-ledger.md`,
`docs/desync-ledger.md`, and the brief/bootstrap record. Calculated from the
measured area, `(0.5315501184 - 0.5318332992) / 0.5318332992 * 100` is
**-0.0532461582%**, within the brief's unchanged **0.1% tolerance**. The historical
number was not replaced. `build/t06/baseline-comparison.log` records explicit
area-tolerance and exact architectural-bit assertions passing.

Storage was read with the upstream command:

```sh
python3.12 tools/area_ratio.py build/map-clocked-runtime/netlist.json \
  build/map-clocked-runtime/netlist.json \
  --liberty .tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib \
  --liberty .tools/gf180-sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1__tt_025C_3v30.lib
```

Only its raw inventory/storage measurements are used here. Its ratios of one
are self-comparisons, not evidence of agreement with the historical area.

## Export inventory

Measured with `python3 build/t06/collect_mapping.py` from the successful
clocked export. Paths are relative to `build/export/clocked`; sizes are
bytes. These generated files remain under the archived checkout.

| File | Bytes |
| --- | ---: |
| `ClockedControl.sv` | 83242 |
| `ClockedCore.sv` | 49951 |
| `ClockedElapsedTicks.sv` | 12099 |
| `ClockedFabric.sv` | 145331 |
| `ClockedGate.sv` | 8656 |
| `ClockedHousekeeping.sv` | 14930 |
| `ClockedI2cTarget.sv` | 55063 |
| `ClockedSampleScaler.sv` | 5464 |
| `ClockedSoc.sv` | 28100 |
| `ClockedSpiAdc.sv` | 9095 |
| `ClockedSram.sv` | 14667 |
| `ClockedSram_1.sv` | 12708 |
| `ClockedWake.sv` | 7934 |
| `chip/ClockedSocChip.sv` | 2740 |
| `chip/README.txt` | 759 |
| `chip/riscay_lf_osc.v` | 282 |
| `chip/riscay_lf_osc_model.sv` | 1116 |
| `chip/riscay_reset_hold.sv` | 853 |
| `chip/riscay_service_osc.v` | 485 |
| `chip/riscay_service_osc_model.sv` | 988 |
| `chip/riscay_supply_monitor.v` | 259 |
| `chip/riscay_supply_monitor_model.sv` | 959 |
| `clocked.json` | 222 |
| `filelist.f` | 273 |
| `gf180mcu_ocd_ip_sram__sram1024x8m8wm1.sv` | 22050 |
| `ports.json` | 6077 |
| `sram.json` | 518 |
| `verification/assert/layers-ClockedSoc-Verification-Assert.sv` | 377 |
| `verification/assume/layers-ClockedSoc-Verification-Assume.sv` | 377 |
| `verification/cover/layers-ClockedSoc-Verification-Cover.sv` | 374 |
| `verification/layers-ClockedSoc-Verification.sv` | 238 |

## Retained attempts and clean replay

All initial attempts are preserved under
`build/t06/attempts/riscay-mcu`, including the successful full gate and mapping.
The original receipt bytes were not rewritten: paths beginning
`/work/build/riscay-mcu` in those receipts resolve to this archive prefix when
auditing them. Nix paths resolve to the copied store. No failed evidence was
deleted or filtered out of an acceptance result.

The successful mapped receipt is
`build/t06/attempts/riscay-mcu/build/map-clocked-runtime/receipt.json`, SHA-256
`372763ab4f41abebbd3f3724ff285a6f73fac956b8be298aa77e0d833a11d8f4`.
`python3 build/t06/collect_mapping.py` verified all 43 recorded input, tool and
output hashes after archival. Its evidence is in `build/t06/mapping-evidence.json`.

A fresh clone at the canonical path reuses the pinned tool/dependency caches,
with no previous RISCay design/test build outputs, targets or receipts. It reran
the original Python/full gates with the tooling fixes. Final receipts are
`build/riscay-mcu/build/python-20261114-191203/receipt.json` and
`build/riscay-mcu/build/ci-20261114-191306/receipt.json`, both `pass`.
`python3 build/t06/check_final_receipts.py` checks the complete, nonempty receipt
glob without exclusions, the required receipts and counts, and an unchanged
upstream source checkout. It passed; the literal brief's receipt command prints
`['pass', 'pass']`.

The separate final export passed again. `python3 build/t06/verify_final_export.py`
verified the exact set and bytes of all 31 export files, regenerated the mapper's
digital/reset shell inputs with the unchanged upstream generator, checked all
36 mapping inputs/tools against the original receipt, and rehashed all 1,229
runtime files. No source-text behavior oracle is used: these are artifact
identity checks. The measured mapping was not rerun after the clean checkout;
its unchanged inputs and preserved outputs were validated instead. Logs are
`build/t06/final-acceptance.log` and `build/t06/final-export-identity.log`.

The retained tooling failures are:

- CRLF caused `set: pipefail: invalid option name`; the LF copy fixes invocation.
- An initial full attempt was stopped during compilation because sbt ignored
  shell `SBT_OPTS` and cached under `/root`. JVM properties put caches in the repo.
- `test_ci` rejected a newly written fixture as stale with
  `CI_MISSING_FRESH_SUITE:riscay.Chip`, before Scala ran. The timestamp probe
  observed host/VM disagreement; it did not reproduce that exact stale offset.
  The unchanged test passed on native tmpfs, followed by the complete recovery
  gate. The failed receipt remains in archived `build/ci-20261114-183302/`.
- The first mapper launch failed before synthesis with
  `ModuleNotFoundError: No module named 'encodings'`. Supplying the matching
  embedded-Python runtime fixed startup. Its failed receipt remains in archived
  `build/map-clocked/`.

This is reproduction of the upstream clocked reference, not adoption into
Deadhorse or qualification of the new cores, reset/sleep behavior, timing,
physical implementation or flight application.
