# T19 USB formal ledger

## OUT occupancy and independent-reset packet closure (2026-11-20)

The approved deferred attempt closes the remaining OUT byte-integrity claim.
Read-only evidence accounting discharges all twelve independent-reset packet
assertions: five at production sixteen-byte size, seven **proved at small model,
simulated at full size**. The older common-reset inventory is unchanged. This
closes the packet-interface reset/SIE obligation under the existing producer,
binding and D50 qualifications, not EP0 sampling, exception or physical signoff.

**Measured** at base `0216c37ea7cd92a6a28aa02983ecfa7f8aad45fd` plus exact
archived sources in `build/t19/packet-occupancy-02/result.json`. Production RTL,
original assertions, arbitrary later root/transport resets, positive depth 48,
120-second per-job cap and depth-128 small-model covers are unchanged. No E1/E2
or other new environment restriction. No CI, USB aggregate, timing or new
full-size simulation ran.

`UsbOutOccupancyLemma.scala` adds two stateless source-emitted observers on the
eight-byte/nine-slot model. With `d(a,b)` the forward ring distance:

```text
!reject => d(head,tail) +& d(tail,speculative) <= 8
!reject => queued +& packet <= 8 + appValid
```

The widened sum prevents modular wrap from hiding overlapping intervals.
`d(head,speculative) <= 8` alone would not exclude the prior impossible witness.
The counter consequence uses the proved `queued=d(head,tail)+appValid` and
`!reject => packet=d(tail,speculative)` links. Storage/warmup and every helper
are freshly proved on canonical hash
`ee0007c84befbb00132ec3237211c8fbf6ad0ab88defcdf9da3356c23739e14b`.
Only authenticated PASS receipts for that identical model become assumptions.
Original assertions remain in the canonical model with their original reset
enable and predicate. Observer projection restores every original cell;
binding forbids DUT drivers, state, new assumptions and ambiguous aliases.

Commands actually run in the pinned environment:

```text
python tools/env/run.py run -- python3 hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-occupancy-02 --role out --packet-bytes 8 --properties integrity --sparse --upper --occupancy --prior-audit build/t19/packet-focused-audit-01/result.json
  storage-warmup PASS; occupancy-geometry PASS; occupancy-count PASS
  position PASS; position-upper PASS; ownership PASS
  owned-data PASS; read-pipeline PASS; out integrity PASS
  UNRESOLVED independent-reset packet out (exit 1: only one of six role originals selected)
python tools/env/run.py run -- python3 hw/ip/usb/evidence.py --manifest build/t19/occupancy-evidence-manifest.json --output build/t19/occupancy-evidence-01
  PASS USB evidence; closed=12 unresolved=[]
python tools/env/run.py run -- python3 -m unittest discover -s hw/ip/usb/formal -p test_packet*.py
  Ran 17 tests; OK
python tools/env/run.py run -- python3 -m unittest discover -s hw/ip/usb -p test_evidence.py
  Ran 12 tests; OK
```

The subset runner's overall unresolved label is its unchanged requirement that
one invocation select all six role originals. The individual integrity claim
proved; the combined audit accounts for every original exactly once and is the
complete inventory result. No unresolved result was relabeled as a proof.

Per-job wall times are **measured** by the focused command above. Engines are
the unchanged ABC PDR/Z3 induction portfolio; all positives are unbounded.

| Job | Result | Seconds |
| --- | --- | ---: |
| Storage/warmup prerequisites | proved | 37.312 |
| Pointer geometry | proved | 1.120 |
| Counter consequence | proved | 0.373 |
| Position lower / upper | proved | 0.422 / 0.578 |
| Ownership | proved | 35.623 |
| Owned data | proved | 10.551 |
| Read pipeline | proved | 69.059 |
| Original OUT byte integrity | proved at small model | 7.936 |
| Real epoch covers | covered, depth 128 | 0.624 |

Both occupancy faults force the actual production `full` signal low, admitting
overflow, with **no helper assumptions**. Sparse and real-RAM models reject
both faults. The real geometry witness has **47 measured samples** within
depth 48: released reset high, reject low, appValid high, head=1, tail=8,
speculative=1. Its intervals total `7+2=9 > 8`. The counter fault, original
data-corruption fault and all existing helper faults also fail. The existing
upper-position fault remains the explicitly labelled joint cadence/reject
mutation, not a reject-only detection claim. All eleven real epoch covers
remain reachable, including reset phases/reassertion and overlength wrap,
abort and recovery. Prior full/empty/wrap/retry/max-packet covers and memory
refinement remain hash authenticated.

The evidence manifest replaces only `packet-epoch-out-finish-01` with
`packet-occupancy-02` and adds the latter as an emission anchor. It retains
the SIE proof, wrapper binding/archive and historical full-size seeded
simulation `nonproof-fullsize-01`; the collector checks their exact current
production-source bindings. No fresh full-size simulation is claimed.

`packet-occupancy-01` preserves a pre-solver tooling failure: the guarded
observer importer omitted unsigned `$lt` (`sum <= 8` emitted as `sum < 9`).
Allowing that combinational comparator fixed import without changing any
assertion or model restriction. No timed-out job was rerun; no extra lemma
after a new timeout or cap extension was needed. Independent review verified
the arithmetic, reset guard, exact-model chaining, real overflow witnesses,
all twelve claims and SIE/full-size evidence. Focused guard tests reject bad
widths/aliases, DUT drivers, state, assumptions and unsupported model size.

## Non-proof acceptance plumbing (2026-11-20)

The user approved one extra unchanged-cap OUT combined-occupancy attempt, then
prioritized non-proof work. That attempt is deferred; no proof solver was run
in this follow-up. Original assertions, environments and caps are unchanged.

`hw/ip/usb/evidence.py` now audits the existing expanded epoch inventory and
actual SIE/wrapper receipts without retrying jobs. `hw/ip/usb/check.py` accepts
an explicit `--packet-evidence` manifest and retains each unresolved original
claim. It does not remove or skip any existing aggregate command, physical
qualification or negative control. The original common-reset proof inventory
and the broader independent-reset composition obligation remain distinct.

Independent review requested complete source-inventory guards, exact wrapper
model binding, archived-source/artifact links and full-size simulation
provenance. These guards are implemented with focused negative tests.
`python tools/env/run.py run -- python3 -m unittest discover -s hw/ip/usb -p
test_evidence.py` passes **twelve tests (measured)** on `8084eb2` plus this
follow-up. This is a tooling unit suite, not a new hardware proof or CI run.

The final read-only collector command `python tools/env/run.py run -- python3
hw/ip/usb/evidence.py --manifest build/t19/nonproof-evidence-manifest.json
--output build/t19/nonproof-evidence-03` authenticates **eleven claims (measured
inventory)** and deliberately returns unresolved/exit one for `out.integrity`.
SIE/wrapper and full-size simulation evidence qualify. No new proof is claimed.

Fresh focused simulation, `python tools/env/run.py run -- python3
scratch/t19_fullsize_capture.py` wrapping `python3 tools/sbt.py "testOnly
deadhorse.usb.UsbThroughputSpec"`, passes both unchanged tests with **57
source/fixture bindings (measured inventory)** before/after. Receipt:
`build/t19/nonproof-fullsize-01/result.json`. Simultaneous payload is **measured**
1,022,483.316 bit/s each way; slow service measures 286,567.164 bit/s and is
correctly rejected. This is the existing offered-load test, not a maximum-rate
measurement. Raw vendor hashes remain recorded; only terminal LF count differs
between the applied files and Chisel resource export. The earlier strict-byte
audit failure is preserved under `nonproof-evidence-02`; all other byte changes
are rejected by the reviewed guard.

The physical deliverable is the reviewed
[handoff](../spec/usb-physical-handoff.md), with historical source-bound timing
and explicit open hold/RDC/placement work. Fast CI, full CI and the USB
aggregate remain unrun by user instruction. T19 is not merge-ready.

## Independent reset/SIE composition follow-up (2026-11-19)

**Open, narrowed to OUT ownership/integrity.** From `b2e9845c2889e585859e710db3266bbe52c9f8e4`,
this follow-up changes verification and documentation only. No production RTL,
original assertion, environment assumption, positive depth or solver cap changes.
The user explicitly prohibited CI: neither CI tier nor the USB aggregate ran.
Earlier common-reset proofs remain valid; this is a broader composition obligation.

`UsbPacketEpoch.scala` inherits the original six assertions in each direction.
The actual shared `ResetRelease` resets the buffer/oracle independently while
production cadence continues. Root and transport resets can reassert arbitrarily.
IN now exercises zero-byte ACK, including clearing retained ownership without
removing queued bytes. OUT accepts arbitrary packet length, including counter
wrap. A separate saturating monitor proves overlength rejection, sticky reject,
unchanged committed tail and rollback at termination. No legal-host assumption
is added. All unreset memory/pipeline state remains arbitrary.

The old common-reset-only warmup and unqualified tag helpers remain in the
canonical model but are never assumed. New helpers prove qualified IN reads and
actual OUT captures occur only after memory warmup; the sparse tag relation is
proved under `enable && age == 3`. The existing same-size, source-bound memory
refinement therefore applies at every data observation, including independently
released epochs. Fresh exact-model helper receipts precede each assumed lemma.
No E1/E2, application spacing, initialized RAM, fairness or reset-removal premise.

The actual production engine/SIE/PHY proves request implies consume, qualified
normal IN consume implies valid, and IN/OUT endpoint isolation. The proof has no
cutpoints. IN operation normalization gives request priority, then ACK, then
normal read; idle ACK is harmless. OUT uses idle/error/byte/terminator priority.
The epoch root binds to the engine's shared-release output, not its raw input.
Fresh wrapper netlist binding checks cadence, reset releases, memory resets,
USB clock, packet geometry, CDC-facing application pins and patched vendor hashes.
Arbitrary application inputs already include the wrapper's CDC behavior; no new
CDC guarantee is assumed. This does not assert a stronger pre-CDC application
transaction lifetime contract.

