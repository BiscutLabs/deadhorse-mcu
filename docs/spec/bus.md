# T14 bus contract

PLAN05 production binding: remove general toMain and lite main-peripheral
access; retain toAon, mailbox and the dedicated lite execution-debug bridge.
The reusable bridge protocol below is unchanged. The authoritative production
map and ownership are in [soc.md](soc.md); earlier address examples below are
historical T14 assumptions, not an additional production map.

Draft for independent review. This specifies reusable blocks, not SoC wiring.
Addresses and bounds below are implementation configuration assumptions pending
G1 integration. No peripheral, core, clock controller or reset controller is
implemented by T14.

## Clocked transaction

Each domain uses the Ibex request/grant interface: `req`, `gnt`, 32-bit byte
`addr`, `we`, four byte enables `be`, 32-bit `wdata`, `rvalid`, 32-bit `rdata`,
and `err`. Acceptance is a rising edge with `req && gnt`; a requester holds
the entire payload until that edge. Exactly one response follows an accepted
request, at least one edge later, in order. There is no response backpressure.
Writes and errors return zero data. Reset of the requester ends its obligations.
Responses without an outstanding grant are ignored. Reset is asynchronous
assertion and synchronous release in the receiving domain.

The fabric permits one accepted transaction at a time. Round-robin arbitration
advances after each accepted request, including errors. A master may issue
again after its response. Incoming bridge traffic is a separate master; its
trusted origin identity is preserved, never replaced by the bridge's identity.
DMA likewise inherits a checked origin from its controller. CPU and gateway
origin tags are assigned by integration, not software-writable request data.

The fabric captures a selected request, gives a registered grant, forwards a
registered target request, and captures the response into registered outputs.
The target request stays stable through grant. Endpoint ownership/memory
permission is checked at the endpoint at acceptance; failure produces an error
without a side effect. Unmapped, misaligned, reserved-window and denied fabric
accesses also produce an error without issuing a target request. Region decode
is disjoint and parameterized. Generated register descriptions supply endpoint
offset decode; no duplicate handwritten register decoder is permitted.

## Domains and regions

| Region | Window | Home / access |
| --- | --- | --- |
| Boot ROM | 0x00000000–0x0000ffff | Main; local fetch, checked programming/debug |
| XIP | 0x10000000–0x1fffffff | Main; performance-local, checked gateway/debug |
| Performance SRAM | 0x20000000–0x20003fff baseline | Main; performance-local, checked gateway/debug |
| Retained SRAM | 0x30000000–0x30000bff baseline | AON; lite-local, checked remote |
| Power/reset/timer | 0x40000000–0x40000fff | AON; checked remote |
| Mailbox local endpoint | 0x40001000–0x40001fff | Each core's local endpoint; no remote alias |
| Serial controllers / DMA | 0x40010000–0x4001ffff | Sleep-capable HF; endpoint ownership for all masters |
| ADC player / I2C loader | 0x40020000–0x4002ffff | AON baseline; checked remote |
| PWM output reservation | 0x40030000–0x40030fff | Main-local bus; T22 functional profile uses main-service reset, legacy stub retains its reset contract |
| Gateway / optional USB FIFO | 0x40040000–0x40040fff | Gateway; checked access, optional USB CDC later |
| Future bridge reservation | 0x60000000–0x6fffffff | Always error; one interrupt reservation, tied inactive |

Main masters: instruction, data, bounded DMA, gateway/debug, incoming AON bridge.
AON masters: lite, authorized gateway/debug, incoming main bridge. Fetch and
performance-local SRAM/actuator accesses stay local; permitted remote access
uses the bridge. Exact master counts, endpoint assignments and interrupt number
are integration parameters. The reservation implements no NoC logic.

## Admission and maximum wait

An AON-resident round-robin direction permit allows **one cross-domain bus
transaction chip-wide**. Each outbound source holds a permit request until its
response/cancellation, then waits for permit removal before requesting again.
Denied outbound requests remain ungranted and do not occupy the local fabric.
The fabric remains available to the incoming bridge and local masters. This
prevents AON-to-main and main-to-AON requests from circularly blocking each
other. A permit is never preempted during a transaction. This applies only to
bus transactions; mailbox FIFOs operate independently.

Local target grant plus response is limited to 128 running local-clock edges;
the bridge's own completion watchdog uses 131072 source edges, **not** the local
128-edge limit. The fabric's bridge-region watchdog is 131080 edges, adding
eight edges for registered request/grant/return overhead; it must never preempt
the inner bridge watchdog. Integration checks both parameters together.
The source timer starts at its accepted grant and includes forwarding, wake,
target grant, response crossing and registered return; a response on the final
allowed edge wins over expiry. These are assumed configurable
watchdog defaults, not physical startup guarantees. Each implementation reports
its exact accounting. A timeout returns an error once and isolates the target
slot: no new request may reuse an untagged late response. Other targets remain
serviceable; isolated-target requests receive errors. Reopening requires a
drained response or explicit endpoint-quiescent acknowledgement. Persistent
requests get a turn within one round of completing contenders, under the stated
finite target/clock bounds. A permanently stopped source cannot observe a grant
or completion; clock progress is an explicit liveness premise.

