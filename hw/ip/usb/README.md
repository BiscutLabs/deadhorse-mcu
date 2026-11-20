# USB CDC-ACM peripheral (T19)

D60/E1, D61/E2 and D62/E3 (2026-11-19) authorize the scoped packet-proof
decomposition: phase-aligned stimulus only with exact proved producer
guarantees, IN push spacing only with a proved shared-CDC guarantee, and
eight-byte small-model covers to depth 128. Positive bounds and solver caps
remain unchanged. Every original assertion remains required; environment-
dependent results and small-model results must be labelled explicitly. See
`formal/README.md` for assumptions, applicability and proof status.

Status: consume-path change verified and estimated pad/reset contract measured;
complete T19 acceptance remains blocked.

Packet decomposition now discharges all original common-reset harness claims:
seven at production size and five at eight bytes, backed by the prior passing
full-size seeded simulation: "proved at small model, simulated at full size".
The focused follow-up proves IN progress at 16 bytes and OUT byte integrity at
eight bytes using separately proved ownership/position lemmas. Production RTL,
original assertions and environments are unchanged; arbitrary later common
resets remain. This is not an independent transport-reset/SIE composition proof.
No CI or USB aggregate was run in this follow-up, per user instruction. Exact
claims, historical simulation provenance and focused receipts are in the USB
formal ledger.

D59 (2026-11-19) sets the active USB sample-clock single-cycle warning ceiling
to 15 ns. The target remains estimated 12.5 ns, and post-placement timing with
real wire delays is mandatory. D58 FP remains strict 12.5 ns; CP stays 37.5 ns,
CC stays 50 ns, and electrical/reset/hold/formal obligations are unchanged.

D58 (2026-11-19) replaces the aligned-enable candidate with pre-enable capture
of every packet flag. The approved amendment keeps packetData full-rate.
Certified launch to proved pre-enable capture would use setup 3 / hold 2 and estimated 0.60×3×1000/48=37.5 ns.
Full-rate launches into that class retain strict 12.5 ns, overriding D57's
warning band there. No new constraint is applied before cadence, mapped-pin
and whole-engine/wrapper equivalence qualification.

The original preflight found `packetData → out.received → memory.writeData →
wordData=RegNext(writeData)`, an unconditional downstream capture. The user
explicitly approved keeping packetData full-rate on 2026-11-19. Only flags
now use pre-enable capture; all other register states and outputs must match
every cycle. No consumer or state-match obligation is relaxed.
Engine and wrapper equivalence now prove by unbounded induction, including
reset and every non-exempt state/output; phase and real-wire consumer controls
reject their faults. Reset-safe P proofs and exact source/mapped certificates
pass. CP is 3/2 only for reset-compatible R/B/H launches; S and other full-rate
launches into P retain strict FP timing. The final frozen run passes all 19 simulations, equivalence, focused formal
and CDC. That historical USB acceptance/fast CI run failed on then-open packet
proofs, hold/reset and prior qualification obligations. The new focused packet
receipts still need aggregate integration; CI has not been rerun. Full tier and post-placement
real-wire timing are not run; no merge. See the T19 report for exact commands.

The standalone SIE fixture remains a measured diagnostic under the user-approved
step 1b option: its unconstrained endpoint-mask and boundary IO paths differ from
the integrated engine/wrapper acceptance targets. Its numerical failures remain
in the receipt. A missing measurement or invalid source/certificate binding still
fails the aggregate; this does not waive any engine/wrapper check.

## Pad/reset boundary contract (2026-11-19 follow-up)

This is an **estimated integration contract**, applied to `UsbEngine` and `Usb`
by `tools/timing/usb_boundary.py`. It is not a characterized pad ring, board
measurement, fast-corner hold result or physical signoff. No RTL changes.