All commands below use `python tools/env/run.py run -- python3`. Results are
**measured** on the above base plus the exact working-source hashes in receipts:

```text
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-in-01 --role in --properties capacity read_nonempty held_valid held_data progress
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-out-01 --role out --packet-bytes 8 --properties capacity read_nonempty held_valid held_data progress integrity
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-in-02 --role in --properties integrity
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-in-sparse-01 --role in --packet-bytes 8 --properties integrity --sparse --prior-audit build/t19/packet-focused-audit-01/result.json
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-out-sparse-01 --role out --packet-bytes 8 --properties integrity --sparse --prior-audit build/t19/packet-focused-audit-01/result.json
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-out-sparse-02 --role out --packet-bytes 8 --properties integrity --sparse --upper --prior-audit build/t19/packet-focused-audit-01/result.json
hw/ip/usb/formal/packet_epoch.py --output build/t19/packet-epoch-out-finish-01 --resume-upper build/t19/packet-epoch-out-sparse-02/result.json
hw/ip/usb/formal/sie_packet_contract.py --output build/t19/sie-packet-contract-02
hw/ip/usb/formal/sie_packet_contract.py --output build/t19/sie-wrapper-binding-03 --bind-proof build/t19/sie-packet-contract-02/result.json --regmap build/t19/regmap/usb_regs.json --simulate
hw/ip/usb/formal/packet_epoch.py --audit-receipts build/t19/packet-epoch-in-01/result.json build/t19/packet-epoch-in-sparse-01/result.json build/t19/packet-epoch-out-01/result.json build/t19/packet-epoch-out-finish-01/result.json --anchors build/t19/packet-epoch-in-02/result.json build/t19/packet-epoch-in-sparse-01/result.json build/t19/packet-epoch-out-sparse-02/result.json --output build/t19/packet-epoch-audit-02
-m unittest discover -s hw/ip/usb/formal -p 'test_packet*.py'
tools/sbt.py "testOnly deadhorse.usb.UsbThroughputSpec"
```

The receipt audit passes and correctly leaves composition unresolved.
Fresh `sie-wrapper-binding-03 --simulate` passes the wrapper binding and all
four real-traffic/fault tests. `python scratch/t19_epoch_archive.py` preserves
receipt-local positive/mutant emissions, source snapshot and logs with matching
hashes in `sie-wrapper-binding-03/archive.json`; no mutable shared simulation
directory is the only retained copy. Historical
harness versions are accepted only against byte-identical current emitted RTL;
all solver inputs, actual original predicates, guarded helper dependencies and
real negative mutations are rechecked. Monitor HDL/prepared-model hashes and
exact upper-monitor projection are retained. Fourteen focused unit tests pass
(`packet-epoch-unit-02.log`). No solver is launched by the receipt audit.

Per-original accounting, exactly once. Seconds are measured job wall time from
those commands; all accepted safety jobs are unbounded PDR/Z3 proofs, not BMC:

| Original assertion | Model bytes | Kind | Seconds | Receipt |
| --- | ---: | --- | ---: | --- |
| IN capacity | 16 | proved | 0.318 | `packet-epoch-in-01` |
| IN read_nonempty | 16 | proved | 0.470 | same |
| IN integrity | 8 | proved at small model | 0.768 | `packet-epoch-in-sparse-01` |
| IN held_valid | 16 | proved | 1.269 | `packet-epoch-in-01` |
| IN held_data | 16 | proved | 49.575 | same |
| IN progress | 16 | proved | 4.223 | same |
| OUT capacity | 8 | proved at small model | 0.369 | `packet-epoch-out-01` |
| OUT read_nonempty | 8 | proved at small model | 0.318 | same |
| OUT integrity | 8 | unresolved | 121.275 direct; 121.949 final ownership | `packet-epoch-out-finish-01` |
| OUT held_valid | 8 | proved at small model | 0.318 | `packet-epoch-out-01` |
| OUT held_data | 8 | proved at small model | 0.318 | same |
| OUT progress | 8 | proved at small model | 2.421 | same |

All accepted originals have actual-DUT negative controls with zero helper
assumptions. Real eight-byte covers pass: four reset-release phases, repeated
reset, reset after pending/stalled activity, zero-byte ACK, and OUT overlength
through counter wrap, abort and recovery, in addition to inherited byte covers.
The approved earlier full/empty/wrap/retry/maximum-packet covers/refinement remain
hash-authenticated. All six accepted small-model results are labelled **proved at small model,
simulated at full size**: the focused unchanged `UsbThroughputSpec` completed
with two tests passing, including seeded IN/OUT/simultaneous MMIO/CDC streams
and the slow-service negative (`packet-epoch-fullsize-simulation-01.log`).
Measured simultaneous payload: 1,022,483.316 bit/s each way; slow service:
286,567.164 bit/s each way, correctly rejected. The offered load was unchanged;
this is not a maximum-rate measurement.

`UsbEpochOwnership` adds only the proved unsigned relation
`watching && inPacket && !reject => position < (queued +& packet)`.
Its binding cannot drive an input, introduce state/assumptions, or alter the DUT.
The reject-only negative did not fail within depth 48; this is preserved as a
failed qualification in `packet-epoch-out-sparse-02`. The unchanged positive is
reused with a **joint cadence-enable-high/overflow-reject-low DUT fault**, which
fails on real and sparse models within the unchanged bound. It is not labelled
as detection of the reject-only fault. Remaining ownership still times out.

Step-0/triage measurements from the actual reduced solver JSON/logs:

| OUT attempt | Cells | Sequential bits | RAM bits | Requested/reached | Result |
| --- | ---: | ---: | ---: | --- | --- |
| Real integrity portfolio | 270 | 140 | 128 | depth 48; no unbounded closure | timeout |
| Sparse ownership + lower bound | 274 | 101 | 0 | depth 48; induction fails | timeout |
| Sparse ownership + both bounds | 282 | 101 | 0 | basecase 48 passes; induction fails; PDR frame 40 | timeout |

Each attempt retains the 120-second cap. Quarter/half-depth growth runs were
not performed: this follow-up retains positive depth 48 and stops after the
third changed formulation. The final cone contains no RAM; further memory
abstraction is not the remaining issue. An induction counterexample is not a
trace from reset and is not evidence of a hardware defect.

The final witness has `queued=5, packet=7, appValid=1, head=7, tail=2,
speculative=0, reject=0, selected slot=8, position=11` in the nine-slot model.
It permits impossible combined committed/speculative occupancy. The smallest
proposed next step is a separate control-only proof of
`!reject => queued +& packet <= packetBytes + appValid`, then reuse that exact
receipt for ownership and integrity. This is an inference from the witness,
not a proved fact. No further OUT proof attempt or RTL change was made after
the triage budget. Aggregate integration, EP0 sampling qualification and
physical-flow items remain separate T19 blockers.

## Focused IN progress / OUT integrity closure (2026-11-19)

Base `b6326d00eb0df77d98f6e028caee7bdcd61fa3d5`; exact source/model hashes in
receipts. User authorized these strengthening proofs and explicitly prohibited
CI. No production RTL, original assertion, reset restriction, environment,
positive depth or solver cap changed. No CI tier, USB aggregate, simulation or
timing command ran in this follow-up. Prior full-size simulation is historical
`packet-frozen-fast-02/fast/usb/simulation.log`: all 19 tests passed on the same
production sources and original packet harness, whose hashes remain unchanged.

IN: `UsbInProgressFormal` inherits every original assertion and adds
`pending => head != visibleTail`. Storage plus this ownership invariant prove
on the real 16-byte model before the unchanged service assertion is attempted.
The former induction witness started with an empty retained packet; the proved
invariant excludes it without restricting inputs or later resets.

OUT: splitting the existing helper group proves owned-data lifetime and read
pipeline facts, but original integrity still times out in `packet-focused-out-01`.
Its induction witness starts with `watching=1, inPacket=1, reject=1,
position=6, queued=9, packet=0`. That impossible uncommitted byte later appears
at the committed front. The new asserted relation is precisely
`watching && inPacket => position >= queued`.

The separate Chisel monitor has no state or assumptions after monitor-only
formal retiming. Its predicate is unsigned five-bit comparison, enabled by
`reset_n && watching && inPacket`. Binding validates exact named widths,
predicate, guards and driver ownership. Deleting its cells restores both old
canonical models exactly. All storage/position/ownership/data/pipeline lemmas
reprove on the identical augmented model hash; none is imported under a
mismatched hash. All original assertions remain in that canonical model.

Commands use the pinned prefix `python tools/env/run.py run -- python3`:

```text
hw/ip/usb/formal/packet_remaining.py --role in --output build/t19/packet-focused-in-01
hw/ip/usb/formal/packet_remaining.py --role out --prior-audit build/t19/packet-focused-audit-01/result.json --output build/t19/packet-focused-out-01
hw/ip/usb/formal/packet_remaining.py --role out --position-bridge --prior-audit build/t19/packet-focused-audit-01/result.json --output build/t19/packet-focused-out-03
hw/ip/usb/formal/packet_remaining.py --audit-result build/t19/packet-focused-in-01/result.json --output build/t19/packet-focused-in-audit-01
hw/ip/usb/formal/packet_remaining.py --audit-result build/t19/packet-focused-out-03/result.json --output build/t19/packet-focused-out-audit-01
-m unittest discover -s hw/ip/usb/formal -p 'test_packet*.py'
```

