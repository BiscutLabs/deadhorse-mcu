# T42: local admission for the single main-to-AON bridge

Proposal, not approved hardware. T40 was merged into main at `f680c3f`.
T42 step 2 requires explicit approval before implementing this change.
D104 still accepts the maximum-image latency exception; the original 250 ms
target, nominal 32 kHz AON, supported 1024-byte image and full RAM CRC readback
remain unchanged. T41's paired-image warm reset contract applies.

## Measured baseline

Measured on `f680c3f` plus the passive test-only taps and observer recorded in
`build/t42/baseline02/result.json`:

```
python tools/env/run.py run -- python dv/soc/boot/load_profile.py --output build/t42/baseline02
python tools/env/run.py run -- python dv/soc/boot/analyze_load.py --profile build/t42/baseline02 --output build/t42/analysis03
```

The production ROM, cores, NOR wire peer and all existing image/release/latency
assertions are used. Neither an injected bus master nor modified production
RTL is involved. These are two scoped boot cases, not the full boot campaign.

| Image | Measured writes + readbacks | Measured simulation quanta | Estimated elapsed time | Original target |
| --- | --- | --- | --- | --- |
| Watcher, 588 bytes | 147 + 147 words | 16,406,604 | 170.902125 ms | Meets 250 ms |
| Supported maximum, 1024 bytes | 256 + 256 words | 28,505,604 | 296.933375 ms | Exceeds 250 ms; D104 |

Time conversion assumes 96 MHz simulation quanta, 48 MHz oscillator, 8 MHz
main and nominal 32 kHz AON. These are simulated counts and estimated times,
not silicon measurements. Window starts at the first CPU lite write offer and
ends at retirement of the existing boot-context commit. It includes config and
context work after readback; it has not been shortened to the final RAM read.

For the maximum image the measured copy phase is 13,811,604 quanta and readback
phase 14,591,592 quanta (first offer through last retirement in each phase).
The remaining 102,408 quanta are the phase transition and context/config tail.
The disjoint time inventory is 25,609,416 quanta in lite transactions,
1,585,152 with flash chip select active outside those transactions, and
1,311,036 in other main work. The last category includes CPU CRC/control,
peripheral polling, stack and context operations; it is not pure CPU compute
time. The observer counts 113,558 retired instructions in the complete window.
Flash/CPU work overlapping a transfer is not charged twice.

Every row below is measured from that maximum-image trace. Quanta statistics
are per word; AON edges count actual observed target-clock rising edges. Full
per-word identities/timestamps are in `analysis03/max-lite-held-words.json`.

| Interval | Copy quanta, min / mean / max | Readback quanta, min / mean / max | Copy / readback AON edges |
| --- | --- | --- | --- |
| CPU offer -> bridge request for permit | 36 / 36 / 36 | 7812 / 7814.90625 / 8556 | 0 / 3 |
| Request for permit -> permit high | 8508 / 11089.875 / 11100 | 11976 / 11976 / 11976 | 3–4 / 4 |
| Permit high -> source acceptance | 48 / 48 / 48 | 48 / 48 / 48 | 0 / 0 |
| Source acceptance -> request FIFO pop | 11931 / 11931 / 11931 | Same | 4 / 4 |
| Request FIFO pop -> AON fabric acceptance | 6000 / 6000 / 6000 | Same | 2 / 2 |
| AON fabric acceptance -> RAM acceptance | 6000 / 6000 / 6000 | Same | 2 / 2 |
| RAM acceptance -> RAM response | 3000 / 3000 / 3000 | 6000 / 6000 / 6000 | 1 / 2 |
| RAM response -> AON fabric response | 3000 / 3000 / 3000 | Same | 1 / 1 |
| AON fabric response -> response FIFO pop | 3045 / 3045 / 3045 | Same | 1 / 1 |
| Response FIFO pop -> CPU retirement | 36 / 36 / 36 | Same | 0 / 0 |
| Total offer -> retirement | 41604 / 44185.875 / 44196 | 55848 / 55850.90625 / 56592 | 14–15 / 19 |
| Response FIFO pop -> permit low, overlapping subsequent work | 8976 / 8976 / 8976 | Same | 3 / 3 |

Handshakes use pre-edge values; RVFI uses the established post-edge sampling.
Read/write retirement is qualified by decoding the actual RV32IMFC instruction,
including compressed loads/stores, not by an unused RVFI read-mask field.
The analyzer requires a complete, ordered set of stages for each offered word,
one retirement, exact ascending write/read addresses and exact values from the
independent flash image. Internal stage addresses label the outstanding source
word, not independent downstream payload observations: this attribution is
limited to these serial held-lite cases. It is not a concurrent-master proof.
Ten corrupted-trace controls reject wrong data, a missing word, a duplicate
word and missing/duplicate permit withdrawals in each case. Prepared fixture
metadata is hash-authenticated before use; each response must have exactly one
withdrawal before the next request for a permit. These checks validate the
observer, not future RTL fault handling.

## Smallest proposed change

