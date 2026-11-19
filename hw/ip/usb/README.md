# USB CDC-ACM peripheral (T19)

Status: implementation in progress; acceptance has not passed.
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

Area is unqualified. The historical diagnostic in the adoption assessment
measured only the old engine and cannot establish this implementation's fit.
Formal assumptions/proof results, behavioral negative controls and production
GF180 timing must be recorded before T19 can be complete. Pad/ESD, VBUS
conditioning, clock tolerance and host/board electrical compliance remain
physical integration obligations.

The retained SIE path `sie.data_q` to `sie.out_toggle_q` exceeds the existing
sample-clock budget. Both registers use the protocol enable. The
[timing decision proposal](../../../docs/spec/usb-timing-decision.md) describes
the measured path, preliminary enable proofs and narrowly scoped multicycle
qualification requested. No timing exception is currently applied.