Both final focused proofs and their artifact audits **PASS**. All ten focused
unit tests **PASS** (`packet-focused-unit-02.log`). The inherited memory/cover
chain was re-audited with `packet_receipt.py --audit
build/t19/packet-small-accounting-01/result.json --helpers
build/t19/packet-small-originals-01/result.json --small-cover-receipt
build/t19/packet-small-covers-01/result.json --output
build/t19/packet-focused-audit-01`: audit PASS; its historical original inventory
correctly stays unresolved until combined with the new receipts.

Measured positive-job wall seconds from those commands (not estimates):

| Job | Size | Unbounded engine | Seconds | Negative control |
| --- | ---: | --- | ---: | --- |
| IN storage + pending ownership | 16 | Z3 induction | 62.889 | Actual pending forced high; rejected |
| IN original progress | 16 | Z3 induction, k=38 | 4.622 | Actual valid withheld; rejected |
| OUT storage | 8 | ABC PDR | 14.184 | Actual tail corrupted; sparse/real rejected |
| OUT position lower bound | 8 | ABC PDR / Z3 | 0.373 | Actual appValid forced high; sparse/real rejected |
| OUT ownership | 8 | ABC PDR | 100.023 | Actual speculative pointer corrupted; sparse/real rejected |
| OUT owned-data lifetime | 8 | ABC PDR | 59.135 | Sparse pending data / real write data corrupted; rejected |
| OUT read pipeline | 8 | ABC PDR | 32.659 | Sparse read stage / real write data corrupted; rejected |
| OUT original byte integrity | 8 | Z3 induction, k=43 | 4.973 | Actual application data corrupted; rejected |

All negative jobs use zero helper assumptions. The five fresh real IN covers
pass at unchanged depth 48. OUT retains authenticated real eight-byte covers
at approved depth 128, including full/empty/wrap/retry/maximum-size packet, and
the separately proved matching-size sparse-memory refinement with its fault.

Assumptions are exactly the original common-reset environment: one digital
clock, initial reset asserted and later resets arbitrary; IN consumes only
valid data and ACKs only after consumed data; OUT packet length at most MPS.
All other inputs remain arbitrary. IN progress assumes nine proved guarded
predicates (the eight storage predicates plus pending ownership). OUT integrity
assumes sixteen proved guarded predicates (the prior fifteen helpers plus the
new position lower bound), with exact receipts and dependency order. No E1/E2,
fairness, reset-removal, initialized RAM or additional producer assumption.

Current original-assertion accounting, exactly once per claim:

| Original claim | Current receipt | Kind |
| --- | --- | --- |
| IN capacity | `packet-helpers-03/in/capacity-positive` | proved, 16 bytes |
| IN read nonempty | `packet-helpers-03/in/read_nonempty-positive` | proved, 16 bytes |
| IN byte integrity | `packet-helpers-03/in/integrity-positive` | proved, 16 bytes |
| IN held valid | `packet-decompose-split-01/in/held_valid-positive` | proved, 16 bytes |
| IN held data | `packet-small-helpers-01/in/held_data-positive` | proved at small model, simulated at full size |
| IN progress | `packet-focused-in-01/progress-positive` | proved, 16 bytes |
| OUT capacity | `packet-small-originals-01/out-capacity-positive` | proved at small model, simulated at full size |
| OUT read nonempty | `packet-small-originals-01/out-read_nonempty-positive` | proved at small model, simulated at full size |
| OUT byte integrity | `packet-focused-out-03/integrity-positive` | proved at small model, simulated at full size |
| OUT held valid | `packet-decompose-split-01/out/held_valid-positive` | proved, 16 bytes |
| OUT held data | `packet-decompose-split-01/out/held_data-positive` | proved, 16 bytes |
| OUT progress | `packet-small-originals-01/out-progress-positive` | proved at small model, simulated at full size |

Earlier row engine/time/assumption details remain in the historical table
below; the two replacement rows are detailed above. Seven claims are proved
at full size and five under the approved small-model rule. This closes the
original common-reset harness inventory, not independent transport-reset/SIE
composition. Aggregate receipt integration and physical/prior qualification
remain open; CI/full tier are **not run in this follow-up** by user instruction.

Preserved unsuccessful diagnostics: out01 original integrity TIMEOUT,
measured 121.577 s after both helper groups pass. Out02 stops before proofs
because ordinary clocked-assert lowering introduced sampling registers into
the intended combinational monitor. `packet-monitor-lowering-01` confirms
lowering before async2sync is unsupported; `packet-monitor-lowering-02` confirms
`async2sync; chformal -lower; chformal -early; opt_clean` produces the exact
combinational predicate. Out03 validates that predicate before proof. No
unchanged timed-out job, increased cap, weakened assertion or production edit.

## Historical D60–D62 packet decomposition (2026-11-19)

Base `20bcb66995886ec8ff182012157360868a529f91`, descendant of requested
`33cf251`; production RTL and all original assertions are unchanged. All
measurements below use the pinned environment through
`python tools/env/run.py run -- python3 …`. Exact source/model/configuration
hashes and solver artifacts are retained in the named receipts under `build/t19`.

The requested reset-return premise is false: the production memory has
**measured 59 unreset non-RAM pipeline bits per buffer**, including write
address/data and read stages. `scratch/t19_packet_inventory.py` generated
`packet-decompose-preflight-02/result.json` from the production emission.
This is an inventory, not a proof that only RAM survives. No reset was removed
from the data proofs, and no reset-return theorem is claimed. Initial reset is
asserted; later common reset remains arbitrary in every result below. The
proposed initial-state-set amendment was not assumed approved. Independent
transport-reset/SIE composition remains outside these packet harness proofs.

Step 2 command: `hw/ip/usb/formal/packet_decompose.py --baseline
build/t19/boundary-frozen-fast-01/fast/usb --output
build/t19/packet-decompose-split-01`. Each original assertion has its own job;
none of the other original assertions is assumed. Progress uses Z3 induction
at depth 48, above the unchanged 12/8-edge conditions; other jobs use ABC PDR.

Step 3 command: `hw/ip/usb/formal/packet_partition.py --helpers
--helper-portfolio --split build/t19/packet-decompose-split-01/result.json
--refinement build/t19/packet-refinement-01/proof/result.json --output
build/t19/packet-helpers-03`. Earlier helper01 grouped control invariants;
helper02 split storage/ownership/data; both PDR attempts timed out. Helper03
adds Z3 induction to PDR, with the same depth 48 and 120-second solver cap.
There are no unchanged timeout retries. IN storage (measured 62.382 s, Z3),
ownership (19.889 s, PDR), and data (10.529 s, Z3) prove. Both sparse and real
DUT mutations fail for each group. OUT storage remains unresolved; no OUT
dependent lemma or original assertion is allowed to assume it.

The chain converts only proved helper predicates to assumptions, retaining
their exact A/EN reset guards. Canonical model hash, predicate hash, unbounded
PASS status, prior dependency set, job artifacts and actual faulty-DUT controls
must match. Missing, stale, bounded, UNKNOWN and circular receipts fail closed.
The original six assertions are never helper assumptions. Fresh 16-byte memory
refinement (`memory_refinement.py --emit build/t19/packet-refinement-01/emit
--packet-bytes 16 --output build/t19/packet-refinement-01/proof`) proves with
real RAM witnesses, covers and a mis-phased negative control. Common-reset
cadence proves memory age three before a qualified RAM observation; this
connects sparse-model results to the real memory without an environment assumption.

Step-0 measurements from split01's prepared `stat -width` and solver logs:

| Original property | IN cells / FF bits / RAM bits | IN result and measured seconds | OUT cells / FF bits / RAM bits | OUT result and measured seconds |
| --- | ---: | --- | ---: | --- |
| capacity | 120 / 52 / 0 | TIMEOUT 121.371 | 101 / 46 / 0 | TIMEOUT 121.980 |
| read nonempty | 122 / 52 / 0 | TIMEOUT 121.284 | 102 / 46 / 0 | TIMEOUT 121.675 |
| byte integrity | 206 / 137 / 192 | TIMEOUT 121.433 | 198 / 133 / 192 | TIMEOUT 121.138 |
| held valid | 124 / 49 / 0 | proved 0.318 | 97 / 41 / 0 | proved 0.268 |
| held data | 181 / 127 / 192 | TIMEOUT 121.382 | 155 / 119 / 192 | proved 0.268 |
| progress | 142 / 59 / 0 | UNKNOWN 7.825 | 108 / 50 / 0 | UNKNOWN 39.309 |

Both progress basecases pass through step 47; induction exhausts 48→0. UNKNOWN
is unresolved, not a reachable DUT counterexample (the initial split runner
used an imprecise `failed` label; raw evidence is preserved). PDR's highest
frames for timed-out IN capacity/nonempty/integrity/held-data are measured
67/75/42/99; OUT capacity/nonempty/integrity are 54/55/37. These are algorithm
frames, not bounded proof depths. Current quarter/half-depth timings are not
available: a depth argument does not bound PDR, and shortening induction would
remove history used by the successful helper proofs (steps 43/45). Historical
576-bit-model growth measurements are not reused as current evidence.

Real cover bounds in the authenticated boundary snapshot are measured IN
14/22/18/22 for tracked read/repeated read/commit/service and OUT 15/10/16 for
tracked take/rollback/held take. Counts are solver bounds; traces contain one
more sampled state. Capacity/nonempty/progress already have no RAM cone, so
their difficulty is control reachability rather than RAM size alone.

Original environment assumptions retained: one digital sample clock; initial
common reset low and subsequently arbitrary; IN consumes only valid bytes and
ACKs only after consumed data; OUT packets contain at most the configured MPS.
Application data/push/ready, byte selection, request/retry and later reset are
otherwise arbitrary. No fairness or CDC-spacing assumption is added.

E2/D61 is skipped: no exact proved raw-push spacing guarantee exists. A CDC
accepted-transfer gap does not imply that its valid level cannot remain high
while stalled. It is not used as a substitute assumption.

