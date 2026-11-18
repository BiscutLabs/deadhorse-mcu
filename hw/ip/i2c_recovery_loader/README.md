# Lite I2C recovery loader

An external I2C programmer can recover a lite image, verify its CRC, request
execution and lock programming through this standalone endpoint.
RecoveryLoader instantiates the adapted clocked target and loader control.
The [contract](../../../docs/spec/i2c-recovery-loader.md) defines the host
ABI, memory handshake, wake boundary and reset causes.

Deadhorse's shared synchronizers sample the pins. Inverting each signal on
both sides of the synchronizer preserves the idle-high reset history. Frame
and read-start signals stay in the service-clock domain. SDA pull-low is
registered. Program SRAM, the lite CPU and the clock/reset controller attach
at the documented ports. The included LICENSE reproduces the original licence.

## Pinned adoption inputs

RISCay revision `4671317186003740ceb61360ba08c59bbdf10136`, Apache-2.0. The table identifies the original Git blobs. [Provenance](provenance.json) maps the blobs to adapted files and records the changes.

| Upstream path | Git blob |
| --- | --- |
| `designs/clocked/src/main/scala/riscay/clocked/ClockedI2cTarget.scala` | `db17c78eb8be1ca9038316f432cea937750aa44a` |
| `designs/clocked/src/main/scala/riscay/clocked/ClockedFabric.scala` | `31394f25f456a2fa6244832829b7a093509471a2` |
| `designs/clocked/src/main/scala/riscay/clocked/ClockedControl.scala` | `a3e4250c3bd4c40209dba7f2ba5888b47e033c7c` |
| `designs/clocked/src/main/scala/riscay/clocked/ClockedSram.scala` | `e51caa29d5996182a7411460c9993eb91ab52056` |
| `soc/src/main/scala/riscay/soc/ControlSchema.scala` | `8f71444e7e993539d4c031c4ead6cd0f27759b69` |
| `soc/src/main/scala/riscay/soc/Platform.scala` | `e5984209aa269faf6273e48919bc7e92dd81f14d` |
| `shared/src/main/scala/riscay/HostSchema.scala` | `b73beb650bbc7401aeabd10d9a19b6f5fc161200` |
| `LICENSE` | `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64` |