| Boundary | Reference | Estimated min / max delay (ns) | Basis |
| --- | --- | --- | --- |
| dpRx, dnRx, vbus | USB clock, diagnostic phase only | 0 / 2 | Assumed 0..1 ns digital pad plus 0..1 ns package/board transport. They remain asynchronous; zero effective minimum preserves first-sampler hold diagnostics. No synchronous input-phase guarantee is claimed. |
| dpTx, dnTx, txEnable, pullupEnable (engine emitted pullup_0) | USB clock | 0 / 2 output reserve | Same assumed pad plus package/board transport, 1+1=2 ns. Output max reduces the available setup window; both setup and hold polarities are checked. |
| engine reset_n rising release | USB clock | 2.420 / 3.882109 | Upstream GF180 dffrnq_1 CLK-to-Q envelope, described below. |
| appReset_n rising release | appClock | 2.420 / 3.882109 | Same upstream release-cell requirement, only relative to its owning clock. |
| usbReset_n rising release | usbClock | 2.420 / 3.882109 | Same requirement. |
| aonReset_n rising release | aonClock | 2.420 / 3.882109 | Same requirement. |
| Every active-low reset falling assertion | Asynchronous | 0 / 0 diagnostic phase | Assertion remains asynchronous in RTL and is not delayed by a new register. The existing 0.5 ns fall-slew screen remains. |

The reset release range is calculated from the pinned SS/125 C/3.0 V
`gf180mcu_fd_sc_mcu7t5v0__dffrnq_1` rising CLK-to-Q table, over assumed upstream
clock slew 0.02..0.5 ns and Q load 0.001..0.05 pF. Bilinear extrema are recomputed
from the actual library in every measurement and its SHA is recorded. The
estimated rising output slew is 2.4 ns, rounding the table-envelope maximum
2.362750 ns upward. The source cell and slew/load envelope are requirements on
the eventual reset controller, not measured properties of that unimplemented
upstream integration. An SS minimum does not establish a fast-corner hold bound.
`vbus` denotes the already-conditioned digital level at this boundary; analog
VBUS detection and filtering latency are outside this transport estimate.

`commonReset = appReset_n && usbReset_n` reaches both local reset-release
blocks. Neither external release is assumed synchronous to the peer clock.
Every directly reachable asynchronous reset pin is inventoried with its source
and capture domains; peer-domain entries remain RDC-unqualified. A separate
all-domain zero-delay STA run on the identical netlist retains the former raw
phase diagnostics. Internal ResetRelease outputs receive no artificial delay.
Reset assertion still clears the shared release flops asynchronously, including
with stopped clocks; their release still needs the existing local edges.

All other IO, mapped loads/slew limits, clocks, electrical checks, multicycle
certificates and path budgets are unchanged. Asynchronous RX/VBUS phase, actual
pad/board delays, upstream reset implementation, RDC/MTBF, fast-corner timing,
clock trees and routed wire delays remain physical-flow obligations. Negative
pre-CTS hold is reported as a physical-flow item; no RTL delay is added.
The retained `boundary.sdc` is the boundary-constraint snapshot before later
multicycle commands; `timing.tcl`, `protocol.tcl` and the applied-edge audits
retain the complete analysis context. Existing domain-prefixed IO report rows
are repeated all-IO query buckets, not ownership claims; the SDC assigns each
contracted port to its stated reference clock.

The frozen boundary run reproduces the targeted measurements exactly: measured
AON removal changes from -0.975158 ns in the raw zero-delay comparison to
+1.143400 ns under this contract. Measured pad hold remains -0.102503 ns
(engine two paths, wrapper four), retained as failed physical-flow items.
These are mapped pre-layout SS results, not signoff. The core's identical raw
removal value is the same missing-boundary artifact; see T19 for its recorded
command and receipt commit. All 19 USB simulations, focused formal and exact
equivalence pass in the fresh frozen run. USB/fast still fail retained packet,
physical and prior qualification obligations; full tier/post-placement unrun.
Commands and provenance: `python tools/env/run.py run -- python3 tools/ci.py
--tier fast --output build/t19/boundary-frozen-fast-01`, nested USB receipt
`fast/usb/result.json`, base `33cf251` plus recorded source/flow hashes;
[T19 report](../../../docs/plan/tasks/reports/T19.md).

Historical D57 candidate and policy (D59 supersedes its 70% ceiling):

D55 approved comparison of enable-captured IN consume and Chisel endpoint
predecode. D56 approved shared-gate use for enable-only banks. The later D57
instruction (2026-11-19) narrows active work to the identified 15.56 ns consume
path; gating, boundary-contract, packet-proof and higher-load experiments are
deferred. The broader unaccepted candidate and cancelled checks are preserved
under `build/t19/d56-superseded-checkpoint`; they are not the active RTL.

