# USB CDC-ACM peripheral (T19)

Status: implementation in progress; acceptance has not passed.

Current D51 status: reset-compatible register pairs are certified, and enable
buffer sizing closes the enable-to-PHY path numerically. Integrated full-rate
packet-boundary, reset-data and resume paths still fail. Packet proofs and
sampling/exception qualification remain open. See [D51 below](#d51-reset-aware-follow-up)
and the [T19 report](../../../docs/plan/tasks/reports/T19.md).

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
endpoint one has a 64-byte maximum packet. Descriptor bytes retain the supplied
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
