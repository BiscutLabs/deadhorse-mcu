# T16 SPI formal ledger

Measured 2026-11-17 at base `ea9f238` plus T16 source hashes in the final
aggregate receipt. Command: `python tools/env/run.py run -- python3
hw/ip/spi_host/check.py --output build/t16/check-final`. Its formal child runs
`python3 hw/ip/spi_host/formal/check.py --json build/t16/check-final/regmap/spi_host_regs.json
--output build/t16/check-final/formal`; receipt `build/t16/check-final/formal/result.json`.
The aggregate binds input sources and child-receipt hashes.

| Property | Result / engine | Configuration | Measured correct-job seconds |
| --- | --- | --- | ---: |
| Mode 0 frame, CS, bit sequence, bus response and clock hold | Bounded, BTOR btormc | 128 edges, FIFO 2, CS0, H3, one arbitrary accepted TX byte | 13.236336 |
| Mode 3 frame, CS, bit sequence, bus response and clock hold | Bounded, BTOR btormc | 128 edges, FIFO 2, CS1, H3, one arbitrary accepted TX byte | 13.489111 |
| Denied accesses return errors/zero and preserve observable disabled state | Proved, ABC PDR | Owner 0, denied tags 1..7, FIFO 2, arbitrary traffic; configured depth 32, unbounded engine | 0.465288 |

Each frame case has nine assertions and two covers: completed A5 transaction
and selected midpoint with sleep requested. The denied case has eleven
assertions and two covers: error response and error response with a concurrent
request. All covers reached concrete witnesses. All actual production faults
were rejected with concrete counterexample traces: inverted MOSI register
updates in each mode and bypassed owner comparison. Cover/fault jobs use BTOR
btormc at the listed depths. No job timed out or was deferred; the unchanged
per-invocation timeout is 120 seconds.

## Assumptions and limits

- Reset is initially low, subsequently arbitrary. Single HF clock and qualified
  domain reset; physical recovery/removal and reset distribution are excluded.
- Frame setup uses a specified legal write sequence. The arbitrary byte is
  captured on grant. MISO is constant one and timeNow zero. Sleep is arbitrary
  after selection, initially run mode. These are external stimulus constraints,
  not assumptions about internal DUT state.
- Frame results are bounded, not unbounded protocol proofs. They do not prove
  RX data, timestamps, arbitrary firmware, all divider values or FIFO sizes.
  Independent public-pin/reference-model simulations provide broader evidence.
- Denial maps tag zero to one to cover all denied tags against owner zero.
  Active ownership transfer still requires the documented external drain/block
  protocol; this proof concerns observable disabled-state preservation.
- Digital synchronizers do not qualify metastability, MTBF, external device
  delay, pads, board timing, oscillator tolerance or complete-system sleep.

Independent review authenticated all model hashes, solver statuses and concrete
witnesses. The initial `build/t16/formal-initial` failed compilation because
Scala equality was used in two intended Chisel hardware comparisons. Replacing
it with hardware equality preserved the properties; that failed attempt is
retained and is not solver evidence.