The superseded D57 candidate captured request, consume and ACK together on the existing
protocol enable. This keeps their ordering while adding one protocol edge of
latency. Capturing consume alone failed all five unchanged retry tests; cached
endpoint predecode failed four because it was stale at the first request.
Aligned capture passed all five, including the application-write phase sweep
(measured `testOnly deadhorse.usb.UsbRetrySpec`, base `099c27f`, receipts
`build/t19/d55-option1-retry.log`, `d55-option2-retry.log`,
`d55-option1b-retry.log`). Fresh source/mapped certificates are required for the
three root-reset flags. No vendor or packet-buffer RTL changes are included.

D57 originally kept the 60% USB sample-clock target and accepted a **warning** above it
through 70% of the period. Estimated thresholds at 48 MHz are 12.5 ns and
0.70×1000/48=14.583333 ns (about 14.6 ns). D59 now replaces that ceiling with 15 ns.
Certified compatible four-edge paths retain the 50 ns budget; app/AON domains,
other blocks, electrical, clock-gate, hold/reset and formal checks are unchanged.
Every warned path must be reported. A post-placement timing recheck with real
wire delays is mandatory before final USB timing qualification; it has not run.
That candidate's warning families were SIE endpoint to EP0 `control.inReady`,
reset-incompatible control state to `in.consume`, and PHY RX NRZI-to-shift
state. They retain single-cycle treatment; all measured endpoints/polarities
are listed in its diagnostic timing receipt. Its SIE-to-consume pair
used the four-edge class; that candidate is no longer active. Packet composition,
hold/reset and broader qualification obligations remain open.

D54 (user approval 2026-11-19) authorizes testing immutable offered IN packet
ownership until qualified ACK or reset, including terminal-ZLP retries. Later
application writes must remain queued for the next packet; empty NAK requests
must not lock future data. The scoped repair keeps packet RAM, protocol cadence,
service deadlines and all timing/formal acceptance limits unchanged. Diagnostic
results and independent review are required before accepting the hypothesis.