E1 command: `hw/ip/usb/formal/packet_partition.py --environment-attempt
--split build/t19/packet-accounting-01/result.json --baseline
build/t19/boundary-frozen-fast-01/fast/usb --output build/t19/packet-e1-02`.
The encoded operation captures on the production `preEnable`; data, choose,
push and ready remain arbitrary. Guarantee references are that snapshot's
`timing/engine/certificate/result.json` pre-enable source registers
8074–8079 (IN request/consume/ACK, OUT valid/ready/error), source-bound cadence
receipt `formal/result.json`, and `preenable-equivalence/result.json`.
The exact aliases, source hashes and sorted-JSON equivalence digest are checked.
This is the approved conditional encoded-operation environment, not a theorem
that the full SIE satisfies every packet-harness assumption. E1 is applied only
to still-open integrity/progress, never held-data stability.

Measured E1 results: IN progress UNKNOWN 8.425 s; OUT integrity TIMEOUT
121.608 s; OUT progress UNKNOWN 44.762 s. Real IN/OUT covers and all three
original-assertion faults remain reachable. No proof closed under E1, so no
original-environment result is silently promoted from it. E1 preflight01
stopped before emission on a receipt serialization mismatch; 02 fixes the
digest to the certificate's canonical sorted JSON representation. No timed-out
solver was repeated unchanged.

Exact non-environment lemma assumptions (only after a matching PASS receipt):

| Canonical helper indices (zero based) | Predicate inventory | Guarantee receipt |
| --- | --- | --- |
| IN storage 0–7, 17 | CE implies memoryAge=3; pointer range; stagingVisible implies stagingValid; appReady implies no stagingValid; queued=distance(head,tail)+stagingValid; offset=distance(head,speculative); speculative distance<=offered distance<=tail distance; CE implies three-stage read tag=speculative | `packet-helpers-03/in/storage-receipt.json` (16 bytes); `packet-small-helpers-01/in/storage-receipt.json` (8) |
| IN ownership 8–11 | watching implies position<queued, position=distance(head,slot), and selected; selected implies slot<=MPS | corresponding `in/ownership-receipt.json` |
| IN data 12–16, 18–19 | watched staging/pending/tracked bytes match; a watched queued byte is pending or tracked; CE requires its tracked value; stageSeen/outputSeen imply the watched RAM stage/output | corresponding `in/data-receipt.json` |
| OUT storage 0–3, 12 | CE implies memoryAge=3; pointer range; queued=distance(head,tail)+appValid; reject or packet=distance(tail,speculative); CE implies three-stage read tag=head | `packet-small-helpers-01/out/storage-receipt.json` only; full-size storage did not prove |
| OUT ownership 4–7 | watching implies inPacket or position<queued; under the original owned-byte guard position=distance(head,slot)+appValid; watching implies selected; selected implies slot<=MPS | corresponding small `out/ownership-receipt.json` |
| OUT data 8–11, 13–14 | owned pending/tracked bytes match watched; an owned byte is pending or tracked; CE requires its tracked value; stageSeen/outputSeen imply watched RAM stage/output | May be assumed only if its own exact-model receipt proves; unresolved helpers are never assumptions |

Indices map to `assert__chisel3_builtin` then `_0`, `_1`, … in the authenticated
canonical JSON. The receipts carry the exact predicate/guard connections,
hashes and predecessor sets; prose does not override those identities. IN
original helper-dependent jobs use 20 proved predicates; the original singleton
held-valid/data results use none. Any remaining job's receipt records its actual
qualified subset. Memory containment is a proved relation, not an extra input
constraint or assumed RAM initialization.

### Terminal small-model attempt and original-assertion accounting

The D53 generator is unchanged: eight-byte proofs pass only `packetBytes=8`
through the same buffer/memory constructors. Ring size, pointer widths, bank
count and oracle widths derive from that parameter. Fixed constants remain
eight-bit bytes, eight-word banks, three RAM read stages, four sample edges
per enable, and the original 12/4/8 service conditions. Production remains 16.

Commands (same pinned prefix above):

```
hw/ip/usb/formal/packet_partition.py --small-covers --split build/t19/packet-accounting-01/result.json --output build/t19/packet-small-covers-01
tools/sbt.py "runMain deadhorse.usb.EmitUsbPacketProof build/t19/packet-small-refinement-01/emit memory 8 real"
hw/ip/usb/formal/memory_refinement.py --emit build/t19/packet-small-refinement-01/emit --packet-bytes 8 --output build/t19/packet-small-refinement-01/proof
hw/ip/usb/formal/packet_partition.py --helpers --helper-portfolio --packet-bytes 8 --split build/t19/packet-decompose-split-01/result.json --refinement build/t19/packet-small-refinement-01/proof/result.json --output build/t19/packet-small-helpers-01
hw/ip/usb/formal/packet_partition.py --finish-small build/t19/packet-small-helpers-01/result.json --output build/t19/packet-small-originals-01
```

All ten IN and nine OUT real covers pass at authorized depth 128, measured
3.421/0.868 s. Latest earliest witnesses are measured bounds 102/59. They include
full, nontrivial empty, physical pointer wrap, retry/rollback, and a maximum-size
packet. The eight-byte memory refinement passes with its real fault. No E1/E2
assumption or reset removal is used in the small model. The small attempt stays
within its approved 60-minute wall budget and the unchanged per-job cap.

Five of six small helper groups prove; OUT data times out (measured 121.146 s).
The completion command attempts only original OUT assertions never reached by
the helper runner, using the nine proved storage/ownership predicates. It does
not assume the timed-out data helpers or rerun any IN assertion. OUT progress
then proves by induction. All accepted original assertions have a concrete real
DUT fault targeting that assertion, with no good-DUT helper assumptions.

Terminal audits: `packet_receipt.py --audit … --helpers …` produces
`packet-audit-03/result.json` for the full-size accounting and
`packet-small-audit-01/result.json` for the small accounting (the latter uses
`--small-cover-receipt build/t19/packet-small-covers-01/result.json`). Audit status
passes; aggregate status remains unresolved. Real-model faults, covers, exact
solver input copies, source/flow hashes, memory witnesses, reset guards and
acyclic helper dependencies were independently reviewed.

This table accounts for each original assertion **once**, choosing the earliest
qualified result. Times are **measured** positive-job wall seconds from the
commands/receipts above; PDR is unbounded, and induction proves unbounded safety
of the bounded-response assertion. `A` means the original environment listed
above; `I16/I8` add the 20 proved IN helpers at that exact geometry; `O8` adds
only the nine proved OUT control helpers. The small-model claims are labelled
"proved at small model, simulated at full size": all 19 full-size seeded USB
simulations pass in both `packet-frozen-fast-01/fast/usb/simulation.log` and
the final `packet-frozen-fast-02/fast/usb/simulation.log`.

| Original assertion | Job receipt / property | Kind | Winning engine | Seconds | Assumptions |
| --- | --- | --- | --- | ---: | --- |
| IN queued<=slots | helpers-03 / in.capacity | proved, 16 bytes | ABC PDR | 0.372 | A + I16 |
| IN take implies offset<queued | helpers-03 / in.read_nonempty | proved, 16 bytes | ABC PDR | 0.418 | A + I16 |
| IN matchPosition implies data=watched | helpers-03 / in.integrity | proved, 16 bytes | ABC PDR | 4.021 | A + I16 |
| IN idle held valid | split-01 / in.held_valid | proved, 16 bytes | ABC PDR | 0.318 | A |
| IN idle held data | small-helpers-01 / in.held_data | proved at small model, 8 bytes | Z3 induction | 5.782 | A + I8 |
| IN service=1 implies valid | small-helpers-01 / in.progress | unresolved (UNKNOWN) | Z3, induction unsuccessful | 7.631 | A + I8 |
| OUT queued<=slots | small-originals-01 / out.capacity | proved at small model, 8 bytes | ABC PDR | 0.319 | A + O8 |
| OUT appValid implies queued!=0 | small-originals-01 / out.read_nonempty | proved at small model, 8 bytes | ABC PDR | 0.374 | A + O8 |
| OUT selected position-zero data=watched | small-originals-01 / out.integrity | unresolved (TIMEOUT) | ABC PDR + Z3 | 121.251 | A + O8 |
| OUT held valid | split-01 / out.held_valid | proved, 16 bytes | ABC PDR | 0.268 | A |
| OUT held data | split-01 / out.held_data | proved, 16 bytes | ABC PDR | 0.268 | A |
| OUT waitForData<8 | small-originals-01 / out.progress | proved at small model, 8 bytes | Z3 induction | 2.770 | A + O8 |

Paths in the table abbreviate the `packet-` prefix and `build/t19` parent.
Six original claims prove at production size; four more prove only at eight
bytes; two remain unresolved. No complete packet proof or T19 closure is claimed.

The IN progress induction witness initializes `pending=1` while
`head=visibleTail=0`. The existing retry-boundary invariant forbids that state,
but it is absent from this helper set. The basecase passes through step 47;
this is not a reachable RTL counterexample. The smallest proposed next proof
change is to add/reprove that ownership invariant in the identical canonical
size/reset model before using it as a lemma. A separate 16-byte receipt cannot
be assumed in the eight-byte model. OUT still needs its selected-byte/data
invariants to close. No further attempt follows the step-5 stop.

Final step-0 rows for the two unresolved small-model jobs, **measured** from
their preserved `job/model/design.log` and engine logs (same commands above):

| Property | Cells / FF bits / RAM bits | Requested depth / cap | Solver reach | Positive wall seconds |
| --- | ---: | --- | --- | ---: |
| IN progress | 377 / 192 / 0 | 48 / 120 s | Z3 basecase through 47; induction 48→0 unsuccessful | 7.631 |
| OUT integrity | 278 / 158 / 0 | 48 / 120 s | PDR frame 36; Z3 basecase through 47, induction 48→0 unsuccessful | 121.251 |