Replace only the production `toAon` instance's `DirectionPermit` with one
main-clock registered permit follower, reset low by the existing main warm
release. At each main rising edge, permit takes the previous edge's sampled
`toAon.permitRequest`. Implement it as a small Chisel module so the exact
production primitive can be tested and proved independently.

Today `permits.requestAon` is permanently false after PLAN05 removed general
`toMain`. Nevertheless each request is synchronized to AON, allocated there,
returned to main, and acknowledged back to AON before revocation completes.
No second requester can use this arbitration instance. The dedicated lite
execution-debug bridge has its own permit and stays unchanged.

Keep `BusBridge`, `BridgeSource`, `BridgeTarget`, both CDC FIFOs, CdcEpoch,
the ordinary fabrics, drain credit and SRAM service unchanged. Do not tie
permit permanently high: `BridgeSource` starts in `releasing` and needs to
observe permit low before entering idle. The registered follower preserves
that low phase after request withdrawal, including completion and abort.

| Concern | Preserved contract / validation required |
| --- | --- |
| CDC | Only the obsolete arbitration round trip is removed. Payload/response FIFOs, reset fence and target-demand synchronization remain; no payload samples cross directly |
| Ordering/duplicates | Source still permits one outstanding word and holds its captured packet; source response handling, target issue accounting and FIFOs are unchanged. Test each accepted word exactly once |
| Backpressure | `admit` and source grant still require idle, request, permit, request FIFO ready and `linkUp`; the local permit alone never grants a transfer |
| Reset/timeout | Existing D107 immediate quarantine, acknowledged flush, target poison/drain and uncertain-write no-replay remain. Grant resets low; test cancellation before/after issue and late replies |
| Ownership | Main/AON fabric origin checks, lite boot-held acknowledgment and SRAM program-write authority are untouched; denied owners still have no effect |
| Clock stop/wake | Source demand still follows offer, ask, outstanding/aborting work and target demand. Fence reopening still holds clocks until acknowledged; no new wake source or reset cohort |
| Shared services | The faster grant applies to the existing production toAon service, including power/boot registers, not just RAM. Register values, ordering, owners and deadlines are unchanged; validate dormant and warm-boot interactions |
| Debug/USB | Separate debug transport, unlocked debug permissions and USB reset behavior remain unchanged |

This intentionally changes transaction latency and the admission implementation;
it is why approval is required despite preserving the bus functional contract.

## Expected benefit and physical consequences

Measured permit-assert waits total 5,904,864 quanta. Replacing them with an
estimated one main cycle per word gives an illustrative saving of
`(5,904,864 - 512*12)/96,000 = 61.445 ms`. The measured readback offer-to-ask
wait totals 2,000,616 quanta. If its revocation stall reduces to the observed
ordinary 36-quanta preparation, the further estimated saving is
`(2,000,616 - 256*36)/96,000 = 20.74375 ms`.

Thus an illustrative estimate is `296.933375 - 61.445 - 20.74375 =
214.744625 ms`. This is not a bound or passing measurement: faster admission
changes AON sampling phase and software/peripheral overlap. Actual production
loading must meet 250 ms before D104 is removed. Do not add the entire measured
permit-withdrawal interval again; much of it already overlaps flash/CPU work.

Structural estimate before constant propagation: the qualified old permit has
three two-bit synchronizers and five arbitration bits, versus one proposed
grant bit. Mapping may already remove some constant-direction state, so ten
bits is not a measured flop saving. No numerical area saving is claimed.
No new mux/decode/data path is proposed; the new request-to-permit path is a
main-clock flop-to-flop path. Map the changed block and complete production SoC
after implementation, retain the 8 MHz main budget and all current AON/USB
classes, and stop for negative area headroom or failing main timing.

## Scoped implementation acceptance, after approval

1. Prove the production local grant's reset-low and one-cycle request-following
   properties with a stuck-high/wrong-phase negative control and covers for
   grant/revoke/regrant. Check initialization and offer withdrawal. Use the
   existing capped proof policy; do not rerun unchanged timed-out bridge jobs.
2. Run the affected bridge source/transport/cancellation suites with the new
   grant in an integration fixture, including a stopped target, backpressure,
   reset/timeout at each stage, wrong data, dropped/duplicate work and stale
   response after cancellation. Retain existing assertions and fault controls.
3. Run relevant production owner/lite boot-release, warm reset, dormant/wake
   and load cases. Keep exact-copy and full readback CRC checks for watcher and
   maximum images. Run malformed-image and reset-during-transfer cases and the
   paired-image warm fast/reload cases with their existing independent oracles.
   List the exact selected tests and unrun remainder in the implementation receipt.
4. Reuse this passive profiler for before/after attribution; require the unchanged
   maximum-image 250 ms window to pass without the D104 bypass. Measure changed
   block/SoC area, main/AON/USB timing, map and structure checks; independent review
   of RTL, tests/proofs and measurements before commit/push.

User policy for this task: scoped relevant tests and capped proofs only, no
aggregate fast or full CI. No unrelated IP tests or broad timeout sweep. This
proposal does not mark T42 complete or waive any inherited proof/physical debt.
