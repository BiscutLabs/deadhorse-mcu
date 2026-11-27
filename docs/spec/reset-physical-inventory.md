# T44 production reset inventory

This is the inventory before reset RTL changes. Production base:
`5b0cf93814ddfd35bc9bc48258c54068b30b51c4`; preflight tooling checkpoint:
`e385e78`. The reset contract is in [reset-physical-contract.md](reset-physical-contract.md).
An inventory role is not permission to remove a reset or exempt a timing arc.

## Reproduction and measurement boundary

Commands use the pinned environment through `python tools/env/run.py run --`:

```
python tools/sbt.py "hw/runMain deadhorse.top.EmitSoc build/t44/production01/emit production 8"
python hw/top/reference/measurements/plan04_map.py --base build/t44/production01 --usb-reference build/t33/pre-fast03/fast/usb/timing/usb --stability-reference build/t43/new-stability02 --threshold-control --sram --rom-image build/t36/rom/rom.hex
python hw/top/reference/measurements/t44_usb_context.py --base build/t44/production01 --output build/t44/usb-context05
python tools/physical/reset_inventory.py --map build/t44/production01/map --context build/t44/usb-context05/result.json --output build/t44/inventory08
```

Canonical mapped graph SHA-256:
`a2779d8ec81e6c75f5ed495dd406ef8b5089690d9714b0c09d9fac28bb1f9182`.
The current production test-access hooks are present. T37 scan replacement,
inserted scan chains and the rejected dlyb/dlyc experiment are absent.
The task report records the two failed fast baselines and focused repairs;
no third pre-RTL full fast run is substituted for the required final fast run.

Generated evidence remains under `build/t44/inventory08/`:

| Artifact | Contents |
| --- | --- |
| `inventory.json` | Every mapped standard-cell FF; every asynchronous clear/set pin, polarity, driver, fanout, source identities, role, cohort, sink clock and launch clock |
| `control-cones.json` | Complete combinational reset-source expressions, all contributing register/port/macro boundaries and sink lists |
| `functional-blocks.json` | Reset/non-reset counts and largest reset nets for every functional block; merged cross-block identities counted separately once |
| `block-summary.json` | Counts by source module type and role |
| `source-hierarchy/reset-inventory.json` | Every source ResetRelease instance and its source, owning clock, downstream group and state count |

The source hierarchy comes from the authenticated fresh context import, not an
unsealed intermediate mapping file. Imported helpers, libraries, receipts and
certificates are hashed. Unknown mapped macro types are rejected. Only the two
locked SRAM macro types are outside the explicit standard-cell FF inventory.

## Measured counts

The following values are **measured** by the mapping/inventory commands above.
These are pre-layout numbers, not post-CTS results.

| Quantity | Value |
| --- | ---: |
| Mapped standard-cell FFs | 20,392 |
| FFs with an asynchronous clear/set pin | 13,247 |
| FFs without an asynchronous clear/set pin | 7,145 |
| Asynchronous control pins | 13,247 |
| Buffer-collapsed asynchronous control origins | 49 |
| Source ResetRelease instances / state bits | 32 / 64 |
| Mapped digital standard-cell area | 3.4739676608 mm2 |
| Mapped sequential standard-cell area | 1.4449486912 mm2 |

SRAM macro internal state and area are outside these FF/standard-cell counts.
The pretechnology hierarchy is a different measurement boundary: 23,074 state
bits, 15,032 reset-controlled bits and 8,042 without reset controls. Its
preoptimization latch bits must not be confused with surviving mapped storage;
the other mapped standard-cell state is the existing ICG.

## Largest reset distributions

Counts are **measured reset/set pin loads after collapsing ordinary buffers**.
They are not total data-pin fanout or an electrical capacitance estimate. The
per-pin records also retain immediate drivers and actual buffer paths.

| Source | Launch clock | Reset/set loads | Sink clocks |
| --- | --- | ---: | --- |
| warmMain, `_237865_/Q` | Ungated main | 7,019 | Main-gated and core-gated |
| warmAon, `_237767_/Q` | AON | 3,150 | AON |
| coldMain, `_237798_/Q` | Ungated main | 1,212 | Ungated/main-gated |
| coldAon AND warmAon | AON contributors | 385 | AON |
| coldAon, `_237796_/Q` | AON | 316 | AON |
| USB engine release, `usb._6357_/Q` | OSC_IN | 263 | OSC_IN |
| coldScan, `_237801_/Q` | TCK | 221 | TCK |
| Oscillator warm/bootstrap conjunction | AON contributors | 123 | AON |
| USB engine release AND NOT bus reset | OSC_IN contributors | 101 | OSC_IN |

Clock ancestry records distinguish the main root, main ICG and core ICG,
including actual cell connections and edge polarity. A shared `main` domain
label alone does not justify a timing exception or adequate first-edge margin.

The cohort follows the actual reset source. For example, coldAon's 316 direct
loads remain cold even where they serve watchdog logic; the 106 debugger memory
frontend loads on warmMain remain warm even though they belong to the debugger.
The debug module/transport cold state and D106 cancellation are separately
identified. USB/application reset contributions remain explicit; adjacent
registers in the boundary slot do not automatically have the same reset.

