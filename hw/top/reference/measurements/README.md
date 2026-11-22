# PLAN03 measurement source snapshots

These are the exact executed source files behind the B4 measurements at
736ed5c, preserved for review and later reproduction. They are measurement
producers, not generated results or production RTL. Their original working
location was scratch/. Hashes below bind the tracked copies to those executed
files; original receipts retain their original paths.

Run from the repository root through the pinned environment. The historical
commands and limitations are in [the measurement report](../../../../docs/spec/soc-production-measurements.md).
To replay the recorded commands, copy these sources to scratch/ without
overwriting different local files. A replay needs fresh output directories;
these scripts deliberately refuse to overwrite existing evidence. A clean
replay of these tracked copies has not been run; the original executions and
byte identity of these copies were verified.

Dependencies/order:
1. B3 USB/check and fast receipts under build/plan03/fast02, and existing
   pinned environment/PDK. Emit DeadhorseSoc at 8 and 9 MHz with the production
   emitter into production-measure01/emit-8 and emit-9. Run hierarchy import,
   then the original production_map producer for the six macro socket records.
2. Create production-measure03 and run the source/context binding. Fresh USB
   mapping, production_map06, transform audit, per-frequency STA, certificate09,
   attestation, class constraints, exception audit and boundary diagnostics
   follow in the report's order. Area partition and area_budget02 consume these.
3. production_benchmark04 prepares exact reference and production firmware;
   qemu_checksums runs the reference. Its compressed-store parser diagnostic is
   preserved: checksums02 corrects analysis of those traces without rerunning
   simulation. run_production_benchmark06 uses the Chisel emitter and final C++
   driver for each frequency; float_reference02 compares each final trace.
   The older C++ driver is retained only to identify the diagnostic run.
4. The seal producer inventories transitive source and build evidence. Use a
   new seal name after final documentation. build/ evidence is never committed.

No new timing exceptions, assumptions, limits, or RTL changes are introduced
by these sources. The preparation paths are intentionally historical; these
are not a new CI tier or a claimed single-command production physical flow.

## Executed source identity

| Source (originally scratch/) | SHA-256 |
| --- | --- |
| `plan03_usb_mapping.py` | `289a0e542e99ddef63ba5983aa240aa93cbd6aa0ff4ea2a39049adc899ff2170` |
| `plan03_production_hierarchy.py` | `995a0cec38924bec77e0ade22a92ca80115b59534a7010b7d47846744369a213` |
| `plan03_production_map.py` | `bd3498962369c540b2184f55415c2b5fa0e673a09f8314dc38edf24ee47f2225` |
| `plan03_production_map06.py` | `c5f19eae6c881327eddadbaa4acacac9d86bae3a4c51117a6142125cb87674e9` |
| `plan03_usb_context.py` | `20fe385e3fdf415a1c2cb89915c2df80f9ebc96dd7bb91dcb8e61e4b337c9fdf` |
| `plan03_mapping_audit.py` | `6580e0c20dddd5266edd3b65d05ab70daf0a8e33b5b543b80071057b0f75d476` |
| `plan03_production_sta.py` | `4a2e5edc48ffd0721b8cecc286336ad37c13e2daf1b7e4570860720ec874acde` |
| `plan03_production_certificate09.py` | `2ecc69d5eaebcdfb34e222759c63e472334a1fa854c375e555d034aa2ff25f76` |
| `plan03_mapping_attestation.py` | `7f8d8b892c40d6ea9c311e5de4d15c3b9e19aadb1c5e7913af6f639f495a1bf3` |
| `plan03_production_classes06.py` | `270a997705903ca530b6506adb36f11f3e7fd8be50bf38e3c65903158ec1a6c9` |
| `plan03_class_audit07.py` | `db4f6b772f5c4a2cf34aa2c785d0cb6c1e5fa07691d978f38f60d8dbf60c8201` |
| `plan03_production_boundary.py` | `6d66ccfd8a95ceda035ee1d1f30106b4e4c17cefbebb6d95c2fa1fe9015e4441` |
| `plan03_area_partition.py` | `02a17ecda69ca53fa6643ab487fb21bdf59b7032f05218db5f1c4379545bae69` |
| `plan03_area_budget02.py` | `fd86720405a043e8f5e263c61da5f01180f06a5b94b85e79d00b2b2e6c286ba7` |
| `plan03_production_benchmark04.py` | `a553e68191268ffe5abc52c2733780cd5eb3372aab2b62098501a991d172e070` |
| `plan03_qemu_checksums.py` | `0a1d07b57b738ae8dfafce673920e5b2b0ac1f48a3df51c3a766c4939c53e896` |
| `plan03_qemu_checksums02.py` | `4aa5e83f8e0a0b509dd99c93063675a4e146d2ccbdc6b6dc819b0d3af2799d52` |
| `plan03_run_production_benchmark06.py` | `77f6190d018153acb4b9602ace79b5740c4473eba866461daa663f88cae35416` |
| `plan03_float_reference02.py` | `6e452a651bb16ef1a7ff4f816432fcd3394880c73754bb618110fc8012b45cd3` |
| `EmitProductionBenchmark.scala` | `5d6d1309ae37db382d2665b180cc21f8738020950e470b78091e9d803883017a` |
| `production_benchmark.cpp` | `a931bf2c23acb53e4a4f80f2f2a991646f839944f0e5b44205593efe72df8f96` |
| `production_benchmark_v1.cpp` | `66a3ce60abb55a8ac66e89b8f0872fd9f96be54f083a7733c190e232e77feb63` |
| `plan03_b4_seal.py` | `534197b010b4f405354fbe165bb3da85567aeb8e91cf9e79959d4b3ae8425ce9` |