A source timeout initiates an acknowledged transport abort: flush any request
not yet issued, prevent subsequent dispatch from that epoch, and isolate any
already granted target work. The direction permit is released only after that
abort is acknowledged. It does not wait for an isolated endpoint's late response;
the other direction and local targets remain serviceable. A poisoned endpoint
gets error service rather than successful service. Healthy permit acquisition
is at most one competing transaction plus two synchronization round trips and
local round-robin service. A controller that never restarts a requested clock
violates the liveness premise; the bridge cannot promise a physical-time bound
independent of that controller. These bounds must be checked separately from
the accepted-request watchdog.

## Shared crossing and reset

All CDC uses the shared clocked primitives. FIFO storage uses flop words,
registered Gray pointers and two receiving flops per pointer bit. Reset of
either side flushes transport on both sides with asynchronous assertion and
per-clock synchronous release. No multi-bit payload is independently bit
synchronized. Physical integration must constrain Gray-pointer skew and stable
data paths and qualify synchronizer MTBF; digital proof does not prove analog
metastability behavior. FIFO output is registered and held until consumed.
The baseline depth is two words including the registered head: the read pointer
advances only when the consumer accepts that head, not when it is prefetched.

A surviving source remembers its accepted bus request outside the shared FIFO
flush. Peer reset observed before source response commitment returns one error
for that request, including a short reset while its clock is stopped. Once a
registered response is published, a simultaneous/later peer reset does not
retroactively revoke it. A resetting source discards its old response.
Already granted downstream work must drain or be explicitly cancelled before
reusing the target slot. Destination reset alone does not establish cancellation
of an independently reset actuator/shared peripheral. Recovery therefore
requires an endpoint-quiescent acknowledgement: no old response or delayed side
effect can remain. This handshake belongs to the reset/isolation controller and
must be connected and verified by the later SoC brief. It is not tied true for
an endpoint that can retain work across reset.

An error after downstream grant means the outcome may be uncertain; writes
are never automatically retried. Mailbox reset flush is reported to the
surviving endpoint as a sticky peer-reset event.

Clock demand is a retained source-side level asserted for offered crossing
work before permit/grant and held through completion/draining. The always-on
controller receives it through the shared synchronizer when necessary. It may
not rely on destination clock edges to start that clock. Clock demand also
remains active during recovery. A clock controller must not stop a domain
with pending work; its startup bound is an explicit environment contract.
The target endpoint also exports registered `targetClockHold` for retained
downstream work. Integration must collect that level through the shared
synchronizer into the ungated AON controller even while the source domain is
held in reset; source-side demand alone cannot retain an orphan's clock.

## Mailbox endpoint registers

Each direction has a small FIFO, with the local receive head held stable until
an explicit POP. Exactly one local owner accesses each staging interface;
gateway/debug access requires that owner's software be halted or ownership
transferred after draining. Register semantics come from `mailbox.regmap.yaml`.

| Offset | Register | Semantics |
| --- | --- | --- |
| 0x00 | tx_data | Full-word WO staging; byte-partial command errors; zero strobes no-op |
| 0x04 | command | W1P PUSH bit 0, POP bit 1; separate from data staging |
| 0x08 | rx_data | RO current head; zero when empty; reading never consumes |
| 0x0c | status | RO TX-ready bit 0, RX-valid bit 1, link-ready bit 2 |
| 0x10 | events | W1C overflow bit 0, underflow bit 1, peer-reset bit 2; set wins clear |

PUSH while full raises overflow and changes no queued word. POP while empty
raises underflow. Successful PUSH uses the most recent completed staging write;
staging alone does not enqueue. Non-empty continuously asserts interrupt and
wake, independent of software masks. Reset clears staging and local events;
peer reset flushes messages and raises the surviving endpoint's peer-reset flag.
PUSH during link recovery raises overflow; POP during recovery raises underflow;
neither command changes a queue. Sender-side retained queued/pending state also
requests the receiver's clock through the shared synchronizer and ungated AON
controller; receive-valid alone is insufficient to start a stopped receiver.
FIFO acceptance, not a bus write acknowledgement alone, determines PUSH success;
software reads events/status. Mailbox capacity and exact registered flag latency
are documented by its implementation.

## Verification boundary

The optional T23 DMA controller presents registered memory/peripheral requests
and preserves every offered request until grant, even after software abort.
An item drains its required peripheral and memory side effects before abort
completion; a bus error stops it without replay. RX memory write can precede
a failed FIFO POP. Firmware owns active DMA buffers and FIFO/configuration
changes exclusively; DMA readiness inputs are hints, not reservations.
The initial binding assigns performance origin in hardware, admits only fixed
UART/SPI/PWM addresses, and confines its native memory port to performance SRAM.
The memory arbiter alternates requesting DMA and CPU service, retaining the
prior instruction/data preference when DMA is idle. These are finite-count,
single-item channels with transaction-level round robin, not linked descriptors.


Independent queue/transaction models cover contention, ownership denial, delayed
grants, backpressure inside CDC, opposite-direction traffic, reset/grant/response
races, short reset with stopped clocks, timeout/late response and mailbox errors.
Unbounded small-block safety proofs, reachable covers and real fault controls
are required. Any clock-progress/quiescence assumptions are listed next to the
properties. A bounded wake/cancel result cannot close T14.

References: the [pinned Ibex interface](https://ibex-core.readthedocs.io/en/stable/03_reference/load_store_unit.html)
defines grant/response behavior; D24/D37/D43 define ownership, reset and topology.
