# USB formal contracts

## Packet-proof decomposition decisions (2026-11-19)

D60/E1 permits enable/pre-enable-aligned protocol stimulus only where a named
proved production guarantee supports the exact signal and phase. D61/E2 permits
an IN push-spacing assumption only after proving the shared CDC spacing, and
only if E1 leaves the property open. D62/E3 permits depth-128 covers for the
D50 eight-byte model; positive bounds and the 120-second job cap are unchanged.
Original assertions remain mandatory, with one receipt per assertion. Dependent
results must say "proved under environment assumptions E1[/E2]" and cite each
guarantee; small-model acceptance also needs full-size simulation.

Accepted partial proofs use no new environment restriction. The separate E1
diagnostic did not close a proof; E2 was skipped. D58 keeps packetData full-rate,
and symbolic choose is not a certified producer. The literal reset-return
premise is false: production memory read/write staging contains unreset
registers as well as uninitialized RAM. All data proofs retain arbitrary later
common resets; no first-cycle-only reset assumption was applied.

Run through the pinned environment:

```sh
python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --output build/t19/formal
python3 hw/lib/formal/cdc_proof.py --width 8 --depth 2 --output build/t19/cdc
python3 hw/ip/usb/formal/sie_enable.py --packet-bytes 16 --output build/t19/sie-enable
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
- The OUT harness generates packets up to the configured bulk MPS (D53 candidate: 16 bytes), with
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
[approved timing decision and remaining obligations](../../../../docs/spec/usb-timing-decision.md).

`enable_certificate.py` additionally binds eligible production registers to
scalar mapped GF180 Q/D/CLK identities, rejects ambiguous or recoded aliases,
and proves mapped D holds Q when enable is low. It checks the mapped cadence
transition, root clock/reset, and every certified asynchronous reset cone;
SIE's bus-reset source must share the root clock and hold when enable is low.
Targeted wrong-pin, always-enable, cadence-transition/reset, endpoint-reset and
bus-reset-update mutations must fail. Temporal reset-safe cadence is separately
proved and bound by emitted/source hashes. Exhaustive applied exception
coverage, per-class path faults and protocol sampling equivalence still block
acceptance. `UsbSieTiming` measures the retained production SIE parameters with
that cadence, leaving its other inputs external and full-rate.

## Sparse packet-memory proof attempt (D47)

`UsbSparsePacketMemory.scala` retains one selected physical slot and a current
read-address cache. Forgotten bytes are unconstrained inputs; control remains
the production buffer. `memory_refinement.py` binds witness values to muxes
over the actual production RAM registers, without input assumptions, and proves
cache/tracked-word consistency and output equivalence after read-pipeline
warmup. Duplicate/missing RAM identities are rejected. A shifted output stage
must fail. Covers retain and observe the real RAM.

The helper cases assert pointer bounds, occupancy/offset correspondence,
selected-slot ownership and reset warmup. Original public-interface assertions
remain unchanged. The original oracles do not read DUT state; only the added
strengthening assertions inspect optional proof outputs, absent in production
emission. IN data is observed at protocol enables; OUT samples RAM only at
those enables, and resets its data/valid pair. The harness resets the
consumer and cadence together, so its asserted warmup guarantee covers only
that common-reset model. Production inRelease/outRelease may reset buffers
independently of engine cadence. Qualified-read warmup and SIE consumption
across these independent transport resets remain an OPEN composition proof;
the unconditional enable-implies-warmup helper is not a production guarantee.

Sparse results cannot be accepted without all original/helper assertions,
real-model covers/faults, matching source-bound refinement and independent
review. The runner labels sparse jobs unresolved pending that qualification;
it does not substitute an abstracted pass for production acceptance.

## D52 proof refinements

`resume_equivalence.py` compares every next-state, clock/reset input function
and output with all register values and inputs free. It checks the exact state
bijection and register/reset parameters, reproduces the pinned D51 reference
from Git when needed, and rejects a mutation to the actual prepared carry D pin.
The USB aggregate runs this proof against its freshly emitted candidate.

`buffer_reset` uses production cadence and ResetRelease with arbitrary independent
transport reset. It proves IN qualified-read warmup, OUT actual-capture warmup,
and the delayed capture/head-change correspondence. Real-buffer covers observe
all release phases, repeated reset, and both read predicates after another reset.
The IN-valid fault must fail. This is a local sampled-digital proof; the full
SIE consumption/ACK contract remains open. No minimum packet length or ACK
qualification is assumed in this reset harness.

`packet_partition.py` partitions the original six assertions into four
control/service assertions and two data equalities, with exact inventory and
union checks. No assumptions are added. A partition result is not complete
packet acceptance: every partition, real-model controls, memory composition and
production consumption contract remain required. `out_ownership` strengthens
the existing sparse case with a watched-position occupancy invariant; its
helpers remain assertions. Exhausted jobs are not automatically rerun by CI.

## D53 size parameter

`UsbPacketSizing.bulkMaxPacketBytes` supplies the default for the wrapper,
engine, SIE, both bulk descriptors, packet buffers and formal harnesses.
`UsbPacketGeometry` derives a maximum-packet-plus-one ring, pointer width and
eight-word bank count. For the 16-byte candidate these are 17 slots, five-bit
pointers and three banks (24 physical words); one ring slot is reserved.
The staging/prefetched register adds one public byte of capacity. Padding
addresses 17–23 remain real RAM words; addresses 24–31 read zero and ignore writes.

Non-scaling constants are eight-bit bytes, eight-word banks, three RAM read
stages, four sample clocks per protocol enable, and the existing 12/4/8-cycle
service checks. EP0 and interrupt packet sizes remain eight bytes; USB address
and EP0 descriptor/cursor widths are unchanged. There is no packet-size-specific
buffer branch. Maximum packets and repeated pointer wraps are exercised by
the wire suite; the existing depth-48 formal covers are not relabelled as
maximum-packet covers or silently extended.

Memory refinement requires an explicit `--packet-bytes 16` matching the fresh
emission. It checks every mapped RAM identity and rejects a different supported
size as a negative control. A receipt for an earlier size is not current proof.

The OUT oracle uses one extra occupancy bit so an erroneous capacity-plus-packet
commit cannot wrap below the unchanged capacity assertion. This repairs an
existing monitor blind spot; no DUT behavior, assumption or assertion is relaxed.

Historical D53 result (D62 now permits a new depth-128 cover attempt): D50/C
was not eligible under the depth-48 cover cap, even at
the minimum supported eight-byte model. Estimated lower bound: consecutive IN
RAM writes require two four-cycle enables because staging cannot refill on its
drain edge, so filling eight RAM entries takes at least `7 * 8 = 56` sample edges
after the first write, excluding startup. Full and wrap witnesses take longer.
Independent review confirmed this source-derived argument; no small-model job
was launched and no cover bound was raised.

## Packet decomposition receipts

`packet_decompose.py` gives each of the six unchanged assertions per direction
its own job. Safety/data use unbounded PDR; progress uses induction at depth 48.
`packet_partition.py --helpers` separates storage, ownership and data lemmas,
then permits only exact-model PASS lemmas as assumptions. Predicate A/EN guards,
canonical hashes, dependency order and actual sparse/real fault controls are
checked. No original assertion is an assumed helper. The memory-refinement
receipt must match the packet geometry. `packet_receipt.py` accounts for all
twelve original claims exactly once and preserves unresolved results.

The current full-size partial result proves IN capacity, read-nonempty, byte
integrity and held-valid, plus OUT held-valid and held-data. IN integrity and
the two IN queue claims compose the proved sparse-memory refinement with the
common-reset age guarantee. Eight-byte proofs add IN held-data and OUT capacity,
read-nonempty and progress. These four are labelled "proved at small model,
simulated at full size", backed by the passing full-size seeded suite. IN progress
and OUT integrity remain unresolved after the approved attempt. Real covers
and original-assertion-specific faulty-DUT witnesses remain required.

No reset-removal assumption was applied. The literal proposed reset-return
premise is false: unreset read/write pipeline registers survive as well as
RAM. All decomposition proofs retain arbitrary later common resets, and none
is a proof of independently phased transport reset plus SIE behavior.

E1 attempts register only encoded operation on `preEnable`, using the exact
D58 production flag certificate, cadence and engine/wrapper equivalence receipts.
OUT data, symbolic byte selection and application inputs remain arbitrary.
Such results are conditional on the encoded-operation harness contract; the
phase certificate does not establish a new full-SIE composition theorem.
E2 is skipped because no exact raw-push spacing guarantee has been proved.
