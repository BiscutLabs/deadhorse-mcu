# USB formal contracts

Run through the pinned environment:

```sh
python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --output build/t19/formal
python3 hw/lib/formal/cdc_proof.py --width 8 --depth 2 --output build/t19/cdc
python3 hw/ip/usb/formal/sie_enable.py --output build/t19/sie-enable
```

Use fresh output directories. A timeout is unresolved, never an accepted
deferral. `--case` selects a diagnostic subset and `--portfolio` runs ABC PDR
and Z3 induction with unchanged assertions and the same timeout. Results bind
the emitted model hashes. Consult the task report and receipts for the exact
revision actually checked; the existence of a harness is not a proof.

| Case | Public contract | Planted fault |
| --- | --- | --- |
| cadence | One protocol enable per four sample edges, including reset startup | Enable on alternate edges |
| denied | Every non-owner access returns an error and has no TX/pop/ack/config/IRQ side effect | Bypass owner comparison |
| resume | Qualified idle-to-K capture and retention until clear | Drop all wake events |
| pads | Reset or absent VBUS disables drive and pull-up without a clock; otherwise preserve vendor requests | Ignore raw reset |
| control | Address/configuration can change only on bus reset or a qualified status ACK, with SETUP/error precedence | Commit without ACK |
| in | Capacity, selected accepted-byte integrity through speculative reads/replay/ACK, held-byte stability, bounded service after settled data and a new request | Drop ACK commit; permanently withhold valid |
| out | Capacity, selected packet-byte integrity after commit, CRC/error rollback, stable stalled payload, bounded service | Drop packet publish |

The IN oracle counts accepted application bytes and ACKed speculative reads;
it never reads implementation pointers or RAM. An arbitrary accepted byte is
selected and checked at its logical queue position, including replay. The OUT
oracle counts speculative packet bytes separately from committed application
bytes, discarding the former on error/rejection. Covers require actual reads,
replay/commit or rollback, and held-data consumption.

The `in_bit0`–`in_bit7` and `out_bit0`–`out_bit7` diagnostic cases keep the real
byte-wide implementation and all control assertions, but check data equality
and held-data equality for one named bit. This lets cone reduction remove
irrelevant RAM data bits. It introduces no input assumptions. A single lane
cannot establish byte integrity: all eight results must pass to establish the
conjunction. Full-byte covers and fault controls remain required.

## Assumptions and harness restrictions

- Single-clock cases start with reset asserted; subsequent resets and all
  unspecified input values are arbitrary. `async2sync` models digital
  asynchronous-reset behavior for these single-clock proofs.
- Cadence is the actual production `UsbBitEnable`, not an assumed interval.
- The denied-access harness fixes owner zero and maps input origin zero to
  one, covering every non-owner tag. Inputs otherwise remain arbitrary.
- The IN harness generates byte consumption only when valid, qualified ACK
  only after consumption, and arbitrary request/retry/idle choices. This is
  the packet-interface producer contract; it does not prove the whole SIE.
  Service is required by the next protocol edge after a request when queued
  data has remained settled for twelve sample edges, covering staging and RAM
  latency. An early token can legitimately receive NAK and require retry.
- The OUT harness generates packets up to the public 64-byte bulk MPS, with
  arbitrary payload, stalls, termination/error and application readiness.
- Resume proof uses a reduced idle threshold of seventeen samples; production
  timing and simulation use the required 144000-sample threshold. The reduced
  proof does not certify the production counter threshold by itself.
- Pad safety takes arbitrary vendor drive/pull-up requests, a sound
  over-approximation for that combinational boundary. Assertions are active
  even while reset is asserted. Wire simulation establishes real transmissions.
- The shared byte FIFO uses its existing independent-clock proof, including
  stopped clocks, arbitrary later local/peer reset, ordering, retention,
  reset-release covers and planted data/Gray/reset faults.
- Analog metastability, MTBF, clock tolerance, pad electrical behavior and
  board compliance are excluded.

## SIE enable certificate

`sie_enable.py` examines the actual prepared vendor netlist. Every selected
protocol register must be a positive-enable, positive-edge flip-flop with the
same active-low asynchronous reset. Register values and PHY outputs are freed;
SAT must prove every enable is inactive when `clk_gate_i` is low. The negative
control sets a real prepared register enable permanently high, then uses the
same enable extraction and requires a counterexample.

This is only an enable implication certificate. It does not authorize a
multicycle exception or establish reset recovery, mapped pin classification,
hold timing, PHY timing or valid destination sampling by itself. See the
[pending timing proposal](../../../../docs/spec/usb-timing-decision.md).
