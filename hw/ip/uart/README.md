# Reusable UART (T15)

`Uart(json, fifoDepth = 8, base = 0)` is a single HF-domain 8N1 peripheral.
`json` is the generated `uart_regs.json`, `fifoDepth` is 2..16 bytes per FIFO,
and `base` is 256-byte aligned. Base zero is a port-local default, not a SoC
address assignment. The authoritative protocol is `docs/spec/uart.md`.

Inputs: `clk`, domain-qualified active-low `reset_n`, `bus: LocalBus`, trusted
three-bit `owner`, asynchronous `rx`, same-domain `sleepRequest` and two-bit
`sleepMode`. Outputs: registered `tx`, `txEnable`, `irq`, `dmaTxRequest`,
`dmaRxRequest`, `clockHold`, and `quiescent`, plus registered bus responses.
Only origin tags equal to `owner` reach the generated register block. Ownership
changes require the external drain/block handshake described in the contract.

The register map is generated from `uart.regmap.yaml`, using existing RegBlock
and BusRegAdapter. `configuration`/`value` identifiers avoid the generator's
reserved SystemVerilog names `config`/`byte`; offsets and meanings follow the
contract. APPLY examines pre-edge idle/empty state; accepted APPLY suppresses
launch on that edge. Flush wins FIFO enqueue/pop without aborting active frames.
An empty POP cannot consume a byte completing on the same edge. Sticky hardware
events win simultaneous W1C. Disabled TX queues must be flushed before enabling,
because APPLY requires empty queues.

Independent 16-bit accumulators schedule TX bit boundaries and RX center
samples. The first RX sample is half a bit after synchronized start detection.
The synchronizer receives normalized active level, resetting inactive for both
polarities. APPLY allows two HF edges for changed-polarity synchronizer history
to settle before starting reception. Each accumulator has an eight-bit low
pipeline and an eight-bit high pipeline, with registered low carry and full
overflow tick. For `P(n) = seed + n * increment`, launch seeds high with
`hi(P1)`, low with `lo(P2)`, low carry with `carry(lo(P1) + increment_lo)`,
and tick with zero. Each active edge advances the low byte and independently
adds the old low carry to the high-byte update; serial control consumes the
old tick. Induction preserves the original full-accumulator overflow edge.
TX uses seed zero and RX uses seed 32768. Enabled increments 1..8192 make the
initial overflow zero. APPLY cannot change increment while either engine is
busy, and APPLY/reset/launch clear or reseed all pipeline state.
The two high-byte sums use parallel candidates with `increment_hi` and a
precomputed `increment_hi + 1`, selected by the registered low carry. This
avoids a sixteen-bit feedback carry chain without adding external cycles.
The shared sum helper still computes the complete 17-bit sum for arbitrary
16-bit inputs; its combinational formal lemma does not prove the temporal
retiming. That separate evidence consists of independent recurrence review,
bounded frame checks and pin-level boundary tests. Full 16-bit configuration
and readback remain intact, including oversized disabled increments; enabled
rate validation is unchanged.
There are no generated clocks. HF reset asserts asynchronously and must release
synchronously through the integration's shared ResetRelease, as for the other
local-bus endpoints; all enables,
events, queues and busy state clear, TX is high, output-enable is false.

TX work drains during sleep; queued data retains clock demand even with TX
disabled. Receive mode keeps enabled RX clocked; other modes finish an existing
RX frame and retain unread bytes. `clockHold` and `quiescent` are conservative
registered indications; the controller must also account for bus/command work
before gating. DMA requests are hints, not reserved credits.

`UartWake` is separately clocked in AON. Inputs are `clk`, `reset_n`, `rx`,
`armed`, `invert`, `clear`; outputs `wake` and `clockRequest` are aliases of one
sticky register. Shared CDC synchronizes normalized active RX. Capture wins
clear, and disarming preserves pending wake. Change inversion only disarmed and
wait four AON edges before arming. A wake-only sender must hold active at least
four AON periods, allow HF startup and an idle bit, then retry; no first-byte
retention or short-start-bit detection is promised while HF is stopped.

`UartBank(json, fifoDepth, bases)` instantiates exactly three independent HF
endpoints, with shared `clk`/`reset_n` and Vec(3) versions of other UART ports.
Its three LocalBus interfaces remain separate. `bases` defaults to three zeros
for separate port-local maps. AON monitors and physical pin/address assignment
remain integration responsibilities.

The initial local-HF-reset emission failed mapped timing: 30.518593 ns against
24.96 ns, with an increment-to-RX-count ripple-carry path. Its reset-release
flip-flop directly drove 217 reset pins and caused electrical violations.
Receipt `build/t15/timing-initial` preserves that measurement. Moving reset
qualification to the shared domain boundary does not solve physical reset
distribution: reset-tree buffering, recovery/removal and full-domain timing
remain integration obligations. The single-endpoint timing boundary receives
already-qualified reset. AON UartWake keeps its small local ResetRelease.
The first grouped-carry revision still missed timing at 27.434607 ns, with no
electrical violations (`build/t15/timing-03`); the carry/control separation above
addresses that remaining path. These failed receipts are not timing passes.
The corresponding three-instance bank initially measured 26.191912 ns against
24.96 ns (`build/t15/timing-bank-04`). That failure remains preserved.
The masked grouped-carry bank still measured 25.474527 ns against 24.96 ns
(`build/t15/timing-bank-05`); this motivated the carry-select implementation.
The carry-select bank still failed at 25.443443 ns
(`build/t15/timing-bank-06`). The byte pipeline above resolves that feedback
path; all failed measurements remain failure evidence.

Current mapped, pre-layout measurements use GF180 SS/125C/3.0V and the unchanged
24.96 ns allowance: default-depth UART **50,673.9968 um2, 20.436308 ns**;
three-UART bank **151,679.5392 um2, 21.398275 ns**;
AON wake **465.3824 um2, 6.950206 ns**. All have zero reported electrical
violations within their stated module boundaries. These were measured on base
commit `172d4f1` plus the emitted-source hashes in
`build/t15/timing-07/result.json`, `build/t15/timing-bank-07/result.json` and
`build/t15/timing-wake-03/result.json`, using
`python3 tools/timing/check.py --top Uart --clock clk` (or `UartWake`/`UartBank`) with every
emitted module passed through `--source`. Exact command receipts are retained
in those directories. Area excludes physical reset distribution and placement;
the bank excludes AON monitors and is not complete three-port SoC area. Independent tests, formal receipts and
the task report determine final verification status.