IN progress retains data-tracking predicates that are not needed by a control
response claim; its missing ownership relation is the concrete induction
obstacle identified above. OUT integrity needs selected-byte memory lifetime
information; zero RAM cells here reflects the proved sparse abstraction.
Real small covers reach 102/59, with all required witnesses. No current
quarter/half-depth timings or extra timed extension are claimed. OUT progress
does close at Z3 induction step 41 (basecase through 47), measured 2.770 s;
its cone is 231 cells / 87 FF bits / zero RAM cells.

The first frozen fast run preserves a separate historical-fixture failure:
the new proof-only Scala emitter references `preEnable`, which is absent in
the pinned baseline cadence. The reviewed repair excludes only that file from
historical compilation, leaving the actual baseline HDL manifest checks,
candidate and all equivalence properties intact. No packet proof is rerun for
this fixture repair; its production sources and model hashes are unchanged.

Final frozen confirmation: `python tools/env/run.py run -- python3 tools/ci.py
--tier fast --output build/t19/packet-frozen-fast-02` invokes a fresh USB
aggregate under `fast/usb`. All 19 full-size simulations, 31 timing units,
six receipt units, resume and engine/wrapper equivalence/faults, all 16 focused
formal cases, byte CDC and packet covers/faults pass. The historical-fixture
repair is independently verified against the exact pinned baseline HDL hashes.
USB is **failed** (measured 1321.047 s), and fast is **failed, partial tier run**
(measured 2937.287 s): packet positives and existing physical/prior qualification
obligations remain open. Later fast stages and the full tier are **not run**.
`python scratch/t19_packet_final_audit.py` confirms both frozen source inventories
unchanged before reporting updates and exact reproduction of the prior
engine/wrapper timing, area and hold/reset evidence. No further packet proof
attempt, production RTL change or merge follows this stop.

## D48/D50 preflight (2026-11-18)

Decision D48's literal reset-inclusive value-change invariant has a concrete
counterexample on production EP0. **Measured** diagnostic command at
`15161bf897d1b4b4cba69030154daf89ee19ca12`:
`python tools/env/run.py run -- python3 scratch/t19_value_reset_probe.py`.
Receipt and trace: `build/t19/d48-reset-probe-02/`. The exact emitted
`UsbControl.sv` SHA-256 is
`c772e4c749448130391c26e51864269ce2473d29c7255a861b8c039af3fe71ab`.
The diagnostic retains production sequential logic and adds an unreset
previous-value/previous-enable monitor initialized only at formal startup.
The actual emitted `UsbBitEnable` drives the common enable; packet-interface
inputs are synthetic, as in the standalone control harness, not a full
SIE-composed wire trace. The earlier `-01` used an enable too early after
release and is retained only as an invalid-production-cadence diagnostic.
Yosys `async2sync` and SAT find a bounded counterexample: an enabled SETUP
admission changes state to setup, then reset assertion returns it to idle
with both the preceding and current enable low. This witness changes state
bits zero/one, not the failing timing endpoint state[5]; it refutes the vector
invariant and does not substitute for a bitwise state[5] eligibility proof.
The state aliases bind to
the existing mapped scalar Q pins in the receipt. This sampled witness
refutes the invariant; it is not a proof covering every inter-edge reset.
No reset exclusion or additional assumption has been accepted.

Independent source review also identifies EP0's synchronous bus-reset
override as potentially non-idempotent on its first non-enable edge: the
PHY registers bus reset on an enabled edge and EP0 observes the new value
on the following sample edge. Repeated identical reset writes do not resolve
that first value change. This source-derived finding is separate from the
executed root-reset counterexample.

D50 small-model preflight is **not eligible**. Production constructors take
only proof hooks/memory injection, not size parameters. Both buffers hard-code
wrap at 64 and seven-bit pointers; the memory hard-codes nine eight-byte banks,
seven-bit addresses, slices `(2,0)` and `(6,3)`, and bank bound nine. The formal
harness also fixes capacity 65, packet limit 64, pointer bounds and distance
arithmetic. Fixed byte width eight, four-cycle cadence, three read stages and
service bounds are additional non-scaling protocol/timing constants. These
are source constants, not measured performance figures. Substituting a small
memory would not shrink the control ring. Independent review confirms that
an actual small instance requires prohibited RTL parameterization/restructuring.
No small-model solver job was launched; its time box was not started.

Checkpoint results preceding the D45 follow-up are **measured** at Git base
`a280df4fa17516a2ac8507628a6f12e3c4128895` plus uncommitted T19 sources.
Emitted source hashes in each receipt identify the actual checked model.
They do not certify later source changes. T19 remains incomplete.

Commands below are prefixed with `python tools/env/run.py run --`.

| Contract | Actual result | Receipt / command |
| --- | --- | --- |
| Byte-width shared FIFO ordering, retention, reset and Gray/release safety | Unbounded ABC PDR pass; reachable covers and data/Gray/reset faults rejected | `python3 hw/lib/formal/cdc_proof.py --width 8 --depth 2 --output build/t19/formal-cdc-01` |
| Production four-sample cadence | Unbounded ABC PDR pass; cover and early-enable fault pass | `build/t19/formal-02/cadence/`, from `python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --output build/t19/formal-02` |
| Non-owner accesses cannot produce side effects | Unbounded ABC PDR pass; covers and bypass-owner fault pass | `build/t19/formal-02/denied/`, same command |
| Reduced-threshold host-resume capture/retention | Unbounded ABC PDR pass; cover and dropped-wake fault pass | `build/t19/formal-resume-final/resume/` |
| EP0 address/configuration side-effect qualification | Unbounded ABC PDR pass; reachable address/configuration/replacement-SETUP covers and premature-status fault pass | `build/t19/formal-control-final/control/`; this does not establish packet-boundary phase equivalence |
| Raw reset/VBUS pad safety | Unbounded ABC PDR pass; active-reset cover and ignored-reset fault pass | `build/t19/formal-lane-01/pads/` |
| Retained SIE register-enable implication | Yosys SAT pass with arbitrary register values/PHY outputs; always-enabled prepared-register fault rejected | `python3 hw/ip/usb/formal/sie_enable.py --output build/t19/sie-enable-03` |
| IN accepted-byte integrity, replay/commit, stability and service | **Unresolved**; full-byte and lane-zero proofs timed out | `build/t19/formal-in-01/`, `formal-portfolio-01/in/`, `formal-in-lane-02/in_bit0/` |
| OUT packet commit/rollback, byte integrity, stability and service | **Unresolved**; full-byte and lane-zero proofs timed out | `build/t19/formal-out-01/`, `formal-portfolio-01/out/`, `formal-lane-01/out_bit0/` |

The packet-buffer covers reached concrete witnesses, and planted missing
commit/publish faults produced counterexamples. The latest IN lane-zero job
also reached its service cover and rejected permanently withheld valid.
These are not substitutes for the unresolved positive proofs. One bit lane
does not establish byte-wide integrity; the other lanes were not swept after
lane zero timed out.

## Timeout diagnosis

The initial ABC PDR jobs retained the existing 120-second solver cap. The
portfolio added Z3 induction without changing assertions, assumptions or the
cap. The final cone-reduction diagnostic checks one named data bit while
retaining the actual byte-wide RTL and all control assertions; it also timed
out. No timeout is accepted as a deferral or a bounded proof.

Measured prepared original models contain 304 cells/nine memories (IN) and
316 cells/nine memories (OUT), from independent pinned Yosys `stat -width`
inspection of the preserved `design_prep.il`. The symbolic oracle removes the
need for a second full reference RAM, but the DUT RAM remains in the proof.
For the IN portfolio, Z3 basecase logs reach step twelve in under a second,
step twenty-four around seven seconds, and step thirty-five around 108
seconds; these are solver log timestamps, not separate completed BMC jobs.
Initial IN cover witnesses reach at most twenty-three steps; OUT at most
seventeen. No bound was reduced or reported as unbounded.

Further proof engineering needs an explicit scoped plan under the formal
timeout-triage workflow: separate the control/service conjunction from
integrity, and consider independently proved helper invariants or a sound
arbitrary-entry abstraction. Freeing RAM data for a byte-equality assertion,
assuming DUT valid, increasing the timeout, or dropping an assertion is not
an acceptable repair.

See [the harness contract](../../hw/ip/usb/formal/README.md) for every input
restriction and abstraction. Digital proofs do not establish analog CDC,
physical reset recovery, USB electrical compliance or whole-system wake.
The SIE certificate alone does not authorize multicycle timing.
## D45 follow-up: reset cadence and packet-proof triage (2026-11-18)

At baseline `38e0bddb691288eeba92cb257d30935a40c15fb6` plus working changes,
`python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case cadence_reset --output build/t19/d45-cadence-05`
**measured** PASS for covers, two-cycle-enable fault rejection and both
unbounded ABC PDR assertions. The monitor history survives DUT reset and is
initialized only in the initial formal state. Reset is initially low and
then arbitrary. Assertions establish no enabled captures less than four
sample edges apart and four prior reset-released edges before a capture.
This is not yet a binding of the cadence to a measured combined engine.

Independent reviewer step-0 command:
`python tools/env/run.py run -- python3 scratch/t19_packet_step0_review.py`.
Prepared-model statistics were corrected using `--stats-only`, without
repeating solver jobs. Evidence: `build/t19/packet-step0-review-01/result.json`.
The table's counts, times and solver results are **measured** diagnostics.

| Step-0 measurement | IN lane zero | OUT lane zero |
| --- | ---: | ---: |
| Prepared cells | 340 | 319 |
| Sequential state bits, including `$anyinit` | 261 | 244 |
| Memories / storage bits | 9 / 576 | 9 / 576 |
| Quarter-depth BMC (12) | PASS, 0.6167 s | PASS, 0.4662 s |
| Half-depth BMC (24) | PASS, 5.9731 s | PASS, 4.6210 s |
| Preserved depth-48 portfolio | TIMEOUT, 121.3632 s | TIMEOUT, 121.1839 s |
| Preserved earliest cover bounds (zero-based) | 14, 22, 18, 22 | 15, 10, 16 |