## Protected state and identity reconciliation

**Measured:** the protected core/FPU union contains 1,765 asynchronous FFs and
2,405 non-asynchronous FFs. Of the asynchronous FFs, 1,764 use the core-gated
clock; `core_busy_q` uses the incoming main-gated clock. The FPU is already
included in this union. **Estimated share:** `1765 / 7019 = 25.15%` of warmMain
loads, leaving 5,254 other loads. This is the largest combined block on that
root, not most of the root's loads; no numeric definition of dominance is added.

Source alias joins retain all identities when synthesis merged state. There are
**measured** 19,844 unique joins, 89 multiple joins and 459 unmatched joins.
Multiple joins include binary/Gray MSBs, duplicate request payloads and two
shared AON GPIO/SPI synchronizer bits. They do not create extra physical FFs.

The remaining identities are accounted for without granting mutation authority:

- Seven USB release aliases use exactly the mappings in the proved context
  relation. No generic suffix rename qualifies an arbitrary register.
- The unnamed USB cadence bits and enable copy use the retained mapped cadence
  certificate, actual pin correspondence and the copy's D/CLK/RN equality.
- `_233663_` is `dividedClear_s.stable`: its actual D comes from the metastable
  stage; a double inversion leaves the FIFO `reader.clear` output alias. Its
  synchronized coldMain reset remains a real class-C candidate.
- Seven protected bit identities remain unresolved at the exact source-bit
  level: three controller debug-cause exports and four packed mstatus exports.
  They are explicitly retained, with authenticated source locations; no guessed
  bit correspondence permits a reset removal or exception.
- The other unmatched state is already resetless memory/boundary payload.
  Its surviving hierarchy aliases and authenticated source locations retain
  block ownership. No unassigned functional-block subtotal is hidden.

## Payload roles and preservation

The inventory marks data/response/shift banks as payload, including architectural
or software-visible data that must retain reset. Other entries are control or
architectural control state. Every entry has `reset_removal_authorized=false`.
Qualification remains a separate consumer-specific proof or randomized test.

Keep public RegBlock response and write-data reset defaults: existing tests
observe outputs even when invalid. Also keep software-visible timer captures,
DMA current/remaining, mailbox staging that can be pushed before a new write,
and directly readable I2C RX data. Many FIFO arrays and UART/FPU datapaths are
already resetless. Protected core/FPU reset behavior stays unchanged.

Candidate banks still needing observability checks:

- CdcRead head is captured on the same edge that `present` becomes true, but every raw-output
  consumer and synchronous flush must be checked.
- BusRegAdapter/BridgeSource result drives public rdata on invalid cycles;
  written-before-valid alone does not authorize removing its reset default.
- BridgeTarget reply is internal FIFO payload guarded by `replyPending`; all
  orphan, poison, error and transport-close paths still need verification.
- DMA data is written before data-dependent writes, but unused READ wdata can
  expose its prior value. Existing read-data semantics and whole-beat stability
  requirements must be preserved explicitly.

## Historical failing-path identities

These slacks are **historical measurements from T37's rejected recovery03/dlyc
diagnostic**, not fresh T44 measurements or the T38 cts02 comparison baseline.
Authenticated archive SHA-256:
`91de7e09cb3f3aa693fb10c7097c2e956230dca5698ff05f96b1dc82a6045fcc`.

| Historical path | Identity and clocks | Root-cause assessment |
| --- | --- | --- |
| `_224115_/Q` → `usb._7638_/RN`; recovery −9.771710 ns SS | BIST state[0], main → usbUp_r.first, OSC_IN | Actual destination ResetRelease first stage; raw cross-domain contribution is a B candidate. Assertion-source decode still needs glitch/pulse audit |
| `usb._7646_/Q` → `usb._7298_/RN`; removal −13.602067 ns SS | engine.rxReset_REG, OSC_IN → rx.rd.first, main | Actual ResetRelease first stage. USB contribution is a B candidate; the same RN's main-domain appUp contribution remains C |
| `_237865_/Q` → `_225849_/SETN`; removal −7.359250 ns SS | warmMain second, ungated main → Ibex privilege state, core-gated | Real synchronized-release distribution and gated-clock ancestry issue |
| `_237865_/Q` → `_236279_/SETN`; removal −2.430409 ns FF | warmMain second → FPU divider inReady, core-gated | Same distribution issue; protected internal state |
| input_PAD[7] → `_230629_/RN`; recovery −5.043248 ns SS | Tester reset → LiteCore registers_5[9], AON | Historical scan/reset path; requires the class-E tester protocol, not a functional false path |

Both USB endpoint pairs have actual first-D=1, first-Q→second-D, common
clock/reset and source-bound ResetRelease identities. A mixed-source RN cannot
receive an endpoint-wide exception. No exception has been applied here.

## Remaining acceptance

This inventory does not close source-to-pin timing classification, source glitch/
pulse qualification, reset-removal eligibility, distribution equivalence,
release ordering, electrical checks or post-CTS recovery/removal. T44 must
complete those checks and the final fast tier. T38 cts02's historical measured
CTS logic area remains 5.113575712 mm2; the user ceiling is 5.113576 mm2.
