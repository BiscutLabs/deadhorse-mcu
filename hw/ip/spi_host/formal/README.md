# SPI formal scope

`python tools/env/run.py run -- python3 hw/ip/spi_host/formal/check.py
--json build/t16/regmap/spi_host_regs.json --output build/t16/formal-new`
emits fresh models. Aggregate acceptance generates the map first.

| Role | Claim | Scope and method |
| --- | --- | --- |
| frame0 | Single selected CS, exact SCLK/MOSI bit timing, CS duration, hold demand, bus response accounting | Bounded 128 edges; mode0/CS0, H3, FIFO2, one arbitrary byte; scripted configuration; constant MISO1/timeNow0; sleep may assert after start |
| frame3 | Same public-pin contract in mode3 | Bounded 128 edges; mode3/CS1, otherwise same configuration |
| denied | Error/zero response and observable disabled-state preservation for denied accesses | Unbounded ABC PDR, owner0 and all denied tags1..7, FIFO2, arbitrary request/address/data/strobes |

Frame expectations use arithmetic edge positions from externally observed CS
assertion. They never read production state. Covers require a completed A5
frame and selected midpoint while sleeping; each frame fault inverts the real
production MOSI update. Denial covers exercise error responses and requests;
the actual owner-comparison bypass must produce a concrete counterexample.
BTOR btormc supplies bounded, cover and fault witnesses. Initial reset is low;
thereafter reset is arbitrary, with the HF reset qualification contract.
No assumption constrains a production internal signal. The denied harness
maps raw tag0 to1, covering every disallowed origin against fixed owner0.

The frame proofs do not establish RX data integrity, arbitrary firmware,
every divider/length/FIFO configuration, unrestricted ownership transfer, or
physical timing/metastability. Independent full-duplex pin tests supply broader
sampled evidence. No temporal retiming claim follows from the count algebra.
Each formal job has one 120-second attempt; a timeout remains explicitly
deferred/unproved under existing user direction. Tool errors and real
counterexamples fail acceptance; they are never treated as timeouts.