These bounded passes do not close any unbounded acceptance requirement.
The original solver cap remains 120 s; measured wall time includes shutdown.
Full-byte Z3 reached step 35, lane-zero step 36 before timeout. Queue control,
service and symbolic-data integrity remain coupled to the storage model.
All original assertions and reset/input assumptions were retained.

Baseline ABC is followed by rung 1 (portfolio) and rung 4 (exact lane split),
both unresolved. One of the three permitted rungs remains. The proposed
remaining rung 3 is arbitrary-entry memory abstraction with real control and
an exact tracked-entry read/write contract; equality-relevant data must not
be freed or valid assumed. It was not attempted before the new timing stop.
If unresolved, stop: the smallest expected next approach is proved
pointer-distance/occupancy and read-pipeline invariants (rung 6, requiring
approval). No unchanged timed-out job was rerun, no acceptance label changed,
and no new unbounded packet proof is claimed.

## D47 scoped sparse-memory and ownership attempt

User approval: up to 45 minutes, unchanged assertions, assumptions, bounds,
solver caps and acceptance. The attempt ran from 2026-11-19 02:12:29 UTC to
02:54:54 UTC (local date 2026-11-18), **measured** by the session clock;
elapsed time is **estimated** by subtraction as 42 minutes 25 seconds.
No further positive packet-proof jobs were launched after this stop.

The step-0 table above is retained. D47 extends the prior portfolio/lane split
with a sound sparse-memory refinement and asserted helper invariants. This
was one time-boxed proof-engineering attempt with changed model iterations,
not permission for unchanged retries. All original six assertions per buffer
and their input restrictions remain unchanged. Helpers inspect proof-only
state, add no assumptions, and are themselves required to prove.

The table is **measured** from source-bound job receipts at baseline
`38e0bddb691288eeba92cb257d30935a40c15fb6` plus their recorded working models.
Each command is `python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py
--json build/t19/regmap/usb_regs.json --case <case> --output build/t19/<run>`,
combining the listed cases for that run. Sparse03 through Sparse06 also use
`--portfolio` (ABC PDR plus Z3); other rows use ABC PDR. Every solver cap stays
120 seconds, prove depth setting 48; elapsed wall time includes preparation
and shutdown. TIMEOUT is unresolved, not a design failure or a bounded pass.

| Run | Case | Positive result | Measured wall s |
| --- | --- | --- | ---: |
| `d46-helper-01` | `out_helpers` | TIMEOUT | 121.329 |
| `d46-helper-02` | `in_helpers` | TIMEOUT | 121.275 |
| `d46-sparse-01` | `in_sparse` | FAIL | 0.671 |
| `d46-sparse-01` | `out_sparse` | TIMEOUT | 121.875 |
| `d46-sparse-02` | `in_sparse` | TIMEOUT | 121.718 |
| `d46-sparse-02` | `out_sparse` | TIMEOUT | 121.180 |
| `d46-sparse-03` | `in_sparse` | TIMEOUT | 121.465 |
| `d46-sparse-03` | `out_sparse` | TIMEOUT | 121.106 |
| `d46-sparse-04` | `in_sparse` | TIMEOUT | 121.612 |
| `d46-sparse-04` | `out_sparse` | TIMEOUT | 121.192 |
| `d46-sparse-05` | `in_sparse` | TIMEOUT | 121.362 |
| `d46-sparse-05` | `out_sparse` | TIMEOUT | 121.351 |
| `d46-sparse-06` | `in_sparse` | TIMEOUT | 121.116 |
| `d46-sparse-06` | `out_sparse` | TIMEOUT | 121.961 |

Initial sparse-model failures were spurious: the IN trace replay on the real
production memory passed (`python tools/env/run.py run -- python3
scratch/t19_replay_sparse.py`, `build/t19/d46-replay-01`). The model was corrected
to reproduce registered-address/current-array read semantics followed by two
data stages. The first refinement cover erased unused real RAM; corrected
covers explicitly observe both real and sparse outputs. These failed drafts
remain preserved. Helper01 also contains an emitter/source-change failure;
its aggregate receipt is not accepted. Sparse03's OUT helper omitted the
rejected-packet guard; it was corrected before later attempts, without changing
any original assertion.

Final memory refinement command:

```sh
python tools/env/run.py run -- python3 tools/sbt.py "runMain deadhorse.usb.EmitUsbMemoryRefinement build/t19/d46-memory-refine-06/emit"
python tools/env/run.py run -- python3 hw/ip/usb/formal/memory_refinement.py --emit build/t19/d46-memory-refine-06/emit --output build/t19/d46-memory-refine-06/proof
# cover PASS; corrupt FAIL; correct PASS (unbounded ABC PDR)
```

The binding selects actual production RAM words through muxes, removes only
the three witness-input drivers, rejects missing/aliased words, and adds no
assumptions. The read-phase mutant adds a sample edge. Independent review
reran the earlier identical functional refinement and verified its binding
and the common-reset harness warmup scope. Later receipts also bind Scala/script/emission hashes
before and after execution. This proves the memory simulation relation, not
the unresolved packet-buffer contracts.

Final Sparse06 real-model covers and missing-commit/publish/withheld-valid
fault controls pass; both positive jobs time out. Induction-only traces expose
unreachable helper states, not demonstrated production counterexamples.
Independent review confirms the original assertions/guards/bounds are intact.
Fresh default production emission (`EmitUsb build/t19/d46-production-hook-review-01`)
is byte-identical for every IN/OUT RTL file to both `d46-emit-02` and `emit-13`.

Smallest remaining candidate change: prove the OUT oracle lifecycle bound
`watching && inPacket => position < queued +& packet`. The final induction
trace starts with queued=4, packet=37, position=46, then publishes a watched
position beyond committed occupancy. This is an unreachable-start diagnostic.
IN has no new counterexample; Z3 was still working at induction step 38.
The next expected approach is to prove oracle/control helpers independently
with the irrelevant RAM cone removed, then compose data ownership while
retaining every original assertion in the proof union. This is proposed,
unmeasured work, not a guaranteed closure or an approved further attempt.

The aggregate retains packet proofs as blocking unresolved obligations. It
refreshes real-model covers/faults through `--controls-only`, which explicitly
returns nonzero/unresolved and cannot grant acceptance. Positive timed-out jobs
are not silently repeated, skipped into a pass, or accepted as deferrals.

Independent final review identifies a remaining reset-composition gap: the
proof harness resets cadence and buffers together; production inRelease and
outRelease can reset buffers while engine cadence continues. Therefore
`CE => memoryAge == 3` is only common-reset harness evidence. A proposed next
proof must qualify warmup by actual IN-valid/OUT-RAM capture and establish
the retained SIE consumption/reset contract. This is unmeasured, unresolved
work outside the exhausted D47 attempt; no additional positive job was run.

## D48 frozen verification

Command `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output
build/t19/d48-frozen-check-01`, base `15161bf897d1b4b4cba69030154daf89ee19ca12`
plus frozen source hashes, runs all eight non-packet cases with unbounded
proofs, covers and faults successfully. `reset_data` compares the shared
ResetRelease/CdcSync cone's old raw-reset expression with its synchronized
data expression, and checks reset assertion; its early-bypass fault fails.
This is sampled digital evidence with asynchronous-reset lowering, not an
exhaustive inter-edge or physical skew claim. Wire/MMIO/reset/resume tests
pass; byte-width CDC passes. Packet controls/covers pass, but positives stay
unresolved and no unchanged timed-out job was rerun.

Local D48 source/mapped invariants prove for unreset headers with no reset
masking. Other resettable registers are conservatively full-rate, not proved
ineligible bit-by-bit. Value-change, early-release and retained-pin faults
are rejected along with the original faults. Actual enable replica D/CLK/RN
identities bind the unbounded shared-library-FF equality lemma to every copy;
wrong-data and wrong-reset faults fail. The checker uses only those proved
equalities in its otherwise all-Q-free mapped cut. Independent review is clear
for this limited evidence; timing, packet and sampling/exception qualification
remain unresolved. Aggregate and fast CI fail; full tier was not run.

## D51 reset-aware proof composition, 2026-11-18

Baseline `269fa0f7fe1b0560d58dd62c44ef01340e84b06b` plus recorded source hashes.
`python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case cadence_reset --case reset_aware --case reset_aware_early --output build/t19/d51-formal-02`
passes the unbounded ABC PDR proofs, cadence-model covers and missing-suppression/
early-restart faults under the existing per-job caps. Initial reset is low,
subsequently arbitrary; monitor history survives DUT reset. Bus-reset next
data is arbitrary but updates only on the actual production cadence. This is
a sound producer over-approximation, discharged by the source/mapped bus-reset
hold, clock and reset binding; it is not a new environmental assumption.
Both reset-aware lemma cadence emissions must match the cadence_reset proof.

`reset_certificate.py` proves actual source next values and mapped D pins:
normal CE hold, synchronous bus-reset constants, header masking, reset value/
polarity, clock and exact non-ambiguous scalar identities. All unrelated Qs
are free; only separately proved replica equalities are substituted. Actual
source wrong-constant/removed-header-mask mutations and actual mapped wrong-
reset-pin plus wrong-classified-pin controls fail. Receipts list only controls
actually executed; absent S/H groups are explicitly not applicable. All old
controls remain. Reset-aware classification is pair-specific; S→R remains
single-cycle, and the bus-reset producer remains full-rate as reset data.
Standalone EP0 is conditional on both cadence and bus-reset producer contracts,
which the integrated engine discharges. This is sampled digital evidence,
not an inter-edge/physical reset-skew proof.