Historical D53 status: the 16-byte candidate exceeds 1 Mbit/s per direction under
the measured MMIO service contract and reduces mapped area. An inherited
short-packet replay defect, integrated timing failures and packet/qualification
obligations block acceptance. Frozen aggregate and fast CI fail; full tier is
unrun. See [D53 below](#d53-conditional-16-byte-packets) and the
[T19 report](../../../docs/plan/tasks/reports/T19.md).

The D54 candidate stores one pending bit beside the existing IN boundary;
reset clears it. Fresh nonempty requests snapshot the boundary, including a
same-edge RAM write. Retries preserve it; qualified ACK commits only consumed
bytes and releases ownership. No packet RAM or pipeline stage is added.
The retained SIE patch separately remembers an offered bulk ZLP until ACK;
reset, endpoint disable and directional clear-halt clear that state. Existing
full-packet termination eligibility remains separate; EP0 selection is unchanged.

`retry_boundary` proves pending boundary/head stability, nonempty ownership,
ACK release and request rewind on the production buffer. Inputs/operations and
subsequent reset are arbitrary, with the existing initial-reset model and
production cadence. Real covers exercise queued suffix/retry/ACK, partial ACK
and empty-request recovery; disabling boundary retention must fail. This is
an ownership proof, not the unresolved packet-byte proof or a proof of SIE/ZLP
composition. See the report for exact commands and fresh wire/timing results.

## Historical D48-D50 baseline

User decisions D48-D50 (2026-11-18) extend D45 to value changes rather than
write enables, including reset assertion/release, and allow retained PHY
registers only when the same invariant certifies them. Both endpoints must
qualify; setup 4 / hold 3 and the estimated 50 ns budget remain unchanged.
Actual full-rate paths retain the estimated 12.5 ns budget. No reset event
is implicitly excluded from the new property.

The packet proof may use the original assertions at small size plus seeded
full-size simulation only if production RTL is already cleanly size-parametric,
with wrap/full/empty/retry/maximum-packet covers and listed non-scaling constants.
The approved single attempt is capped at 60 minutes with existing solver caps;
no new assumptions, assertion changes or buffer restructuring are authorized.
Any accepted result must say "proved at small model, simulated at full size".

This follow-up also authorizes equivalent enable-register replication and
synchronized reset-as-data through the shared reset-release block. If timing
still fails after those changes, stop before further restructuring. These
approvals do not establish timing or proof qualification.

D50 preflight found no production size parameter: the ring, pointer widths
and bank geometry are fixed. The conditional small-model proof is therefore
not attempted; buffers remain unchanged. D48 reset-inclusive certification
also has a production EP0 counterexample on off-enable reset assertion.
The stronger certificate is not accepted, and no reset exception is assumed.
See the formal ledger for the command, source hash and diagnostic trace.

The implemented conservative D48 certificate retains only unreset header
registers: all-state source enable implication plus mapped D=Q when disabled
establish their value invariant, including reset-input changes. Resettable
and PHY registers stay full-rate until their reset-inclusive invariant is
proved. Existing fault controls remain, with value-change/early-release and
retained-pin faults added. This is not a claim of maximal certification.

The mapping flow copies the cadence FF in parallel for each first-branch load
group, preserving any leading buffer/inverter prefix. Actual next-state,
clock and asynchronous reset pins are bound and equality proved under the
production initial-reset contract; physical reset skew remains unqualified.
The wrapper now derives engine reset-data from shared `usbUp`; asynchronous
assertion is retained. Its sampled digital equivalence and wire tests pass.
Post-step-4 timing still fails, so further restructuring, the proposed pad
delay contract and standalone-fixture changes are stopped. Existing hold/reset
checks remain failures, not waived physical-flow items under an unimplemented
contract. The task report and timing ledger contain commands and paths.
## Interface and integration

The [brief](../../../docs/plan/tasks/T19-usb.md) and
[adoption assessment](../../../docs/spec/usb-adoption.md) define the scope.

The USB engine is entirely in the required 48 MHz sample-clock domain.
It retains the pinned MIT SIE/PHY, with Chisel control endpoint, packet buffers
and composition. Endpoint zero has an eight-byte maximum packet; bulk IN/OUT
endpoint one uses the conditional D53 16-byte maximum packet candidate (the
previous D52 baseline used 64 bytes). Descriptor bytes retain the supplied
single-channel CDC configuration. VID/PID are product parameters; zero defaults
are simulation-only and are not assigned shipping identifiers.

The application domain uses the shared byte-width CDC FIFOs. A generated
register block provides checked access inside a parameterized subwindow of the
existing gateway region (default reserved subwindow `0x40040800`–`0x400408ff`).
Integration holds `owner` stable whenever `appReset_n` is high. To transfer
ownership, assert `appReset_n`, change `owner` while reset remains asserted,
then release reset and reconfigure using the new owner. This explicitly cancels
all pending USB traffic; TX-ready does not establish quiescence. The gateway consumes this same interface,
not a second unsynchronized FIFO consumer. Whole-chip gateway RTL is separate.

Proposed local register contract (all offsets relative to the configured base):

| Offset | Register | Fields/behavior |
| --- | --- | --- |
| 0x00 | control | RW enable bit 0; reset disabled |
| 0x04 | tx_data | WO byte value; accepted write enqueues if ready, otherwise overflow event |
| 0x08 | command | W1P RX POP bit 0, wake acknowledge bit 1 |
| 0x0c | rx_data | RO receive head; read does not consume |
| 0x10 | status | RO TX ready bit 0, RX valid bit 1, configured bit 2, connected bit 3 |
| 0x14 | events | W1C TX overflow bit 0, RX underflow bit 1, session reset bit 2, host resume bit 3; hardware set wins |
| 0x18 | irq_enable | RW RX valid bit 0 and events bit 1; reset masked |
| 0x1c | frame | RO coherent latest configured-session USB frame snapshot, bits 10:0; zero outside a configured session |

Reset asserts asynchronously and releases through shared `ResetRelease`.
External reset/VBUS loss disables drive/pull-up even with stopped clocks.
Session reset/deconfiguration flush both protocol and application buffers;
old bytes are not replayed after reconnection. Domain reset flushes shared
transport on both sides. Clock-demand/wake is retained in its live source
domain and must feed ungated AON synchronization; receive-valid in a stopped
application domain alone is insufficient. USB clock remains available while
attached, including host suspend/resume detection.

Host suspend requires 144000 consecutive idle-J sample edges (3 ms at the
required 48 MHz, an estimated duration). Resume captures synchronized K and is
sticky until the explicit wake acknowledgement, with capture winning clear.
Suspend qualification survives transient SE0/SE1 pin skew; four consecutive
illegal samples cancel it. Sustained bus reset, detach and local drive therefore
cannot preserve an old idle interval. This digital filter is not an analog
metastability or USB electrical compliance claim.

The user approved retaining the vendor PHY's D+/D- sampler and combinational
decoded/safety-gated outputs on 2026-11-18. This narrow structural exception
does not waive electrical timing, protocol, or MCU-domain shared CDC checks.
New packet storage has synchronous registered reads; internal bit-enable
interfaces are exercised at their documented sampling edges. The added
vendor/endpoint pipeline still needs its explicit sampling-equivalence proof.
No asynchronous
circuits or new handwritten Verilog are introduced.

Mapped areas are recorded for SIE, EP0, buffers, engine and the complete wrapper
in the [area ledger](../../../docs/ledger/usb-area.md). These measurements and
the report-only SRAM estimate do not establish routed die fit.
Formal assumptions/proof results, behavioral negative controls and production
GF180 timing must be recorded before T19 can be complete. Pad/ESD, VBUS
conditioning, clock tolerance and host/board electrical compliance remain
physical integration obligations.

The retained SIE path `sie.data_q` to `sie.out_toggle_q` exceeds the existing
sample-clock budget. Both registers use the protocol enable. User decision
[D45](../../../docs/plan/10-decisions-and-risks.md) (2026-11-18) approves setup 4 /
hold 3 only between launch and capture registers proved to update exclusively
on the common protocol enable, in SIE and Chisel `UsbControl`. The estimated
budget is 0.60 × 4 × 1000/48 = 50 ns; all other paths retain their existing
limits. The [timing decision](../../../docs/spec/usb-timing-decision.md) retains
mandatory production-source/mapped-pin certificates, reset-safe cadence,
classification, negative controls and independent review. Draft 4/3 constraints
are applied only in unaccepted diagnostic runs; qualification remains unresolved.
Approval does not qualify a full-rate
decode or a pipeline at another enable phase. The user requires a stop before
further restructuring if EP0's failing path is not enable-gated or any
certified path exceeds 50 ns.

The user subsequently authorized moving EP0 SETUP-header/decode work onto
the common enable phase. Header staging is removed; descriptor/decode
registers now use that enable. This is not yet qualified: proof that the
retained SIE leaves sufficient CRC/EOP spacing for decode consumption is
pending. Output and packet-boundary stages remain because their capture
registers update at full sample rate. Under D46, an address-nonzero flag now
shares the address register's reset/update priority; its equivalence invariant
and fault control pass. Final frozen EP0 mapping fails: measured FC delay
13.370109 ns from state[5] to header_5[6], against the estimated 12.5 ns
budget. The earlier numerical pass used a different FSM mapping; final
certificate-preserving mapping uses `-nofsm` on identical emitted RTL. State
has a full-rate bus-reset override and cannot enter the certified class.
The explicit stop condition applies; no further restructuring was performed.
Standalone SIE, engine and wrapper also fail full-rate and hold/reset checks.
Commands, paths and provenance are in the timing ledger.
The draft class runner fails closed on incomplete qualification and does
not establish an accepted multicycle exception. See the T19 report.

D47 authorizes one packet-proof attempt of at most 45 minutes using a proved
sparse-memory refinement and pointer/ownership invariants. All original
assertions, assumptions and solver caps remain. Refinement alone does not
establish the original buffer contracts; unresolved jobs remain required.

D47 stopped within its time box: the sparse-memory refinement lemma passes,
while both packet proofs remain unresolved. Common-reset warmup evidence
does not qualify independent production transport resets or SIE consumption.
Frozen aggregate and fast CI fail; the full tier was not run. The user
subsequently authorized a review commit/push with these failures preserved;
this does not qualify the implementation or authorize merging. See the T19 report.

The D48-D50 frozen aggregate and fast tier both fail at USB. Local certificates, reset/replica proofs, wire/MMIO/resume and supporting controls pass; timing and packet obligations remain open. Full tier was not run. The user requested publication to `codex/t19-usb-review` with failures preserved, without merging.

## D51 reset-aware follow-up

The user approved a reset-aware extension to D48 on 2026-11-18: affected
captures must be proved suppressed during reset and unable to resume early
afterward, on production source and mapped identities. Approval alone does
not qualify registers. Common enable, setup 4 / hold 3, the estimated 50 ns
budget and all other limits remain unchanged. Focused enable fanout/placement
work may preserve phase while reducing delay, followed by boundary-contract,
fixture and pipeline work. Packet proofs are separate and remain unresolved.

D51 implementation uses reset-compatible R/B/H/S groups; S→R remains
single-cycle, as does the PHY bus-reset producer's reset-as-data launch.
Standalone EP0 needs both the integrated cadence and bus-reset producer
guarantees. New local constant/mask/reset-pin faults and reset/restart temporal
faults supplement every existing control. The actual GF180 SETN pin is included
in reset-removal reports. Weak enable-tree buffers are sized with proved
same-function replacement; no production RTL or enable phase changes.
Targeted measurements close the enable path but retain integrated full-rate
failures, so no further restructuring follows. Boundary contract, fixture and
sampling/exception qualification remain open. Frozen aggregate and fast CI fail at USB; full tier was not run. Eleven simulations, ten non-packet formal cases and supporting controls pass, while timing/packet/qualification failures remain blocking.

## D52 full-rate closure pass

The user approved cell sizing and latency-preserving combinational factoring
on 2026-11-19. Protocol phase, reset/ACK priority, interfaces and all limits
remain unchanged. Compare old/new transition behavior and retain every fault
control. Follow with pad/hold reporting, sampling/exception qualification and
a separately scoped control/ownership-memory packet proof attempt under the
existing caps/triage limits. No buffer restructuring or SRAM swap is authorized.

D52 diagnostic measurements (command `python tools/env/run.py run -- python3
scratch/t19_d52_measure.py d52-timing-05`, base acf8edb090f9ec9cda0c413d3bbbd54da4c6dccf
plus receipt hashes) leave two full-rate CF failures: engine configured to
IN consume, 13.703803 ns; wrapper endpoint decode to EP0 IN ready, 12.707026 ns.
The budget remains 12.5 ns. Resume count-only decode boundaries preserve all
state/latency and are proved equivalent to D51. Mapped buffer/gate sizing proves
actual library functions equal and preserves every connection; clocks are
excluded. All other measured engine/wrapper register classes pass numerically.
Further restructuring stops at the remaining CF paths. No pipeline is removed.

Independent-reset qualified-read warmup is proved with real-model covers and
faults. Complete packet integrity, SIE consumption, sampling equivalence,
exception qualification and the pad/board contract remain open. Existing
zero-delay IO hold/removal screens remain visible; no pre-CTS hold RTL is added.
The scoped ownership and all four assertion-partition jobs timed out under existing caps; no unchanged retry follows. Frozen USB aggregate and fast CI fail at USB; full tier was not run. Eleven simulations, eleven focused formal cases, resume equivalence and supporting controls pass. Independent review confirms the limited claims; T19 remains incomplete.


## D53 conditional 16-byte packets

The user approved a 16-byte bulk-packet candidate on 2026-11-19 if throughput
is acceptable, giving a 1 Mbit/s target. The assessment uses 1,000,000 payload
bits/s (125,000 bytes/s) in each direction through the complete MMIO/CDC wrapper.
These are acceptance targets, not measured throughput. The candidate coordinates
SIE maximum packet size and both bulk descriptors with derived FIFO geometry:
17 logical slots, five-bit pointers, three eight-byte banks (24 physical bytes).
The reserved ring slot and staging/prefetch byte remain; public capacity is 17.
EP0/interrupt packet sizes, four-sample cadence, RAM latency, service deadlines
and timing/solver limits stay unchanged. Measured full-packet throughput meets
the target below; adoption remains blocked by replay correctness, timing and
the unresolved proof/qualification requirements.


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

Measured D53 mapped areas are IN 39542.1376 um², OUT 38339.1680 um²,
engine 156976.5568 um² and complete wrapper 197043.3472 um². Estimated reduction
versus the measured D52 areas is 63.601/63.810/46.770/40.715 percent respectively
(100×(old−new)/old); exact figures are in the area ledger. Engine CF/FC/FF and
wrapper CF setup paths still fail; all limits remain. Actual-RAM refinement,
eleven focused formal cases and their controls pass, while full packet proof
is unresolved. D50/C remains ineligible at depth 48: even the 8-byte model has an
estimated 56-edge minimum IN fill interval after its first RAM write.

Independent review clears these limited claims for an incomplete checkpoint.
Repairing replay requires separately approved packet-boundary ownership; that
approval is pending. No such state change or SRAM swap is included. Functional
sources stayed frozen through aggregate and fast CI; only reporting changed
after the matching source-inventory audit. Full tier was not run.