Diagnostic preparation failures are preserved: formal01's unused cover history
was removed before fminit and was corrected with a reachable release cover;
cert01-03 exposed constant alias and actual GF180 SETN pin handling; cert04
refuted rx_en_q's common-CE hold (it is sample-clock driven); cert05 exposed a
lost primary cadence name, repaired through exact aliases. cert06 was local
proof only before review excluded bus_reset_q from relaxed reset-as-data paths.
cert07 passes the corrected integrated binding. No existing assertion, cap or
assumption was relaxed. Timing now also inventories SETN reset-removal pins.

No packet proof was attempted or restarted; D47 remains exhausted and D50
ineligible. Sampling equivalence and exhaustive applied-exception/per-class
over-budget qualification remain open. Independent review checked the group
composition, reset-as-data exclusion, aliases, controls, enable sizing and
constraint partition. Fresh frozen aggregate and fast CI fail at USB. All ten non-packet cases, their covers/faults and supporting controls pass; packet positives and sampling/exception qualification remain open. Full tier was not run.

## D52 scoped packet attempt, 2026-11-19

Baseline acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf plus receipts' source hashes.
The approved attempt retains the existing depth 48 and 120-second solver cap,
with a 45-minute wall-clock ceiling and at most three distinct rungs. No
unchanged timed-out positive job is restarted. Production buffers are unchanged.

Step 0 reuses preserved measured diagnostics, not new acceptance results:
`python tools/env/run.py run -- python3 scratch/t19_packet_step0_review.py`
and its `--split-stat` run; receipts `build/t19/packet-step0-review-01` and
`build/t19/packet-partition-stat-review-01`.

| Historical measured model | Cells / state bits / RAM bits | Depth 12 / 24 seconds | Control-only cells / bits / RAM |
| --- | --- | --- | --- |
| IN lane | 340 / 261 / 576 | 0.617 / 5.973 | 158 / 81 / 0 |
| OUT lane | 319 / 244 / 576 | 0.466 / 4.621 | 126 / 69 / 0 |

The earlier depth-48 positives timed out; shallow bounded passes are not proofs.
The control partition removes data equalities only in that partition; its
complement retains them, and the union must equal all six original assertions.
Existing real-model covers and faults remain required. Sparse memory requires
its separate actual-word refinement, and all helper invariants stay assertions.

Rungs: independent-reset qualified-read composition; exhaustive assertion
partition; one OUT ownership strengthening motivated by the preserved trace.
The unconditional common-reset memory-age/tag premises cannot establish
independent-reset warmup. The new harness uses production cadence and shared
ResetRelease, with arbitrary independent transport reset. It proves qualified
IN reads and actual OUT head-advance/capture occur after RAM warmup. This local
result does not prove the retained SIE consumption/ACK contract.

D52 results (measured commands on the baseline/hash inventories above):

- `python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case buffer_reset --case cadence_reset --case reset_aware --case reset_aware_early --output build/t19/d52-cadence-02`: all proofs, covers and faults pass. The revised local reset harness directly observes the proof-only production OUT capture condition, proves its delayed head-change correspondence, and covers IN and OUT reads after another reset. No default production buffer state or behavior changes.
- `python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case cadence_reset --case reset_aware --case reset_aware_early --case out_ownership --output build/t19/d52-formal-01`: OUT strengthened sparse proof TIMEOUT, measured 121.638 seconds including orchestration at the unchanged 120-second solver cap; real-model cover/fault pass. No retry.
- `python tools/env/run.py run -- python3 hw/ip/usb/formal/packet_partition.py --json build/t19/regmap/usb_regs.json --output build/t19/d52-packet-partition-01`: all four partitions TIMEOUT. Measured elapsed seconds: IN control 121.726, IN data 121.186, OUT control 121.133, OUT data 121.136; total runner 507.834 seconds including emission/preparation. Configured depth 48, unbounded ABC PDR, unchanged solver cap. No positive acceptance result.

The third distinct rung exhausts this scoped attempt before its wall-clock
ceiling. The smallest next proposed work is separate proved pointer/occupancy
and service-lifecycle invariants, then data ownership composition; RAM removal
alone did not close even the control partitions. That is unmeasured future
proof engineering, not an assumption or accepted deferral. No unchanged job
is rerun and no buffer restructuring or parameterization occurs.

Independent review corrected initially vacuous reset covers and an inferred
capture witness; the final reset proof has actual observation covers and a
proved witness relation. It also requested build-only output containment and
nonzero exit for unresolved partition results. Those CLI-only safeguards were
added after preserving the solver receipts, without rerunning exhausted jobs.
The historical partition command exited zero while its receipt explicitly
said unresolved; the maintained runner now fails closed. Complete packet/SIE
composition remains unresolved.


D52 frozen confirmation: `python tools/env/run.py run -- python3
hw/ip/usb/check.py --output build/t19/d52-frozen-check-01` passes all eleven
focused cases, covers/faults, byte CDC and reproduced-reference resume
equivalence. Both IN/OUT default production emissions match D51 byte for byte.
No exhausted positive packet proof is rerun. Aggregate and fast CI fail with
the original outstanding obligations retained; full tier is unrun. All frozen
input hashes match before reporting-only edits. Independent reviews clear
certificate-preserving sizing, equivalence/fault extraction, reset warmup and
the assertion partition for an incomplete review checkpoint only.


## D53 measured candidate, 2026-11-19

D53 current checks (same base commit plus exact hashes in receipts):

```sh
python tools/env/run.py run -- python3 tools/sbt.py hw/compile
# success
python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case in --case out --case buffer_reset --output build/t19/d53-packet-01
# FAILED USB focused formal: IN/OUT TIMEOUT; reset emitter hit SBT-lock wait cap
python tools/env/run.py run -- python3 scratch/t19_d53_refinement.py
# emit 0, proof 0: actual-RAM refinement and mis-phased/wrong-size controls pass
python tools/env/run.py run -- python3 hw/ip/usb/formal/sie_enable.py --packet-bytes 16 --output build/t19/d53-sie-enable-01
# PASS SIE enable implication; no timing exception applied
python tools/env/run.py run -- python3 scratch/t19_d53_sram_area.py
# PASS pinned SRAM catalog: 28 LEF views, verified archive hashes; area estimate only
python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d53-frozen-check-01
# FAILED T19 USB; inspect result.json for every unresolved obligation
python tools/env/run.py run -- python3 tools/ci.py --tier fast --output build/t19/d53-frozen-fast-01
# FAILED T19 USB; inspect result.json for every unresolved obligation
```

The refinement helper runs the reproducible component commands
`python3 tools/sbt.py "runMain deadhorse.usb.EmitUsbMemoryRefinement build/t19/d53-refinement-01/emit"`
and `python3 hw/ip/usb/formal/memory_refinement.py --emit build/t19/d53-refinement-01/emit --packet-bytes 16 --output build/t19/d53-refinement-01/proof`.
The initial `testOnly deadhorse.usb.UsbThroughputSpec` compile failed on a test
method/Boolean name collision; after that local fix the diagnostic simulation
passed its positive rate test and exposed the same replay failure. Frozen
simulation repeats it with the reviewed clock scheduler and recurring tail SOFs.

Frozen USB simulation: 12 passed, 1 failed (all 11 prior tests and the positive
throughput test pass; throttled replay fails). Eleven focused formal cases,
real-buffer covers/faults, byte CDC, resume equivalence, mapping/certificate
controls and actual-RAM refinement pass. The reset-emission infrastructure
failure is recovered by fresh `buffer_reset` proof in the aggregate. No timed-out
positive packet job is retried. Earlier IN/OUT timeout receipts predate the OUT
oracle-width correction and are historical diagnostics, not current proof.

Standalone buffers/resume/register timing passes. EP0 numerically passes but is
qualification-blocked. Engine, wrapper and standalone SIE fail. Both frozen
commands exit 1; fast CI stops at USB, with preceding checks and existing explicitly
unproved deferrals retained. **Full tier: not run.** All source inventories match
before reporting-only edits; repeated timing classes/areas match exactly.
This is an incomplete review checkpoint, not adoption or T19 completion.


Measured by `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output
build/t19/d53-frozen-check-01`, base commit
d45e50f457f3576949b8fdbfd6e1bb69652aaa53 plus frozen source hashes.
Full public MMIO/CDC wrapper, assumed USB 48 MHz and application/AON 12 MHz,
continuous fair polling, seed 5715/5716. Host schedule offers 128 payload bytes
per 1 ms frame per active direction for 10 frames; CRC/stuffing, SOFs, retries,
refill/drain and final transport overhead are included. Unique ACK-committed IN
bytes and OUT bytes actually read/popped through MMIO form the numerator.
These are digital simulation rates under this service contract, not host/board
qualification or a maximum-throughput estimate.

| Traffic | Measured samples | Measured IN bytes | Measured OUT bytes | Measured IN bit/s | Measured OUT bit/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| IN only | 480712 | 1280 | 0 | 1022483.316 | 0.000 |
| OUT only | 480000 | 0 | 1280 | 0.000 | 1024000.000 |
| Simultaneous | 480712 | 1280 | 1280 | 1022483.316 | 1022483.316 |

Each active IN run delivered 80 full 16-byte packets, seven deliberate lost-ACK
retries and one final ZLP; no short IN packets occurred in the positive schedule.
The target is the user-approved 1 Mbit/s, conservatively required in each direction.

The throttled-service negative control **fails on a real protocol defect before
the rate oracle is reached**: DATA1 payload `[126]` replays as `[126,214]` after
another application write and a lost ACK. The exact retry assertion is retained.
Independent review confirms the same visible-tail refresh logic in the 64-byte
D52 baseline: this is an inherited replay-boundary bug, not a size-induced data
corruption claim. A host may discard the longer duplicate then ACK, losing the
added byte when the DUT commits it. No successful rate-negative-control result
or complete packet correctness is claimed.

Step 0 evidence for the changed production 16-byte diagnostic, measured by the
formal command above and `python tools/env/run.py run -- python3 scratch/t19_d53_model_stats.py`
on its preserved prepared models (Yosys `stat`; no solver retry):

| Property | Prepared cells | Sequential bits excluding RAM | RAM bits | Requested depth / last printed PDR frame | Result |
| --- | ---: | ---: | ---: | --- | --- |
| IN original assertions |256|161|192|48 /83|TIMEOUT,122.080 s measured wall time;120 s solver cap|
| OUT original assertions, before oracle-width fix |235|153|192|48 /27|TIMEOUT,121.183 s measured wall time;120 s solver cap|

Measured cover traces have 15/19/23/23 time steps for IN and 11/16/17 for OUT.
These are the existing public-behavior covers, not full/wrap/max-packet covers.
Quarter/half-depth growth sweeps are not rerun: ABC PDR is unbounded, the prior
triage portfolio/lane/sparse/partition budget is exhausted, and no unchanged
timeout retry is justified. Memory is still the dominant state component;
complete packet lifecycle/control remains relevant to the original properties.

No small-model attempt starts. Estimated minimum IN fill spacing at the smallest
supported 8-byte model is 7 intervals×8 sample edges=56 edges after the first RAM
write, excluding startup; full/wrap take longer than the fixed 48 cover bound.
Independent review confirms the parametric source and this lower bound. The
smallest proof-path change would require an explicit cover-budget decision and
separate proved lifecycle/occupancy/service invariants, not more unchanged PDR
time. Fixing the observed replay defect is a prerequisite for full protocol claims.


## D54 retry lifecycle, 2026-11-19

The D54 production buffer holds its offered boundary until qualified ACK/reset, and the reproducibly patched SIE retains offered bulk ZLPs separately from full-packet termination eligibility. No packet RAM, pipeline phase, original assertion, assumption, service deadline or proof cap changes.

`python tools/env/run.py run -- python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --case retry_boundary --output build/t19/d54-retry-formal-03` proves six ownership assertions unbounded with ABC PDR, covers four real control scenarios at unchanged depth 48, and rejects the actual moving-boundary DUT fault. Initial reset is the only model restriction; subsequent reset and operations are arbitrary. Production buffer RTL is instantiated unchanged; unused RAM/data logic is optimized out of this control-only cone. The partial-ACK cover requires a strict interior pointer and no invalid reads since reset; independent review confirms two genuinely queued bytes, one consumed, then ACK. Earlier cover receipts 01/02 are superseded; their safety assertions were unchanged. Frozen aggregate/fast repeat the exact final source proof.

This is ownership-only, not a packet-data or SIE/ZLP composition proof. After the actual lifecycle RTL change, one fresh attempt of the six original IN assertions (`--case in --output build/t19/d54-in-original-01`) remains TIMEOUT under the unchanged 120-second solver / 180-second subprocess caps: measured wall time 122.000742 seconds, last printed PDR frame 71. Real covers and both planted faults pass. No unchanged timeout retry or additional ladder rung follows; OUT RTL is unchanged and its positive proof is not rerun. Existing real covers/faults remain in the aggregate. The small-model cover-depth obstacle documented under D53 is unchanged.

Step 0 measurement command `python tools/env/run.py run -- python3 scratch/t19_d54_model_stats.py` reads the preserved prepared model without another solver run: measured 267 cells, 162 sequential bits excluding RAM, three RAM cells / 192 RAM bits. Requested cover/fault depth remains 48; positive ABC PDR is unbounded, so quarter/half-depth growth sweeps do not measure this job and are not rerun. The RAM/data-tracking cone remains beyond the new control-only ownership proof. The next substantive proof change would be reviewed composition with queue-occupancy and selected-byte memory invariants; this is an expectation, not an established proof or authorization for further ladder work.

Directed `testOnly deadhorse.usb.UsbRetrySpec` baseline reproduces short retry [126]→[126,214] and terminal ZLP→NAK. The final same command (log d54-retry-final.log) passes all five tests, including the scheduled 383 one-sample write offsets (121 initial-request + 121 retry + 141 ACK offsets); reset, reconfiguration and clear-halt; full packet/wrap; ZLP/SOF/queued-data replay. The fixed DUT is checked by public wire/byte ports. Frozen all-USB simulation passes all 18 tests and existing negative controls.

`python tools/env/run.py run -- python3 hw/ip/usb/formal/sie_enable.py --packet-bytes 16 --output build/t19/d54-sie-enable-01` also passes with the new source-bound state and actual always-enabled fault. Fresh mapped certificate/fanout controls run in the frozen timing flow; no old receipt is reused for the changed SIE.

Measured by `python tools/env/run.py run -- python3 hw/ip/usb/check.py --output build/t19/d54-frozen-check-03`, base commit `c20e625ea44baaf65c9a523f7a9e12fb070dee22` plus the receipt's exact frozen source hashes. Fast CI independently repeats the same measurements. GF180 7-track SS/125 C/3.0 V, Yosys 0.71+34/OpenSTA 3.2.0, mapped pre-layout cell area/delay and ideal clocks; no routed or board signoff. Budgets remain estimated 0.60×1000/48=12.5 ns full-rate and 0.60×4×1000/48=50 ns for certified compatible pairs; other domains retain existing limits.

Assumed USB 48 MHz and application/AON 12 MHz; full public MMIO/CDC wrapper, deterministic seeds and unchanged host/service schedule. Measured rates count unique ACK-committed IN bytes and OUT bytes actually read/popped through MMIO, including SOFs, CRC/stuffing, retries and final drain. This is simulated payload throughput under that contract, not board qualification.

| Traffic | Service gap | Measured samples | Measured IN bytes | Measured OUT bytes | Measured IN bit/s | Measured OUT bit/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| IN | 0 | 480548 | 1280 | 0 | 1022832.266 | 0.000 |
| OUT | 0 | 480000 | 0 | 1280 | 0.000 | 1024000.000 |
| Simultaneous | 0 | 480712 | 1280 | 1280 | 1022483.316 | 1022483.316 |
| Throttled negative control | 64 | 343040 | 256 | 256 | 286567.164 | 286567.164 |

The slow-service case now completes with bytes intact and reaches the intended `USB_PAYLOAD_RATE` rejection. Its replay/data assertions remain unchanged.


## D58 flags-only follow-up — 2026-11-19 (historical timeout)

User approved leaving packetData full-rate; all packet flags use the registered
preEnable strobe. Independent source review found no other off-enable flag
consumer. Fresh engine/wrapper emissions pass; baseline HDL hashes reproduce
D54 exactly. Base `099c27f` plus candidate source, not a committed result.

`python tools/env/run.py run -- python3 hw/ip/usb/formal/preenable_equivalence.py --before build/t19/d58-equivalence-01/before --after build/t19/d58-equivalence-01/after --output build/t19/d58-equivalence-proof-02`
hit the existing 120-second cap on engine induction: **unresolved**, not a
counterexample. The diagnostic checker is preserved under that result directory
as `checker.py`; it was not adopted as an acceptance tool. Relational model
couples arbitrary unchanged Q values, retains real flags/cadence, and compares
all other state-transition/control functions and outputs. No producer-stability
or consumer-sampling assumption was introduced. Initial unreset state is shared.

Measured via `yosys -Q -T -s build/t19/d58-equivalence-proof-02/step0.ys`
in the pinned environment: original miter 48,053 cells / 33 sequential bits;
exact diagnostic `opt -full` 5,717 cells / 30 sequential bits, no RAM cells.
No second proof after optimization was run. Buffered solver progress was not
available after timeout; growth/cover runs stop with the explicit user rule.
Independent review requires fail-closed strobe clock/reset/type guards,
initialization and sequential-state guards, robust bit allocation, source
binding and concrete fault validation before acceptance. Wrapper proof and
faults were not reached; no cadence or constraint qualification, frozen aggregate,
fast CI or full-tier result is claimed. See the T19 report for commands and
remaining work. No commit/push/merge.


## D58 closure of flags-only equivalence — 2026-11-19

The earlier timeout is superseded by `build/t19/d58-equivalence-proof-06/result.json`:
engine and wrapper both prove by induction at step 2, comparing 1,175/1,661
unchanged bits with exactly 13 excluded flag identities each. Source/HDL hashes
and pinned baseline 099c27f are authenticated. Early/late phase and off-enable
consumer mutations fail in the relational model; real EP1 traffic independently
rejects the full-rate consumer (phase 10) while preserving enable-edge samples
and payload. `build/t19/d58-cadence-03/result.json` proves all eight cadence/reset
cases, with covers/faults. Exact commands and initialization relation are in the
T19 report. No new producer-stability assumption or packet-proof attempt.

D59 only changes the eligible USB single-cycle warning ceiling to 15 ns. D58
mapped P certification and negative controls pass for 10 physical captures per
block in `build/t19/d59-timing-01`; S-to-P remains strict FP. The full measured
cadence hash is bound to the pre-enable proofs; the CE-only projected cadence
hash remains separately bound to the original reset lemmas. Applied STA edges
are audited. Independent review clears this digital result; complete T19
acceptance and physical qualification are not claimed.

Final frozen confirmation: `python tools/env/run.py run -- python3 tools/ci.py --tier fast --output build/t19/d59-frozen-fast-02` runs a fresh USB aggregate under `fast/usb`. Both equivalence proofs, every focused formal case, CDC, all 19 simulations and real packet/phase/consumer controls pass. Original positive packet proofs remain unresolved and are not rerun. The USB aggregate and fast tier fail existing qualification; full tier is not run. Exact source inventories match before reporting-only updates.
